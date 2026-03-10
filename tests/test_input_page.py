# tests/test_input_page.py

import pytest
from unittest.mock import MagicMock
from PyQt5.QtWidgets import QApplication, QPushButton, QMessageBox, QWidget
from PyQt5.QtCore import Qt
from src.gui.input_page import InputPage
from src.models.models import Container

# Define a minimal stub parent class
class TestParent(QWidget):
    def __init__(self):
        super().__init__()
        # Initialize necessary attributes
        self.data_manager = MagicMock()
        self.data_manager.items = []
        self.data_manager.containers = []
        self.data_manager.sku_color_map = {}
        self.data_manager.generate_color_for_sku.return_value = Qt.black
        self.data_manager.get_base_sku.side_effect = lambda sku: sku  # Simple passthrough

        self.mixed_pallet_list = []

        # Define the methods that InputPage expects to call
        self.add_item = MagicMock()
        self.set_margin = MagicMock()
        self.on_issue_clicked = MagicMock()
        # Add other methods as needed

    # Define any additional methods required by InputPage
    def update_containers(self):
        pass

    def run_packing(self):
        pass

    def import_data(self):
        pass

    def import_istia(self):
        pass

    def export_data(self):
        pass

    def reset_all(self):
        pass

    def show_visualization_page(self):
        pass

    def split_item(self, row, left_qty, right_qty):
        pass

    def delete_item_by_row(self, row):
        pass

# Fixture to ensure a QApplication instance exists
@pytest.fixture(scope="session")
def app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

# Fixture to create an instance of TestParent
@pytest.fixture
def test_parent(qtbot):
    parent = TestParent()
    qtbot.addWidget(parent)  # Register with qtbot
    return parent

# Fixture to create an instance of InputPage with the stub parent
@pytest.fixture
def input_page(test_parent, qtbot, app):
    page = InputPage(parent=test_parent)
    qtbot.addWidget(page)
    return page

def test_initialization(input_page):
    """Test that the InputPage initializes correctly with all essential widgets."""
    # Check if key input fields exist
    assert input_page.sku_input is not None
    assert input_page.length_input is not None
    assert input_page.width_input is not None
    assert input_page.height_input is not None
    assert input_page.weight_input is not None
    assert input_page.quantity_input is not None
    assert input_page.cartons_input is not None
    assert input_page.mixed_pallet_input is not None
    assert input_page.stackable_input is not None
    assert input_page.rotatable_input is not None
    assert input_page.europallet_input is not None

    # Check if essential buttons exist
    add_item_button = input_page.findChild(QPushButton, "add_item_button")
    assert add_item_button is not None, "Add Item button not found."

    # Add any other essential widgets you want to verify

def test_add_valid_item(qtbot, input_page, test_parent):
    """Test adding a valid item updates the data model and calls parent.add_item."""
    # Set valid inputs
    input_page.sku_input.setText("SKU123")
    input_page.length_input.setValue(100)
    input_page.width_input.setValue(50)
    input_page.height_input.setValue(75)
    input_page.weight_input.setValue(20.5)
    input_page.quantity_input.setValue(10)
    input_page.cartons_input.setValue(1)
    input_page.mixed_pallet_input.setText("MP001")
    input_page.stackable_input.setChecked(True)
    input_page.rotatable_input.setChecked(False)
    input_page.europallet_input.setChecked(True)

    # Simulate clicking the "Add Item" button
    add_item_button = input_page.findChild(QPushButton, "add_item_button")
    assert add_item_button is not None, "Add Item button not found."
    qtbot.mouseClick(add_item_button, Qt.LeftButton)

    # Ensure the parent.add_item was called once
    test_parent.add_item.assert_called_once()

def test_add_item_with_missing_sku(qtbot, input_page, test_parent, monkeypatch):
    """Test adding an item with an empty SKU shows a warning and calls parent.add_item with False."""
    # Set inputs with empty SKU
    input_page.sku_input.setText("")
    input_page.length_input.setValue(100)
    input_page.width_input.setValue(50)
    input_page.height_input.setValue(75)
    input_page.weight_input.setValue(20.5)
    input_page.quantity_input.setValue(10)
    input_page.cartons_input.setValue(1)

    # Mock QMessageBox.warning to prevent actual dialog
    with monkeypatch.context() as m:
        m.setattr(QMessageBox, 'warning', lambda *args, **kwargs: None)
        # Simulate clicking the "Add Item" button
        add_item_button = input_page.findChild(QPushButton, "add_item_button")
        assert add_item_button is not None, "Add Item button not found."
        qtbot.mouseClick(add_item_button, Qt.LeftButton)

    # Ensure the parent.add_item was called once with False
    test_parent.add_item.assert_called_once_with(False)

def test_toggle_stackable(qtbot, input_page):
    """Test toggling the stackable button updates its text correctly."""
    # Initially checked
    assert input_page.stackable_input.isChecked()
    assert input_page.stackable_input.text() == "Yes"

    # Toggle off
    qtbot.mouseClick(input_page.stackable_input, Qt.LeftButton)
    assert not input_page.stackable_input.isChecked()
    assert input_page.stackable_input.text() == "No"

    # Toggle on
    qtbot.mouseClick(input_page.stackable_input, Qt.LeftButton)
    assert input_page.stackable_input.isChecked()
    assert input_page.stackable_input.text() == "Yes"

def test_add_container(qtbot, input_page, test_parent):
    """Test adding a container updates the container list and table."""
    # Select a container type
    input_page.container_type_combo.setCurrentText("20ft")

    # Simulate clicking the "Add Container" button
    add_container_button = input_page.findChild(QPushButton, "add_container_button")
    if add_container_button is None:
        # Fallback if objectName is not set
        add_container_button = input_page.findChild(QPushButton, "Add Container")
    assert add_container_button is not None, "Add Container button not found."
    qtbot.mouseClick(add_container_button, Qt.LeftButton)

    # Ensure a new container is added to data_manager.containers
    assert len(test_parent.data_manager.containers) == 1
    new_container = test_parent.data_manager.containers[0]
    assert new_container.container_type == "20ft"
    assert new_container.length == 589.5
    assert new_container.width == 235.0
    assert new_container.height == 239.2
    assert new_container.max_weight == 28200

    # Ensure the container table is updated
    assert input_page.container_table.rowCount() == 1
    assert input_page.container_table.item(0, 0).text() == "20ft"
    assert input_page.container_table.item(0, 1).text() == "589.5"
    assert input_page.container_table.item(0, 2).text() == "235.0"
    assert input_page.container_table.item(0, 3).text() == "239.2"
