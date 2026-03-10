import math
import itertools
from typing import List, Tuple, Optional, Callable
from src.models.models import Item, Container, PackedItem, PackedContainer

class SpatialIndex2D:
    def __init__(self, length: float, width: float, step: float):
        self.step = step
        self.grid_length = int(math.ceil(length / step))
        self.grid_width = int(math.ceil(width / step))
        self.heights = [[0.0 for _ in range(self.grid_width)] for _ in range(self.grid_length)]

    def get_base_z(self, x: float, y: float, lx: float, ly: float) -> float:
        gx_start = int(x // self.step)
        gx_end = int(math.ceil((x + lx) / self.step))
        gy_start = int(y // self.step)
        gy_end = int(math.ceil((y + ly) / self.step))

        if gx_end > self.grid_length:
            gx_end = self.grid_length
        if gy_end > self.grid_width:
            gy_end = self.grid_width

        base_z = 0.0
        for gx in range(gx_start, gx_end):
            for gy in range(gy_start, gy_end):
                if self.heights[gx][gy] > base_z:
                    base_z = self.heights[gx][gy]
        return base_z

    def update_surface(self, x: float, y: float, lx: float, ly: float, new_top: float):
        gx_start = int(x // self.step)
        gx_end = int(math.ceil((x + lx) / self.step))
        gy_start = int(y // self.step)
        gy_end = int(math.ceil((y + ly) / self.step))

        if gx_end > self.grid_length:
            gx_end = self.grid_length
        if gy_end > self.grid_width:
            gy_end = self.grid_width

        for gx in range(gx_start, gx_end):
            for gy in range(gy_start, gy_end):
                if self.heights[gx][gy] < new_top:
                    self.heights[gx][gy] = new_top


def is_pallet(item: Item) -> bool:
    """
    Identify 'pallet' items by any relevant criteria:
      - item.europallet is True
      - item.sku starts with 'COMBINED-' or 'MIXED-'
      - item is a carton item with standard pallet dimensions (120 x 80)
      - or any other logic (e.g. item.mixed_pallet != '')
    Adjust as needed for your data model.
    """
    if item.europallet:
        return True
    if hasattr(item, "mixed_pallet") and item.mixed_pallet != "":
        return True
    sku_lower = item.sku.lower()
    if (sku_lower.startswith("combp-") or 
        sku_lower.startswith("mixed-")):
        return True
    if (hasattr(item, 'is_carton_item') and item.is_carton_item and 
        item.length == 120.0 and item.width == 80.0):
        return True
    return False


def generate_orientations_for_pallet_pattern(item: Item, c_info: dict) -> List[tuple]:
    """
    Enforce a '3 wide, then 2 length' pattern for pallets in each container:
      Phase A => (width, length, height)
      Phase B => (length, width, height)
    - 3 pallets in phase A => switch to B
    - 2 pallets in phase B => switch to A
    """
    phase = c_info["pallet_pattern_phase"]
    count = c_info["pallet_pattern_count"]

    if phase == "A":
        # e.g., (80, 120, h) first, fallback (120, 80, h)
        primary = (item.width, item.length, item.height)
        secondary = (item.length, item.width, item.height)
    else:
        # e.g., (120, 80, h) first, fallback (80, 120, h)
        primary = (item.length, item.width, item.height)
        secondary = (item.width, item.length, item.height)

    return [primary, secondary]


def generate_orientations(item: Item, c_info: dict) -> List[tuple]:
    """
    Specialized orientation logic:
      - If this item is a pallet AND the container is a 'Trailer - 13,6 m',
        then return only [(width, length, height)].
      - Else if this item is a pallet in a normal container, use the 3/2 pattern.
      - Otherwise, fall back to normal rotation logic for non-pallet items.
    """
    container_type = c_info["container"].container_type

    if is_pallet(item):
        # Special case: For the 'Trailer - 13,6 m' container, always use (width,length,height) only
        if container_type == "Trailer - 13,6 m":
            return [(item.width, item.length, item.height)]
        else:
            # Otherwise do the 3/2 checker pattern
            return generate_orientations_for_pallet_pattern(item, c_info)

    # Non-pallet items:
    if not item.rotatable:
        return [
            (item.length, item.width, item.height),
            (item.width, item.length, item.height),
        ]
    dims = [item.length, item.width, item.height]
    all_perms = set(itertools.permutations(dims, 3))
    return list(all_perms)


def run_packing_algorithm(
    items: List[Item],
    containers: List[Container],
    packing_method: str = "floor_loading",
    progress_callback: Optional[Callable[[int], None]] = None
) -> List[PackedContainer]:

    # Assign container IDs if missing
    for idx, c in enumerate(containers):
        if c.container_id == 0:
            c.container_id = idx + 1

    total_items = sum(i.quantity for i in items)
    def report_progress(packed_count: int):
        if progress_callback and total_items > 0:
            percent = int((packed_count / total_items) * 100)
            progress_callback(percent)

    def calculate_rotation(original_item: Item, placed_size: tuple) -> tuple:
        # Just a placeholder, you can adapt if needed
        return (0,0,0)

    def can_stack(base_z: float, item: Item, item_height: float, container_height: float) -> bool:
        if base_z + item_height > container_height + 1e-2:
            return False
        if base_z > 1e-2 and not item.stackable:
            return False
        return True

    def is_stable_placement(
        s_index: SpatialIndex2D,
        x: float,
        y: float,
        lx: float,
        ly: float,
        tolerance=1e-2,
        fraction=0.8
    ) -> bool:
        gx_start = int(x // s_index.step)
        gx_end = int(math.ceil((x + lx) / s_index.step))
        gy_start = int(y // s_index.step)
        gy_end = int(math.ceil((y + ly) / s_index.step))

        cell_heights = []
        for gx in range(gx_start, gx_end):
            for gy in range(gy_start, gy_end):
                if 0 <= gx < s_index.grid_length and 0 <= gy < s_index.grid_width:
                    cell_heights.append(s_index.heights[gx][gy])

        if not cell_heights:
            return False

        max_h = max(cell_heights)
        close_count = sum(1 for h in cell_heights if abs(h - max_h) <= tolerance)
        return (close_count / len(cell_heights)) >= fraction

    def increment_pallet_pattern(c_info: dict):
        """
        If 'A' => we want to place 3 in A, then switch to B for 2.
        If 'B' => place 2 in B, switch back to A for 3.
        """
        if "pallet_pattern_phase" not in c_info:
            c_info["pallet_pattern_phase"] = "A"
        if "pallet_pattern_count" not in c_info:
            c_info["pallet_pattern_count"] = 0

        c_info["pallet_pattern_count"] += 1

        if c_info["pallet_pattern_phase"] == "A":
            if c_info["pallet_pattern_count"] >= 3:
                c_info["pallet_pattern_phase"] = "B"
                c_info["pallet_pattern_count"] = 0
        else:  # phase B
            if c_info["pallet_pattern_count"] >= 2:
                c_info["pallet_pattern_phase"] = "A"
                c_info["pallet_pattern_count"] = 0


    #
    # FLOOR LOADING
    #
    def floor_loading_algorithm_human_friendly(
        items_to_pack: List[Item],
        containers_list: List[Container]
    ) -> List[PackedContainer]:

        step_size = 10.0
        container_info = []
        for c in containers_list:
            container_info.append({
                "container": c,
                "index": SpatialIndex2D(c.length, c.width, step_size),
                "remaining_weight": c.max_weight,
                "packed_items": [],
                "pallet_pattern_phase": "A",
                "pallet_pattern_count": 0
            })

        packed_count = 0

        # Process items in given order
        for it in items_to_pack:
            for _ in range(it.quantity):
                placed = False
                for c_info in container_info:
                    cont = c_info["container"]
                    s_index = c_info["index"]
                    if c_info["remaining_weight"] < it.weight:
                        continue
                    if it.height > cont.height:
                        continue

                    ors = generate_orientations(it, c_info)

                    best_placement = None
                    for (lx, ly, lh) in ors:
                        if lx > cont.length + 1e-2 or ly > cont.width + 1e-2 or lh > cont.height + 1e-2:
                            continue

                        px = 0.0
                        while px + lx <= cont.length + 1e-2:
                            py = 0.0
                            while py + ly <= cont.width + 1e-2:
                                base_z = s_index.get_base_z(px, py, lx, ly)
                                if can_stack(base_z, it, lh, cont.height):
                                    if base_z < 1e-2 or is_stable_placement(s_index, px, py, lx, ly):
                                        if best_placement is None or base_z < best_placement["z"]:
                                            best_placement = {
                                                "x": px,
                                                "y": py,
                                                "z": base_z,
                                                "lx": lx,
                                                "ly": ly,
                                                "lh": lh
                                            }
                                py += step_size
                            px += step_size

                        if best_placement is not None:
                            # we found a spot for this orientation; use it
                            break

                    if best_placement is not None:
                        x = best_placement["x"]
                        y = best_placement["y"]
                        z = best_placement["z"]
                        lx = best_placement["lx"]
                        ly = best_placement["ly"]
                        lh = best_placement["lh"]
                        new_top = z + lh

                        packed_item = PackedItem(
                            sku=it.sku,
                            position=(x, y, z),
                            size=(lx, ly, lh),
                            rotation=calculate_rotation(it, (lx, ly, lh)),
                            container_id=cont.container_id,
                            weight=it.weight,
                            quantity=1,
                            europallet=it.europallet,
                            contained_items=[]
                        )

                        c_info["packed_items"].append(packed_item)
                        c_info["remaining_weight"] -= it.weight
                        s_index.update_surface(x, y, lx, ly, new_top)
                        packed_count += 1
                        report_progress(packed_count)
                        placed = True

                        if is_pallet(it):
                            increment_pallet_pattern(c_info)
                        break

                if not placed:
                    # create a new container
                    new_id = max(ci["container"].container_id for ci in container_info) + 1
                    ref = container_info[-1]["container"]
                    new_container = Container(
                        length=ref.length,
                        width=ref.width,
                        height=ref.height,
                        max_weight=ref.max_weight,
                        container_id=new_id,
                        container_type=ref.container_type
                    )
                    new_index = SpatialIndex2D(new_container.length, new_container.width, step_size)
                    container_info.append({
                        "container": new_container,
                        "index": new_index,
                        "remaining_weight": new_container.max_weight,
                        "packed_items": [],
                        "pallet_pattern_phase": "A",
                        "pallet_pattern_count": 0
                    })
                    c_info_new = container_info[-1]
                    cont = c_info_new["container"]
                    s_index = c_info_new["index"]
                    ors = generate_orientations(it, c_info_new)

                    for (lx, ly, lh) in ors:
                        if (lx <= cont.length + 1e-2 and
                            ly <= cont.width + 1e-2 and
                            lh <= cont.height + 1e-2 and
                            it.weight <= c_info_new["remaining_weight"]):
                            base_z = s_index.get_base_z(0.0, 0.0, lx, ly)
                            if can_stack(base_z, it, lh, cont.height):
                                new_top = base_z + lh
                                packed_item = PackedItem(
                                    sku=it.sku,
                                    position=(0.0, 0.0, base_z),
                                    size=(lx, ly, lh),
                                    rotation=calculate_rotation(it, (lx, ly, lh)),
                                    container_id=cont.container_id,
                                    weight=it.weight,
                                    quantity=1,
                                    europallet=it.europallet,
                                    contained_items=[]
                                )
                                c_info_new["packed_items"].append(packed_item)
                                c_info_new["remaining_weight"] -= it.weight
                                s_index.update_surface(0.0, 0.0, lx, ly, new_top)
                                packed_count += 1
                                report_progress(packed_count)

                                if is_pallet(it):
                                    increment_pallet_pattern(c_info_new)
                                break

        packed_results: List[PackedContainer] = []
        for c_info in container_info:
            if c_info["packed_items"]:
                packed_results.append(PackedContainer(
                    container_id=c_info["container"].container_id,
                    container=c_info["container"],
                    packed_items=c_info["packed_items"]
                ))
        return packed_results

    #
    # VERTICAL LOADING
    #
    def vertical_loading_algorithm_stack(
        items_to_pack: List[Item],
        containers_list: List[Container]
    ) -> List[PackedContainer]:

        step_size = 5.0
        container_info = []
        for c in containers_list:
            container_info.append({
                "container": c,
                "index": SpatialIndex2D(c.length, c.width, step_size),
                "remaining_weight": c.max_weight,
                "packed_items": [],
                "pallet_pattern_phase": "A",
                "pallet_pattern_count": 0
            })

        packed_results: List[PackedContainer] = []
        packed_count = 0

        # Flatten items to single quantity
        single_items = []
        for it in items_to_pack:
            for _ in range(it.quantity):
                new_item = Item(
                    sku=it.sku,
                    length=it.length,
                    width=it.width,
                    height=it.height,
                    weight=it.weight,
                    quantity=1,
                    stackable=it.stackable,
                    rotatable=it.rotatable,
                    europallet=it.europallet
                )
                # Transfer any extra attributes if needed
                if hasattr(it, 'original_quantity'):
                    new_item.original_quantity = it.original_quantity
                if hasattr(it, 'is_carton_item'):
                    new_item.is_carton_item = it.is_carton_item

                single_items.append(new_item)

        idx_left = 0
        while idx_left < len(single_items):
            item = single_items[idx_left]
            placed = False
            report_progress(packed_count)

            for c_info in container_info:
                if c_info["remaining_weight"] < item.weight:
                    continue
                cont = c_info["container"]
                s_index = c_info["index"]

                ors = generate_orientations(item, c_info)

                for (lx, ly, lh) in ors:
                    if lx > cont.length + 1e-2 or ly > cont.width + 1e-2 or lh > cont.height + 1e-2:
                        continue

                    current_x = 0.0
                    while (current_x + lx <= cont.length + 1e-2) and not placed:
                        # PHASE A: floor
                        floor_placed = False
                        y_coord = 0.0
                        while y_coord + ly <= cont.width + 1e-2 and not floor_placed and not placed:
                            base_z = s_index.get_base_z(current_x, y_coord, lx, ly)
                            if base_z < 1e-2:
                                if can_stack(base_z, item, lh, cont.height):
                                    new_top = base_z + lh
                                    packed_item = PackedItem(
                                        sku=item.sku,
                                        position=(current_x, y_coord, base_z),
                                        size=(lx, ly, lh),
                                        rotation=calculate_rotation(item, (lx, ly, lh)),
                                        container_id=cont.container_id,
                                        weight=item.weight,
                                        quantity=1,
                                        europallet=item.europallet,
                                        contained_items=[]
                                    )
                                    c_info["packed_items"].append(packed_item)
                                    c_info["remaining_weight"] -= item.weight
                                    s_index.update_surface(current_x, y_coord, lx, ly, new_top)
                                    packed_count += 1
                                    floor_placed = True
                                    placed = True

                                    if is_pallet(item):
                                        increment_pallet_pattern(c_info)

                            y_coord += step_size

                        # PHASE B: stacking
                        if not placed:
                            y_coord = 0.0
                            while y_coord + ly <= cont.width + 1e-2 and not placed:
                                base_z = s_index.get_base_z(current_x, y_coord, lx, ly)
                                if base_z >= 1e-2:
                                    if can_stack(base_z, item, lh, cont.height):
                                        if is_stable_placement(s_index, current_x, y_coord, lx, ly, fraction=1.0):
                                            new_top = base_z + lh
                                            packed_item = PackedItem(
                                                sku=item.sku,
                                                position=(current_x, y_coord, base_z),
                                                size=(lx, ly, lh),
                                                rotation=calculate_rotation(item, (lx, ly, lh)),
                                                container_id=cont.container_id,
                                                weight=item.weight,
                                                quantity=1,
                                                europallet=item.europallet,
                                                contained_items=[]
                                            )
                                            c_info["packed_items"].append(packed_item)
                                            c_info["remaining_weight"] -= item.weight
                                            s_index.update_surface(current_x, y_coord, lx, ly, new_top)
                                            packed_count += 1
                                            placed = True

                                            if is_pallet(item):
                                                increment_pallet_pattern(c_info)
                                y_coord += step_size

                        current_x += step_size
                    if placed:
                        break
                if placed:
                    break

            if not placed:
                new_id = max(ci["container"].container_id for ci in container_info) + 1
                last_c = container_info[-1]["container"]
                new_container = Container(
                    length=last_c.length,
                    width=last_c.width,
                    height=last_c.height,
                    max_weight=last_c.max_weight,
                    container_id=new_id,
                    container_type=last_c.container_type
                )
                new_index = SpatialIndex2D(new_container.length, new_container.width, step_size)
                container_info.append({
                    "container": new_container,
                    "index": new_index,
                    "remaining_weight": new_container.max_weight,
                    "packed_items": [],
                    "pallet_pattern_phase": "A",
                    "pallet_pattern_count": 0
                })

                c_info_new = container_info[-1]
                cont = c_info_new["container"]
                s_index = c_info_new["index"]
                ors = generate_orientations(item, c_info_new)

                new_placed = False
                for (lx, ly, lh) in ors:
                    if (lx <= cont.length + 1e-2
                        and ly <= cont.width + 1e-2
                        and lh <= cont.height + 1e-2
                        and item.weight <= c_info_new["remaining_weight"]):
                        base_z = 0.0
                        if can_stack(base_z, item, lh, cont.height):
                            new_top = base_z + lh
                            packed_item = PackedItem(
                                sku=item.sku,
                                position=(0.0, 0.0, base_z),
                                size=(lx, ly, lh),
                                rotation=calculate_rotation(item, (lx, ly, lh)),
                                container_id=cont.container_id,
                                weight=item.weight,
                                quantity=1,
                                europallet=item.europallet,
                                contained_items=[]
                            )
                            c_info_new["packed_items"].append(packed_item)
                            c_info_new["remaining_weight"] -= item.weight
                            s_index.update_surface(0.0, 0.0, lx, ly, new_top)
                            packed_count += 1
                            report_progress(packed_count)
                            new_placed = True

                            if is_pallet(item):
                                increment_pallet_pattern(c_info_new)
                            break
                placed = new_placed

            idx_left += 1

        for c_info in container_info:
            if c_info["packed_items"]:
                pc = PackedContainer(
                    container_id=c_info["container"].container_id,
                    container=c_info["container"],
                    packed_items=c_info["packed_items"]
                )
                packed_results.append(pc)

        report_progress(packed_count)
        return packed_results

    # Main dispatch
    if packing_method == "vertical_loading":
        return vertical_loading_algorithm_stack(items, containers)
    else:
        return floor_loading_algorithm_human_friendly(items, containers)
