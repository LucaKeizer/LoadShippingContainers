# tests/test_data_manager.py

import pytest
from unittest.mock import MagicMock, patch, mock_open
from src.data_io.data_manager import DataManager
from src.models.models import Item, Container
import pandas as pd
import tempfile
import os

# Sample data for carton dimensions
SAMPLE_CARTON_DIMENSIONS = {
    'Product Code': ['SKU1', 'SKU2'],
    'Length': [100.0, 120.0],
    'Width': [50.0, 60.0],
    'Height': [75.0, 80.0],
    'QTY Per Carton': [10, 20]
}

# Sample data for product data
SAMPLE_PRODUCT_DATA = {
    'ProductCode': ['SKU1', 'SKU2'],
    'Category': ['S7', 'A1'],
    'Total length (L) [mm]': [1000, 1200],
    'Width (W) [mm]': [500, 600],
    'Height (H) [mm]': [750, 800],
    'Weight [g]': [20500, 25000],
    'Rotatable': ['YES', 'NO'],
    'Stackable': ['NO', 'YES']
}

@pytest.fixture
def data_manager():
    """Fixture to create a DataManager instance."""
    return DataManager()

@pytest.fixture
def carton_dimensions_file():
    """Fixture to create a temporary Excel file for carton dimensions."""
    df = pd.DataFrame(SAMPLE_CARTON_DIMENSIONS)
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.xlsx', delete=False) as tmp:
        df.to_excel(tmp.name, index=False)
        yield tmp.name
    os.unlink(tmp.name)

@pytest.fixture
def product_data_file():
    """Fixture to create a temporary Excel file for product data."""
    df = pd.DataFrame(SAMPLE_PRODUCT_DATA)
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.xlsx', delete=False) as tmp:
        df.to_excel(tmp.name, index=False)
        yield tmp.name
    os.unlink(tmp.name)

def test_load_carton_dimensions(data_manager, carton_dimensions_file):
    """Test loading carton dimensions from an Excel file."""
    with patch('PyQt5.QtWidgets.QMessageBox.critical') as mock_critical:
        data_manager.load_carton_dimensions(carton_dimensions_file)
        assert not mock_critical.called
        assert not data_manager.carton_dimensions_df.empty
        assert len(data_manager.carton_dimensions_df) == 2
        assert list(data_manager.carton_dimensions_df['Product Code']) == ['SKU1', 'SKU2']

def test_load_carton_dimensions_file_not_found(data_manager):
    """Test loading carton dimensions with a non-existent file."""
    with patch('PyQt5.QtWidgets.QMessageBox.critical') as mock_critical:
        data_manager.load_carton_dimensions('non_existent_file.xlsx')
        mock_critical.assert_called_once()
        assert data_manager.carton_dimensions_df.empty

def test_load_product_data(data_manager, product_data_file):
    """Test loading product data from an Excel file."""
    with patch('PyQt5.QtWidgets.QMessageBox.warning') as mock_warning:
        data_manager.load_product_data(product_data_file)
        assert not mock_warning.called
        assert hasattr(data_manager, 'product_data_df')
        assert not data_manager.product_data_df.empty
        assert len(data_manager.product_data_df) == 2
        assert list(data_manager.product_data_df['ProductCode']) == ['SKU1', 'SKU2']

def test_load_product_data_file_not_found(data_manager):
    """Test loading product data with a non-existent file."""
    with patch('PyQt5.QtWidgets.QMessageBox.warning') as mock_warning:
        data_manager.load_product_data('non_existent_product.xlsx')
        mock_warning.assert_called_once_with(None, "File Not Found", "Could not find the file: non_existent_product.xlsx")
        assert not hasattr(data_manager, 'product_data_df')

def test_get_product_codes(data_manager, product_data_file, carton_dimensions_file):
    """Test retrieving product codes."""
    data_manager.load_product_data(product_data_file)
    product_codes = data_manager.get_product_codes()
    assert product_codes == ['SKU1', 'SKU2']

def test_get_dimensions_for_product_code(data_manager, product_data_file, carton_dimensions_file):
    """Test retrieving dimensions for a specific product code."""
    data_manager.load_product_data(product_data_file)
    dimensions = data_manager.get_dimensions_for_product_code('SKU1')
    assert dimensions == {
        'length': 100.0,
        'width': 50.0,
        'height': 75.0,
        'weight': 20.5,
        'rotatable': 'YES',
        'stackable': 'NO'
    }
    # Test non-existent product code
    dimensions_none = data_manager.get_dimensions_for_product_code('SKU3')
    assert dimensions_none is None

def test_get_items_per_pallet(data_manager, product_data_file):
    """Test retrieving items per pallet based on SKU."""
    data_manager.load_product_data(product_data_file)
    assert data_manager.get_items_per_pallet('SKU1') == 2  # Category 'S7'
    assert data_manager.get_items_per_pallet('SKU2') is None  # Category 'A1'
    assert data_manager.get_items_per_pallet('SKU3') is None  # Non-existent SKU

def test_get_base_sku(data_manager):
    """Test extracting base SKU."""
    assert data_manager.get_base_sku('1234-SKU1') == 'SKU1'
    assert data_manager.get_base_sku('SKU2') == 'SKU2'
    assert data_manager.get_base_sku('5678-SKU3') == 'SKU3'

def test_generate_color_for_sku(data_manager):
    """Test generating unique colors for SKUs, avoiding yellow hues."""
    color1 = data_manager.generate_color_for_sku('SKU1')
    color2 = data_manager.generate_color_for_sku('SKU2')
    assert color1 != color2  # Ensure colors are unique
    # Ensure hues are not within the exclusion range (45° to 75°)
    hue1 = color1[0] * 360  # Convert normalized hue back to degrees
    hue2 = color2[0] * 360
    assert not (45 <= hue1 <= 75)
    assert not (45 <= hue2 <= 75)
    # Re-generating color for existing SKU should return the same color
    assert data_manager.generate_color_for_sku('SKU1') == color1

def test_calculate_cartons(data_manager):
    """Test calculating the number of cartons needed."""
    assert data_manager.calculate_cartons(25, 10) == 3
    assert data_manager.calculate_cartons(20, 20) == 1
    assert data_manager.calculate_cartons(0, 10) == 0
    assert data_manager.calculate_cartons(15, 0) == 0  # Avoid division by zero

def test_get_qty_per_carton(data_manager, carton_dimensions_file):
    """Test retrieving QTY Per Carton for a SKU."""
    data_manager.load_carton_dimensions(carton_dimensions_file)
    assert data_manager.get_qty_per_carton('SKU1') == 10
    assert data_manager.get_qty_per_carton('SKU2') == 20
    assert data_manager.get_qty_per_carton('SKU3') == 120  # Default value

def test_update_item_carton_dimensions_with_matching_sku(data_manager, carton_dimensions_file):
    """Test updating item carton dimensions when SKU matches."""
    data_manager.load_carton_dimensions(carton_dimensions_file)
    item = Item(
        sku='SKU1',
        length=0.0,
        width=0.0,
        height=0.0,
        weight=0.0,
        quantity=10,
        stackable=False,
        rotatable=False
    )
    data_manager.update_item_carton_dimensions(item)
    assert item.length == 100.0
    assert item.width == 50.0
    assert item.height == 75.0
    assert item.cartons == 1  # 10 / 10 = 1

def test_update_item_carton_dimensions_with_non_matching_sku(data_manager, carton_dimensions_file):
    """Test updating item carton dimensions when SKU does not match."""
    data_manager.load_carton_dimensions(carton_dimensions_file)
    item = Item(
        sku='SKU3',
        length=0.0,
        width=0.0,
        height=0.0,
        weight=0.0,
        quantity=240,
        stackable=True,
        rotatable=True
    )
    with patch('PyQt5.QtWidgets.QMessageBox') as mock_msg:
        data_manager.update_item_carton_dimensions(item)
        # Since SKU3 is not in carton_dimensions_df, default dimensions should be set
        assert item.length == 42.0
        assert item.width == 57.0
        assert item.height == 23.0
        assert item.cartons == math.ceil(240 / 120)  # 2

def test_create_item(data_manager):
    """Test creating a new Item."""
    item = data_manager.create_item(
        sku='SKU4',
        length=110.0,
        width=55.0,
        height=80.0,
        weight=22.5,
        quantity=15,
        stackable=True,
        rotatable=False,
        europallet=False,
        mixed_pallet=''
    )
    assert isinstance(item, Item)
    assert item.sku == 'SKU4'
    assert item.length == 110.0
    assert item.width == 55.0
    assert item.height == 80.0
    assert item.weight == 22.5
    assert item.quantity == 15
    assert item.stackable is True
    assert item.rotatable is False
    assert item.europallet is False
    assert item.mixed_pallet == ''

def test_create_carton_item(data_manager, carton_dimensions_file):
    """Test creating a carton item."""
    data_manager.load_carton_dimensions(carton_dimensions_file)
    item = data_manager.create_carton_item(
        sku='SKU1',
        length=0.0,
        width=0.0,
        height=0.0,
        weight=0.0,
        quantity=25,
        stackable=False,
        rotatable=True,
        cartons=3
    )
    assert item.cartons == 3
    assert item.length == 100.0
    assert item.width == 50.0
    assert item.height == 75.0
    assert item.quantity == 25

def test_create_europallet_item(data_manager):
    """Test creating a europallet item."""
    data_manager.margin_percentage = 10  # 1 + 10/100 = 1.1
    item = data_manager.create_europallet_item(
        sku='SKU5',
        weight=30.0,
        stackable=True,
        rotatable=False,
        europallet_quantity=5
    )
    assert item.sku == 'SKU5'
    assert math.isclose(item.length, 88.0)  # 80 * 1.1
    assert math.isclose(item.width, 132.0)  # 120 * 1.1
    assert math.isclose(item.height, 55.0)  # 50 * 1.1
    assert math.isclose(item.weight, (30.0 + 25.0) / 5)  # (30 + 25) / 5 = 11.0
    assert item.quantity == 5
    assert item.europallet is True
    assert item.stackable is True
    assert item.rotatable is False

def test_create_mixed_pallet_item(data_manager):
    """Test creating a mixed pallet item."""
    item = data_manager.create_mixed_pallet_item(
        mixed_pallet='MP004',
        total_weight=150.0,
        stackable=True,
        rotatable=True
    )
    assert item.sku == 'MIXED-MP004'
    assert math.isclose(item.length, 132.0)  # 120 * (1 + 0/100) assuming margin_percentage=0
    assert math.isclose(item.width, 80.0)
    assert math.isclose(item.height, 50.0)
    assert math.isclose(item.weight, 150.0 + 25.0)  # 175.0
    assert item.quantity == 1
    assert item.mixed_pallet == 'MP004'
    assert item.stackable is True
    assert item.rotatable is True
    assert item.europallet is False

def test_generate_color_unique(data_manager):
    """Test that generated colors are unique and not yellow."""
    color1 = data_manager.generate_color_for_sku('SKU6')
    color2 = data_manager.generate_color_for_sku('SKU7')
    assert color1 != color2
    hue1 = color1[0] * 360
    hue2 = color2[0] * 360
    assert not (45 <= hue1 <= 75), "Hue1 is within the exclusion range for yellow."
    assert not (45 <= hue2 <= 75), "Hue2 is within the exclusion range for yellow."

def test_generate_color_existing(data_manager):
    """Test that generating color for existing SKU returns the same color."""
    color1 = data_manager.generate_color_for_sku('SKU8')
    color2 = data_manager.generate_color_for_sku('SKU8')
    assert color1 == color2

def test_generate_color_max_attempts(data_manager):
    """Test color generation fallback after max attempts."""
    with patch('src.data_io.data_manager.colorsys.hsv_to_rgb', return_value=(1, 1, 1)):
        # Manually set current_hue to avoid the exclusion range and ensure distinctness
        data_manager.current_hue = 0
        data_manager.assigned_hues = [i for i in range(0, 360, 10)]  # Fill hues to trigger max_attempts
        color = data_manager.generate_color_for_sku('SKU9')
        # Since the hues are filled, it should fallback to a random color
        assert color == (1, 1, 1, 0.6)

def test_update_item_carton_dimensions_no_carton_data(data_manager):
    """Test updating item carton dimensions when carton_dimensions_df is empty."""
    item = Item(
        sku='SKU10',
        length=0.0,
        width=0.0,
        height=0.0,
        weight=0.0,
        quantity=240,
        stackable=True,
        rotatable=True
    )
    data_manager.update_item_carton_dimensions(item)
    assert item.length == 42.0
    assert item.width == 57.0
    assert item.height == 23.0
    assert item.cartons == math.ceil(240 / 120)  # 2
