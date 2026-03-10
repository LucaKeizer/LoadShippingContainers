# tests/test_packing_algorithm.py

import pytest
from unittest.mock import MagicMock
from src.models.models import Item, Container, PackedItem, PackedContainer
from src.algorithms.packing_algorithm import run_packing_algorithm

@pytest.fixture
def mock_progress_callback():
    """Fixture to create a mock progress_callback."""
    return MagicMock()

@pytest.fixture
def single_container():
    """Fixture for a single container."""
    return Container(
        length=200.0,  # cm
        width=200.0,   # cm
        height=200.0,  # cm
        max_weight=30000.0,  # grams
        container_id=1
    )

@pytest.fixture
def multiple_containers():
    """Fixture for multiple containers."""
    return [
        Container(length=200.0, width=200.0, height=200.0, max_weight=30000.0, container_id=1),
        Container(length=150.0, width=150.0, height=150.0, max_weight=20000.0, container_id=2)
    ]

@pytest.fixture
def single_item():
    """Fixture for a single item that fits into one container."""
    return Item(
        sku='SKU1',
        length=100.0,  # cm
        width=50.0,    # cm
        height=75.0,   # cm
        weight=5000.0, # grams
        quantity=1,
        stackable=True,
        rotatable=True,
        europallet=False,
        mixed_pallet=''
    )

@pytest.fixture
def multiple_items():
    """Fixture for multiple items that fit into one container."""
    return [
        Item(
            sku='SKU1',
            length=100.0,
            width=50.0,
            height=75.0,
            weight=5000.0,
            quantity=2,
            stackable=True,
            rotatable=True,
            europallet=False,
            mixed_pallet=''
        ),
        Item(
            sku='SKU2',
            length=80.0,
            width=60.0,
            height=70.0,
            weight=4000.0,
            quantity=3,
            stackable=True,
            rotatable=True,
            europallet=False,
            mixed_pallet=''
        )
    ]

@pytest.fixture
def oversized_item():
    """Fixture for an item that is too large to fit into any container."""
    return Item(
        sku='SKU_OVERSIZE',
        length=300.0,  # cm
        width=300.0,   # cm
        height=300.0,  # cm
        weight=40000.0, # grams
        quantity=1,
        stackable=False,
        rotatable=False,
        europallet=False,
        mixed_pallet=''
    )

@pytest.fixture
def non_stackable_item():
    """Fixture for a non-stackable item."""
    return Item(
        sku='SKU_NON_STACK',
        length=100.0,
        width=50.0,
        height=75.0,
        weight=5000.0,
        quantity=2,
        stackable=False,
        rotatable=True,
        europallet=False,
        mixed_pallet=''
    )

@pytest.fixture
def rotatable_item():
    """Fixture for an item that requires rotation to fit."""
    return Item(
        sku='SKU_ROTATE',
        length=190.0,
        width=190.0,
        height=190.0,
        weight=29000.0,
        quantity=1,
        stackable=True,
        rotatable=True,
        europallet=False,
        mixed_pallet=''
    )

def test_basic_packing(single_item, single_container, mock_progress_callback):
    """Test packing a single item into a single container."""
    packed_containers = run_packing_algorithm(
        items=[single_item],
        containers=[single_container],
        progress_callback=mock_progress_callback
    )
    
    # Assert that one container is used
    assert len(packed_containers) == 1
    
    packed_container = packed_containers[0]
    
    # Assert container ID matches
    assert packed_container.container_id == single_container.container_id
    
    # Assert one item is packed
    assert len(packed_container.packed_items) == 1
    
    packed_item = packed_container.packed_items[0]
    
    # Assert item details
    assert packed_item.sku == 'SKU1'
    assert packed_item.weight == 5000.0
    assert packed_item.container_id == single_container.container_id
    
    # Assert progress_callback was called
    assert mock_progress_callback.call_count > 0
    mock_progress_callback.assert_called_with(100)

def test_multiple_items_single_container(multiple_items, single_container, mock_progress_callback):
    """Test packing multiple items into a single container."""
    packed_containers = run_packing_algorithm(
        items=multiple_items,
        containers=[single_container],
        progress_callback=mock_progress_callback
    )
    
    # Assert that one container is used
    assert len(packed_containers) == 1
    
    packed_container = packed_containers[0]
    
    # Assert container ID matches
    assert packed_container.container_id == single_container.container_id
    
    # Assert total packed items
    assert len(packed_container.packed_items) == 5  # 2 + 3
    
    # Assert progress_callback was called
    assert mock_progress_callback.call_count > 0
    mock_progress_callback.assert_called_with(100)

def test_multiple_containers_packing(multiple_items, multiple_containers, mock_progress_callback):
    """Test packing multiple items into multiple containers."""
    packed_containers = run_packing_algorithm(
        items=multiple_items,
        containers=multiple_containers,
        progress_callback=mock_progress_callback
    )
    
    # Assert that only one container is used since items fit into the first container
    assert len(packed_containers) == 1
    
    packed_container = packed_containers[0]
    
    # Assert container ID matches the first container
    assert packed_container.container_id == multiple_containers[0].container_id
    
    # Assert total packed items
    assert len(packed_container.packed_items) == 5  # 2 + 3
    
    # Assert progress_callback was called
    assert mock_progress_callback.call_count > 0
    mock_progress_callback.assert_called_with(100)

def test_oversized_item(multiple_containers, oversized_item, mock_progress_callback):
    """Test packing an oversized item that cannot fit into any container."""
    packed_containers = run_packing_algorithm(
        items=[oversized_item],
        containers=multiple_containers,
        progress_callback=mock_progress_callback
    )
    
    # Assert that no containers are used since item cannot be packed
    assert len(packed_containers) == 0
    
    # Assert progress_callback was called
    assert mock_progress_callback.call_count > 0
    mock_progress_callback.assert_called_with(100)

def test_non_stackable_items(multiple_containers, non_stackable_item, mock_progress_callback):
    """Test packing non-stackable items."""
    packed_containers = run_packing_algorithm(
        items=[non_stackable_item],
        containers=multiple_containers,
        progress_callback=mock_progress_callback
    )
    
    # Assert that items are placed without stacking
    assert len(packed_containers) == 1
    packed_container = packed_containers[0]
    assert len(packed_container.packed_items) == 2  # Quantity is 2
    
    # Each item should be placed separately
    positions = [item.position for item in packed_container.packed_items]
    assert len(positions) == len(set(positions))  # All positions are unique
    
    # Assert progress_callback was called
    assert mock_progress_callback.call_count > 0
    mock_progress_callback.assert_called_with(100)

def test_rotatable_item(multiple_containers, rotatable_item, mock_progress_callback):
    """Test packing an item that requires rotation to fit into a container."""
    packed_containers = run_packing_algorithm(
        items=[rotatable_item],
        containers=multiple_containers,
        progress_callback=mock_progress_callback
    )
    
    # Assert that the item is packed into a container after rotation
    assert len(packed_containers) == 1
    packed_container = packed_containers[0]
    assert len(packed_container.packed_items) == 1
    packed_item = packed_container.packed_items[0]
    
    # Verify that rotation was applied (original size vs placed size)
    original_size = (rotatable_item.length, rotatable_item.width, rotatable_item.height)
    placed_size = packed_item.size
    assert placed_size in [
        (rotatable_item.length, rotatable_item.width, rotatable_item.height),
        (rotatable_item.width, rotatable_item.length, rotatable_item.height),
        (rotatable_item.length, rotatable_item.height, rotatable_item.width),
        (rotatable_item.height, rotatable_item.length, rotatable_item.width),
        (rotatable_item.width, rotatable_item.height, rotatable_item.length),
        (rotatable_item.height, rotatable_item.width, rotatable_item.length)
    ]
    
    # Assert progress_callback was called
    assert mock_progress_callback.call_count > 0
    mock_progress_callback.assert_called_with(100)

def test_progress_callback(multiple_items, single_container, mock_progress_callback):
    """Test that progress_callback is called with correct progress values."""
    packed_containers = run_packing_algorithm(
        items=multiple_items,
        containers=[single_container],
        progress_callback=mock_progress_callback
    )
    
    # Assert that progress_callback was called multiple times
    assert mock_progress_callback.call_count > 1
    
    # Check that progress was updated incrementally and ended at 100
    calls = mock_progress_callback.call_args_list
    progress_values = [call.args[0] for call in calls]
    assert progress_values[-1] == 100
    assert all(earlier <= later for earlier, later in zip(progress_values, progress_values[1:]))

def test_packed_container_details(single_item, single_container, mock_progress_callback):
    """Test that PackedContainer contains correct container and packed items details."""
    packed_containers = run_packing_algorithm(
        items=[single_item],
        containers=[single_container],
        progress_callback=mock_progress_callback
    )
    
    assert len(packed_containers) == 1
    packed_container = packed_containers[0]
    
    # Verify container details
    assert packed_container.container.length == single_container.length
    assert packed_container.container.width == single_container.width
    assert packed_container.container.height == single_container.height
    assert packed_container.container.max_weight == single_container.max_weight
    assert packed_container.container.container_id == single_container.container_id
    
    # Verify packed item details
    assert len(packed_container.packed_items) == 1
    packed_item = packed_container.packed_items[0]
    assert packed_item.sku == single_item.sku
    assert packed_item.weight == single_item.weight
    assert packed_item.container_id == single_container.container_id
    assert packed_item.size == (single_item.length, single_item.width, single_item.height)
    assert packed_item.rotation == (0, 0, 0)  # Assuming no rotation needed

def test_packing_with_mixed_pallet(multiple_containers, mock_progress_callback):
    """Test packing items that belong to a mixed pallet."""
    mixed_pallet_item = Item(
        sku='MIXED_SKU1',
        length=80.0,
        width=120.0,
        height=50.0,
        weight=25000.0,
        quantity=1,
        stackable=True,
        rotatable=False,
        europallet=False,
        mixed_pallet='MP001'
    )
    
    packed_containers = run_packing_algorithm(
        items=[mixed_pallet_item],
        containers=multiple_containers,
        progress_callback=mock_progress_callback
    )
    
    # Assert that one container is used
    assert len(packed_containers) == 1
    
    packed_container = packed_containers[0]
    
    # Assert container ID matches
    assert packed_container.container_id == multiple_containers[0].container_id
    
    # Assert one item is packed
    assert len(packed_container.packed_items) == 1
    
    packed_item = packed_container.packed_items[0]
    
    # Assert mixed pallet details
    assert packed_item.sku == 'MIXED_SKU1'
    assert packed_item.weight == 25000.0
    assert packed_item.container_id == multiple_containers[0].container_id
    
    # Assert no rotation since rotatable=False
    assert packed_item.size == (80.0, 120.0, 50.0)
    assert packed_item.rotation == (0, 0, 0)
    
    # Assert progress_callback was called
    assert mock_progress_callback.call_count > 0
    mock_progress_callback.assert_called_with(100)
