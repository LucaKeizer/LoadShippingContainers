# src/utilities/istia_import.py

# Standard Library Imports
import logging
import os
import re  # For splitting input
import math
import requests

# Third-party Imports
import pandas as pd
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QMutex, QEvent
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, 
    QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView, 
    QProgressBar, QProgressDialog, QPlainTextEdit, QDialog, QApplication
)

# Local Application Imports
from src.models.models import Item, Container
from src.utilities.utils import get_permanent_directory, resource_path


# Global variable to cache order_monitor data
order_monitor_cache = None
order_monitor_mutex = QMutex()  # Mutex to ensure thread safety


def run_fabric_query(sql: str) -> pd.DataFrame:
    """
    Execute a query against the Data Warehouse API.
    
    Args:
        sql: SQL query string to execute
        
    Returns:
        pandas DataFrame with the query results
    """
    API_BASE_URL = "test/api"  # Replace with actual API base URL"
    url = f"{API_BASE_URL}/query"
    payload = {"query": sql}
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        if isinstance(data, list):
            return pd.DataFrame(data)
        else:
            logging.error(f"Unexpected response format: {data}")
            return pd.DataFrame()
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {e}")
        return pd.DataFrame()
        
    except Exception as e:
        logging.error(f"Error parsing response: {e}")
        return pd.DataFrame()


class DataFetchThread(QThread):
    """
    Thread to fetch data from the data warehouse API to prevent UI blocking.
    """
    data_fetched = pyqtSignal(pd.DataFrame)
    error_occurred = pyqtSignal(str)

    def __init__(self, transport_order_codes, order_numbers, parent=None):
        super().__init__(parent)
        self.transport_order_codes = transport_order_codes  # List of transport order codes
        self.order_numbers = order_numbers  # List of order numbers
        self.parent = parent  # Reference to IstiaImportPage

    def run(self):
        global order_monitor_cache, order_monitor_mutex
        try:
            # Acquire mutex to ensure thread safety when accessing the cache
            order_monitor_mutex.lock()
            
            # We're not using full cache anymore since we're filtering at query level
            # Instead, we'll check if we have an empty search
            if not self.transport_order_codes and not self.order_numbers:
                order_monitor_mutex.unlock()
                self.error_occurred.emit("No transport order codes or order numbers provided.")
                return
                
            order_monitor_mutex.unlock()

            # Build the query with filtering directly in SQL
            # Escape quotes in the list items for SQL
            to_codes_formatted = ", ".join(["'" + code.replace("'", "''") + "'" for code in self.transport_order_codes])
            order_numbers_formatted = ", ".join(["'" + num.replace("'", "''") + "'" for num in self.order_numbers])
            
            # Construct the WHERE clause based on provided parameters
            where_clause = []
            if self.transport_order_codes:
                where_clause.append(f"Transport_order_number IN ({to_codes_formatted})")
            if self.order_numbers:
                where_clause.append(f"Order_number IN ({order_numbers_formatted})")
                
            where_statement = " OR ".join(where_clause)
            
            # Build and execute the query
            query = f"""
                SELECT Transport_order_number, Order_number, ProductCode, Qty_ordered
                FROM [SONIC_Warehouse].[dbo].[FACT_ORDERMONITOR]
                WHERE {where_statement}
            """
            
            # Execute the query using the API
            order_monitor = run_fabric_query(query)

            if order_monitor.empty:
                self.data_fetched.emit(pd.DataFrame())
                return

            # Ensure 'Transport_order_number' and 'Order_number' are treated as strings
            if 'Transport_order_number' in order_monitor.columns:
                order_monitor['Transport_order_number'] = order_monitor['Transport_order_number'].astype(str)
            else:
                raise ValueError("Column 'Transport_order_number' not found in the fetched data.")

            if 'Order_number' in order_monitor.columns:
                order_monitor['Order_number'] = order_monitor['Order_number'].astype(str)
            else:
                raise ValueError("Column 'Order_number' not found in the fetched data.")

            # Use product_data from DataManager
            product_data = self.parent.parent.data_manager.product_data_df
            required_columns = ["ProductCode", "Width (W) [mm]", "Height (H) [mm]", "Total length (L) [mm]", "Weight [g]", "Rotatable", "Stackable", "Europallet"]
            if not all(col in product_data.columns for col in required_columns):
                raise ValueError(f"Product data is missing required columns: {required_columns}")

            # Ensure 'ProductCode' is treated as string
            product_data['ProductCode'] = product_data['ProductCode'].astype(str)

            # Merge filtered_order_monitor with product_data to get dimensions, weight, rotatable, and stackable
            merged_data = pd.merge(order_monitor, product_data, on='ProductCode', how='left')

            # Drop rows with missing dimension data
            merged_data = merged_data.dropna(subset=['Width (W) [mm]', 'Height (H) [mm]', 'Total length (L) [mm]', 'Weight [g]'])

            # Select and rename columns, including Quantity, Rotatable, and Stackable
            columns_of_interest = {
                "ProductCode": "Product Code",
                "Transport_order_number": "Transport Order Number",
                "Order_number": "Order Number",
                "Height (H) [mm]": "Height (cm)",
                "Total length (L) [mm]": "Length (cm)",
                "Width (W) [mm]": "Width (cm)",
                "Weight [g]": "Weight (kg)",
                "Qty_ordered": "Quantity",
                "Rotatable": "Rotatable",
                "Stackable": "Stackable",
                "Europallet": "Europallet"
            }

            # Check if 'Qty_ordered' exists
            if 'Qty_ordered' not in merged_data.columns:
                raise ValueError("Column 'Qty_ordered' not found in the fetched data.")

            enriched_data = merged_data[list(columns_of_interest.keys())].rename(columns=columns_of_interest)

            # Convert units
            enriched_data["Height (cm)"] = enriched_data["Height (cm)"] / 10  # mm to cm
            enriched_data["Length (cm)"] = enriched_data["Length (cm)"] / 10  # mm to cm
            enriched_data["Width (cm)"] = enriched_data["Width (cm)"] / 10    # mm to cm
            enriched_data["Weight (kg)"] = enriched_data["Weight (kg)"] / 1000  # g to kg
            enriched_data["Quantity"] = enriched_data["Quantity"].astype(int)  # Ensure Quantity is integer

            # Convert 'Rotatable' to boolean
            enriched_data["Rotatable"] = enriched_data["Rotatable"].map({
                'YES': True, 'YES.': True, 'Y': True, 'TRUE': True, True: True, '1': True,
                'NO': False, 'NO.': False, 'N': False, 'FALSE': False, False: False, '0': False
            })
            enriched_data["Rotatable"] = enriched_data["Rotatable"].fillna(False)

            # Convert 'Stackable' to boolean
            enriched_data["Stackable"] = enriched_data["Stackable"].map({
                'YES': True, 'YES.': True, 'Y': True, 'TRUE': True, True: True, '1': True,
                'NO': False, 'NO.': False, 'N': False, 'FALSE': False, False: False, '0': False
            })
            enriched_data["Stackable"] = enriched_data["Stackable"].fillna(False)

            # Convert 'Europallet' to boolean
            enriched_data["Europallet"] = enriched_data["Europallet"].map({
                'YES': True, 'YES.': True, 'Y': True, 'TRUE': True, True: True, '1': True,
                'NO': False, 'NO.': False, 'N': False, 'FALSE': False, False: False, '0': False
            })
            enriched_data["Europallet"] = enriched_data["Europallet"].fillna(False)

            # Rearrange columns to include 'Transport Order Number', 'Order Number', 'Rotatable', and 'Stackable'
            enriched_data = enriched_data[[
                "Transport Order Number", "Order Number", "Product Code", 
                "Height (cm)", "Length (cm)", "Width (cm)", "Weight (kg)", 
                "Quantity", "Rotatable", "Stackable", "Europallet"
            ]]

            self.data_fetched.emit(enriched_data)

        except Exception as e:
            logging.error("Error fetching data", exc_info=True)
            self.error_occurred.emit(str(e))
            if order_monitor_mutex.isLocked():
                order_monitor_mutex.unlock()  # Ensure mutex is unlocked in case of error


class IstiaImportPage(QWidget):
    """
    Page for importing data from Istia.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent  # Reference to MainWindow
        self.fetched_data = pd.DataFrame()  # To keep track of all fetched data

        self.fetching_dialog = None  # Initialize fetching dialog as None
        self.import_dialog = None  # Initialize import dialog as None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Instruction Label
        layout.addWidget(QLabel("<b>Import Istia Order Data</b>"))

        # Order Codes Input
        form_layout = QFormLayout()

        self.transport_order_input = QPlainTextEdit()
        self.transport_order_input.setPlaceholderText("Enter Transport Order Numbers, separated by commas or new lines.")
        form_layout.addRow("Transport Order Numbers:", self.transport_order_input)

        self.order_number_input = QPlainTextEdit()
        self.order_number_input.setPlaceholderText("Enter Order Numbers, separated by commas or new lines.")
        form_layout.addRow("Order Numbers:", self.order_number_input)

        layout.addLayout(form_layout)

        # Fetch Data Button
        fetch_button = QPushButton("Fetch Data")
        fetch_button.clicked.connect(self.fetch_data)
        layout.addWidget(fetch_button)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Table to Display Data
        self.data_table = QTableWidget()
        self.data_table.setColumnCount(12)
        self.data_table.setHorizontalHeaderLabels([
            "TO Number", "Order Number", "Product Code", 
            "Height (cm)", "Length (cm)", "Width (cm)", "Weight (kg)", 
            "Quantity", "Cartons", "Rotatable", "Stackable", "Europallet"
        ])
        self.data_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.data_table.verticalHeader().setVisible(False)
        layout.addWidget(QLabel("<b>Fetched Order Data</b>"))
        layout.addWidget(self.data_table)

        # Confirmation Button
        confirm_button = QPushButton("Confirm Import")
        confirm_button.clicked.connect(self.confirm_import)
        layout.addWidget(confirm_button)

        # Back Button
        back_button = QPushButton("Back to Input")
        back_button.clicked.connect(self.parent.show_input_page)
        layout.addWidget(back_button)

        # Stretch to push everything to the top
        layout.addStretch()

    def fetch_data(self):
        """Fetches data from Istia based on the provided transport order codes and order numbers."""
        transport_order_text = self.transport_order_input.toPlainText().strip()
        order_number_text = self.order_number_input.toPlainText().strip()

        transport_order_codes = re.split(r'[,\n]+', transport_order_text)
        transport_order_codes = [code.strip() for code in transport_order_codes if code.strip()]

        order_numbers = re.split(r'[,\n]+', order_number_text)
        order_numbers = [num.strip() for num in order_numbers if num.strip()]

        if not transport_order_codes and not order_numbers:
            QMessageBox.warning(self, "Input Error", "Please enter at least one Transport Order Number or Order Number.")
            return

        # **Clear the Input Areas after fetching the codes**
        self.transport_order_input.clear()
        self.order_number_input.clear()

        # Initialize and show the fetching dialog with progress
        total_codes = len(transport_order_codes) + len(order_numbers)
        self.fetching_dialog = QProgressDialog(f"Fetching data for {total_codes} codes...", None, 0, total_codes, self)
        self.fetching_dialog.setWindowTitle("Fetching Data")
        self.fetching_dialog.setWindowModality(Qt.WindowModal)
        self.fetching_dialog.show()

        # Initialize and start the data fetch thread
        self.thread = DataFetchThread(transport_order_codes, order_numbers, parent=self)
        self.thread.data_fetched.connect(self.on_data_fetched)
        self.thread.error_occurred.connect(self.on_error)
        self.thread.start()

    def on_data_fetched(self, data):
        """Handles the data fetched from the database."""
        # Close the fetching dialog if it's open
        if self.fetching_dialog:
            self.fetching_dialog.close()
            self.fetching_dialog = None

        if data.empty:
            QMessageBox.information(self, "No Data", "No data found for the specified codes.")
            return

        # Assign 'Cartons' based on QTY Per Carton
        data['Cartons'] = data.apply(
            lambda row: self.parent.data_manager.calculate_cartons(
                row['Quantity'], 
                self.parent.data_manager.get_qty_per_carton(row['Product Code'])
            ) if self.parent.data_manager.get_qty_per_carton(row['Product Code']) > 0 else 0,
            axis=1
        )

        # Append to the fetched_data DataFrame
        self.fetched_data = pd.concat([self.fetched_data, data], ignore_index=True)

        # Remove potential duplicates based on Transport Order Number, Order Number, and Product Code
        self.fetched_data.drop_duplicates(subset=["Transport Order Number", "Order Number", "Product Code"], inplace=True)

        # Populate the table
        self.populate_table()

        # Show the "Data Fetched" message
        QMessageBox.information(
            self, 
            "Data Fetched", 
            f"Data for {len(data['Product Code'].unique())} unique products has been fetched successfully and added to the table."
        )

    def on_error(self, error_message):
        """Handles errors that occur during data fetching."""
        # Close the fetching dialog if it's open
        if self.fetching_dialog:
            self.fetching_dialog.close()
            self.fetching_dialog = None

        QMessageBox.critical(self, "Error", f"An error occurred while fetching data:\n{error_message}")

    def populate_table(self):
        """Populates the data table with the accumulated fetched data."""
        self.data_table.setRowCount(0)
        for index, row in self.fetched_data.iterrows():
            row_position = self.data_table.rowCount()
            self.data_table.insertRow(row_position)
            self.data_table.setItem(row_position, 0, QTableWidgetItem(str(row["Transport Order Number"])))
            self.data_table.setItem(row_position, 1, QTableWidgetItem(str(row["Order Number"])))
            self.data_table.setItem(row_position, 2, QTableWidgetItem(str(row["Product Code"])))
            self.data_table.setItem(row_position, 3, QTableWidgetItem(f"{row['Height (cm)']:.2f}"))
            self.data_table.setItem(row_position, 4, QTableWidgetItem(f"{row['Length (cm)']:.2f}"))
            self.data_table.setItem(row_position, 5, QTableWidgetItem(f"{row['Width (cm)']:.2f}"))
            self.data_table.setItem(row_position, 6, QTableWidgetItem(f"{row['Weight (kg)']:.3f}"))
            self.data_table.setItem(row_position, 7, QTableWidgetItem(str(row["Quantity"])))
            self.data_table.setItem(row_position, 8, QTableWidgetItem(str(row["Cartons"])))  # Cartons
            self.data_table.setItem(row_position, 9, QTableWidgetItem("Yes" if row["Rotatable"] else "No"))  # Rotatable
            self.data_table.setItem(row_position, 10, QTableWidgetItem("Yes" if row["Stackable"] else "No"))  # Stackable
            self.data_table.setItem(row_position, 11, QTableWidgetItem("Yes" if row["Europallet"] else "No"))  # Europallet

    def confirm_import(self):
        """Confirms the import of the fetched data into the application."""
        if self.fetched_data.empty:
            QMessageBox.warning(self, "No Data", "There is no data to import.")
            return

        # Confirm with the user
        confirm = QMessageBox.question(
            self, "Confirm Import",
            "Are you sure you want to import the fetched data?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            try:
                # Collect all items to be imported
                items_to_import = []
                total_items = len(self.fetched_data)
                progress_dialog = QProgressDialog("Importing items...", "Cancel", 0, total_items, self)
                progress_dialog.setWindowTitle("Import Progress")
                progress_dialog.setWindowModality(Qt.WindowModal)
                progress_dialog.setMinimumDuration(0)
                progress_dialog.setValue(0)
                progress_dialog.show()

                for idx, (index, row) in enumerate(self.fetched_data.iterrows()):
                    sku = str(row["Product Code"])
                    height = float(row["Height (cm)"])
                    length = float(row["Length (cm)"])
                    width = float(row["Width (cm)"])
                    weight = float(row["Weight (kg)"])
                    quantity = int(row["Quantity"])
                    cartons = int(row["Cartons"])
                    transport_order = str(row["Transport Order Number"])
                    order_number = str(row["Order Number"])
                    rotatable = row["Rotatable"]
                    stackable = row["Stackable"]

                    # Create the Item instance
                    item = Item(
                        sku=sku,
                        length=length,
                        width=width,
                        height=height,
                        weight=weight,
                        quantity=quantity,
                        stackable=stackable,
                        rotatable=rotatable,
                        transport_order=transport_order
                        # Add order_number to Item class if needed
                    )
                    item.cartons = cartons
                    item.has_carton_issue = False
                    item.has_remainder_issue = False

                    # **Carton Issue Check**
                    base_sku = self.parent.data_manager.get_base_sku(sku)
                    matched_row = self.parent.data_manager.carton_dimensions_df[
                        self.parent.data_manager.carton_dimensions_df['Product Code'] == base_sku
                    ]
                    if not matched_row.empty:
                        qty_per_carton = matched_row['QTY Per Carton'].iloc[0]
                        if qty_per_carton > 0:
                            ideal_cartons = math.ceil(quantity / qty_per_carton)
                            if cartons != ideal_cartons:
                                item.has_carton_issue = True
                            else:
                                item.has_carton_issue = False

                            # **Remainder Issue Check**
                            if quantity % qty_per_carton != 0:
                                item.has_remainder_issue = True
                            else:
                                item.has_remainder_issue = False
                        else:
                            item.has_carton_issue = False
                            item.has_remainder_issue = False
                    else:
                        item.has_carton_issue = False
                        item.has_remainder_issue = False  # Cannot determine, assume no issue

                    items_to_import.append(item)

                    # Update progress
                    progress_dialog.setValue(idx + 1)
                    QApplication.processEvents()
                    if progress_dialog.wasCanceled():
                        QMessageBox.information(self, "Import Canceled", "The import operation was canceled.")
                        return

                # Close the progress dialog
                progress_dialog.close()

                # Add all imported items to data_manager
                for item in items_to_import:
                    self.parent.data_manager.items.append(item)
                    if item.sku not in self.parent.data_manager.sku_color_map:
                        self.parent.data_manager.sku_color_map[item.sku] = self.parent.data_manager.generate_color_for_sku(item.sku)

                # Update the items table in InputPage
                self.parent.input_page.update_items_table(self.parent.data_manager.items)

                # Clear the fetched_data and table after successful import
                self.fetched_data = pd.DataFrame()
                self.data_table.setRowCount(0)

                # Redirect to Input Page
                self.parent.show_input_page()

                # Show confirmation message
                QMessageBox.information(
                    self, "Import Successful",
                    "Items have been successfully imported."
                )

            except Exception as e:
                logging.error("Error during import", exc_info=True)
                QMessageBox.critical(self, "Import Error", f"An error occurred during import:\n{e}")