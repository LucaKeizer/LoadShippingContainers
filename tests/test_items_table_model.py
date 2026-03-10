# tests/test_items_table_model.py

import pytest
from unittest.mock import MagicMock, patch
from PyQt5.QtCore import Qt, QModelIndex
from PyQt5.QtWidgets import QMessageBox
from src.gui.items_table_model import ItemsTableModel
from src.data_io.data_manager import DataManager
from src.models.models import Item, Container

import math

# Define a sample Item class with necessary attributes
class SampleItem(Item):
    def __init__(self, sku, length, width, height, weight, quantity, cartons=0, stackable=False, rotatable=False, europallet=False, mixed_pallet=""):
        super().__init__(sku, length, width, height, weight, quantity, cartons, stackable, rotatable, europallet, mixed_pallet)
        self.has_carton_issue = False
        self.has_remainder_issue = False

# Fixture to create a mocked DataManager
@pytest.fixture
def mock_data_manager():
    data_manager = MagicMock(spec=DataManager)
    data_manager.get_qty_per_carton = MagicMock(side_effect=lambda sku: 10 if sku == "SKU1" else 20)
    data_manager.generate_color_for_sku = MagicMock(return_value=(255, 0, 0))  # Example color
    data_manager.update_item_carton_dimensions = MagicMock()
    return data_manager

# Fixture to create sample items
@pytest.fixture
def sample_items():
    return [
        SampleItem(sku="SKU1", length=100.0, width=50.0, height=75.0, weight=20.5, quantity=10, cartons=1, stackable=True, rotatable=False, europallet=True, mixed_pallet="MP001"),
        SampleItem(sku="SKU2", length=120.0, width=60.0, height=80.0, weight=25.0, quantity=20, cartons=2, stackable=False, rotatable=True, europallet=False, mixed_pallet="")
    ]

# Fixture to create the ItemsTableModel
@pytest.fixture
def items_table_model(mock_data_manager, sample_items):
    mixed_pallet_list = ["MP001", "MP002"]
    mixed_pallet_model = MagicMock()
    mixed_pallet_model.setStringList = MagicMock()
    return ItemsTableModel(
        items=sample_items,
        data_manager=mock_data_manager,
        mixed_pallet_list=mixed_pallet_list,
        mixed_pallet_model=mixed_pallet_model
    )

# Test row and column counts
def test_row_column_count(items_table_model, sample_items):
    assert items_table_model.rowCount() == len(sample_items)
    assert items_table_model.columnCount() == len(items_table_model.headers)

# Test data retrieval for DisplayRole
def test_data_display_role(items_table_model, sample_items):
    for row, item in enumerate(sample_items):
        for column, header in enumerate(items_table_model.headers):
            index = items_table_model.index(row, column)
            expected = None
            if header == "Product Code":
                expected = item.sku
            elif header == "Length (cm)":
                expected = str(int(item.length))
            elif header == "Width (cm)":
                expected = str(int(item.width))
            elif header == "Height (cm)":
                expected = str(int(item.height))
            elif header == "Weight (kg)":
                expected = f"{item.weight:.2f}"
            elif header == "Quantity":
                expected = str(item.quantity)
            elif header == "Cartons":
                expected = str(item.cartons)
            elif header == "Mixed Pallet":
                expected = item.mixed_pallet
            elif header == "Stackable":
                expected = "Yes" if item.stackable else "No"
            elif header == "Rotatable":
                expected = "Yes" if item.rotatable else "No"
            elif header == "Europallet":
                expected = "Yes" if item.europallet else "No"
            elif header == "Split":
                expected = "Split"
            elif header == "Delete":
                expected = "Delete"
            elif header == "Issue":
                expected = ""  # Issue column handled by delegate
            assert items_table_model.data(index, Qt.DisplayRole) == expected

# Test data retrieval for TextAlignmentRole
def test_data_alignment_role(items_table_model, sample_items):
    for row in range(items_table_model.rowCount()):
        for column in range(items_table_model.columnCount()):
            index = items_table_model.index(row, column)
            alignment = items_table_model.data(index, Qt.TextAlignmentRole)
            if items_table_model.headers[column] in ["Length (cm)", "Width (cm)", "Height (cm)", "Weight (kg)", "Quantity", "Cartons", "Europallet", "Issue"]:
                assert alignment == Qt.AlignCenter
            else:
                assert alignment is None  # Default alignment

# Test setData for valid inputs
def test_set_data_valid(items_table_model, mock_data_manager):
    # Connect signals to monitor
    items_data_changed = MagicMock()
    carton_quantity_issue = MagicMock()
    split_requested = MagicMock()
    delete_requested = MagicMock()
    
    items_table_model.itemsDataChanged.connect(items_data_changed)
    items_table_model.cartonQuantityIssue.connect(carton_quantity_issue)
    items_table_model.splitRequested.connect(split_requested)
    items_table_model.deleteRequested.connect(delete_requested)
    
    # Update Quantity for SKU1 to trigger carton issue
    index = items_table_model.index(0, items_table_model.headers.index("Quantity"))
    assert items_table_model.setData(index, 15, Qt.EditRole) == True
    assert items_table_model.items[0].quantity == 15
    assert items_table_model.items[0].has_carton_issue == True
    carton_quantity_issue.assert_called_once_with("SKU1", 15, 1, math.ceil(15 / 10))
    items_data_changed.assert_called_once()
    
    # Update Cartons for SKU1 to fix carton issue
    index_cartons = items_table_model.index(0, items_table_model.headers.index("Cartons"))
    assert items_table_model.setData(index_cartons, 2, Qt.EditRole) == True
    assert items_table_model.items[0].cartons == 2
    assert items_table_model.items[0].has_carton_issue == False
    assert items_table_model.items[0].has_remainder_issue == True  # 2 * 10 > 15
    items_data_changed.assert_called_with(index_cartons, index_cartons, [Qt.DisplayRole])
    
    # Update Mixed Pallet to a new value
    index_mixed_pallet = items_table_model.index(0, items_table_model.headers.index("Mixed Pallet"))
    assert items_table_model.setData(index_mixed_pallet, "MP003", Qt.EditRole) == True
    assert items_table_model.items[0].mixed_pallet == "MP003"
    items_table_model.mixed_pallet_model.setStringList.assert_called_with(["MP001", "MP002", "MP003"])
    items_data_changed.assert_called_with(index_mixed_pallet, index_mixed_pallet, [Qt.DisplayRole])

# Test setData for invalid inputs and QMessageBox warnings
def test_set_data_invalid(items_table_model, mock_data_manager):
    with patch('PyQt5.QtWidgets.QMessageBox.warning') as mock_warning:
        # Attempt to set negative Length
        index = items_table_model.index(0, items_table_model.headers.index("Length (cm)"))
        assert items_table_model.setData(index, -50, Qt.EditRole) == False
        mock_warning.assert_called_with(None, "Input Error", "Length must be greater than zero.")
        assert items_table_model.items[0].length == 100.0  # No change
    
    with patch('PyQt5.QtWidgets.QMessageBox.warning') as mock_warning:
        # Attempt to set empty Product Code
        index = items_table_model.index(0, items_table_model.headers.index("Product Code"))
        assert items_table_model.setData(index, "", Qt.EditRole) == False
        mock_warning.assert_called_with(None, "Input Error", "Product Code cannot be empty.")
        assert items_table_model.items[0].sku == "SKU1"  # No change
    
    with patch('PyQt5.QtWidgets.QMessageBox.warning') as mock_warning:
        # Attempt to set invalid Stackable value
        index = items_table_model.index(0, items_table_model.headers.index("Stackable"))
        assert items_table_model.setData(index, "Maybe", Qt.EditRole) == False
        mock_warning.assert_called_with(None, "Input Error", "Stackable must be a version of 'Yes' or 'No'.")
        assert items_table_model.items[0].stackable == True  # No change

# Test splitRequested and deleteRequested signals
def test_split_delete_signals(items_table_model):
    split_requested = MagicMock()
    delete_requested = MagicMock()
    
    items_table_model.splitRequested.connect(split_requested)
    items_table_model.deleteRequested.connect(delete_requested)
    
    # Simulate clicking the Split button
    split_index = items_table_model.index(0, items_table_model.headers.index("Split"))
    assert items_table_model.setData(split_index, "Split", Qt.EditRole) == False  # Buttons do not set data
    split_requested.assert_called_once_with(0)
    
    # Simulate clicking the Delete button
    delete_index = items_table_model.index(0, items_table_model.headers.index("Delete"))
    assert items_table_model.setData(delete_index, "Delete", Qt.EditRole) == False  # Buttons do not set data
    delete_requested.assert_called_once_with(0)

# Test dataChanged signal emission
def test_data_changed_signal(items_table_model, mock_data_manager):
    with patch.object(items_table_model, 'dataChanged', autospec=True) as mock_data_changed:
        index = items_table_model.index(1, items_table_model.headers.index("Weight (kg)"))
        assert items_table_model.setData(index, 30.0, Qt.EditRole) == True
        mock_data_changed.assert_called_once_with(index, index, [Qt.DisplayRole])
        assert items_table_model.items[1].weight == 30.0

# Test Issue column display based on item issues
def test_issue_display(items_table_model, sample_items):
    # Initially, no issues
    for row, item in enumerate(items_table_model.items):
        index = items_table_model.index(row, items_table_model.headers.index("Issue"))
        assert items_table_model.data(index, Qt.DisplayRole) == ""
        assert items_table_model.data(index, Qt.ForegroundRole) is None
    
    # Introduce a carton issue
    items_table_model.items[0].has_carton_issue = True
    index_issue = items_table_model.index(0, items_table_model.headers.index("Issue"))
    assert items_table_model.data(index_issue, Qt.DisplayRole) == ""
    assert items_table_model.data(index_issue, Qt.ForegroundRole).color() == Qt.red
    
    # Introduce a remainder issue
    items_table_model.items[1].has_remainder_issue = True
    index_issue_2 = items_table_model.index(1, items_table_model.headers.index("Issue"))
    assert items_table_model.data(index_issue_2, Qt.DisplayRole) == ""
    assert items_table_model.data(index_issue_2, Qt.ForegroundRole).color() == Qt.orange
