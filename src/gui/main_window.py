# src/gui/main_window.py

# Standard Library Imports
import getpass
import math
import os
import sys
from pathlib import Path
import hashlib
import json
import shutil

# Third-party Imports
from PyQt5.QtCore import Qt, QThread, QStringListModel
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QMainWindow, QMessageBox, QStackedWidget, QFileDialog,
    QProgressDialog, QPushButton, QDialog, QCompleter, QTableView, QApplication, QAbstractItemView
)
import numpy as np

# Local Application Imports
from src.algorithms.packing_algorithm import run_packing_algorithm  # If still needed for references
from src.algorithms.run_packing import prepare_packing   # Newly created script
from src.data_io.data_manager import DataManager
from src.data_io.io_manager import IOManager
from src.data_io.item_manager import ItemManager
from src.gui.input_page import InputPage
from src.data_io.product_settings import ProductSettingsPage
from src.gui.packing_options_dialog import PackingOptionsDialog
from src.models.models import Item, Container, PackedItem, PackedContainer
from src.models.worker import Worker
from src.utilities.istia_import import IstiaImportPage
from src.utilities.tutorial import TutorialWindow
from src.utilities.utils import resource_path, get_permanent_directory, check_product_data_version
from src.visualization.visualization import VisualizationPage


class NumpyEncoder(json.JSONEncoder):
    """
    Converts NumPy data types (e.g. numpy.bool_, numpy.int64, etc.)
    into their plain Python equivalents for JSON serialization.
    """
    def default(self, obj):
        # Handle NumPy boolean
        if isinstance(obj, np.bool_):
            return bool(obj)
        return super().default(obj)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Container Packing Application")
        
        # Get screen geometry
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        
        # Set window size to 80% of screen size
        window_width = int(screen_width * 0.6)
        window_height = int(screen_height * 0.5)
        
        # Define margin to move the window up (e.g., 70 pixels)
        margin = 70
        y_position = (screen_height - window_height) // 2 - margin
        y_position = max(y_position, 0)  # Ensure y is not negative
        
        # Calculate x position to center the window
        x_position = (screen_width - window_width) // 2
        
        # Apply geometry with adjusted y_position
        self.setGeometry(x_position, y_position, window_width, window_height)

        # Set the window icon for taskbar and title bar
        self.set_window_icon()

        QApplication.instance().setWindowIcon(QIcon(resource_path(r'Data/Img/application_logo.ico')))

        # Check and copy Product data if not in permanent directory
        permanent_dir = get_permanent_directory("DataFiles")
        if not os.path.exists(permanent_dir):
            os.makedirs(permanent_dir, exist_ok=True)

        permanent_product_data = os.path.join(permanent_dir, "Product data.xlsx")
        original_product_data = resource_path(r'Data\Product data.xlsx')

        # Define version flag for product data updates
        PRODUCT_DATA_VERSION = "v2025_03_03"  # Update this when making changes

        should_update = False
        
        # If file doesn't exist, copy it
        if not os.path.exists(permanent_product_data):
            should_update = True
        # If file exists, check version
        elif check_product_data_version(PRODUCT_DATA_VERSION):
            should_update = True

        if should_update:
            if not os.path.exists(original_product_data):
                QMessageBox.critical(
                    self, "File Not Found",
                    f"'{original_product_data}' does not exist. The application cannot continue."
                )
                sys.exit(1)
            
            # Create backup of existing file if it exists
            if os.path.exists(permanent_product_data):
                backup_path = permanent_product_data + '.backup'
                shutil.copy2(permanent_product_data, backup_path)
            
            # Copy new file
            shutil.copyfile(original_product_data, permanent_product_data)
            
            # Clear cached results folder
            cache_directory = get_permanent_directory("CachedResults")
            if os.path.exists(cache_directory):
                # Remove all files in the cache directory
                for filename in os.listdir(cache_directory):
                    file_path = os.path.join(cache_directory, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)

        # Initialize DataManager and IOManager
        self.data_manager = DataManager()
        self.io_manager = IOManager(self.data_manager)

        # Load carton dimensions
        carton_dimensions_path = resource_path(r'Data\QTY Per Carton.xlsx')
        self.data_manager.load_carton_dimensions(carton_dimensions_path)

        # Load collections data
        collections_path = resource_path(r'Data\\Collections.xlsx')
        self.data_manager.load_collections(collections_path)

        # Load product data from the permanent directory now
        self.data_manager.load_product_data(permanent_product_data)

        self.loading_plan_name = ""
        
        # Get product codes for auto-completion
        self.product_codes_list = self.data_manager.get_product_codes()
        
        # Initialize autocompletion list and model for Mixed Pallet
        self.mixed_pallet_list = []
        self.mixed_pallet_model = QStringListModel(self.mixed_pallet_list)
        
        # Initialize autocompletion model for Product Codes
        self.product_codes_model = QStringListModel(self.product_codes_list)
        
        # Set up QCompleter for Product Code input
        self.product_codes_completer = QCompleter(self.product_codes_model, self)
        self.product_codes_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.product_codes_completer.setCompletionMode(QCompleter.PopupCompletion)
        self.product_codes_completer.setFilterMode(Qt.MatchContains)
        self.product_codes_completer.setMaxVisibleItems(10)
        self.product_codes_completer.setWrapAround(False)
        
        # Instantiate ItemManager
        self.item_manager = ItemManager(parent=self)
        
        # Set up the main layout with QStackedWidget
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        # Create pages after ItemManager is instantiated
        self.input_page = InputPage(parent=self)
        self.visualization_page = VisualizationPage(parent=self)
        self.istia_import_page = IstiaImportPage(parent=self)
        self.product_settings_page = ProductSettingsPage(parent=self)
        
        # Set completers after input_page is initialized
        self.input_page.mixed_pallet_input.setCompleter(self.product_codes_completer)
        self.input_page.sku_input.setCompleter(self.product_codes_completer)
        
        # Connect signals
        self.input_page.loading_plan_name_changed.connect(self.set_loading_plan_name)
        
        # Add pages to the stacked widget
        self.stacked_widget.addWidget(self.input_page)               # Index 0
        self.stacked_widget.addWidget(self.visualization_page)       # Index 1
        self.stacked_widget.addWidget(self.istia_import_page)        # Index 2
        self.stacked_widget.addWidget(self.product_settings_page)    # Index 3
        
        # Show Input Page initially
        self.stacked_widget.setCurrentIndex(0)
        
        # Connect containers_updated signal
        self.input_page.containers_updated.connect(self.update_containers)
        
        # Connect itemsDataChanged signal
        self.input_page.items_model.itemsDataChanged.connect(self.on_items_data_changed)
        
        # Connect cartonQuantityIssue signal to ItemManager
        self.input_page.items_model.cartonQuantityIssue.connect(self.item_manager.handle_carton_quantity_issue)
        
        # Connect Quantity input's valueChanged signal
        self.input_page.quantity_input.valueChanged.connect(self.on_quantity_changed)
        
        # Initialize current_qty_per_carton
        self.current_qty_per_carton = None
        
        # Check if tutorial should be shown
        self.check_and_show_tutorial()

    def set_window_icon(self):
        """Sets the window icon for both the title bar and taskbar."""
        icon_path = resource_path(r'Data/Img/application_logo.ico')
        self.setWindowIcon(QIcon(icon_path))

    def check_and_show_tutorial(self):
        user = getpass.getuser()  # Get the current PC username

        if sys.platform == 'win32':
            appdata_dir = os.getenv('APPDATA')
            tutorial_status_file = os.path.join(appdata_dir, 'LoadShippingContainers', 'tutorial_status.txt')
        else:
            home_dir = os.path.expanduser('~')
            tutorial_status_file = os.path.join(home_dir, '.LoadShippingContainers', 'tutorial_status.txt')

        tutorial_status_dir = os.path.dirname(tutorial_status_file)
        if not os.path.exists(tutorial_status_dir):
            os.makedirs(tutorial_status_dir, exist_ok=True)

        users_who_completed_tutorial = set()

        if os.path.exists(tutorial_status_file):
            with open(tutorial_status_file, 'r') as file:
                users_who_completed_tutorial = set(line.strip() for line in file)

        if user not in users_who_completed_tutorial:
            tutorial_window = TutorialWindow()
            if tutorial_window.exec_() == QDialog.Accepted:
                users_who_completed_tutorial.add(user)
                with open(tutorial_status_file, 'w') as file:
                    for u in users_who_completed_tutorial:
                        file.write(f"{u}\n")

    def on_items_data_changed(self):
        """Handles invalidation when items data is changed via the model."""
        self.data_manager.packed_containers = []

    def on_quantity_changed(self, new_value):
        """Automatically calculates and updates the ideal number of cartons based on Quantity."""
        if self.current_qty_per_carton and self.current_qty_per_carton > 0:
            ideal_cartons = self.data_manager.calculate_cartons(new_value, self.current_qty_per_carton)
            self.input_page.cartons_input.setValue(ideal_cartons)

    def show_product_settings_page(self):
        """Navigates to the Product Settings page."""
        self.stacked_widget.setCurrentWidget(self.product_settings_page)

    def show_input_page(self):
        # Commit any pending edits in the table
        if self.input_page.items_table.state() == QAbstractItemView.EditingState:
            editor = self.input_page.items_table.currentEditor()
            if editor:
                self.input_page.items_table.commitData(editor)
                self.input_page.items_table.closeEditor(editor, QAbstractItemView.NoHint)

        self.stacked_widget.setCurrentIndex(0)

    def show_visualization_page(self):
        """Switches to the Visualization Page."""
        if not self.data_manager.packed_containers:
            QMessageBox.warning(self, "No Packing Data", "Please run the packing algorithm first.")
            return
        self.stacked_widget.setCurrentIndex(1)

    def show_istia_import_page(self):
        """Switches to the Istia Import Page."""
        self.stacked_widget.setCurrentIndex(2)

    def set_margin(self):
        """Sets the global margin percentage for all items."""
        self.data_manager.margin_percentage = self.input_page.margin_input.value()
        QMessageBox.information(self, "Margin Set", f"Global margin set to {self.data_manager.margin_percentage}%.")
        self.data_manager.packed_containers = []

    def update_containers(self):
        """Updates the containers in the data_manager based on the container_table in the input_page."""
        self.data_manager.containers = []
        for row in range(self.input_page.container_table.rowCount()):
            container_type_item = self.input_page.container_table.item(row, 0)
            length_item = self.input_page.container_table.item(row, 1)
            width_item = self.input_page.container_table.item(row, 2)
            height_item = self.input_page.container_table.item(row, 3)
            if container_type_item and length_item and width_item and height_item:
                container_type = container_type_item.text()
                length = float(length_item.text())
                width = float(width_item.text())
                height = float(height_item.text())
                max_weight = 30000
                container = Container(length=length, width=width, height=height, max_weight=max_weight, container_type=container_type)
                self.data_manager.containers.append(container)

    def compute_scenario_hash(self, packing_method, combined_pallets):
        items_sorted = sorted(
            self.data_manager.items,
            key=lambda i: (
                i.sku,
                i.length,
                i.width,
                i.height,
                i.weight,
                i.quantity,
                i.stackable,
                i.rotatable,
                i.europallet,
                i.mixed_pallet,
                i.cartons
            )
        )

        containers_sorted = sorted(
            self.data_manager.containers,
            key=lambda c: (
                c.container_type,
                c.length,
                c.width,
                c.height,
                c.max_weight
            )
        )

        scenario = {
            "margin_percentage": self.data_manager.margin_percentage,
            "packing_method": packing_method,
            "combined_pallets": combined_pallets,  # Include the flag here
            "items": [
                {
                    "sku": item.sku,
                    "length": item.length,
                    "width": item.width,
                    "height": item.height,
                    "weight": item.weight,
                    "quantity": item.quantity,
                    "stackable": item.stackable,
                    "rotatable": item.rotatable,
                    "europallet": item.europallet,
                    "mixed_pallet": item.mixed_pallet,
                    "cartons": item.cartons
                }
                for item in items_sorted
            ],
            "containers": [
                {
                    "container_type": container.container_type,
                    "length": container.length,
                    "width": container.width,
                    "height": container.height,
                    "max_weight": container.max_weight
                }
                for container in containers_sorted
            ]
        }

        import hashlib, json
        scenario_json = json.dumps(scenario, sort_keys=True, separators=(',', ':'))
        scenario_hash = hashlib.sha256(scenario_json.encode('utf-8')).hexdigest()
        return scenario_hash

    def create_packing_options_dialog(self):
        """Creates and returns a packing options dialog instance."""
        dialog = PackingOptionsDialog(self)
        return dialog

    def run_packing(self):
        # Commit any pending edits in the items table
        input_page = self.input_page
        if input_page.items_table.state() == QAbstractItemView.EditingState:
            editor = input_page.items_table.currentEditor()
            if editor:
                input_page.items_table.commitData(editor)
                input_page.items_table.closeEditor(editor, QAbstractItemView.NoHint)

        # Use prepare_packing to do the heavy lifting before threading
        from src.algorithms.run_packing import prepare_packing
        scenario_hash, cache_file_path, packing_method, sorted_items = prepare_packing(self)

        # If None returned, packing canceled or invalid conditions
        if scenario_hash is None:
            return

        if not sorted_items:
            QMessageBox.warning(self, "No Valid Items", "There are no valid items available to pack.")
            return

        # Show a progress dialog
        self.progress_dialog = QProgressDialog("Packing items...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowTitle("Please Wait")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.show()

        # Create a QThread object
        self.thread = QThread()

        # Create a Worker object with adjusted items and containers, passing the selected packing method
        self.worker = Worker(sorted_items, self.data_manager.containers, packing_method)

        # Move the Worker object to the thread
        self.worker.moveToThread(self.thread)

        # Connect signals and slots
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_packing_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        # Connect progress signal
        self.worker.progress.connect(self.progress_dialog.setValue)

        # Start the thread
        self.thread.start()

        # Handle cancellation
        self.progress_dialog.canceled.connect(self.on_packing_canceled)

        # Store scenario hash to save cache after packing
        self.current_scenario_hash = scenario_hash
        self.current_cache_file_path = cache_file_path

    def on_packing_finished(self, packed_containers):
        if self.input_page.items_table.state() == QAbstractItemView.EditingState:
            editor = self.input_page.items_table.currentEditor()
            if editor:
                self.input_page.items_table.commitData(editor)
                self.input_page.items_table.closeEditor(editor, QAbstractItemView.NoHint)

        if not packed_containers:
            QMessageBox.warning(self, "Packing Failed", "No items were packed.")
            return

        self.data_manager.packed_containers = packed_containers

        # Important! Make sure items_model.items and data_manager.items reference 
        # the same list after loading cache
        self.input_page.items_model.items = self.data_manager.items

        self.input_page.update_items_table(self.data_manager.items)

        containers_dict = {pc.container_id: pc.container for pc in packed_containers}
        all_packed_items = []
        for pc in packed_containers:
            all_packed_items.extend(pc.packed_items)

        self.visualization_page.display_packed_items(
            containers=containers_dict,
            packed_items=all_packed_items,
            sku_color_map=self.data_manager.sku_color_map
        )

        self.input_page.back_to_visualization_button.setEnabled(True)

        self.save_packing_result_to_cache()
        self.show_visualization_page()

    def save_packing_result_to_cache(self):
        if hasattr(self, 'current_cache_file_path') and hasattr(self, 'data_manager'):
            try:
                packed_containers_data = [pc.to_dict() for pc in self.data_manager.packed_containers]
                items_data = [item.to_dict() for item in self.data_manager.items]
                combined_pallets_data = [cp.to_dict() for cp in self.data_manager.combined_pallets]

                cache_data = {
                    "packing_method": self.worker.packing_method,
                    "packed_containers": packed_containers_data,
                    "items": items_data,
                    "combined_pallets": combined_pallets_data,
                    "used_combined_pallets": self.used_combined_pallets
                }

                with open(self.current_cache_file_path, 'w') as f:
                    json.dump(cache_data, f, indent=4, cls=NumpyEncoder)

            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Cache Save Failed",
                    f"Failed to save packing results to cache.\nError: {e}"
                )
        else:
            QMessageBox.warning(
                self,
                "Cache Save Error",
                "Cannot save packing results because cache file path or data manager is missing."
            )
            
    def on_packing_canceled(self):
        self.worker.stop()  # Set a flag in the worker to stop

    def import_data(self):
        """Imports data using the IOManager."""
        self.io_manager.import_data(self)
        for item in self.data_manager.items:
            mixed_pallet = item.mixed_pallet
            if mixed_pallet:
                mixed_pallet = str(mixed_pallet).strip()
                if mixed_pallet and mixed_pallet not in self.mixed_pallet_list:
                    self.mixed_pallet_list.append(mixed_pallet)

        self.mixed_pallet_model.setStringList(self.mixed_pallet_list)
        self.input_page.update_container_table()
    
    def set_loading_plan_name(self, name):
        """Handles the Loading Plan Name when received from InputPage."""
        if not name:
            QMessageBox.warning(self, "Input Error", "Loading Plan Name cannot be empty.")
            return

        self.loading_plan_name = name
        self.setWindowTitle(f"Container Packing Application - {name}")
        self.input_page.current_loading_plan_label.setText(f"Current Loading Plan: {name}")

    def export_data(self):
        """Exports data using the IOManager."""
        self.io_manager.export_data(self)

    def import_istia(self):
        """Opens the Istia Import Page."""
        self.show_istia_import_page()

    def refresh_ui_after_product_update(self):
        """Refreshes the UI after product data has been updated."""
        try:
            self.data_manager.reload_product_data()
            self.product_codes_list = self.data_manager.get_product_codes()
            self.product_codes_model.setStringList(self.product_codes_list)
            
            self.product_codes_completer.setModel(self.product_codes_model)
            self.input_page.sku_input.setCompleter(self.product_codes_completer)
            self.input_page.mixed_pallet_input.setCompleter(self.product_codes_completer)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Refresh Error",
                f"An error occurred while refreshing the UI:\n{e}"
            )

    def reset_all(self):
        """Resets all inputs and the visualization."""
        confirm = QMessageBox.question(
            self, "Reset Confirmation",
            "Are you sure you want to reset all data?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            # Reset DataManager attributes
            self.data_manager.items = []
            self.data_manager.packed_items = []
            self.data_manager.packed_containers = []
            self.data_manager.containers = []
            self.data_manager.margin_percentage = 0

            # Reset UI components on Input Page
            self.input_page.update_items_table(self.data_manager.items)
            self.input_page.container_type_combo.setCurrentIndex(0)
            self.input_page.container_table.setRowCount(0)
            self.input_page.margin_input.setValue(0)
            self.input_page.mixed_pallet_input.clear()

            # Reset remaining input fields
            self.input_page.sku_input.clear()
            self.input_page.quantity_input.setValue(1)

            # Reset Loading Plan Name
            self.loading_plan_name = ""  # Reset the MainWindow's loading plan name
            self.input_page.current_loading_plan_label.setText("Current Loading Plan: Not Set")  # Update label
            self.input_page.loading_plan_name_input.clear()  # Clear input field

            # Reset Visualization Page
            self.visualization_page.clear_visualization()

            # Disable Visualization Button
            self.input_page.back_to_visualization_button.setEnabled(False)

            # Reset Mixed Pallet List and Model
            self.mixed_pallet_list.clear()
            self.mixed_pallet_model.setStringList(self.mixed_pallet_list)

            # Invalidate Packed Data
            self.data_manager.packed_containers = []

            # Inform the User
            QMessageBox.information(self, "Reset Complete", "All data has been reset.")
