# src/data_io/product_settings.py

# Standard Library Imports
import os
import shutil

# Third-party Imports
import pandas as pd
from PyQt5.QtCore import Qt, QAbstractTableModel, QVariant
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableView, 
    QMessageBox, QLabel, QHeaderView, QLineEdit
)

# Local Application Imports
from src.models.models import Item, Container
from src.utilities.utils import resource_path, get_permanent_directory


class PandasModel(QAbstractTableModel):
    """
    Model to interface a pandas DataFrame with Qt's QTableView.
    """

    def __init__(self, df=pd.DataFrame(), parent=None, read_only_columns=None, header_mapping=None):
        super().__init__(parent)
        self._df = df.copy()
        self.read_only_columns = read_only_columns if read_only_columns else []
        self.header_mapping = header_mapping if header_mapping else {}

    def rowCount(self, parent=None):
        return len(self._df.index)

    def columnCount(self, parent=None):
        return len(self._df.columns) if not self._df.columns.empty else 0

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return QVariant()

        row = self._df.index[index.row()]
        col = self._df.columns[index.column()]
        value = self._df.at[row, col]

        if role in (Qt.DisplayRole, Qt.EditRole):
            return "" if pd.isna(value) else str(value)

        return QVariant()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return QVariant()

        if orientation == Qt.Horizontal:
            original_header = self._df.columns[section]
            return self.header_mapping.get(original_header, original_header)
        elif orientation == Qt.Vertical:
            return str(self._df.index[section])

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        col = self._df.columns[index.column()]
        if col in self.read_only_columns:
            return Qt.ItemFlags(QAbstractTableModel.flags(self, index) & ~Qt.ItemIsEditable)
        return Qt.ItemFlags(QAbstractTableModel.flags(self, index) | Qt.ItemIsEditable)

    def setData(self, index, value, role=Qt.EditRole):
        if index.isValid() and role == Qt.EditRole:
            col = self._df.columns[index.column()]
            if col in self.read_only_columns:
                return False

            row = self._df.index[index.row()]
            try:
                # Handle empty input by keeping existing value
                if isinstance(value, str) and value.strip() == "":
                    cast_value = self._df.at[row, col]
                else:
                    if col in ["Rotatable", "Stackable"]:
                        val_lower = value.strip().lower()
                        if val_lower in ['t', 'yes', 'true', '1']:
                            cast_value = True
                        elif val_lower in ['f', 'no', 'false', '0']:
                            cast_value = False
                        else:
                            raise ValueError(f"Invalid input for '{col}': {value}")
                    else:
                        # Define maximum allowable values
                        max_values = {
                            'Width (W) [mm]': 10000,
                            'Height (H) [mm]': 10000,
                            'Total length (L) [mm]': 100000,
                            'Weight [g]': 1000000
                        }

                        if self._df[col].dtype == 'float64':
                            cast_value = float(value)
                        elif self._df[col].dtype == 'int64':
                            cast_value = int(value)
                        else:
                            cast_value = value  # For string types

                        # Prevent negative values
                        if cast_value < 0:
                            raise ValueError(f"'{col}' cannot be negative.")

                        # Prevent excessively high values
                        if col in max_values and cast_value > max_values[col]:
                            raise ValueError(f"'{col}' exceeds the maximum allowed value of {max_values[col]}.")

                self._df.at[row, col] = cast_value
                self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
                return True
            except ValueError as ve:
                QMessageBox.warning(
                    None,
                    "Invalid Input",
                    f"Cannot set value '{value}' for '{col}': {ve}"
                )
                return False
            except Exception as e:
                QMessageBox.warning(
                    None,
                    "Error",
                    f"An error occurred while setting data:\n{e}"
                )
                return False
        return False

    def get_dataframe(self):
        return self._df.copy()

    def set_dataframe(self, df):
        self.beginResetModel()
        self._df = df.copy()
        self.endResetModel()


class ProductSettingsPage(QWidget):
    """
    Page to view and edit Product data.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Product Settings")
        self.setMinimumSize(1200, 800)
        self.setMaximumSize(1600, 1200)

        layout = QVBoxLayout()
        self.setLayout(layout)

        instructions = QLabel("Edit the product data below. After making changes, click 'Confirm' to save.")
        instructions.setAlignment(Qt.AlignCenter)
        instructions.setFont(QFont("Arial", 16))
        layout.addWidget(instructions)

        # Add Search Bar
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        search_label.setFont(QFont("Arial", 12))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter Product Code or Product Name")
        self.search_button = QPushButton("Search")
        self.search_button.setToolTip("Click to search for a product.")
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)
        layout.addLayout(search_layout)

        # Load product data from DataManager
        self.product_data_df = self.parent.data_manager.product_data_df.copy()
        if self.product_data_df.empty:
            QMessageBox.critical(self, "Error", "Product data is empty or failed to load.")
            self.setEnabled(False)
            return

        self.product_data_df.reset_index(drop=True, inplace=True)

        self.header_mapping = {
            "ProductCode": "Product Code",
            "Product Name": "Product Name",
            "Width (W) [mm]": "Width (mm)",
            "Height (H) [mm]": "Height (mm)",
            "Total length (L) [mm]": "Total length (mm)",
            "Weight [g]": "Weight (g)",
            "Rotatable": "Rotatable",
            "Stackable": "Stackable"
        }

        self.table_view = QTableView()
        self.model = PandasModel(
            self.product_data_df,
            read_only_columns=["ProductCode", "Product Name"],
            header_mapping=self.header_mapping
        )
        self.table_view.setModel(self.model)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setSelectionMode(QTableView.SingleSelection)
        self.table_view.resizeColumnsToContents()
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.setAlternatingRowColors(True)
        layout.addWidget(self.table_view)

        # Hide "Category" column
        try:
            category_col_index = self.product_data_df.columns.get_loc("Category")
            self.table_view.hideColumn(category_col_index)
        except KeyError:
            QMessageBox.warning(self, "Warning", "The 'Category' column was not found and cannot be hidden.")

        # Adjust column widths
        self.adjust_column_widths()

        # Buttons
        button_layout = QHBoxLayout()
        self.confirm_button = QPushButton("Confirm")
        self.confirm_button.setToolTip("Click to save changes to Product data.xlsx.")
        self.confirm_button.clicked.connect(self.confirm_changes)
        button_layout.addWidget(self.confirm_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setToolTip("Click to discard changes and revert to original data.")
        self.cancel_button.clicked.connect(self.reject_changes)
        button_layout.addWidget(self.cancel_button)

        # **Add "Back to Default" Button**
        self.back_to_default_button = QPushButton("Back to Default")
        self.back_to_default_button.setToolTip("Reset Product data to default settings.")
        self.back_to_default_button.clicked.connect(self.back_to_default)
        button_layout.addWidget(self.back_to_default_button)

        layout.addLayout(button_layout)

        # Connect search signals
        self.search_button.clicked.connect(self.search_products)
        self.search_input.returnPressed.connect(self.search_products)

        # Initialize search tracking
        self.current_search_term = ""
        self.match_indices = []
        self.current_match = -1

    def adjust_column_widths(self):
        """Adjusts column widths: fixed for booleans and Product Name, stretch others."""
        header = self.table_view.horizontalHeader()
        total_columns = self.model.columnCount()

        boolean_columns = ["Rotatable", "Stackable"]
        product_name_column = "Product Name"

        boolean_width = 100
        product_name_width = 300

        for column in range(total_columns):
            original_header = self.model._df.columns[column]
            if original_header in boolean_columns:
                header.setSectionResizeMode(column, QHeaderView.Fixed)
                header.resizeSection(column, boolean_width)
            elif original_header == product_name_column:
                header.setSectionResizeMode(column, QHeaderView.Fixed)
                header.resizeSection(column, product_name_width)
            else:
                header.setSectionResizeMode(column, QHeaderView.Stretch)

    def confirm_changes(self):
        """Saves changes to the permanent Product data.xlsx via DataManager."""
        updated_df = self.model.get_dataframe()

        # Validate required columns are present
        required_columns = ["ProductCode", "Product Name", "Width (W) [mm]", "Height (H) [mm]",
                            "Total length (L) [mm]", "Weight [g]", "Rotatable", "Stackable", "Category"]
        if not all(col in updated_df.columns for col in required_columns):
            QMessageBox.critical(self, "Error", f"Missing required columns. Required columns are: {required_columns}")
            return

        try:
            # Update DataManager's product_data_df
            self.parent.data_manager.product_data_df = updated_df.copy()

            # Save changes via DataManager
            self.parent.data_manager.save_product_data()

            QMessageBox.information(self, "Success", "Product data has been successfully updated.")

            # Refresh UI components that depend on product data
            self.parent.refresh_ui_after_product_update()

            # Navigate back to Input Page
            self.parent.show_input_page()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save Product data:\n{e}")

    def reject_changes(self):
        """Discards changes and reloads data from DataManager."""
        confirm = QMessageBox.question(
            self,
            "Discard Changes",
            "Are you sure you want to discard all changes?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            try:
                # Reload product data from DataManager
                self.parent.data_manager.reload_product_data()

                # Update local DataFrame and model
                self.product_data_df = self.parent.data_manager.product_data_df.copy()
                self.model.set_dataframe(self.product_data_df)
                self.table_view.resizeColumnsToContents()
                self.adjust_column_widths()

                QMessageBox.information(self, "Changes Discarded", "All changes have been discarded.")

                # Navigate back to Input Page
                self.parent.show_input_page()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to reload Product data:\n{e}")

    def back_to_default(self):
        """Resets the Product data to default by delegating to DataManager."""
        # Step 1: Initial Confirmation
        confirm = QMessageBox.question(
            self,
            "Confirm Reset",
            "Are you sure you want to reset Product data to default? This will overwrite any current changes.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        # Step 2: Detailed Warning
        warning = QMessageBox.warning(
            self,
            "Warning",
            "Resetting will overwrite your current Product data with the default settings.\n"
            "All unsaved changes will be lost.",
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Cancel
        )
        if warning != QMessageBox.Ok:
            return

        # Step 3: Final Confirmation
        final_confirm = QMessageBox.question(
            self,
            "Final Confirmation",
            "This action cannot be undone. Do you want to proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if final_confirm != QMessageBox.Yes:
            return

        try:
            # Delegate reset to DataManager
            self.parent.data_manager.reset_product_data_to_default()

            # Reload product data from DataManager
            self.parent.data_manager.reload_product_data()

            # Update local DataFrame and model
            self.product_data_df = self.parent.data_manager.product_data_df.copy()
            self.model.set_dataframe(self.product_data_df)
            self.table_view.resizeColumnsToContents()
            self.adjust_column_widths()

            # Refresh UI components that depend on product data
            self.parent.refresh_ui_after_product_update()

            # Inform the User and Navigate Back
            QMessageBox.information(
                self,
                "Reset Complete",
                "Product data has been reset to default and reloaded."
            )
            self.parent.show_input_page()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to reset Product data:\n{e}"
            )

    def search_products(self):
        """Searches and navigates through matching products."""
        search_text = self.search_input.text().strip()
        if not search_text:
            QMessageBox.information(self, "Empty Search", "Please enter a search term.")
            return

        if search_text != self.current_search_term:
            # New search term
            self.current_search_term = search_text
            self.match_indices = self.product_data_df[
                self.product_data_df['ProductCode'].str.contains(search_text, case=False, na=False) |
                self.product_data_df['Product Name'].str.contains(search_text, case=False, na=False)
            ].index.tolist()
            self.current_match = -1

        if not self.match_indices:
            QMessageBox.information(self, "No Match", "No matching Product Code or Product Name found.")
            return

        # Move to next match
        self.current_match = (self.current_match + 1) % len(self.match_indices)
        row_number = self.match_indices[self.current_match]

        # Select and scroll to the row
        self.table_view.selectRow(row_number)
        model_index = self.model.index(row_number, 0)
        self.table_view.scrollTo(model_index, QTableView.PositionAtCenter)
