import math
import json
import os
from pathlib import Path

from PyQt5.QtWidgets import QMessageBox
from src.models.models import PackedContainer, Item
from src.utilities.utils import get_permanent_directory

def prepare_packing(main_window):
    """
    Prepares for the packing algorithm by performing all the steps currently in run_packing()
    up until the creation of the progress dialog and threading. 
    Returns scenario_hash, cache_file_path, packing_method, and sorted_items.
    """

    # Extract needed references
    data_manager = main_window.data_manager
    original_items = data_manager.items  # Keep original items separate
    floor_loading = False
    vertical_loading = False

    # Show the packing options dialog
    packing_options_dialog = main_window.create_packing_options_dialog()
    result = packing_options_dialog.exec_()
    if result != packing_options_dialog.Accepted:
        QMessageBox.information(main_window, "Packing Canceled", "Packing algorithm was canceled.")
        return None, None, None, None

    options = packing_options_dialog.get_selected_option()
    floor_loading = options['floor_loading']
    vertical_loading = options['vertical_loading']
    use_cached_result = options['use_cache']
    combined_pallets = options['combined_pallets']

    # Store the combined pallets flag in main_window for later use in caching
    main_window.used_combined_pallets = combined_pallets

    if not floor_loading and not vertical_loading:
        QMessageBox.warning(main_window, "No Packing Method Selected", "Please select a packing method.")
        return None, None, None, None

    if vertical_loading:
        packing_method = "vertical_loading"
    else:
        packing_method = "floor_loading"

    # Validate input
    if not original_items:
        QMessageBox.warning(main_window, "No Items", "Please add items to pack.")
        return None, None, None, None

    if not data_manager.containers:
        QMessageBox.warning(main_window, "No Containers", "Please add containers before running the packing algorithm.")
        return None, None, None, None

    # Step 0: Process collections - split large products into smaller components
    if hasattr(data_manager, 'collections_df') and not data_manager.collections_df.empty:
        expanded_items = []
        for item in original_items:
            # Check if this item is in the collections as a productId
            if item.sku in data_manager.collections_df['productId'].values:
                # Get all component parts for this product
                components = data_manager.collections_df[data_manager.collections_df['productId'] == item.sku]
                
                # For each component, create a new item
                for _, component in components.iterrows():
                    component_code = component['productcode']
                    component_quantity = component['quantity'] * item.quantity  # Multiply by original item quantity
                    
                    # Get dimensions for this component
                    dimensions = data_manager.get_dimensions_for_product_code(component_code)
                    
                    if dimensions:
                        component_item = data_manager.create_item(
                            sku=component_code,
                            length=dimensions['length'],
                            width=dimensions['width'],
                            height=dimensions['height'],
                            weight=dimensions['weight'],
                            quantity=component_quantity,
                            stackable=dimensions['stackable'],
                            rotatable=dimensions['rotatable'],
                            europallet=dimensions['europallet'],
                            mixed_pallet=getattr(item, 'mixed_pallet', '')
                        )
                        # Track original quantity and parent information
                        component_item.original_parent_sku = item.sku
                        component_item.original_quantity = component_quantity
                        expanded_items.append(component_item)
                    else:
                        # If dimensions not found, create a placeholder with same dimensions as parent
                        component_item = data_manager.create_item(
                            sku=component_code,
                            length=item.length,
                            width=item.width,
                            height=item.height / len(components),  # Divide height by number of components
                            weight=item.weight * (component_quantity / item.quantity),  # Proportional weight
                            quantity=component_quantity,
                            stackable=item.stackable,
                            rotatable=item.rotatable,
                            europallet=getattr(item, 'europallet', False),
                            mixed_pallet=getattr(item, 'mixed_pallet', '')
                        )
                        # Track original quantity and parent information
                        component_item.original_parent_sku = item.sku
                        component_item.original_quantity = component_quantity
                        expanded_items.append(component_item)
                    
                    # Generate color for the new component SKU
                    if component_code not in data_manager.sku_color_map:
                        data_manager.sku_color_map[component_code] = data_manager.generate_color_for_sku(component_code)
            else:
                # Keep the original item
                expanded_items.append(item)
        
        # Replace original_items with expanded items
        original_items = expanded_items

    # Compute a hash of the current items to detect changes
    def compute_items_hash(items):
        """Compute a hash of the items list for change detection"""
        items_data = []
        for item in items:
            item_dict = {
                'sku': item.sku,
                'length': item.length,
                'width': item.width, 
                'height': item.height,
                'weight': item.weight,
                'quantity': item.quantity,
                'stackable': item.stackable,
                'rotatable': item.rotatable,
                'europallet': getattr(item, 'europallet', False),
                'mixed_pallet': getattr(item, 'mixed_pallet', ''),
                'cartons': getattr(item, 'cartons', 0)
            }
            items_data.append(item_dict)
        
        import hashlib, json
        items_json = json.dumps(items_data, sort_keys=True)
        return hashlib.sha256(items_json.encode('utf-8')).hexdigest()
    
    current_items_hash = compute_items_hash(original_items)
    
    # Check if the items have changed since last cache load
    if hasattr(main_window, 'last_cached_items_hash') and main_window.last_cached_items_hash != current_items_hash:
        # Items have changed, force a fresh packing by disabling cache usage
        use_cached_result = False

    # **Start of Modification: Filter out items with any dimension equal to 0**
    valid_items = []
    invalid_items_count = 0
    for item in original_items:
        if item.length > 0 and item.width > 0 and item.height > 0:
            valid_items.append(item)
        else:
            invalid_items_count += 1

    if invalid_items_count > 0:
        QMessageBox.warning(
            main_window,
            "Invalid Items Detected",
            f"{invalid_items_count} item(s) with zero dimensions were excluded from packing."
        )

    # Proceed only if there are valid items after filtering
    if not valid_items:
        QMessageBox.warning(main_window, "No Valid Items", "No valid items available for packing after excluding items with zero dimensions.")
        return None, None, None, None

    total_quantity = sum(item.quantity for item in valid_items)
    if total_quantity > 1000:
        reply = QMessageBox.question(
            main_window, "Are you Ready?",
            f"The total number of items is <b>{total_quantity}</b>. This may take a while.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return None, None, None, None

    scenario_hash = main_window.compute_scenario_hash(packing_method, combined_pallets)
    cache_directory = get_permanent_directory("CachedResults")
    cache_file_path = os.path.join(cache_directory, f"{scenario_hash}.json")
    os.makedirs(cache_directory, exist_ok=True)

    # Check Cache
    if os.path.exists(cache_file_path) and use_cached_result:
        try:
            with open(cache_file_path, 'r') as f:
                cached_data = json.load(f)

            if (cached_data.get("packing_method") == packing_method
                and cached_data.get("used_combined_pallets") == combined_pallets):
                # Load packed_containers
                packed_containers = [
                    PackedContainer.from_dict(pc)
                    for pc in cached_data.get("packed_containers", [])
                ]
                data_manager.packed_containers = packed_containers

                # Load items (including combined pallets) into local list
                items_loaded = [
                    Item.from_dict(item_dict)
                    for item_dict in cached_data.get("items", [])
                ]
                # Do not overwrite original items; just pass them
                combined_items = items_loaded

                # Load combined_pallets from the cache if present
                combined_pallets_loaded = []
                if "combined_pallets" in cached_data:
                    for cp_data in cached_data["combined_pallets"]:
                        combined_pallet_item = Item.from_dict(cp_data)
                        # Generate color if needed
                        if combined_pallet_item.sku not in data_manager.sku_color_map:
                            data_manager.generate_color_for_sku(combined_pallet_item.sku)
                        combined_pallets_loaded.append(combined_pallet_item)

                # Assign combined pallets to the data manager
                data_manager.combined_pallets = combined_pallets_loaded

                main_window.input_page.update_items_table(combined_items)

                # Add this line to ensure model items and data_manager items are in sync
                main_window.data_manager.items = main_window.input_page.items_model.items
                
                # Store the hash of loaded items for future change detection
                main_window.last_cached_items_hash = compute_items_hash(main_window.data_manager.items)

                # Generate colors for SKUs if not present
                for item in combined_items:
                    sku = item.sku
                    if sku not in data_manager.sku_color_map:
                        data_manager.generate_color_for_sku(sku)

                # Now display containers and packed items
                containers_dict = {pc.container_id: pc.container for pc in packed_containers}
                all_packed_items = []
                for pc in packed_containers:
                    all_packed_items.extend(pc.packed_items)

                main_window.visualization_page.display_packed_items(
                    containers=containers_dict,
                    packed_items=all_packed_items,
                    sku_color_map=data_manager.sku_color_map
                )

                # Enable the visualization button so it remains clickable
                main_window.visualization_enabled = True
                main_window.input_page.back_to_visualization_button.setEnabled(True)

                QMessageBox.information(
                    main_window, "Cached Result Loaded",
                    "A cached result was loaded."
                )
                main_window.show_visualization_page()
                # Return None to skip fresh packing
                return None, None, None, None

            else:
                # Different packing method => run fresh
                pass
        except Exception as e:
            QMessageBox.warning(
                main_window,
                "Cache Load Failed",
                f"Failed to load cached results. Proceeding.\nError: {e}"
            )

    # Step 1: Process items with priority: Mixed Pallet > Europallet > Cartons
    processed_items = []
    for item in valid_items:  # Use valid_items, not data_manager.items
        if item.mixed_pallet:
            # Treat as a single mixed pallet item
            processed_items.append(item)
        elif item.europallet:
            # Treat as a europallet item
            processed_items.append(item)
        elif item.cartons > 0:
            # Get carton dimensions without modifying the original item
            carton_dimensions = data_manager.get_carton_dimensions(item)
            total_weight = item.weight * item.quantity
            
            # Look up the carton weight
            base_sku = data_manager.get_base_sku(item.sku)
            matched_row = data_manager.carton_dimensions_df[
                data_manager.carton_dimensions_df['Product Code'] == base_sku
            ]
            carton_weight = 0
            if not matched_row.empty:
                carton_weight = matched_row['Carton Weight'].iloc[0]
            
            qty_per_carton = data_manager.get_qty_per_carton(item.sku)

            if qty_per_carton > 0 and item.quantity == 1 and item.weight < 4:
                processed_items.append(item)
            else:
                if qty_per_carton > 0:
                    # Calculate per-carton weight as the average item weight plus the carton weight
                    weight_per_carton = (total_weight / item.cartons) + carton_weight
                else:
                    weight_per_carton = item.weight  # Fallback if QTY Per Carton not found
                
                # Create a new carton item with carton dimensions for packing purposes
                carton_item = data_manager.create_item(
                    sku=item.sku,
                    length=carton_dimensions['length'] * (1 + data_manager.margin_percentage / 100),
                    width=carton_dimensions['width'] * (1 + data_manager.margin_percentage / 100),
                    height=carton_dimensions['height'] * (1 + data_manager.margin_percentage / 100),
                    weight=weight_per_carton,
                    quantity=item.cartons,
                    stackable=item.stackable,
                    rotatable=item.rotatable,
                    mixed_pallet=item.mixed_pallet
                )
                
                # Set the flags to indicate this is a carton item with the original quantity
                carton_item.is_carton_item = True
                carton_item.original_quantity = item.quantity
                carton_item.original_cartons = item.cartons
                

                processed_items.append(carton_item)
        else:
            # No special conditions, just append normally
            processed_items.append(item)

    # Step 2: Group items with the same Mixed Pallet
    mixed_pallet_groups = {}
    remaining_items = []

    for item in processed_items:
        if item.mixed_pallet:
            if item.mixed_pallet not in mixed_pallet_groups:
                # Initialize the group
                mixed_pallet_groups[item.mixed_pallet] = {
                    'sku': f"MIXED-{item.mixed_pallet}",
                    'length': 120.0,
                    'width': 80.0,
                    'height': 50.0,
                    'weight': item.weight * item.quantity,
                    'quantity': 1,
                    'stackable': item.stackable,
                    'rotatable': item.rotatable,
                    'europallet': item.europallet,
                    'mixed_pallet': item.mixed_pallet,
                    'items': [item]  # Track contained items
                }
            else:
                mixed_pallet_groups[item.mixed_pallet]['weight'] += item.weight * item.quantity
                mixed_pallet_groups[item.mixed_pallet]['items'].append(item)  # Add to contained items
        else:
            remaining_items.append(item)

    # Step 3: Add 25 kg per unique Mixed Pallet
    for group in mixed_pallet_groups.values():
        group['weight'] += 25.0  # Add 25 kg per mixed pallet

    # Step 4: Add 25 kg per Europallet per item quantity
    adjusted_remaining_items = []
    for item in remaining_items:
        if item.europallet:
            items_per_pallet = data_manager.get_items_per_pallet(item.sku)
            if items_per_pallet:
                new_quantity = math.ceil(item.quantity / items_per_pallet)
            else:
                new_quantity = item.quantity  # Fallback if no items-per-pallet value found

            total_weight = (item.weight * new_quantity) + 25.0  # Pallet weight fixed addition
            # Create a new europallet item with the computed quantity
            adjusted_item = data_manager.create_europallet_item(
                sku=item.sku,
                weight=item.weight,
                stackable=item.stackable,
                rotatable=item.rotatable,
                quantity=new_quantity  # Use the computed quantity
            )
            adjusted_remaining_items.append(adjusted_item)
        else:
            adjusted_length = item.length * (1 + data_manager.margin_percentage / 100)
            adjusted_width = item.width * (1 + data_manager.margin_percentage / 100)
            adjusted_height = item.height * (1 + data_manager.margin_percentage / 100)
            adjusted_weight = item.weight
            adjusted_item = data_manager.create_item(
                sku=item.sku,
                length=adjusted_length,
                width=adjusted_width,
                height=adjusted_height,
                weight=adjusted_weight,
                quantity=item.quantity,
                stackable=item.stackable,
                rotatable=item.rotatable,
                mixed_pallet=item.mixed_pallet
            )
            
            # Transfer special carton item attributes if they exist
            if hasattr(item, 'is_carton_item') and item.is_carton_item:
                adjusted_item.is_carton_item = True
                adjusted_item.original_quantity = item.original_quantity
                adjusted_item.original_cartons = getattr(item, 'original_cartons', item.cartons)
            
            # Also transfer the cartons value which might be getting lost
            adjusted_item.cartons = item.cartons
            
            adjusted_remaining_items.append(adjusted_item)

    # Step 5: Create combined europallets for trailer containers
    if any(c.container_type == "Trailer - 13,6 m" for c in main_window.data_manager.containers):
        EUROPALLET_LENGTH = 120.0
        EUROPALLET_WIDTH = 80.0
        EUROPALLET_MAX_HEIGHT = 220.0
        EUROPALLET_MAX_WEIGHT = 1500.0
        EUROPALLET_BASE_HEIGHT = 14.4

        class ShelfPallet3D:
            def __init__(self, sku, length, width, max_height, max_weight):
                self.sku = sku
                self.length = length
                self.width = width
                self.max_height = max_height
                self.max_weight = max_weight
                self.shelves = []
                self.current_weight = 25.0

            def total_pallet_height(self):
                return sum(sh["height"] for sh in self.shelves) + EUROPALLET_BASE_HEIGHT

            def can_fit_weight(self, item):
                return (self.current_weight + item.weight) <= self.max_weight

            def place_item(self, item):
                if not self.can_fit_weight(item):
                    return False
                if not self.shelves:
                    self.shelves.append({"used_length": 0.0, "height": 0.0, "items": []})
                if self.try_place_in_existing_shelves(item):
                    self.current_weight += item.weight
                    return True
                if self.total_pallet_height() + item.height <= self.max_height:
                    new_shelf = {"used_length": 0.0, "height": 0.0, "items": []}
                    self.shelves.append(new_shelf)
                    if self.place_on_shelf(new_shelf, item):
                        self.current_weight += item.weight
                        return True
                return False

            def try_place_in_existing_shelves(self, item):
                for shelf in self.shelves:
                    if self.place_on_shelf(shelf, item):
                        return True
                return False

            def place_on_shelf(self, shelf, item):
                needed_length = shelf["used_length"] + (item.width if self.use_rotated(item, shelf) else item.length)
                shelf_height = max(shelf["height"], item.height)
                new_pallet_height = self.total_pallet_height() - shelf["height"] + shelf_height
                if (needed_length <= self.length and item.width <= self.width and new_pallet_height <= self.max_height) or \
                   (needed_length <= self.length and item.length <= self.width and new_pallet_height <= self.max_height and item.rotatable):
                    shelf["used_length"] = needed_length
                    shelf["height"] = shelf_height
                    shelf["items"].append(item)
                    return True
                return False

            def use_rotated(self, item, shelf):
                return (item.rotatable and item.width <= self.length - shelf["used_length"] and item.length <= self.width)

        non_pallet_items = []
        remaining_items_after_europallets = []
        for it in adjusted_remaining_items:
            if not it.europallet and not it.mixed_pallet:
                non_pallet_items.append(it)
            else:
                remaining_items_after_europallets.append(it)

        def by_volume(x):
            return x.length * x.width * x.height

        non_pallet_items.sort(key=by_volume, reverse=True)
        pallets = []

        for orig_item in non_pallet_items:
            q = orig_item.quantity
            while q > 0:
                single = data_manager.create_item(
                    sku=orig_item.sku,
                    length=orig_item.length,
                    width=orig_item.width,
                    height=orig_item.height,
                    weight=orig_item.weight,
                    quantity=1,
                    stackable=orig_item.stackable,
                    rotatable=orig_item.rotatable,
                    europallet=orig_item.europallet,
                    mixed_pallet=orig_item.mixed_pallet,
                    items_per_pallet=orig_item.items_per_pallet
                )
                placed = False
                for pallet in pallets:
                    if pallet.place_item(single):
                        placed = True
                        break
                if not placed:
                    pallet_sku = f"EuroP-{len(pallets)+1}"
                    new_pallet = ShelfPallet3D(
                        sku=pallet_sku,
                        length=EUROPALLET_LENGTH,
                        width=EUROPALLET_WIDTH,
                        max_height=EUROPALLET_MAX_HEIGHT,
                        max_weight=EUROPALLET_MAX_WEIGHT
                    )
                    if new_pallet.place_item(single):
                        pallets.append(new_pallet)
                        placed = True
                    else:
                        remaining_items_after_europallets.append(orig_item)
                        break
                if placed:
                    q -= 1
                else:
                    break

        europallet_items = []
        idx = 1

        for p in pallets:
            singles = []
            for shelf in p.shelves:
                singles.extend(shelf["items"])
            grouped_map = {}
            for si in singles:
                if si.sku not in grouped_map:
                    grouped_map[si.sku] = data_manager.create_item(
                        sku=si.sku,
                        length=si.length,
                        width=si.width,
                        height=si.height,
                        weight=si.weight,
                        quantity=si.quantity,
                        stackable=si.stackable,
                        rotatable=si.rotatable,
                        europallet=si.europallet,
                        mixed_pallet=si.mixed_pallet,
                        items_per_pallet=si.items_per_pallet
                    )
                else:
                    grouped_map[si.sku].quantity += si.quantity
                    grouped_map[si.sku].weight += si.weight
            combined = list(grouped_map.values())
            total_weight = sum(x.weight for x in combined) + 25.0
            new_item = data_manager.create_item(
                sku=f"EuroP-{idx}",
                length=p.length,
                width=p.width,
                height=p.total_pallet_height(),
                weight=total_weight,
                quantity=1,
                stackable=False,
                rotatable=False,
                europallet=True
            )
            new_item.contained_items = combined
            if new_item.sku not in data_manager.sku_color_map:
                data_manager.generate_color_for_sku(new_item.sku)
            europallet_items.append(new_item)
            idx += 1

        remaining_items = remaining_items_after_europallets + europallet_items
    else:
        pass

    # Step 6: Efficient grouping of “loose” items into combined pallets
    if combined_pallets:
        PALLET_LENGTH = 120.0
        PALLET_WIDTH  = 80.0
        PALLET_HEIGHT = 50.0
        PALLET_MAX_WEIGHT = 1500.0  # includes items + 25 kg pallet

        def can_item_fit_in_combined_pallet(
            existing_items,
            single_unit,
            max_length=PALLET_LENGTH,
            max_width=PALLET_WIDTH,
            max_height=PALLET_HEIGHT,
            max_total_weight=PALLET_MAX_WEIGHT
        ):
            """
            Checks if adding a single unit (quantity=1) 'single_unit' to 'existing_items'
            still fits within combined pallet constraints:
              (1) Single-item dimension check
              (2) Naive volume check
              (3) Weight check: sum(existing_items) + single_unit + 25.0 <= max_total_weight
            """
            if (single_unit.length > max_length or
                single_unit.width  > max_width  or
                single_unit.height > max_height):
                return False

            # (2) Naive volume check
            sum_volume = 0.0
            for i in existing_items:
                sum_volume += i.length * i.width * i.height

            new_unit_vol = single_unit.length * single_unit.width * single_unit.height
            total_volume = sum_volume + new_unit_vol
            max_vol = max_length * max_width * max_height

            if total_volume > max_vol:
                return False

            # (3) Weight check
            current_weight = sum(x.weight for x in existing_items)
            total_with_pallet = current_weight + single_unit.weight + 25.0

            if total_with_pallet > max_total_weight:
                return False

            return True

        # Filter out loose items (not on mixed or europallet)
        loose_items = []
        processed_items_post45 = []
        for item in remaining_items:  # <-- Use remaining_items instead of adjusted_remaining_items
            if not item.mixed_pallet and not item.europallet:
                loose_items.append(item)
            else:
                processed_items_post45.append(item)

        # Sort loose items by volume, descending
        loose_items.sort(key=lambda it: (it.length * it.width * it.height) * it.quantity, reverse=True)

        pallets_contents = []  # Each element is a list of single-unit Items
        pallet_index = 0

        for loose_item in loose_items:
            # If item is too big, skip combining
            if (loose_item.length > PALLET_LENGTH or
                loose_item.width  > PALLET_WIDTH  or
                loose_item.height > PALLET_HEIGHT):
                processed_items_post45.append(loose_item)
                continue

            qty_remaining = loose_item.quantity
            while qty_remaining > 0:
                # Create a single-unit clone
                single_unit = main_window.data_manager.create_item(
                    sku=loose_item.sku,
                    length=loose_item.length,
                    width=loose_item.width,
                    height=loose_item.height,
                    weight=loose_item.weight,
                    quantity=1,
                    stackable=loose_item.stackable,
                    rotatable=loose_item.rotatable,
                    mixed_pallet=loose_item.mixed_pallet
                )

                # Try to place single_unit in an existing combined pallet
                placed = False
                for existing_units in pallets_contents:
                    if can_item_fit_in_combined_pallet(existing_units, single_unit):
                        existing_units.append(single_unit)
                        placed = True
                        break

                if not placed:
                    pallet_index += 1
                    pallets_contents.append([single_unit])

                qty_remaining -= 1

        # Now create actual "CombP-n" items from these single-unit groups
        combined_pallet_items = []
        for idx, pallet_units in enumerate(pallets_contents, start=1):
            sum_weight = sum(u.weight for u in pallet_units)
            margin_factor = 1 + main_window.data_manager.margin_percentage / 100
            c_len = PALLET_LENGTH
            c_wid = PALLET_WIDTH
            c_hei = PALLET_HEIGHT
            final_weight = sum_weight + 25.0  # plus pallet

            combined_item = main_window.data_manager.create_item(
                sku=f"CombP-{idx}",
                length=c_len,
                width=c_wid,
                height=c_hei,
                weight=final_weight,
                quantity=1,
                stackable=True,
                rotatable=False,
                mixed_pallet=""
            )
            # Store the single-unit items
            combined_item.contained_items = pallet_units

            # Generate a color if not present
            if combined_item.sku not in main_window.data_manager.sku_color_map:
                main_window.data_manager.generate_color_for_sku(combined_item.sku)

            combined_pallet_items.append(combined_item)

        remaining_items = processed_items_post45 + combined_pallet_items
    else:
        # If combined_pallets is False, skip step 6
        processed_items_post45 = remaining_items  # Use the updated remaining_items from Step 5
        combined_pallet_items = []
        remaining_items = processed_items_post45

    # Step 7: Create a list of grouped mixed pallet items
    grouped_mixed_pallet_items = []
    for group in mixed_pallet_groups.values():
        adjusted_item = main_window.data_manager.create_mixed_pallet_item(
            mixed_pallet=group['mixed_pallet'],
            total_weight=group['weight'],
            stackable=group['stackable'],
            rotatable=group['rotatable']
        )
        # Color logic
        if adjusted_item.sku not in main_window.data_manager.sku_color_map:
            main_window.data_manager.generate_color_for_sku(adjusted_item.sku)

        # Link the real items in 'contained_items'
        group_items = group.get('items', [])
        adjusted_item.contained_items = list(group_items)

        grouped_mixed_pallet_items.append(adjusted_item)

    # Step 8: Combine grouped mixed pallet items with the "remaining" items
    combined_items = grouped_mixed_pallet_items + remaining_items

    # Step 9: Expand items based on quantity, but don't overwrite data_manager.items
    expanded_items = []
    for item in combined_items:
        if item.mixed_pallet:
            # Keep as single item
            expanded_items.append(item)
        elif hasattr(item, 'is_carton_item') and item.is_carton_item:
            # For carton items, preserve them as-is without expanding
            expanded_items.append(item)
        else:
            # Expand out by quantity for non-carton items
            for _ in range(item.quantity):
                single = main_window.data_manager.create_item(
                    sku=item.sku,
                    length=item.length,
                    width=item.width,
                    height=item.height,
                    weight=item.weight,
                    quantity=1,
                    stackable=item.stackable,
                    rotatable=item.rotatable,
                    mixed_pallet=item.mixed_pallet,
                    europallet=item.europallet
                )
                expanded_items.append(single)

    # Filter items that actually fit in at least one container dimension
    fit_capable_items = []
    for item in expanded_items:
        if any(
            item.length <= c.length and
            item.width  <= c.width  and
            item.height <= c.height
            for c in main_window.data_manager.containers
        ):
            fit_capable_items.append(item)

    expanded_items = fit_capable_items

    # Compute aggregated counts for each SKU in expanded_items
    sku_counts = {}
    for item in expanded_items:
        if hasattr(item, 'is_carton_item') and item.is_carton_item and item.original_quantity is not None:
            sku_counts[item.sku] = sku_counts.get(item.sku, 0) + item.original_quantity
        else:
            sku_counts[item.sku] = sku_counts.get(item.sku, 0) + 1

    def sort_key(x):
        # Check if item is a pallet (including pallet-sized carton items)
        is_pallet = (
            x.europallet or 
            (x.mixed_pallet != "") or 
            x.sku.startswith("CombP-") or
            x.sku.startswith("EuroP-") or
            x.sku.startswith("MIXED-") or
            # Check for pallet-sized carton items (exactly 120x80)
            (hasattr(x, 'is_carton_item') and x.is_carton_item and x.length == 120.0 and x.width == 80.0)
        )

        if is_pallet:
            group = 0
        else:
            # Check for small items in any dimension
            if x.height < 5 or x.width < 7 or x.length < 7:
                group = 3  # Flat or small items are in the last group
            else:
                if sku_counts.get(x.sku, 0) > 20:
                    group = 1
                else:
                    group = 2
        
        volume = x.length * x.width * x.height
        sku_count = sku_counts.get(x.sku, 0)
        
        # Composite score prioritizing size slightly over weight and considering SKU count
        composite_score = (0.4 * volume) + (0.3 * x.weight * 1000) + (0.3 * sku_count * 100)
        return (group, -composite_score)

    sorted_items = sorted(expanded_items, key=sort_key)

    all_combined_pallets = [
        i for i in combined_items
        if i.sku.startswith("CombP-") or i.sku.startswith("EuroP-")
    ]
    main_window.data_manager.combined_pallets = all_combined_pallets

    return scenario_hash, cache_file_path, packing_method, sorted_items


