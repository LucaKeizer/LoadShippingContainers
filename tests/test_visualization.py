# tests/test_visualization.py

import pytest
from unittest.mock import MagicMock, patch
from PyQt5.QtWidgets import QApplication, QMessageBox
from src.visualization.visualization import VisualizationPage
from src.models.models import Container, PackedItem
import sys

@pytest.fixture(scope="session")
def app():
    """Fixture to create a QApplication instance."""
    app = QApplication(sys.argv)
    yield app
    app.quit()

@pytest.fixture
def visualization_page(qtbot):
    """Fixture to create and return a VisualizationPage instance with mocked LeftPanel and RightPanel."""
    with patch('src.visualization.visualization.LeftPanel') as MockLeftPanel, \
         patch('src.visualization.visualization.RightPanel') as MockRightPanel:
        
        mock_left_panel = MockLeftPanel.return_value
        mock_right_panel = MockRightPanel.return_value

        # Mock essential methods of LeftPanel
        mock_left_panel.update_aggregated_table = MagicMock()
        mock_left_panel.update_loading_order_table = MagicMock()
        mock_left_panel.update_space_metrics = MagicMock()
        mock_left_panel.update_weight_used = MagicMock()
        mock_left_panel.container_label = MagicMock()
        mock_left_panel.prev_button = MagicMock()
        mock_left_panel.next_button = MagicMock()
        mock_left_panel.items_table = MagicMock()
        mock_left_panel.loading_order_table = MagicMock()

        # Mock essential methods of RightPanel
        mock_right_panel.clear_visualization = MagicMock()
        mock_right_panel.draw_container = MagicMock()
        mock_right_panel.draw_packed_item = MagicMock(return_value=MagicMock())
        mock_right_panel.highlight_packed_item_by_sku = MagicMock()
        mock_right_panel.highlight_packed_item = MagicMock()
        mock_right_panel.reset_highlights = MagicMock()

        # Instantiate the VisualizationPage
        window = VisualizationPage()
        qtbot.addWidget(window)
        window.show()
        return window

def test_initialization(visualization_page, qtbot):
    """Test that the VisualizationPage initializes correctly."""
    window = visualization_page
    assert window.containers == {}
    assert window.containers_packed_items == {}
    assert window.sku_color_map == {}
    assert window.current_container_index == 0
    assert window.total_containers == 0
    assert window.items == []

    # Verify that LeftPanel and RightPanel are added to the layout
    assert window.layout.count() == 2  # LeftPanel and RightPanel
    window.left_panel.setMinimumWidth.assert_called_once_with(400)

def test_display_packed_items(visualization_page, qtbot):
    """Test displaying packed items updates the visualization and side panels correctly."""
    window = visualization_page

    # Create sample data
    containers = {
        1: Container(length=200.0, width=200.0, height=200.0, max_weight=30000.0, container_id=1),
        2: Container(length=150.0, width=150.0, height=150.0, max_weight=20000.0, container_id=2)
    }

    packed_items = [
        PackedItem(sku='SKU1', position=(0,0,0), size=(100,50,75), rotation=(0,0,0), container_id=1, weight=5000),
        PackedItem(sku='SKU2', position=(100,50,0), size=(80,60,70), rotation=(0,0,0), container_id=1, weight=4000),
        PackedItem(sku='SKU3', position=(0,0,0), size=(120,80,50), rotation=(0,0,0), container_id=2, weight=25000)
    ]

    sku_color_map = {
        'SKU1': (1, 0, 0, 1),  # Red
        'SKU2': (0, 1, 0, 1),  # Green
        'SKU3': (0, 0, 1, 1)   # Blue
    }

    # Call display_packed_items
    window.display_packed_items(containers, packed_items, sku_color_map)

    # Verify that clear_visualization is called first
    window.clear_visualization.assert_called_once()

    # Verify that containers and SKU color maps are stored correctly
    assert window.containers == containers
    assert window.sku_color_map == sku_color_map

    # Verify that containers_packed_items are grouped by container_id
    assert window.containers_packed_items == {
        1: packed_items[:2],
        2: packed_items[2:]
    }

    # Verify that total_containers is updated
    assert window.total_containers == 2

    # Verify that current_container_index is reset
    assert window.current_container_index == 0

    # Verify that container_label is updated
    window.left_panel.container_label.setText.assert_called_with("Container 1 of 2")

    # Verify that navigation buttons are updated
    window.update_navigation_buttons.assert_called_once()

    # Verify that RightPanel's draw_container is called for the first container
    window.right_panel.draw_container.assert_called_once_with(containers[1])

    # Verify that draw_packed_item is called for each packed item in the first container
    calls = [
        ((packed_items[0], sku_color_map, containers[1]),),
        ((packed_items[1], sku_color_map, containers[1]),)
    ]
    window.right_panel.draw_packed_item.assert_has_calls([patch.call(*call[0]) for call in calls], any_order=True)

    # Verify that LeftPanel's side panels are updated
    window.left_panel.update_aggregated_table.assert_called_once_with(packed_items[:2], sku_color_map, window.items)
    window.left_panel.update_loading_order_table.assert_called_once_with(packed_items[:2])
    window.left_panel.update_space_metrics.assert_called_once_with(containers[1], packed_items[:2])
    window.left_panel.update_weight_used.assert_called_once_with(containers[1], packed_items[:2])

def test_navigation_buttons(visualization_page, qtbot):
    """Test navigating between containers updates the visualization and labels correctly."""
    window = visualization_page

    # Setup multiple containers and packed items
    containers = {
        1: Container(length=200.0, width=200.0, height=200.0, max_weight=30000.0, container_id=1),
        2: Container(length=150.0, width=150.0, height=150.0, max_weight=20000.0, container_id=2)
    }

    packed_items = [
        PackedItem(sku='SKU1', position=(0,0,0), size=(100,50,75), rotation=(0,0,0), container_id=1, weight=5000),
        PackedItem(sku='SKU2', position=(100,50,0), size=(80,60,70), rotation=(0,0,0), container_id=2, weight=4000)
    ]

    sku_color_map = {
        'SKU1': (1, 0, 0, 1),
        'SKU2': (0, 1, 0, 1)
    }

    # Display packed items
    window.display_packed_items(containers, packed_items, sku_color_map)

    # Simulate clicking 'Next' button to go to the second container
    window.on_next_clicked()
    window.current_container_index = 1
    window.left_panel.container_label.setText.assert_called_with("Container 2 of 2")
    window.update_navigation_buttons.assert_called()
    window.right_panel.draw_container.assert_called_with(containers[2] if 2 in containers else MagicMock())

    # Simulate clicking 'Previous' button to go back to the first container
    window.on_prev_clicked()
    window.current_container_index = 0
    window.left_panel.container_label.setText.assert_called_with("Container 1 of 2")
    window.update_navigation_buttons.assert_called()
    window.right_panel.draw_container.assert_called_with(containers[1])

def test_clear_visualization(visualization_page, qtbot):
    """Test that clear_visualization resets the visualization and side panels."""
    window = visualization_page

    # Populate with some data
    window.containers = {1: MagicMock()}
    window.containers_packed_items = {1: [MagicMock(spec=PackedItem)]}
    window.sku_color_map = {'SKU1': (1, 0, 0, 1)}
    window.total_containers = 1
    window.current_container_index = 0
    window.items = [MagicMock()]

    # Call clear_visualization
    window.clear_visualization()

    # Verify that RightPanel's clear_visualization is called
    window.right_panel.clear_visualization.assert_called_once()

    # Verify that LeftPanel's tables are cleared
    window.left_panel.items_table.setRowCount.assert_called_once_with(0)
    window.left_panel.loading_order_table.setRowCount.assert_called_once_with(0)

    # Verify that labels are reset
    window.left_panel.space_used_label.setText.assert_called_with("Space Used: 0.00%")
    window.left_panel.space_remaining_label.setText.assert_called_with("Space Remaining: 0.00 m³")
    window.left_panel.weight_used_label.setText.assert_called_with("Weight Used: 0.00 / 0.00 kg")

def test_selection_highlighting(visualization_page, qtbot):
    """Test that selecting items in the tables highlights the correct items in the visualization."""
    window = visualization_page

    # Setup data
    containers = {
        1: Container(length=200.0, width=200.0, height=200.0, max_weight=30000.0, container_id=1)
    }

    packed_items = [
        PackedItem(sku='SKU1', position=(0,0,0), size=(100,50,75), rotation=(0,0,0), container_id=1, weight=5000),
        PackedItem(sku='SKU2', position=(100,50,0), size=(80,60,70), rotation=(0,0,0), container_id=1, weight=4000)
    ]

    sku_color_map = {
        'SKU1': (1, 0, 0, 1),
        'SKU2': (0, 1, 0, 1)
    }

    # Display packed items
    window.display_packed_items(containers, packed_items, sku_color_map)

    # Simulate selecting 'SKU1' in items_table
    sku1_item = MagicMock()
    sku1_item.text.return_value = 'SKU1'
    window.left_panel.items_table.selectedItems.return_value = [sku1_item]
    window.on_items_table_selection_changed()

    # Verify that RightPanel highlights SKU1 items
    window.right_panel.highlight_packed_item_by_sku.assert_called_once_with('SKU1')

    # Reset mock
    window.right_panel.highlight_packed_item_by_sku.reset_mock()

    # Simulate selecting the second packed item in loading_order_table
    window.left_panel.loading_order_table.selectedItems.return_value = [MagicMock(text='SKU2')]
    window.left_panel.loading_order_table.currentRow.return_value = 1  # Assuming second row
    window.left_panel.loading_order_table.item.return_value = MagicMock(data=MagicMock(return_value=id(packed_items[1])))

    window.on_loading_order_selection_changed()

    # Verify that RightPanel highlights the specific packed item
    window.right_panel.highlight_packed_item.assert_called_once_with(id(packed_items[1]))

def test_display_packed_items_no_containers(visualization_page, qtbot):
    """Test displaying packed items with no containers shows a warning and resets UI."""
    window = visualization_page

    # Empty data
    containers = {}
    packed_items = []
    sku_color_map = {}

    # Call display_packed_items
    with patch('PyQt5.QtWidgets.QMessageBox.warning') as mock_warning:
        window.display_packed_items(containers, packed_items, sku_color_map)
        mock_warning.assert_called_once_with(window, "No Containers", "No containers were packed.")

    # Verify that container_label is updated
    window.left_panel.container_label.setText.assert_called_with("Container 0 of 0")

    # Verify that navigation buttons are disabled
    window.left_panel.prev_button.setEnabled.assert_called_with(False)
    window.left_panel.next_button.setEnabled.assert_called_with(False)
