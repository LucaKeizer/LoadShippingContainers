# models.py

# Standard Library Imports
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class Item:
    """
    Represents an item to be packed, which can optionally contain other items (e.g., in combined pallets).
    """
    sku: str
    length: float  # in cm
    width: float   # in cm
    height: float  # in cm
    weight: float  # in kg
    quantity: int
    stackable: bool
    rotatable: bool
    europallet: bool = False
    mixed_pallet: str = ""
    cartons: int = 0
    transport_order: str = ""
    items_per_pallet: Optional[int] = field(default=None)
    has_carton_issue: bool = False
    has_remainder_issue: bool = False
    has_missing_dimension_issue: bool = False
    contained_items: List['Item'] = field(default_factory=list)  # Nested items for combined pallets
    original_quantity: int = None  # Store original quantity before carton conversion
    is_carton_item: bool = False   # Flag to mark an item that has been converted to a carton

    def to_dict(self) -> dict:
        """Serializes the Item instance to a dictionary, including nested contained_items."""
        return {
            "sku": self.sku,
            "length": self.length,
            "width": self.width,
            "height": self.height,
            "weight": self.weight,
            "quantity": self.quantity,
            "stackable": self.stackable,
            "rotatable": self.rotatable,
            "europallet": self.europallet,
            "mixed_pallet": self.mixed_pallet,
            "cartons": self.cartons,
            "transport_order": self.transport_order,
            "items_per_pallet": self.items_per_pallet,
            "has_carton_issue": self.has_carton_issue,
            "has_remainder_issue": self.has_remainder_issue,
            "has_missing_dimension_issue": self.has_missing_dimension_issue,
            "contained_items": [item.to_dict() for item in self.contained_items],  # Serialize nested items
            "original_quantity": self.original_quantity,
            "is_carton_item": self.is_carton_item
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Item':
        """Deserializes a dictionary to an Item instance, including nested contained_items."""
        item = cls(
            sku=data["sku"],
            length=data["length"],
            width=data["width"],
            height=data["height"],
            weight=data["weight"],
            quantity=data["quantity"],
            stackable=data["stackable"],
            rotatable=data["rotatable"],
            europallet=data.get("europallet", False),
            mixed_pallet=data.get("mixed_pallet", ""),
            cartons=data.get("cartons", 0),
            transport_order=data.get("transport_order", ""),
            items_per_pallet=data.get("items_per_pallet"),
            has_carton_issue=data.get("has_carton_issue", False),
            has_remainder_issue=data.get("has_remainder_issue", False),
            has_missing_dimension_issue=data.get("has_missing_dimension_issue", False),
            original_quantity=data.get("original_quantity"),
            is_carton_item=data.get("is_carton_item", False)
        )
        # Deserialize contained_items recursively
        contained_items_data = data.get("contained_items", [])
        for contained_item_data in contained_items_data:
            contained_item = cls.from_dict(contained_item_data)
            item.contained_items.append(contained_item)
        return item


@dataclass
class Container:
    """
    Represents a container in which items are packed.
    """
    length: float  # in cm
    width: float   # in cm
    height: float  # in cm
    max_weight: float  # in kg
    container_id: int = 0  # Unique identifier for the container
    container_type: str = "Custom"  # Type or name of the container

    def to_dict(self) -> dict:
        """Serializes the Container instance to a dictionary."""
        return {
            "length": self.length,
            "width": self.width,
            "height": self.height,
            "max_weight": self.max_weight,
            "container_id": self.container_id,
            "container_type": self.container_type
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Container':
        """Deserializes a dictionary to a Container instance."""
        return cls(
            length=data["length"],
            width=data["width"],
            height=data["height"],
            max_weight=data["max_weight"],
            container_id=data.get("container_id", 0),
            container_type=data.get("container_type", "Custom")
        )


@dataclass
class PackedItem:
    """
    Represents an item that has been packed into a container, including its position and rotation.
    """
    sku: str
    position: Tuple[float, float, float]  # (x, y, z) in cm
    size: Tuple[float, float, float]      # (length, width, height) in cm
    rotation: Tuple[int, int, int]        # (rot_x, rot_y, rot_z) in degrees
    container_id: int                     # ID of the container this item is packed in
    weight: float                         # weight in kg
    quantity: int = 1                     # Number of such items packed
    europallet: bool = False              # Indicates if the item is on a Europallet
    contained_items: List['PackedItem'] = field(default_factory=list)  # For Europallets

    def to_dict(self) -> dict:
        """Serializes the PackedItem instance to a dictionary."""
        return {
            "sku": self.sku,
            "position": self.position,
            "size": self.size,
            "rotation": self.rotation,
            "container_id": self.container_id,
            "weight": self.weight,
            "quantity": self.quantity,
            "europallet": self.europallet,
            "contained_items": [item.to_dict() for item in self.contained_items]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PackedItem':
        """Deserializes a dictionary to a PackedItem instance."""
        return cls(
            sku=data["sku"],
            position=tuple(data["position"]),
            size=tuple(data["size"]),
            rotation=tuple(data["rotation"]),
            container_id=data["container_id"],
            weight=data["weight"],
            quantity=data.get("quantity", 1),
            europallet=data.get("europallet", False),
            contained_items=[cls.from_dict(item) for item in data.get("contained_items", [])]
        )

@dataclass
class PackedContainer:
    """
    Represents a container with packed items.
    """
    container_id: int
    container: Container
    packed_items: List[PackedItem]

    def to_dict(self) -> dict:
        """Serializes the PackedContainer instance to a dictionary."""
        return {
            "container_id": self.container_id,
            "container": self.container.to_dict(),
            "packed_items": [item.to_dict() for item in self.packed_items]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PackedContainer':
        """Deserializes a dictionary to a PackedContainer instance."""
        container = Container.from_dict(data["container"])
        packed_items = [PackedItem.from_dict(item) for item in data["packed_items"]]
        return cls(
            container_id=data["container_id"],
            container=container,
            packed_items=packed_items
        )
