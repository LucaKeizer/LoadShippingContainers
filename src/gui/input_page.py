# src/gui/input_page.py

# Standard Library Imports
import os
import subprocess
import sys

# Third-party Imports
from PyQt5.QtCore import Qt, pyqtSignal, QModelIndex, QStringListModel
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton, 
    QTableView, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, 
    QMessageBox, QSlider, QDialog, QSpinBox, QDoubleSpinBox, QLineEdit, QSizePolicy, QApplication, QAbstractItemView
)

# Local Application Imports
from src.gui.items_table_model import (
    SelectableLineEdit, SelectableSpinBox, MixedPalletDelegate, ItemsTableModel, ButtonDelegate, IssueDelegate, SelectableDoubleSpinBox
)
from src.models.models import Container, Item
from src.utilities.utils import resource_path
from src.data_io.custom_import import CustomImportDialog


class InputPage(QWidget):
    """
    Page for inputting items and container specifications.
    """
    containers_updated = pyqtSignal()  # Signal to notify when containers are updated
    loading_plan_name_changed = pyqtSignal(str)  # Signal for Loading Plan Name changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent  # Reference to MainWindow
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        # *** Item Input Section ***
        item_section = QWidget()
        item_layout = QHBoxLayout()  # Use horizontal layout
        item_section.setLayout(item_layout)
        layout.addWidget(QLabel("<b>Item Input</b>"))

        # Group for Product Code
        product_code_layout = QHBoxLayout()
        product_code_label = QLabel("Product Code:")
        product_code_label.setFixedWidth(100)  # Fixed width for labels
        self.sku_input = SelectableLineEdit()
        self.sku_input.setPlaceholderText("Enter SKU here")
        product_code_layout.addWidget(product_code_label)
        product_code_layout.addWidget(self.sku_input)

        # Group for Quantity
        quantity_layout = QHBoxLayout()
        quantity_label = QLabel("Quantity:")
        quantity_label.setFixedWidth(70)
        self.quantity_input = SelectableSpinBox()
        self.quantity_input.setRange(1, 1000000)
        self.quantity_input.setValue(1)
        self.quantity_input.setToolTip("Enter the quantity of items.")
        quantity_layout.addWidget(quantity_label)
        quantity_layout.addWidget(self.quantity_input)

        # Group for Mixed Pallet
        mixed_pallet_layout = QHBoxLayout()
        mixed_pallet_label = QLabel("Mixed Pallet:")
        mixed_pallet_label.setFixedWidth(100)
        self.mixed_pallet_input = SelectableLineEdit()
        self.mixed_pallet_input.setPlaceholderText("Enter Mixed Pallet ID")
        self.mixed_pallet_input.setToolTip("Enter the Mixed Pallet identifier.")
        mixed_pallet_layout.addWidget(mixed_pallet_label)
        mixed_pallet_layout.addWidget(self.mixed_pallet_input)

        # Add all groups to the item_layout
        item_layout.addLayout(product_code_layout)
        item_layout.addSpacing(20)  # Add spacing between groups
        item_layout.addLayout(quantity_layout)
        item_layout.addSpacing(20)
        item_layout.addLayout(mixed_pallet_layout)

        # *** Add Item Button ***
        add_item_button = QPushButton("Add Item")
        add_item_button.setObjectName("add_item_button")
        add_item_button.setToolTip("Click to add the item to the list.")
        add_item_button.setFixedWidth(100)  # Fixed width for consistency
        # Connect to the new wrapper method
        add_item_button.clicked.connect(self.on_add_item_clicked)
        item_layout.addSpacing(20)  # Space before the button
        item_layout.addWidget(add_item_button)

        layout.addWidget(item_section)

        # *** Items Table ***
        self.items_table = QTableView()
        self.items_table.setObjectName("items_table")
        self.items_table.setSelectionBehavior(QTableView.SelectRows)
        self.items_table.setSelectionMode(QTableView.SingleSelection)
        self.items_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.setMinimumHeight(300)
        self.items_table.setMaximumHeight(300)
        self.items_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(QLabel("<b>Items List</b>"))
        layout.addWidget(self.items_table)

        # *** Set Edit Triggers ***
        # Ensure that edits are committed when the user presses Enter or changes focus
        self.items_table.setEditTriggers(
            QAbstractItemView.DoubleClicked |
            QAbstractItemView.SelectedClicked |
            QAbstractItemView.EditKeyPressed |
            QAbstractItemView.AnyKeyPressed
        )

        # Initialize the mixed_pallet_model
        self.mixed_pallet_model = QStringListModel(self.parent.mixed_pallet_list)

        # Initialize the model with all required arguments
        self.items_model = ItemsTableModel(
            items=self.parent.data_manager.items,
            data_manager=self.parent.data_manager,
            mixed_pallet_list=self.parent.mixed_pallet_list,
            mixed_pallet_model=self.mixed_pallet_model,
            parent=self
        )

        # Set the model for the table
        self.items_table.setModel(self.items_model)

        # *** Set Delegates ***
        self.issue_delegate = IssueDelegate(parent=self.items_table)
        self.items_table.setItemDelegateForColumn(13, self.issue_delegate)
        self.issue_delegate.issueClicked.connect(self.parent.item_manager.on_issue_clicked)

        # Set custom delegate for Mixed Pallet Column (column index 7)
        mixed_pallet_delegate = MixedPalletDelegate(self.parent.mixed_pallet_list, self.items_table)
        self.items_table.setItemDelegateForColumn(7, mixed_pallet_delegate)

        # Connect signals
        self.items_table.clicked.connect(self.handle_table_click)

        # *** Adjust Column Widths ***
        self.adjust_column_widths()

        # *** Settings Section ***
        settings_section = QWidget()
        settings_layout = QVBoxLayout()
        settings_section.setLayout(settings_layout)
        layout.addWidget(QLabel("<b>Settings</b>"))
        layout.addWidget(settings_section)

        # *** Loading Plan Name Input and Set Name Button ***
        loading_plan_layout = QHBoxLayout()

        # Left alignment for the label
        label_layout = QHBoxLayout()
        label_layout.addWidget(QLabel("Loading Plan Name:"))
        label_layout.addStretch()  # Add stretch to push other widgets to the right

        # Right alignment for input, button, and current label
        right_layout = QHBoxLayout()

        self.loading_plan_name_input = QLineEdit()
        self.loading_plan_name_input.setPlaceholderText("Enter Loading Plan Name")
        self.loading_plan_name_input.setToolTip("Enter a name for the loading plan.")
        self.loading_plan_name_input.setFixedWidth(450)
        self.loading_plan_name_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        right_layout.addWidget(self.loading_plan_name_input)

        self.set_name_button = QPushButton("Set Name")
        self.set_name_button.setToolTip("Click to set the Loading Plan Name.")
        self.set_name_button.setFixedWidth(450)
        self.set_name_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.set_name_button.clicked.connect(self.handle_set_name)
        right_layout.addWidget(self.set_name_button)

        self.current_loading_plan_label = QLabel("Current Loading Plan: Not Set")
        self.current_loading_plan_label.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(self.current_loading_plan_label)

        # Combine left and right layouts
        loading_plan_layout.addLayout(label_layout)
        loading_plan_layout.addLayout(right_layout)

        settings_layout.addLayout(loading_plan_layout)

        # *** Margin Input and Set Margin Button ***
        margin_layout = QHBoxLayout()

        margin_label = QLabel("Margin (%):")
        self.margin_input = SelectableDoubleSpinBox()
        self.margin_input.setSuffix(" %")
        self.margin_input.setRange(0, 100)
        self.margin_input.setDecimals(2)
        self.margin_input.setValue(0)
        self.margin_input.setToolTip("Set the margin percentage.")
        margin_layout.addWidget(margin_label)
        margin_layout.addWidget(self.margin_input)

        self.set_margin_button = QPushButton("Set Margin")
        self.set_margin_button.setToolTip("Click to apply the margin percentage.")
        self.set_margin_button.clicked.connect(self.parent.set_margin)
        margin_layout.addWidget(self.set_margin_button)

        settings_layout.addLayout(margin_layout)

        # *** Container Selection Section ***
        container_section = QWidget()
        container_layout = QVBoxLayout()
        container_section.setLayout(container_layout)
        layout.addWidget(QLabel("<b>Container Selection</b>"))
        layout.addWidget(container_section)

        container_form_layout = QHBoxLayout()

        self.container_type_combo = QComboBox()
        self.container_type_combo.addItems(["Select...", "CNT - 20 ft", "CNT - 40 ft", "CNT - 40 ft hc", "Trailer - 13,6 m"])
        self.container_type_combo.setToolTip("Select a container type to add.")
        container_form_layout.addWidget(QLabel("Container Type:"))
        container_form_layout.addWidget(self.container_type_combo)

        self.add_container_button = QPushButton("Add Container")
        self.add_container_button.setObjectName("add_container_button")
        self.add_container_button.setToolTip("Click to add the selected container to the list.")
        self.add_container_button.clicked.connect(self.add_container)
        container_form_layout.addWidget(self.add_container_button)

        container_layout.addLayout(container_form_layout)

        # *** Container List Table ***
        self.container_table = QTableWidget()
        self.container_table.setColumnCount(5)
        self.container_table.setHorizontalHeaderLabels(["Container Type", "Length (cm)", "Width (cm)", "Height (cm)", "Delete"])
        self.container_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.container_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.container_table.verticalHeader().setVisible(False)
        self.container_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.container_table.setSelectionMode(QTableWidget.SingleSelection)

        # **Make the table shorter**
        self.container_table.setMinimumHeight(100)
        self.container_table.setMaximumHeight(100)
        self.container_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # **Optional: Set fixed row height**
        for row in range(self.container_table.rowCount()):
            self.container_table.setRowHeight(row, 25)

        container_layout.addWidget(self.container_table)

        # *** Action Buttons ***
        action_layout = QHBoxLayout()

        self.run_packing_button = QPushButton("Run Packing Algorithm")
        self.run_packing_button.setToolTip("Click to execute the packing algorithm.")
        self.run_packing_button.clicked.connect(self.parent.run_packing)
        action_layout.addWidget(self.run_packing_button)

        # Import Data Button
        self.import_data_button = QPushButton("Import Data")
        self.import_data_button.setToolTip("Click to import data using different methods.")
        self.import_data_button.clicked.connect(self.show_import_data_popup)
        action_layout.addWidget(self.import_data_button)

        export_button = QPushButton("Export Load Plan")
        export_button.setToolTip("Click to export the current load plan to a file.")
        export_button.clicked.connect(self.parent.export_data)
        action_layout.addWidget(export_button)

        product_settings_button = QPushButton("Product Settings")
        product_settings_button.setToolTip("Click to open product settings.")
        action_layout.addWidget(product_settings_button)
        product_settings_button.clicked.connect(self.show_product_settings)

        # *** Add "Open Manual" Button ***
        open_manual_button = QPushButton("Open Manual")
        open_manual_button.setToolTip("Click to open the user manual.")
        open_manual_button.clicked.connect(self.open_manual)
        action_layout.addWidget(open_manual_button)
        # *** End of "Open Manual" Button ***

        reset_button = QPushButton("Reset")
        reset_button.setToolTip("Click to reset all inputs and clear the visualization.")
        reset_button.clicked.connect(self.parent.reset_all)
        action_layout.addWidget(reset_button)

        layout.addLayout(action_layout)

        # *** Set Delegates for Split and Delete Columns ***
        split_delegate = ButtonDelegate(parent=self.items_table, button_type="Split")
        split_delegate.clicked.connect(self.items_model.splitRequested)
        self.items_table.setItemDelegateForColumn(11, split_delegate)  # Column index for "Split"

        delete_delegate = ButtonDelegate(parent=self.items_table, button_type="Delete")
        delete_delegate.clicked.connect(self.items_model.deleteRequested)
        self.items_table.setItemDelegateForColumn(12, delete_delegate)  # Column index for "Delete"

        # Connect the model's signals to the relevant functions
        self.items_model.splitRequested.connect(self.show_split_stack_dialog)
        self.items_model.deleteRequested.connect(self.parent.item_manager.delete_item_by_row)

        # *** Back to Visualization Button ***
        self.back_to_visualization_button = QPushButton("Back to Visualization")
        self.back_to_visualization_button.setToolTip("Click to return to the visualization page.")
        self.back_to_visualization_button.clicked.connect(self.parent.show_visualization_page)
        self.back_to_visualization_button.setEnabled(False)
        layout.addWidget(self.back_to_visualization_button)
        
    def adjust_column_widths(self):
        """Adjusts the column widths to make the 'Issue' column thinner and positioned at the far right."""
        header = self.items_table.horizontalHeader()
        for column in range(self.items_model.columnCount()):
            header_label = self.items_model.headers[column]
            if header_label == "Issue":
                header.setSectionResizeMode(column, QHeaderView.Fixed)
                header.resizeSection(column, 50)  # Set the desired width for 'Issue' column
            else:
                header.setSectionResizeMode(column, QHeaderView.Stretch)

    def raise_exception(self):
        raise RuntimeError("Intentional Exception for Logging Test")

    def add_container(self):
        """Adds the selected container to the container list."""
        container_type = self.container_type_combo.currentText()
        if container_type == "Select...":
            QMessageBox.warning(self, "Input Error", "Please select a valid container type.")
            return

        # Define container specifications based on type, including max_weight
        container_specs = {
            "CNT - 20 ft": {"length": 589.7, "width": 234.8, "height": 238.4, "max_weight": 28200},
            "CNT - 40 ft": {"length": 1203.1, "width": 234.8, "height": 238.4, "max_weight": 30480},
            "CNT - 40 ft hc": {"length": 1203.1, "width": 234.8, "height": 269.2, "max_weight": 30480},
            "Trailer - 13,6 m": {"length": 1360.0, "width": 244.0, "height": 265.0, "max_weight": 24000}
        }

        specs = container_specs.get(container_type)
        if not specs:
            QMessageBox.warning(self, "Input Error", "Unknown Container Type selected.")
            return

        # Add Container to DataManager
        new_container = Container(
            length=specs["length"],
            width=specs["width"],
            height=specs["height"],
            max_weight=specs["max_weight"],
            container_type=container_type  # Store the container type
        )
        self.parent.data_manager.containers.append(new_container)

        # Update container table
        self.update_container_table()

        # Emit signal that containers have been updated
        self.containers_updated.emit()

    def update_container_table(self):
        """Updates the container table to reflect the current list of containers."""
        self.container_table.setRowCount(0)
        for idx, container in enumerate(self.parent.data_manager.containers):
            row_position = self.container_table.rowCount()
            self.container_table.insertRow(row_position)

            # Container Type
            item_type = QTableWidgetItem(container.container_type)
            item_type.setTextAlignment(Qt.AlignCenter)
            self.container_table.setItem(row_position, 0, item_type)

            # Length (cm)
            item_length = QTableWidgetItem(str(container.length))
            item_length.setTextAlignment(Qt.AlignCenter)
            self.container_table.setItem(row_position, 1, item_length)

            # Width (cm)
            item_width = QTableWidgetItem(str(container.width))
            item_width.setTextAlignment(Qt.AlignCenter)
            self.container_table.setItem(row_position, 2, item_width)

            # Height (cm)
            item_height = QTableWidgetItem(str(container.height))
            item_height.setTextAlignment(Qt.AlignCenter)
            self.container_table.setItem(row_position, 3, item_height)

            # Add delete button
            delete_button = QPushButton("Delete")
            delete_button.clicked.connect(lambda _, idx=idx: self.delete_container(idx))
            self.container_table.setCellWidget(row_position, 4, delete_button)

    def delete_container(self, idx):
        """Deletes a container from the list and updates the table."""
        if idx < 0 or idx >= len(self.parent.data_manager.containers):
            QMessageBox.warning(
                self, "Delete Error",
                f"No container found at index '{idx}'."
            )
            return

        # Confirm deletion
        confirm = QMessageBox.question(
            self, "Delete Confirmation",
            f"Are you sure you want to delete container '{self.parent.data_manager.containers[idx].container_type}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            # Remove the container from the data manager's list
            del self.parent.data_manager.containers[idx]

            # Update the container table
            self.update_container_table()

            # Emit signal that containers have been updated
            self.containers_updated.emit()

    def update_items_table(self, items):
        """Updates the items model to reflect current items."""
        self.items_model.beginResetModel()
        self.items_model.items = items
        self.items_model.endResetModel()

    def handle_table_click(self, index):
        """Handles clicks on the items table."""
        if not index.isValid():
            return

        column = index.column()
        row = index.row()

    def show_custom_import_dialog(self):
        """Opens the Custom Import dialog."""
        dialog = CustomImportDialog(self.parent)
        dialog.exec_()

    def show_product_settings(self):
        """Navigates to the Product Settings page."""
        self.parent.show_product_settings_page()

    def show_split_stack_dialog(self, row):
        """Shows the Split Stack dialog for the given row."""
        item = self.parent.data_manager.items[row]
        current_quantity = item.quantity

        if current_quantity < 2:
            QMessageBox.warning(self, "Cannot Split", "Quantity must be at least 2 to split.")
            return

        # Create the split dialog
        self.split_dialog = QWidget(self)
        self.split_dialog.setWindowFlags(Qt.Popup)

        layout = QVBoxLayout()
        self.split_dialog.setLayout(layout)

        # Split Layout
        split_layout = QHBoxLayout()

        self.left_quantity_input = QSpinBox()
        self.left_quantity_input.setRange(1, current_quantity - 1)
        self.left_quantity_input.setValue(current_quantity // 2)
        self.left_quantity_input.setToolTip("Enter the quantity for the first split.")

        self.right_quantity_input = QSpinBox()
        self.right_quantity_input.setRange(1, current_quantity - 1)
        self.right_quantity_input.setValue(current_quantity - self.left_quantity_input.value())
        self.right_quantity_input.setToolTip("Enter the quantity for the second split.")

        self.left_quantity_input.valueChanged.connect(lambda val: self.update_split_quantities(current_quantity))
        self.right_quantity_input.valueChanged.connect(lambda val: self.update_split_quantities(current_quantity))

        split_layout.addWidget(QLabel("Left Quantity:"))
        split_layout.addWidget(self.left_quantity_input)

        self.split_slider = QSlider(Qt.Horizontal)
        self.split_slider.setRange(1, current_quantity - 1)
        self.split_slider.setValue(self.left_quantity_input.value())
        self.split_slider.setToolTip("Adjust the split using the slider.")
        self.split_slider.valueChanged.connect(lambda val: self.on_slider_value_changed(val, current_quantity))

        split_layout.addWidget(self.split_slider)

        split_layout.addWidget(QLabel("Right Quantity:"))
        split_layout.addWidget(self.right_quantity_input)

        layout.addLayout(split_layout)

        # Buttons
        button_layout = QHBoxLayout()
        cancel_button = QPushButton("Cancel")
        cancel_button.setToolTip("Click to cancel the split.")
        cancel_button.clicked.connect(self.split_dialog.close)
        split_button = QPushButton("Split")
        split_button.setToolTip("Click to perform the split.")
        split_button.clicked.connect(lambda: self.perform_split(row, current_quantity))

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(split_button)

        layout.addLayout(button_layout)

        # First, ensure the dialog has a size
        self.split_dialog.adjustSize()
        popup_width = self.split_dialog.width()
        popup_height = self.split_dialog.height()

        # Get the visual rectangle of the Split button's cell
        # Assuming the Split button is in column 11
        split_index = self.items_model.index(row, 11)  # Column index for "Split"
        split_rect = self.items_table.visualRect(split_index)

        # Map the rectangle to global coordinates
        split_global_pos = self.items_table.viewport().mapToGlobal(split_rect.bottomRight())

        # Calculate the new position to the left of the Split button
        x = split_global_pos.x() - popup_width - 10  # 10 pixels padding
        y = split_global_pos.y()

        # Ensure the popup doesn't go off the left edge of the screen
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        if x < screen_geometry.x():
            # If it goes off-screen, position it at the minimum x
            x = screen_geometry.x() + 10  # 10 pixels padding from the edge

        # Move the dialog to the new position
        self.split_dialog.move(x, y)

        # Show the dialog
        self.split_dialog.show()

    def update_split_quantities(self, total_quantity):
        """Updates quantities and slider when spin boxes change."""
        sender = self.sender()
        if sender == self.left_quantity_input:
            left_qty = self.left_quantity_input.value()
            right_qty = total_quantity - left_qty
            self.right_quantity_input.blockSignals(True)
            self.right_quantity_input.setValue(right_qty)
            self.right_quantity_input.blockSignals(False)
            self.split_slider.blockSignals(True)
            self.split_slider.setValue(left_qty)
            self.split_slider.blockSignals(False)
        elif sender == self.right_quantity_input:
            right_qty = self.right_quantity_input.value()
            left_qty = total_quantity - right_qty
            self.left_quantity_input.blockSignals(True)
            self.left_quantity_input.setValue(left_qty)
            self.left_quantity_input.blockSignals(False)
            self.split_slider.blockSignals(True)
            self.split_slider.setValue(left_qty)
            self.split_slider.blockSignals(False)

    def on_slider_value_changed(self, value, total_quantity):
        """Updates spin boxes when slider value changes."""
        left_qty = value
        right_qty = total_quantity - left_qty
        self.left_quantity_input.blockSignals(True)
        self.left_quantity_input.setValue(left_qty)
        self.left_quantity_input.blockSignals(False)
        self.right_quantity_input.blockSignals(True)
        self.right_quantity_input.setValue(right_qty)
        self.right_quantity_input.blockSignals(False)

    def perform_split(self, row, total_quantity):
        """Performs the split and updates the items."""
        left_qty = self.left_quantity_input.value()
        right_qty = self.right_quantity_input.value()

        if left_qty < 1 or right_qty < 1 or (left_qty + right_qty) != total_quantity:
            QMessageBox.warning(self, "Invalid Split", "Split quantities must add up to total quantity.")
            return

        self.split_dialog.close()

        # Inform ItemManager to perform the split
        self.parent.item_manager.split_item(row, left_qty, right_qty)

    def handle_set_name(self):
        name = self.loading_plan_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Loading Plan Name cannot be empty.")
            return
        # Emit the signal to send the name to MainWindow
        self.loading_plan_name_changed.emit(name)
        # Update this page’s label
        self.current_loading_plan_label.setText(f"Current Loading Plan: {name}")
        # Optionally clear the input field
        self.loading_plan_name_input.clear()

    def show_import_data_popup(self):
        """Displays a popup with Import Load Plan, Custom Import, and Import From Istia buttons."""
        popup = QWidget(self, Qt.Popup)
        popup.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        popup.setStyleSheet("background-color: white; border: 1px solid black;")
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)  # Add spacing between buttons
        popup.setLayout(layout)

        # Define a consistent style for buttons
        button_style = """
            QPushButton {
                padding: 10px 20px;
                font-size: 14px;
                border: 1px solid #ccc;
                border-radius: 5px;
                background-color: #f0f0f0;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """

        import_load_plan_btn = QPushButton("Import Load Plan")
        import_load_plan_btn.setToolTip("Click to import a load plan from a file.")
        import_load_plan_btn.setStyleSheet(button_style)
        import_load_plan_btn.setMinimumHeight(40)
        import_load_plan_btn.clicked.connect(lambda: [self.parent.import_data(), popup.close()])
        layout.addWidget(import_load_plan_btn)

        custom_import_btn = QPushButton("Custom Import")
        custom_import_btn.setToolTip("Click to perform a custom import.")
        custom_import_btn.setStyleSheet(button_style)
        custom_import_btn.setMinimumHeight(40)
        # Update the connection to open the CustomImportDialog
        custom_import_btn.clicked.connect(lambda: [self.show_custom_import_dialog(), popup.close()])
        layout.addWidget(custom_import_btn)

        # **Import From Istia Button**
        import_istia_btn = QPushButton("Import From Istia")
        import_istia_btn.setToolTip("Click to import data from Istia.")
        import_istia_btn.setStyleSheet(button_style)
        import_istia_btn.setMinimumHeight(40)
        import_istia_btn.clicked.connect(lambda: [self.parent.show_istia_import_page(), popup.close()])
        layout.addWidget(import_istia_btn)

        # Adjust the size of the popup based on its content
        popup.adjustSize()

        # Get the global position of the Import Data button
        button_pos = self.import_data_button.mapToGlobal(self.import_data_button.rect().topLeft())

        # Calculate the position to show the popup above the Import Data button
        popup_width = popup.width()
        popup_height = popup.height()
        button_width = self.import_data_button.width()

        x = button_pos.x() + (button_width - popup_width) // 2
        y = button_pos.y() - popup_height - 5  # 5 pixels above the button

        popup.move(x, y)
        popup.show()

    def open_manual(self):
        """Opens the user manual in the selected language."""
        # Create a dialog to ask for language selection
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Language")
        dialog.setModal(True)
        dialog.setFixedSize(300, 125)

        layout = QVBoxLayout()
        dialog.setLayout(layout)

        label = QLabel("Choose your language for the user manual:")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        button_layout = QHBoxLayout()

        english_button = QPushButton("English")
        english_button.clicked.connect(lambda: self.open_manual_file(dialog, 'English'))
        button_layout.addWidget(english_button)

        dutch_button = QPushButton("Dutch")
        dutch_button.clicked.connect(lambda: self.open_manual_file(dialog, 'Dutch'))
        button_layout.addWidget(dutch_button)

        layout.addLayout(button_layout)

        dialog.exec_()

    def open_manual_file(self, dialog, language):
        """Opens the manual file based on the selected language."""
        dialog.accept()  # Close the language selection dialog

        if language == 'English':
            manual_path = resource_path('Data/User Manual English.docx')
        elif language == 'Dutch':
            manual_path = resource_path('Data/User Manual Dutch.doc')
        else:
            QMessageBox.warning(self, "Unknown Language", "Selected language is not supported.")
            return

        if not os.path.exists(manual_path):
            QMessageBox.critical(self, "File Not Found", f"The manual file for {language} was not found.")
            return

        try:
            if sys.platform.startswith('darwin'):
                subprocess.call(('open', manual_path))
            elif os.name == 'nt':
                os.startfile(manual_path)
            elif os.name == 'posix':
                subprocess.call(('xdg-open', manual_path))
            else:
                QMessageBox.warning(self, "Unsupported OS", "Your operating system is not supported for opening files.")
        except Exception as e:
            QMessageBox.critical(self, "Error Opening File", f"An error occurred while opening the manual:\n{e}")

    def on_add_item_clicked(self):
        """Commits any pending edits and adds a new item."""
        # Commit any active edits in the items table
        if self.items_table.state() == QAbstractItemView.EditingState:
            editor = self.items_table.currentEditor()
            if editor:
                self.items_table.commitData(editor)
                self.items_table.closeEditor(editor, QAbstractItemView.NoHint)

        # Now proceed to add the item
        self.parent.item_manager.add_item()
