# tests/test_visualization_right_panel.py

import pytest
from unittest.mock import MagicMock, patch
from PyQt5.QtWidgets import QApplication
from src.visualization.visualization_right_panel import RightPanel, CustomGLMeshItem, CustomGLViewWidget
from src.models.models import Container, PackedItem
import sys

@pytest.fixture(scope="session")
def app():
    """Fixture to create a QApplication instance."""
    app = QApplication(sys.argv)
    yield app
    app.quit()

@pytest.fixture
def right_panel(qtbot):
    """Fixture to create and return a RightPanel instance with mocked parent."""
    mock_parent = MagicMock()
    mock_parent.left_panel = MagicMock()
    mock_parent.left_panel.prev_button = MagicMock()
    mock_parent.left_panel.next_button = MagicMock()
    
    panel = RightPanel(parent=mock_parent)
    qtbot.addWidget(panel)
    panel.show()
    return panel, mock_parent

def test_initialization(right_panel, qtbot):
    """Test that the RightPanel initializes correctly."""
    panel, mock_parent = right_panel
    
    # Verify initial state
    assert panel.containers_packed_items == {}
    assert panel.packed_visual_items == []
    assert panel.container_walls == {}
    assert panel.visible_walls == set()
    
    # Verify that grid is added
    assert any(isinstance(item, GLGridItem) for item in panel.view.items)

def test_clear_visualization(right_panel, qtbot):
    """Test that clear_visualization clears all items and walls."""
    panel, _ = right_panel
    
    # Add mock packed items and walls
    mock_packed_item = MagicMock(spec=CustomGLMeshItem)
    mock_wall = MagicMock(spec=CustomGLMeshItem)
    panel.packed_visual_items.append(mock_packed_item)
    panel.container_walls['front'] = mock_wall
    panel.visible_walls.add('front')
    
    # Call clear_visualization
    panel.clear_visualization()
    
    # Verify that items are removed from the view
    panel.view.removeItem.assert_any_call(mock_packed_item)
    panel.view.removeItem.assert_any_call(mock_wall)
    
    # Verify internal lists are cleared
    assert panel.packed_visual_items == []
    assert panel.container_walls == {}
    assert panel.visible_walls == set()

def test_draw_container(right_panel, qtbot):
    """Test that draw_container adds walls to the view."""
    panel, _ = right_panel
    
    # Create a sample container
    container = Container(length=200.0, width=200.0, height=200.0, max_weight=30000.0, container_id=1)
    
    # Call draw_container
    panel.draw_container(container)
    
    # Verify that walls are created and added
    assert len(panel.container_walls) == 6  # front, back, left, right, top, bottom
    assert len(panel.visible_walls) == 6
    
    for wall_name in ['front', 'back', 'left', 'right', 'top', 'bottom']:
        assert wall_name in panel.container_walls
        panel.view.addItem.assert_any_call(panel.container_walls[wall_name])

def test_draw_packed_item(right_panel, qtbot):
    """Test that draw_packed_item adds a packed item to the view with correct properties."""
    panel, _ = right_panel
    
    # Create a sample packed item and SKU color map
    packed_item = PackedItem(sku='SKU1', position=(0, 0, 0), size=(100, 50, 75), rotation=(0, 0, 0), container_id=1, weight=5000.0)
    sku_color_map = {'SKU1': (1, 0, 0, 1)}  # Red
    container = Container(length=200.0, width=200.0, height=200.0, max_weight=30000.0, container_id=1)
    
    # Call draw_packed_item
    packed_mesh = panel.draw_packed_item(packed_item, sku_color_map, container)
    
    # Verify that the mesh is added to the view
    panel.view.addItem.assert_called_with(packed_mesh)
    
    # Verify that the packed item is stored
    assert packed_mesh in panel.packed_visual_items
    assert packed_mesh.packed_item == packed_item
    assert packed_mesh.opts['edgeColor'] == (0, 0, 0, 1)  # Black edges
    assert packed_mesh.edgeWidth == 2.0

def test_highlight_packed_item_by_sku(right_panel, qtbot):
    """Test that highlight_packed_item_by_sku highlights the correct items."""
    panel, _ = right_panel
    
    # Create sample packed items
    packed_item1 = PackedItem(sku='SKU1', position=(0, 0, 0), size=(100, 50, 75), rotation=(0, 0, 0), container_id=1, weight=5000.0)
    packed_item2 = PackedItem(sku='SKU2', position=(100, 50, 0), size=(80, 60, 70), rotation=(0, 0, 0), container_id=1, weight=4000.0)
    
    # Draw packed items
    mesh1 = panel.draw_packed_item(packed_item1, {'SKU1': (1, 0, 0, 1)}, MagicMock())
    mesh2 = panel.draw_packed_item(packed_item2, {'SKU2': (0, 1, 0, 1)}, MagicMock())
    
    # Call highlight_packed_item_by_sku for SKU1
    panel.highlight_packed_item_by_sku('SKU1')
    
    # Verify that mesh1 has updated edge color and width
    mesh1.set_edge_color.assert_called_with((1, 1, 0, 1))  # Bright yellow
    mesh1.set_edge_width.assert_called_with(5.0)
    
    # Verify that mesh2 remains unchanged
    mesh2.set_edge_color.assert_not_called()
    mesh2.set_edge_width.assert_not_called()

def test_highlight_packed_item(right_panel, qtbot):
    """Test that highlight_packed_item highlights the specific packed item."""
    panel, _ = right_panel
    
    # Create a sample packed item
    packed_item = PackedItem(sku='SKU1', position=(0, 0, 0), size=(100, 50, 75), rotation=(0, 0, 0), container_id=1, weight=5000.0)
    mesh = panel.draw_packed_item(packed_item, {'SKU1': (1, 0, 0, 1)}, MagicMock())
    
    # Call highlight_packed_item with the packed item's id
    panel.highlight_packed_item(id(packed_item))
    
    # Verify that the mesh has updated edge color and width
    mesh.set_edge_color.assert_called_with((1, 1, 0, 1))  # Bright yellow
    mesh.set_edge_width.assert_called_with(5.0)

def test_reset_highlights(right_panel, qtbot):
    """Test that reset_highlights resets all highlights to default."""
    panel, _ = right_panel
    
    # Create and draw a packed item
    packed_item = PackedItem(sku='SKU1', position=(0, 0, 0), size=(100, 50, 75), rotation=(0, 0, 0), container_id=1, weight=5000.0)
    mesh = panel.draw_packed_item(packed_item, {'SKU1': (1, 0, 0, 1)}, MagicMock())
    
    # Highlight the packed item
    panel.highlight_packed_item(id(packed_item))
    
    # Reset highlights
    panel.reset_highlights()
    
    # Verify that the mesh's edge color and width are reset to default
    mesh.set_edge_color.assert_called_with(mesh.default_edge_color)
    mesh.set_edge_width.assert_called_with(mesh.default_edge_width)
