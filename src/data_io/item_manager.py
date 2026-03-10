# src/data_io/item_manager.py

import math
from PyQt5.QtWidgets import QMessageBox, QAbstractItemView

class ItemManager:
    def __init__(self, parent):
        """
        :param parent: Reference to MainWindow instance to access data_manager, input_page, etc.
        """
        self.parent = parent

    def add_item(self):
        """Adds an item to the items list and updates the table."""
        # Commit any pending edits in the items table
        input_page = self.parent.input_page
        if input_page.items_table.state() == QAbstractItemView.EditingState:
            editor = input_page.items_table.currentEditor()
            if editor:
                input_page.items_table.commitData(editor)
                input_page.items_table.closeEditor(editor, QAbstractItemView.NoHint)

        sku = self.parent.input_page.sku_input.text().strip()
        if not sku:
            QMessageBox.warning(self.parent, "Input Error", "Product Code cannot be empty.")
            return

        mixed_pallet = self.parent.input_page.mixed_pallet_input.text().strip()  # Get Mixed Pallet input
        quantity = self.parent.input_page.quantity_input.value()

        if mixed_pallet:
            # Create Mixed Pallet Item using DataManager's method
            item = self.parent.data_manager.create_mixed_pallet_item(
                mixed_pallet=mixed_pallet,
                total_weight=0,  # Weight is handled within DataManager
                stackable=False,  # Default values; adjust if needed
                rotatable=False   # Default values; adjust if needed
            )
        else:
            # Retrieve dimensions and attributes from DataManager
            dimensions = self.parent.data_manager.get_dimensions_for_product_code(sku)
            if not dimensions:
                QMessageBox.warning(self.parent, "Input Error", "Invalid SKU or dimensions not found.")
                return

            # Retrieve QTY Per Carton
            qty_per_carton = self.parent.data_manager.get_qty_per_carton(sku)

            # Calculate cartons automatically
            if qty_per_carton > 0:
                cartons = self.parent.data_manager.calculate_cartons(quantity, qty_per_carton)
            else:
                cartons = 0  # or handle differently if desired

            item = self.parent.data_manager.create_item(
                sku=sku,
                length=dimensions['length'],
                width=dimensions['width'],
                height=dimensions['height'],
                weight=dimensions['weight'],
                quantity=quantity,
                stackable=dimensions['stackable'],
                rotatable=dimensions['rotatable'],
                europallet=False,
                mixed_pallet=mixed_pallet
            )

            # Add carton information as an attribute
            item.cartons = cartons

        # Determine Europallet status from product data dimensions.
        if dimensions.get('europallet', False) and not mixed_pallet:
            item.europallet = True

        # Check carton quantity issues
        if not mixed_pallet and item.cartons > 0:
            self.check_carton_quantity(sku, quantity, item.cartons)
            base_sku = self.parent.data_manager.get_base_sku(sku)
            matched_row = self.parent.data_manager.carton_dimensions_df[
                self.parent.data_manager.carton_dimensions_df['Product Code'] == base_sku
            ]
            if not matched_row.empty:
                qty_per_carton = matched_row['QTY Per Carton'].iloc[0]
                ideal_cartons = math.ceil(quantity / qty_per_carton)
                item.has_carton_issue = (item.cartons != ideal_cartons)
            else:
                item.has_carton_issue = False

            if qty_per_carton and qty_per_carton > 0:
                remainder = quantity % qty_per_carton
                item.has_remainder_issue = (remainder > 0)
            else:
                item.has_remainder_issue = False
        else:
            item.has_carton_issue = False
            item.has_remainder_issue = False

        # Check if SKU already exists in the same "mixed pallet" and "cartons" configuration
        existing_item = next(
            (existing for existing in self.parent.data_manager.items
             if existing.sku == item.sku and existing.mixed_pallet == item.mixed_pallet and existing.cartons == item.cartons),
            None
        )

        if existing_item:
            existing_item.quantity += item.quantity
            if item.europallet:
                existing_item.europallet = True
                existing_item.europallet_quantity = item.europallet_quantity
                existing_item.items_per_pallet = item.items_per_pallet

            if not mixed_pallet and existing_item.cartons > 0 and qty_per_carton > 0:
                self.check_carton_quantity(existing_item.sku, existing_item.quantity, existing_item.cartons)
                existing_item.has_carton_issue = (existing_item.cartons != math.ceil(existing_item.quantity / qty_per_carton))
                remainder = existing_item.quantity % qty_per_carton
                existing_item.has_remainder_issue = (remainder > 0)

            current_item = existing_item
        else:
            # Append the new item to data_manager.items
            self.parent.data_manager.items.append(item)
            if item.sku not in self.parent.data_manager.sku_color_map:
                self.parent.data_manager.sku_color_map[item.sku] = self.parent.data_manager.generate_color_for_sku(item.sku)
            current_item = item

        # *** Existing approach: reset the entire model. ***
        self.parent.input_page.update_items_table(self.parent.data_manager.items)

        # Update Mixed Pallet autocompletion
        if mixed_pallet and mixed_pallet not in self.parent.mixed_pallet_list:
            self.parent.mixed_pallet_list.append(mixed_pallet)
            self.parent.mixed_pallet_model.setStringList(self.parent.mixed_pallet_list)

        # Reset input fields
        self.parent.input_page.sku_input.clear()
        self.parent.input_page.quantity_input.setValue(1)
        self.parent.input_page.mixed_pallet_input.clear()

        # Invalidate Packed Data
        self.parent.data_manager.packed_containers = []

    def delete_item_by_row(self, row):
        """Deletes an item from the items list based on its row index and updates the table."""
        # Commit any pending edits in the items table
        input_page = self.parent.input_page
        if input_page.items_table.state() == QAbstractItemView.EditingState:
            editor = input_page.items_table.currentEditor()
            if editor:
                input_page.items_table.commitData(editor)
                input_page.items_table.closeEditor(editor, QAbstractItemView.NoHint)

        if 0 <= row < len(self.parent.data_manager.items):
            item_to_delete = self.parent.data_manager.items[row]
            sku = item_to_delete.sku
            mixed_pallet = item_to_delete.mixed_pallet

            confirm = QMessageBox.question(
                self.parent, "Delete Confirmation",
                f"Are you sure you want to delete the item with SKU '{sku}'?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                self.parent.data_manager.items.pop(row)

                # Clean up SKU color map if no items use this SKU anymore
                if not any(item.sku == sku for item in self.parent.data_manager.items):
                    self.parent.data_manager.sku_color_map.pop(sku, None)

                # Clean up Mixed Pallet list if no items use this pallet
                if mixed_pallet and not any(item.mixed_pallet == mixed_pallet for item in self.parent.data_manager.items):
                    if mixed_pallet in self.parent.mixed_pallet_list:
                        self.parent.mixed_pallet_list.remove(mixed_pallet)
                        self.parent.mixed_pallet_model.setStringList(self.parent.mixed_pallet_list)

                # Update the table
                self.parent.input_page.update_items_table(self.parent.data_manager.items)
                self.parent.data_manager.packed_containers = []
        else:
            QMessageBox.warning(
                self.parent, "Delete Error",
                f"No item found at row '{row}'."
            )

    def check_carton_quantity(self, sku, quantity, cartons):
        """Checks if the number of cartons is appropriate."""
        base_sku = self.parent.data_manager.get_base_sku(sku)
        matched_row = self.parent.data_manager.carton_dimensions_df[
            self.parent.data_manager.carton_dimensions_df['Product Code'] == base_sku
        ]

        if not matched_row.empty:
            qty_per_carton = matched_row['QTY Per Carton'].iloc[0]
            if qty_per_carton > 0:
                ideal_cartons = math.ceil(quantity / qty_per_carton)
                if cartons != ideal_cartons:
                    message = (
                        f"For SKU '<b>{sku}</b>' with quantity <b>{quantity}</b>,<br><br>"
                        f"<span style='color: blue;'>QTY Per Carton:</span> <b>{qty_per_carton}</b><br>"
                        f"<span style='color: green;'>Ideal number of cartons:</span> <b>{ideal_cartons}</b><br>"
                        f"<span style='color: red;'>Your specified number of cartons:</span> <b>{cartons}</b><br><br>"
                        "Please adjust the number of cartons to match the ideal value."
                    )
                    QMessageBox.information(self.parent, "Carton Quantity Suggestion", message)

    def handle_carton_quantity_issue(self, sku, quantity, cartons, ideal_cartons):
        """Handles carton quantity issues from the model."""
        qty_per_carton = self.parent.data_manager.get_qty_per_carton(sku)
        if qty_per_carton is None or qty_per_carton <= 0:
            qty_per_carton = "N/A"

        message = (
            f"For SKU '<b>{sku}</b>' with quantity <b>{quantity}</b>,<br><br>"
            f"<span style='color: blue;'>QTY Per Carton:</span> <b>{qty_per_carton}</b><br>"
            f"<span style='color: green;'>Ideal number of cartons:</span> <b>{ideal_cartons}</b><br>"
            f"<span style='color: red;'>Your specified number of cartons:</span> <b>{cartons}</b><br><br>"
            "Please adjust the number of cartons to match the ideal value."
        )
        QMessageBox.information(self.parent, "Carton Quantity Suggestion", message)

    def handle_remainder_issue(self, item):
        """Handles remainder issues from the model."""
        qty_per_carton = self.parent.data_manager.get_qty_per_carton(item.sku)
        cartons = item.cartons
        if qty_per_carton is None or qty_per_carton <= 0:
            qty_per_carton_display = "N/A"
            remaining_space = "N/A"
        else:
            total_capacity = cartons * qty_per_carton
            remaining_space = max(total_capacity - item.quantity, 0)
            qty_per_carton_display = f"{qty_per_carton}"

        message = (
            f"For SKU '<b>{item.sku}</b>' with quantity <b>{item.quantity}</b>,<br><br>"
            f"<span style='color: blue;'>QTY Per Carton:</span> <b>{qty_per_carton_display}</b><br>"
            f"<span style='color: orange;'>Space left in the last carton:</span> <b>{remaining_space}</b><br><br>"
            "Consider adjusting the quantity or cartons to better utilize space."
        )
        QMessageBox.information(self.parent, "Leftover Space Notice", message)

    def handle_missing_dimension_issue(self, item):
        """Handles missing dimension/weight issues for the item."""
        import math

        missing_attrs = []
        if math.isnan(item.length):
            missing_attrs.append("Length")
        if math.isnan(item.width):
            missing_attrs.append("Width")
        if math.isnan(item.height):
            missing_attrs.append("Height")
        if math.isnan(item.weight):
            missing_attrs.append("Weight")

        if missing_attrs:
            attrs_str = ", ".join(missing_attrs)
        else:
            attrs_str = "unknown attributes"

        message = (
            f"For SKU '<b>{item.sku}</b>', the following attributes are missing:<br><br>"
            f"<span style='color: blue;'>{attrs_str}</span><br><br>"
            "Without complete dimensions and weight information, the packing algorithm cannot properly handle this item.<br><br>"
            "Please open <b>Product Settings</b> to update or add these missing attributes."
        )
        QMessageBox.information(self.parent, "Missing Dimensions/Weight Notice", message)

    def on_issue_clicked(self, row_index, issue_type):
        """Handles issue cell clicks in the items table."""
        if 0 <= row_index < len(self.parent.data_manager.items):
            item = self.parent.data_manager.items[row_index]

            if issue_type == 'carton' and item.has_carton_issue:
                qty_per_carton = self.parent.data_manager.get_qty_per_carton(item.sku)
                if not qty_per_carton:
                    qty_per_carton = "N/A"
                    ideal_cartons = "N/A"
                else:
                    ideal_cartons = math.ceil(item.quantity / qty_per_carton)

                self.handle_carton_quantity_issue(item.sku, item.quantity, item.cartons, ideal_cartons)

            elif issue_type == 'remainder' and item.has_remainder_issue:
                self.handle_remainder_issue(item)

            elif issue_type == 'missing_dimension' and item.has_missing_dimension_issue:
                self.handle_missing_dimension_issue(item)

    def split_item(self, row, left_qty, right_qty):
        """Splits the item at the given row into two items."""
        # Commit any edits in the table before splitting
        input_page = self.parent.input_page
        if input_page.items_table.state() == QAbstractItemView.EditingState:
            editor = input_page.items_table.currentEditor()
            if editor:
                input_page.items_table.commitData(editor)
                input_page.items_table.closeEditor(editor, QAbstractItemView.NoHint)

        if 0 <= row < len(self.parent.data_manager.items):
            original_item = self.parent.data_manager.items[row]

            if left_qty + right_qty != original_item.quantity:
                QMessageBox.warning(
                    self.parent,
                    "Split Error",
                    "Split quantities must sum up to the original quantity."
                )
                return

            base_sku = self.parent.data_manager.get_base_sku(original_item.sku)
            next_prefix_number = self.parent.data_manager.get_next_prefix_number(base_sku)

            # Decide if this item is a "carton" item
            if original_item.cartons > 0:
                qty_per_carton = self.parent.data_manager.get_qty_per_carton(original_item.sku)
                if qty_per_carton <= 0:
                    QMessageBox.warning(
                        self.parent,
                        "Split Error",
                        f"QTY Per Carton not found or invalid for SKU '{original_item.sku}'."
                    )
                    return
                cartons1 = self.parent.data_manager.calculate_cartons(left_qty, qty_per_carton)
                cartons2 = self.parent.data_manager.calculate_cartons(right_qty, qty_per_carton)
            else:
                qty_per_carton = 0
                cartons1 = 0
                cartons2 = 0

            item1_sku = f"{next_prefix_number}-{base_sku}"
            item2_sku = f"{next_prefix_number + 1}-{base_sku}"

            # Use create_item instead of create_carton_item
            item1 = self.parent.data_manager.create_item(
                sku=item1_sku,
                length=original_item.length,
                width=original_item.width,
                height=original_item.height,
                weight=original_item.weight,
                quantity=left_qty,
                stackable=original_item.stackable,
                rotatable=original_item.rotatable,
                europallet=getattr(original_item, 'europallet', False),
                mixed_pallet=getattr(original_item, 'mixed_pallet', "")
            )
            # Set cartons attribute after creation
            item1.cartons = cartons1

            item2 = self.parent.data_manager.create_item(
                sku=item2_sku,
                length=original_item.length,
                width=original_item.width,
                height=original_item.height,
                weight=original_item.weight,
                quantity=right_qty,
                stackable=original_item.stackable,
                rotatable=original_item.rotatable,
                europallet=getattr(original_item, 'europallet', False),
                mixed_pallet=getattr(original_item, 'mixed_pallet', "")
            )
            # Set cartons attribute after creation
            item2.cartons = cartons2

            # Update issues
            for it in [item1, item2]:
                if it.cartons > 0 and qty_per_carton > 0:
                    ideal_cartons = math.ceil(it.quantity / qty_per_carton)
                    if it.cartons < ideal_cartons:
                        it.has_carton_issue = True
                        it.has_remainder_issue = False
                    else:
                        it.has_carton_issue = False
                        total_capacity = it.cartons * qty_per_carton
                        it.has_remainder_issue = (total_capacity > it.quantity)
                else:
                    it.has_carton_issue = False
                    it.has_remainder_issue = False

            # Replace the original item with the two new items
            self.parent.data_manager.items.pop(row)
            self.parent.data_manager.items.insert(row, item2)
            self.parent.data_manager.items.insert(row, item1)

            for it in [item1, item2]:
                if it.sku not in self.parent.data_manager.sku_color_map:
                    self.parent.data_manager.sku_color_map[it.sku] = self.parent.data_manager.generate_color_for_sku(it.sku)

                mixed_pallet = it.mixed_pallet
                if mixed_pallet and mixed_pallet not in self.parent.mixed_pallet_list:
                    self.parent.mixed_pallet_list.append(mixed_pallet)
                    self.parent.mixed_pallet_model.setStringList(self.parent.mixed_pallet_list)

            # Reset the table to reflect changes
            self.parent.input_page.update_items_table(self.parent.data_manager.items)
            self.parent.data_manager.packed_containers = []

            QMessageBox.information(
                self.parent,
                "Item Split",
                f"Item '{original_item.sku}' has been split into two items."
            )