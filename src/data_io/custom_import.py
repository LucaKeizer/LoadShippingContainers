# src/data_io/custom_import.py 

# Standard Library Imports
import math  # For ceiling function
import os
import subprocess
import sys
import tempfile

# Third-party Imports
import pandas as pd
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QMessageBox
)

# Local Application Imports
from src.utilities.utils import get_permanent_directory


class CustomImportDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent  # Reference to MainWindow
        self.data_manager = parent.data_manager

        self.setWindowTitle("Custom Import")
        self.setFixedSize(450, 200)

        # **Remove only the Context Help button while keeping the Close ('X') button**
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout()
        self.setLayout(layout)

        # *** Instructions with increased font size ***
        instructions = QLabel(
            "1. Click 'Open Excel' to input your data.\n"
            "2. Enter data in the Excel window.\n"
            "3. Save and close the Excel window.\n"
            "4. Click 'Import Data' to import the entries."
        )
        instructions.setAlignment(Qt.AlignLeft)
        instructions.setWordWrap(True)
        instructions.setFont(QFont("Arial", 14))  # Increased font size
        layout.addWidget(instructions)

        button_layout = QHBoxLayout()

        self.open_excel_button = QPushButton("Open Excel")
        self.open_excel_button.setToolTip("Click to open the Excel window for data input.")
        self.open_excel_button.clicked.connect(self.open_excel)
        button_layout.addWidget(self.open_excel_button)

        self.import_data_button = QPushButton("Import Data")
        self.import_data_button.setToolTip("Click to import the data from the Excel file.")
        self.import_data_button.setEnabled(False)  # Disabled until Excel is opened
        self.import_data_button.clicked.connect(self.import_data)
        button_layout.addWidget(self.import_data_button)

        layout.addLayout(button_layout)

        # Initialize temporary file path
        self.temp_file_path = None

        # Load product data for lookups
        self.product_data_df = self.load_product_data()

    def load_product_data(self):
        # Ensure Product data.xlsx is loaded from the permanent directory
        permanent_dir = get_permanent_directory("DataFiles")
        product_data_path = os.path.join(permanent_dir, "Product data.xlsx")

        if not os.path.exists(product_data_path):
            QMessageBox.critical(self, "Data Error", "Product data file not found.")
            return pd.DataFrame()

        try:
            # Load product data
            df = pd.read_excel(product_data_path, dtype={'ProductCode': str, 'Category': str})
            return df
        except Exception as e:
            QMessageBox.critical(self, "Data Error", f"Failed to load product data:\n{e}")
            return pd.DataFrame()

    def open_excel(self):
        """Creates a temporary Excel file with headers and opens it in the default Excel application."""
        try:
            # Create a temporary file
            fd, self.temp_file_path = tempfile.mkstemp(suffix='.xlsx')
            os.close(fd)  # Close the file descriptor

            # Define headers
            headers = ["Product Code", "Quantity", "Europallet", "Mixed Pallet"]

            # Create an empty DataFrame with headers
            df = pd.DataFrame(columns=headers)

            # Save the empty DataFrame to the temporary Excel file with specified column widths
            with pd.ExcelWriter(self.temp_file_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Custom Import')

                # Access the workbook and worksheet to set column widths
                workbook = writer.book
                worksheet = writer.sheets['Custom Import']

                # Set column widths
                column_widths = {
                    'A': 13,  # Product Code
                    'B': 9,   # Quantity
                    'C': 11,  # Europallet
                    'D': 13   # Mixed Pallet
                }

                for col, width in column_widths.items():
                    worksheet.column_dimensions[col].width = width

            # Open the Excel file with the default application
            if sys.platform.startswith('darwin'):
                subprocess.call(('open', self.temp_file_path))
            elif os.name == 'nt':
                os.startfile(self.temp_file_path)
            elif os.name == 'posix':
                subprocess.call(('xdg-open', self.temp_file_path))
            else:
                QMessageBox.warning(self, "Unsupported OS", "Your operating system is not supported for opening files.")
                return

            # Enable the Import Data button
            self.import_data_button.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while opening Excel:\n{e}")
            if self.temp_file_path and os.path.exists(self.temp_file_path):
                os.remove(self.temp_file_path)
            self.temp_file_path = None

    def import_data(self):
        """Imports data from the temporary Excel file into the application."""
        if not self.temp_file_path or not os.path.exists(self.temp_file_path):
            QMessageBox.warning(self, "Import Error", "No Excel file found to import.")
            return

        try:
            # Read the Excel file
            df = pd.read_excel(self.temp_file_path, dtype={
                'Product Code': str,
                'Quantity': float,
                'Europallet': str,
                'Mixed Pallet': str
            })

            # Validate required columns
            required_columns = ["Product Code", "Quantity", "Europallet", "Mixed Pallet"]
            for col in required_columns:
                if col not in df.columns:
                    QMessageBox.critical(self, "Import Error", f"Missing required column: '{col}'.")
                    return

            # Drop rows where 'Product Code' is missing
            df = df.dropna(subset=["Product Code"])

            new_items = []
            errors = []

            for index, row in df.iterrows():
                product_code = str(row["Product Code"]).strip()
                quantity = row["Quantity"] if not pd.isna(row["Quantity"]) else 1  # Default to 1
                europallet_str = str(row["Europallet"]).strip().lower() if not pd.isna(row["Europallet"]) else "no"
                europallet = True if europallet_str in ["yes", "true", "1"] else False
                mixed_pallet = str(row["Mixed Pallet"]).strip() if not pd.isna(row["Mixed Pallet"]) else ""  # Default to None

                # Validate quantity
                if not isinstance(quantity, (int, float)) or quantity < 1:
                    errors.append(f"Row {index + 2}: Invalid quantity '{quantity}'. Defaulting to 1.")
                    quantity = 1  # Default to 1

                # Lookup product data
                matched = self.product_data_df[
                    self.product_data_df['ProductCode'].str.strip().str.lower() == product_code.lower()
                ]
                if matched.empty:
                    errors.append(f"Row {index + 2}: Product Code '{product_code}' not found in product data. Skipping.")
                    continue

                # Extract required fields from product_data_df
                length_mm = matched['Total length (L) [mm]'].iloc[0]
                width_mm = matched['Width (W) [mm]'].iloc[0]
                height_mm = matched['Height (H) [mm]'].iloc[0]
                weight_g = matched['Weight [g]'].iloc[0]
                rotatable = matched['Rotatable'].iloc[0]
                stackable = matched['Stackable'].iloc[0]
                # qty_per_carton will be fetched using get_qty_per_carton()

                # Convert units
                length_cm = length_mm / 10.0
                width_cm = width_mm / 10.0
                height_cm = height_mm / 10.0
                weight_kg = weight_g / 1000.0

                # Convert rotatable and stackable to bool
                rotatable_bool = self.to_bool(rotatable)
                stackable_bool = self.to_bool(stackable)

                # **Automatically Calculate Cartons Using data_manager.calculate_cartons()**
                qty_per_carton = self.data_manager.get_qty_per_carton(product_code)
                if qty_per_carton > 0:
                    ideal_cartons = self.data_manager.calculate_cartons(quantity, qty_per_carton)
                else:
                    ideal_cartons = 0  # Assign 0 if QTY Per Carton is not defined

                # Create the item
                from src.models.models import Item

                item = Item(
                    sku=product_code,
                    length=length_cm,
                    width=width_cm,
                    height=height_cm,
                    weight=weight_kg,
                    quantity=int(quantity),
                    stackable=stackable_bool,
                    rotatable=rotatable_bool,
                    europallet=europallet,
                    mixed_pallet=mixed_pallet,
                    cartons=ideal_cartons
                )

                new_items.append(item)

            if errors:
                error_message = "\n".join(errors)
                QMessageBox.warning(self, "Import Warnings", f"The following issues were found during import:\n{error_message}")

            if not new_items:
                QMessageBox.warning(self, "No Items Imported", "No valid items were found or imported.")
            else:
                # **Post-Import Carton and Remainder Issue Checks**
                for item in new_items:
                    # Initialize issue flags
                    item.has_carton_issue = False
                    item.has_remainder_issue = False

                    # Only check if not a mixed pallet item and has cartons
                    if not item.mixed_pallet and item.cartons > 0:
                        base_sku = self.data_manager.get_base_sku(item.sku)
                        qty_per_carton = self.data_manager.get_qty_per_carton(item.sku)
                        if qty_per_carton > 0:
                            # Calculate ideal cartons again for verification
                            ideal_cartons = self.data_manager.calculate_cartons(item.quantity, qty_per_carton)
                            if item.cartons != ideal_cartons:
                                item.has_carton_issue = True
                            else:
                                item.has_carton_issue = False

                            # Check for remainder
                            if item.quantity % qty_per_carton != 0:
                                item.has_remainder_issue = True
                            else:
                                item.has_remainder_issue = False
                        else:
                            # If QTY Per Carton is not defined, assume no issues
                            item.has_carton_issue = False
                            item.has_remainder_issue = False

                # **Append these new items to the data_manager items**
                self.data_manager.items.extend(new_items)

                # Assign colors for newly added SKUs
                for it in new_items:
                    if it.sku not in self.data_manager.sku_color_map:
                        self.data_manager.sku_color_map[it.sku] = self.data_manager.generate_color_for_sku(it.sku)

                # Update items table
                self.parent.input_page.update_items_table(self.data_manager.items)

                # Invalidate Packed Data
                self.data_manager.packed_containers = []
                self.parent.input_page.back_to_visualization_button.setEnabled(False)

                QMessageBox.information(self, "Import Successful", f"{len(new_items)} items have been successfully imported and carton/remainder issues have been checked.")

            # Clean up: delete the temporary file
            os.remove(self.temp_file_path)
            self.temp_file_path = None
            self.import_data_button.setEnabled(False)

            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"An error occurred during import:\n{e}")

    def to_bool(self, val):
        """Convert various representations of booleans to Python bool."""
        true_values = ['yes', 'true', 'y', '1', True]
        # Convert val to string for uniformity
        val_str = str(val).strip().lower()
        return val_str in true_values

    def calculate_cartons(self, quantity, qty_per_carton):
        """Calculate the number of cartons based on quantity and QTY Per Carton."""
        if qty_per_carton <= 0:
            return 0
        return math.ceil(quantity / qty_per_carton)
