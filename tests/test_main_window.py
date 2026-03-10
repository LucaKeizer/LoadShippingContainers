# tests/test_main_window.py

import pytest
from unittest.mock import MagicMock, patch
from PyQt5.QtWidgets import QApplication, QMessageBox
from src.gui.main_window import MainWindow
from src.models.models import Item, Container
from src.data_io.data_manager import DataManager
from src.algorithms.packing_algorithm import run_packing_algorithm

import sys

@pytest.fixture(scope="session")
def app():
    """Fixture to create a QApplication instance."""
    app = QApplication(sys.argv)
    yield app
    app.quit()

@pytest.fixture
def main_window(qtbot):
    """Fixture to create and return a MainWindow instance with mocks."""
    with patch.object(DataManager, '__init__', lambda x: None):
        mock_data_manager = MagicMock(spec=DataManager)
        mock_data_manager.get_product_codes.return_value = ['SKU1', 'SKU2']
        mock_data_manager.get_dimensions_for_product_code.return_value = {
            'length': 100.0,
            'width': 50.0,
            'height': 75.0,
            'weight': 20.5,
            'rotatable': False,
            'stackable': True
        }
        mock_data_manager.get_qty_per_carton.return_value = 10
        mock_data_manager.generate_color_for_sku.return_value = (1, 0, 0, 0.6)
        mock_data_manager.calculate_cartons.return_value = 1
        mock_data_manager.get_base_sku.return_value = 'SKU1'

        with patch('src.gui.main_window.IOManager'):
            with patch('src.gui.main_window.InputPage'):
                with patch('src.gui.main_window.VisualizationPage'):
                    with patch('src.gui.main_window.IstiaImportPage'):
                        window = MainWindow()
                        window.data_manager = mock_data_manager
                        qtbot.addWidget(window)
                        return window

def test_initialization(main_window, qtbot):
    """Test that the MainWindow initializes correctly."""
    assert main_window.windowTitle() == "Container Packing Application"
    assert main_window.geometry().width() == 1200
    assert main_window.geometry().height() == 900
    assert main_window.stacked_widget.currentIndex() == 0  # Input Page

def test_add_item(main_window, qtbot):
    """Test adding an item to the MainWindow."""
    input_page = main_window.input_page
    input_page.sku_input = MagicMock()
    input_page.length_input = MagicMock()
    input_page.width_input = MagicMock()
    input_page.height_input = MagicMock()
    input_page.weight_input = MagicMock()
    input_page.quantity_input = MagicMock()
    input_page.cartons_input = MagicMock()
    input_page.stackable_input = MagicMock()
    input_page.rotatable_input = MagicMock()
    input_page.europallet_input = MagicMock()
    input_page.mixed_pallet_input = MagicMock()
    input_page.update_items_table = MagicMock()

    # Set input values
    input_page.sku_input.text.return_value = 'SKU1'
    input_page.length_input.value.return_value = 100.0
    input_page.width_input.value.return_value = 50.0
    input_page.height_input.value.return_value = 75.0
    input_page.weight_input.value.return_value = 20.5
    input_page.quantity_input.value.return_value = 10
    input_page.cartons_input.value.return_value = 1
    input_page.stackable_input.isChecked.return_value = True
    input_page.rotatable_input.isChecked.return_value = False
    input_page.europallet_input.isChecked.return_value = False
    input_page.mixed_pallet_input.text.return_value = ''

    with patch.object(main_window, 'check_carton_quantity') as mock_check_carton:
        main_window.add_item()
        mock_check_carton.assert_called_once_with('SKU1', 10, 1)

    # Verify that the item was added to data_manager
    main_window.data_manager.create_carton_item.assert_called_once_with(
        sku='SKU1',
        length=100.0,
        width=50.0,
        height=75.0,
        weight=20.5,
        quantity=10,
        stackable=True,
        rotatable=False,
        cartons=1
    )

    # Verify that update_items_table was called
    input_page.update_items_table.assert_called_once()

def test_delete_item(main_window, qtbot):
    """Test deleting an item from the MainWindow."""
    main_window.data_manager.items = [
        Item(sku='SKU1', length=100.0, width=50.0, height=75.0, weight=20.5, quantity=10)
    ]

    input_page = main_window.input_page
    input_page.update_items_table = MagicMock()

    with patch('PyQt5.QtWidgets.QMessageBox.question', return_value=QMessageBox.Yes):
        main_window.delete_item_by_row(0)
        assert len(main_window.data_manager.items) == 0
        input_page.update_items_table.assert_called_once()

def test_run_packing(main_window, qtbot):
    """Test running the packing algorithm."""
    # Setup mock containers and items
    main_window.data_manager.containers = [
        Container(length=200.0, width=200.0, height=200.0, max_weight=30000, container_type='TypeA')
    ]
    main_window.data_manager.items = [
        Item(sku='SKU1', length=100.0, width=50.0, height=75.0, weight=20.5, quantity=10)
    ]

    # Mock the Worker and QThread
    with patch('src.gui.main_window.Worker') as MockWorker, \
         patch('src.gui.main_window.QThread') as MockThread:
        
        mock_worker_instance = MockWorker.return_value
        mock_thread_instance = MockThread.return_value
        
        # Simulate worker.finished signal
        packed_containers = ['PackedContainer1']
        mock_worker_instance.run = MagicMock()
        mock_worker_instance.moveToThread = MagicMock()
        mock_worker_instance.run = MagicMock()
        mock_worker_instance.run.return_value = None
        mock_worker_instance.finished.emit = MagicMock()
        mock_worker_instance.progress.connect = MagicMock()
        
        # Simulate QThread behavior
        MockThread.return_value.start = MagicMock()
        MockThread.return_value.quit = MagicMock()
        MockThread.return_value.finished.connect = MagicMock()
        
        # Mock run_packing_algorithm to return packed_containers
        with patch('src.gui.main_window.run_packing_algorithm', return_value=packed_containers):
            # Mock QMessageBox
            with patch('PyQt5.QtWidgets.QMessageBox.warning') as mock_warning:
                main_window.run_packing()
                
                # Check that Run Packing Algorithm button was disabled
                main_window.input_page.run_packing_button.setEnabled.assert_called_with(False)
                
                # Check that Worker was created and started
                MockWorker.assert_called_once_with(main_window.data_manager.items, main_window.data_manager.containers)
                mock_worker_instance.moveToThread.assert_called_once_with(MockThread.return_value)
                mock_thread_instance.start.assert_called_once()
    
    # After packing is finished, verify that packed_containers are updated and visualization is shown
    main_window.on_packing_finished.assert_called_once_with(packed_containers)

def test_show_initial_page(main_window, qtbot):
    """Test that the Input Page is shown initially."""
    assert main_window.stacked_widget.currentIndex() == 0  # Input Page

def test_switch_to_visualization_page_without_packing(main_window, qtbot):
    """Test switching to Visualization Page without running packing."""
    with patch('PyQt5.QtWidgets.QMessageBox.warning') as mock_warning:
        main_window.show_visualization_page()
        mock_warning.assert_called_once_with(
            main_window,
            "No Packing Data",
            "Please run the packing algorithm first."
        )

def test_switch_to_visualization_page_with_packing(main_window, qtbot):
    """Test switching to Visualization Page after running packing."""
    main_window.data_manager.packed_containers = ['PackedContainer1']
    with patch.object(main_window, 'visualization_page') as mock_visualization:
        main_window.show_visualization_page()
        mock_visualization.display_packed_items.assert_called_once()
        assert main_window.stacked_widget.currentIndex() == 1  # Visualization Page

def test_reset_all(main_window, qtbot):
    """Test resetting all data in MainWindow."""
    # Setup data_manager with items and containers
    main_window.data_manager.items = [
        Item(sku='SKU1', length=100.0, width=50.0, height=75.0, weight=20.5, quantity=10)
    ]
    main_window.data_manager.containers = [
        Container(length=200.0, width=200.0, height=200.0, max_weight=30000, container_type='TypeA')
    ]
    main_window.data_manager.packed_containers = ['PackedContainer1']
    main_window.data_manager.margin_percentage = 10

    input_page = main_window.input_page
    input_page.update_items_table = MagicMock()
    input_page.run_packing_button = MagicMock()
    input_page.back_to_visualization_button = MagicMock()
    input_page.container_type_combo = MagicMock()
    input_page.container_table.setRowCount = MagicMock()
    input_page.margin_input = MagicMock()
    input_page.europallet_input = MagicMock()
    input_page.mixed_pallet_input = MagicMock()
    input_page.cartons_input = MagicMock()
    visualization_page = main_window.visualization_page
    visualization_page.clear_visualization = MagicMock()

    with patch('PyQt5.QtWidgets.QMessageBox.question', return_value=QMessageBox.Yes):
        main_window.reset_all()

        # Verify data_manager is reset
        assert main_window.data_manager.items == []
        assert main_window.data_manager.containers == []
        assert main_window.data_manager.packed_containers == []
        assert main_window.data_manager.margin_percentage == 0

        # Verify GUI elements are reset
        input_page.update_items_table.assert_called_once_with([])
        input_page.run_packing_button.setEnabled.assert_called_with(True)
        input_page.back_to_visualization_button.setEnabled.assert_called_with(False)
        input_page.container_type_combo.setCurrentIndex.assert_called_with(0)
        input_page.container_table.setRowCount.assert_called_with(0)
        input_page.margin_input.setValue.assert_called_with(0)
        input_page.europallet_input.setChecked.assert_called_with(False)
        input_page.mixed_pallet_input.clear.assert_called_once()
        input_page.cartons_input.setValue.assert_called_with(0)
        visualization_page.clear_visualization.assert_called_once()

        # Verify that QMessageBox.information was called
        with patch('PyQt5.QtWidgets.QMessageBox.information') as mock_info:
            main_window.reset_all()
            mock_info.assert_called_with(main_window, "Reset Complete", "All data has been reset.")

