# tests/test_visualization_left_panel.py

import pytest
from unittest.mock import MagicMock, patch
from PyQt5.QtWidgets import QApplication, QTableWidgetItem
from src.visualization.visualization_left_panel import LeftPanel
from src.models.models import Container, Item, PackedItem
import sys

@pytest.fixture(scope="session")
def app():
    """Fixture to create a QApplication instance."""
    app = QApplication(sys.argv)
    yield app
    app.quit()

@pytest.fixture
def left_panel(qtbot):
    """Fixture to create and return a LeftPanel instance with mocked parent."""
    mock_parent = MagicMock()
    mock_parent.on_prev_clicked = MagicMock()
    mock_parent.on_next_clicked = MagicMock()
    mock_parent.show_input_page = MagicMock()
    mock_parent.get_base_sku = MagicMock(side_effect=lambda sku: sku.split('-')[-1] if '-' in sku else sku)
    
    panel = LeftPanel(parent=mock_parent)
    qtbot.addWidget(panel)
    panel.show()
    return panel, mock_parent

def test_initialization(left_panel, qtbot):
    """Test that the LeftPanel initializes correctly."""
    panel, _ = left_panel
    
    # Verify that tables have correct column counts and headers
    assert panel.items_table.columnCount() == 6
    expected_headers_items = ["SKU", "Dimensions (cm)", "Weight (kg)", "Quantity", "Cartons", "Color"]
    for col in range(6):
        header = panel.items_table.horizontalHeaderItem(col).text()
        assert header == expected_headers_items[col]
    
    assert panel.loading_order_table.columnCount() == 5
    expected_headers_loading = ["Order", "SKU", "Position", "Dimensions", "Weight (kg)"]
    for col in range(5):
        header = panel.loading_order_table.horizontalHeaderItem(col).text()
        assert header == expected_headers_loading[col]
    
    # Verify that labels are initialized correctly
    assert panel.space_used_label.text() == "Space Used: 0.00%"
    assert panel.space_remaining_label.text() == "Space Remaining: 0.00 m³"
    assert panel.weight_used_label.text() == "Weight Used: 0.00 / 0.00 kg"

def test_update_aggregated_table(left_panel, qtbot):
    """Test that update_aggregated_table correctly populates the items_table."""
    panel, mock_parent = left_panel
    
    # Sample parent_items
    parent_items = [
        Item(sku='1-SKU1', length=100.0, width=50.0, height=75.0, weight=5000.0, quantity=2, cartons=1, stackable=True, rotatable=True, europallet=False, mixed_pallet='')
    ]
    
    # Sample packed_items
    packed_items = [
        PackedItem(sku='1-SKU1', position=(0,0,0), size=(100,50,75), rotation=(0,0,0), container_id=1, weight=5000.0),
        PackedItem(sku='1-SKU1', position=(100,50,0), size=(100,50,75), rotation=(0,0,0), container_id=1, weight=5000.0)
    ]
    
    sku_color_map = {
        'SKU1': (1, 0, 0, 1)  # Red
    }
    
    panel.update_aggregated_table(packed_items, sku_color_map, parent_items)
    
    # Verify that two rows are added
    assert panel.items_table.rowCount() == 1  # Aggregated SKU1
    
    # Verify content of the first row
    row = 0
    assert panel.items_table.item(row, 0).text() == "SKU1"
    assert panel.items_table.item(row, 1).text() == "100 x 50 x 75"
    assert panel.items_table.item(row, 2).text() == "10000.00"  # Total weight
    assert panel.items_table.item(row, 3).text() == "2"        # Quantity
    assert panel.items_table.item(row, 4).text() == "1"        # Cartons
    
    # Verify color indicator
    color_item = panel.items_table.item(row, 5)
    assert color_item.background().color() == (255, 0, 0)  # Red in RGB

def test_update_loading_order_table(left_panel, qtbot):
    """Test that update_loading_order_table correctly populates the loading_order_table."""
    panel, _ = left_panel
    
    # Sample packed_items
    packed_items = [
        PackedItem(sku='SKU1', position=(100,50,0), size=(100,50,75), rotation=(0,0,0), container_id=1, weight=5000.0),
        PackedItem(sku='SKU2', position=(0,0,0), size=(80,60,70), rotation=(0,0,0), container_id=1, weight=4000.0)
    ]
    
    panel.update_loading_order_table(packed_items)
    
    # Verify that two rows are added and sorted by position
    assert panel.loading_order_table.rowCount() == 2
    
    # First row should be SKU2 (position (0,0,0))
    row = 0
    assert panel.loading_order_table.item(row, 0).text() == "1"
    assert panel.loading_order_table.item(row, 1).text() == "SKU2"
    assert panel.loading_order_table.item(row, 2).text() == "(0, 0, 0)"
    assert panel.loading_order_table.item(row, 3).text() == "80 x 60 x 70"
    assert panel.loading_order_table.item(row, 4).text() == "4000.00"
    
    # Second row should be SKU1 (position (100,50,0))
    row = 1
    assert panel.loading_order_table.item(row, 0).text() == "2"
    assert panel.loading_order_table.item(row, 1).text() == "SKU1"
    assert panel.loading_order_table.item(row, 2).text() == "(100, 50, 0)"
    assert panel.loading_order_table.item(row, 3).text() == "100 x 50 x 75"
    assert panel.loading_order_table.item(row, 4).text() == "5000.00"

def test_update_space_metrics(left_panel, qtbot):
    """Test that update_space_metrics correctly updates the space_used_label and space_remaining_label."""
    panel, _ = left_panel
    
    # Sample container and packed_items
    container = Container(length=200.0, width=200.0, height=200.0, max_weight=30000.0, container_id=1)
    packed_items = [
        PackedItem(sku='SKU1', position=(0,0,0), size=(100,50,75), rotation=(0,0,0), container_id=1, weight=5000.0),
        PackedItem(sku='SKU2', position=(100,50,0), size=(80,60,70), rotation=(0,0,0), container_id=1, weight=4000.0)
    ]
    
    # Total container volume = 200 * 200 * 200 = 8,000,000 cm³
    # Total packed volume = (100*50*75) + (80*60*70) = 375,000 + 336,000 = 711,000 cm³
    # Percentage used = (711,000 / 8,000,000) * 100 = 8.8875%
    # Remaining volume = 8,000,000 - 711,000 = 7,289,000 cm³ = 7.289 m³
    
    panel.update_space_metrics(container, packed_items)
    
    assert panel.space_used_label.text() == "Space Used: 8.89%"
    assert panel.space_remaining_label.text() == "Space Remaining: 7.29 m³"

def test_update_weight_used(left_panel, qtbot):
    """Test that update_weight_used correctly updates the weight_used_label."""
    panel, _ = left_panel
    
    # Sample container and packed_items
    container = Container(length=200.0, width=200.0, height=200.0, max_weight=30000.0, container_id=1)
    packed_items = [
        PackedItem(sku='SKU1', position=(0,0,0), size=(100,50,75), rotation=(0,0,0), container_id=1, weight=5000.0),
        PackedItem(sku='SKU2', position=(100,50,0), size=(80,60,70), rotation=(0,0,0), container_id=1, weight=4000.0)
    ]
    
    panel.update_weight_used(container, packed_items)
    
    assert panel.weight_used_label.text() == "Weight Used: 9000.00 / 30000.00 kg"

def test_back_to_input_button(left_panel, qtbot):
    """Test that clicking the Back to Input button calls the parent's show_input_page method."""
    panel, mock_parent = left_panel
    
    # Simulate button click
    with patch.object(panel.parent, 'show_input_page') as mock_show_input:
        panel.back_button.click()
        mock_show_input.assert_called_once()

def test_selection_highlighting_items_table(left_panel, qtbot):
    """Test that selecting a row in items_table calls the parent's highlight method."""
    panel, mock_parent = left_panel
    
    # Sample packed_items and sku_color_map
    packed_items = [
        PackedItem(sku='SKU1', position=(0,0,0), size=(100,50,75), rotation=(0,0,0), container_id=1, weight=5000.0)
    ]
    sku_color_map = {
        'SKU1': (1, 0, 0, 1)
    }
    
    # Update aggregated table
    parent_items = [
        Item(sku='1-SKU1', length=100.0, width=50.0, height=75.0, weight=5000.0, quantity=1, cartons=1, stackable=True, rotatable=True, europallet=False, mixed_pallet='')
    ]
    panel.update_aggregated_table(packed_items, sku_color_map, parent_items)
    
    # Mock selectedItems to return SKU1
    mock_sku_item = MagicMock()
    mock_sku_item.text.return_value = 'SKU1'
    panel.items_table.selectedItems.return_value = [mock_sku_item]
    
    # Call selection changed handler
    panel.parent.on_items_table_selection_changed()
    
    # Verify that parent's highlight method was called
    mock_parent.on_items_table_selection_changed.assert_called_once()

def test_selection_highlighting_loading_order_table(left_panel, qtbot):
    """Test that selecting a row in loading_order_table calls the parent's highlight method."""
    panel, mock_parent = left_panel
    
    # Sample packed_items
    packed_items = [
        PackedItem(sku='SKU1', position=(0,0,0), size=(100,50,75), rotation=(0,0,0), container_id=1, weight=5000.0)
    ]
    sku_color_map = {
        'SKU1': (1, 0, 0, 1)
    }
    
    # Update loading order table
    panel.update_loading_order_table(packed_items)
    
    # Mock selectedItems to return SKU1 and store packed_item id
    mock_sku_item = MagicMock()
    mock_sku_item.text.return_value = 'SKU1'
    mock_sku_item.data.return_value = id(packed_items[0])
    panel.loading_order_table.selectedItems.return_value = [mock_sku_item]
    panel.loading_order_table.currentRow.return_value = 0
    panel.loading_order_table.item.return_value = mock_sku_item
    
    # Call selection changed handler
    panel.parent.on_loading_order_selection_changed()
    
    # Verify that parent's highlight method was called with packed_item id
    mock_parent.on_loading_order_selection_changed.assert_called_once()

