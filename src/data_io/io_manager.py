# src/data_io/io_manager.py

# Standard Library Imports
import json
import os
from pathlib import Path

# Third-party Imports
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import (
    QFileDialog, QMessageBox, QDialog, QVBoxLayout, QPushButton, 
    QLabel, QHBoxLayout, QTableWidgetItem
)

# Local Application Imports
from src.data_io.data_manager import DataManager
from src.models.models import Item, Container
from src.utilities.utils import get_permanent_directory, resource_path


class IOManager:
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def export_data(self, parent):
        """Exports items, containers, margin, Europallet, and loading_plan_name to a JSON or XLSX file."""
        # Validation Checks
        missing_conditions = []
        if not parent.loading_plan_name or parent.loading_plan_name.strip() == "":
            missing_conditions.append("Loading Plan Name is not set.")
        if not self.data_manager.containers:
            missing_conditions.append("No containers available.")
        if not self.data_manager.items:
            missing_conditions.append("No items available.")

        if missing_conditions:
            QMessageBox.warning(
                parent, 
                "Export Error", 
                "Cannot export due to the following issue(s):\n" + "\n".join(missing_conditions)
            )
            return  # Stop the export process

        # Create a custom dialog for selecting export format
        dialog = QDialog(parent)
        dialog.setWindowTitle("Select Export Format")
        dialog.setFixedSize(300, 100)

        layout = QVBoxLayout()

        label = QLabel("Choose export format:")
        layout.addWidget(label)

        button_layout = QHBoxLayout()

        excel_button = QPushButton("Excel")
        json_button = QPushButton("JSON")

        button_layout.addWidget(excel_button)
        button_layout.addWidget(json_button)

        layout.addLayout(button_layout)
        dialog.setLayout(layout)

        def export_excel():
            dialog.accept()
            self._export_to_excel(parent)

        def export_json():
            dialog.accept()
            self._export_to_json(parent)

        excel_button.clicked.connect(export_excel)
        json_button.clicked.connect(export_json)

        dialog.exec_()

    def _export_to_json(self, parent):
        """Exports the load plan to a JSON file using loading_plan_name as filename."""
        try:
            # Get the loading_plan_name from MainWindow
            loading_plan_name = parent.loading_plan_name
            if not loading_plan_name or loading_plan_name.strip() == "":
                QMessageBox.warning(parent, "Export Error", "Loading Plan Name is not set.")
                return

            # Sanitize loading_plan_name for filename (remove invalid characters)
            invalid_chars = '<>:"/\\|?*'
            for char in invalid_chars:
                loading_plan_name = loading_plan_name.replace(char, '_')

            # Set default directory
            default_directory = get_permanent_directory("Load Plans")

            # Ensure the directory exists
            os.makedirs(default_directory, exist_ok=True)

            # Create filename
            filename = os.path.join(default_directory, f"{loading_plan_name}.json")

            # Gather Containers
            containers_export = []
            for idx, container in enumerate(self.data_manager.containers, start=1):
                containers_export.append({
                    "Container ID": idx,
                    "Container Type": container.container_type,
                    "Length (cm)": container.length,
                    "Width (cm)": container.width,
                    "Height (cm)": container.height,
                    "Max Weight (kg)": container.max_weight
                })

            # Gather Items
            items_export = [
                {
                    "sku": item.sku,
                    "length": item.length,
                    "width": item.width,
                    "height": item.height,
                    "weight": item.weight,
                    "quantity": item.quantity,
                    "cartons": item.cartons,
                    "stackable": item.stackable,
                    "rotatable": item.rotatable,
                    "europallet": item.europallet,
                    "mixed_pallet": item.mixed_pallet
                } for item in self.data_manager.items
            ]

            # Gather Packed Containers
            packed_containers_export = []
            for packed_container in self.data_manager.packed_containers:
                packed_items = []
                for p_item in packed_container.packed_items:
                    packed_items.append({
                        "sku": p_item.sku,
                        "position": p_item.position,
                        "size": p_item.size,
                        "rotation": p_item.rotation,
                        "container_id": p_item.container_id,
                        "weight": p_item.weight
                    })
                packed_containers_export.append({
                    "container_id": packed_container.container_id,
                    "packed_items": packed_items
                })

            # Prepare Data Dictionary
            data = {
                "loading_plan_name": loading_plan_name,
                "margin": self.data_manager.margin_percentage,
                "containers": containers_export,
                "items": items_export,
                "packed_containers": packed_containers_export
            }

            # Write to JSON
            with open(filename, 'w') as file:
                json.dump(data, file, indent=4)

            QMessageBox.information(parent, "Export Successful", f"Load plan has been exported successfully as '{loading_plan_name}.json'.")

        except Exception as e:
            QMessageBox.critical(parent, "Export Error", f"An error occurred while exporting data:\n{e}")

    def _export_to_excel(self, parent):
        """Exports the load plan to an Excel file using loading_plan_name as filename."""
        try:
            # Get the loading_plan_name from MainWindow
            loading_plan_name = parent.loading_plan_name
            if not loading_plan_name or loading_plan_name.strip() == "":
                QMessageBox.warning(parent, "Export Error", "Loading Plan Name is not set.")
                return

            # Sanitize loading_plan_name for filename (remove invalid characters)
            invalid_chars = '<>:"/\\|?*'
            for char in invalid_chars:
                loading_plan_name = loading_plan_name.replace(char, '_')

            # Set default directory
            default_directory = get_permanent_directory("Load Plans")

            # Ensure the directory exists
            os.makedirs(default_directory, exist_ok=True)

            # Create filename
            filename = os.path.join(default_directory, f"{loading_plan_name}.xlsx")

            # Prepare Containers DataFrame
            containers_data = [
                {
                    "Container ID": idx,
                    "Container Type": container.container_type,
                    "Length (cm)": container.length,
                    "Width (cm)": container.width,
                    "Height (cm)": container.height,
                    "Max Weight (kg)": container.max_weight
                } for idx, container in enumerate(self.data_manager.containers, start=1)
            ]
            df_containers = pd.DataFrame(containers_data)

            # Prepare Items DataFrame
            items_data = [
                {
                    "SKU": item.sku,
                    "Length": item.length,
                    "Width": item.width,
                    "Height": item.height,
                    "Weight": item.weight,
                    "Quantity": item.quantity,
                    "Cartons": item.cartons,
                    "Stackable": item.stackable,
                    "Rotatable": item.rotatable,
                    "Europallet": item.europallet,
                    "Mixed Pallet": item.mixed_pallet
                } for item in self.data_manager.items
            ]
            df_items = pd.DataFrame(items_data)

            # Prepare Packed Containers DataFrame
            packed_containers_data = []
            for packed_container in self.data_manager.packed_containers:
                for p_item in packed_container.packed_items:
                    packed_containers_data.append({
                        "SKU": p_item.sku,
                        "Position (cm)": p_item.position,
                        "Size (cm)": p_item.size,
                        "Rotation (degrees)": p_item.rotation,
                        "Container ID": p_item.container_id,
                        "Weight (kg)": p_item.weight
                    })
            df_packed_containers = pd.DataFrame(packed_containers_data)

            # Prepare Metadata DataFrame
            metadata = {
                "Loading Plan Name": loading_plan_name,
                "Margin (%)": self.data_manager.margin_percentage
            }
            df_metadata = pd.DataFrame([metadata])

            # Write to Excel with multiple sheets
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df_metadata.to_excel(writer, sheet_name='Metadata', index=False)
                df_containers.to_excel(writer, sheet_name='Containers', index=False)
                df_items.to_excel(writer, sheet_name='Items', index=False)

                if not df_packed_containers.empty:
                    df_packed_containers.to_excel(writer, sheet_name='Packed Containers', index=False)
                else:
                    # Create an empty Packed Containers sheet if no data
                    df_empty = pd.DataFrame(columns=[
                        "SKU", "Position (cm)", "Size (cm)",
                        "Rotation (degrees)", "Container ID", "Weight (kg)"
                    ])
                    df_empty.to_excel(writer, sheet_name='Packed Containers', index=False)

            QMessageBox.information(parent, "Export Successful", f"Load plan has been exported successfully as '{loading_plan_name}.xlsx'.")

        except Exception as e:
            QMessageBox.critical(parent, "Export Error", f"An error occurred while exporting data:\n{e}")

    def import_data(self, parent):
        """
        Imports items, multiple container data, margin, Europallet, and loading_plan_name
        from a JSON or XLSX file. Also converts np.int64 and similar numeric fields into
        native Python types before further processing.
        """

        # Helper function that only converts numerical values (e.g., np.int64) to int.
        def convert_int64_to_int(obj):
            """
            Recursively walks through obj (dict or list) and converts any np.int64/np.integer
            to a built-in int and any np.float64/np.floating to a built-in float.
            Non-numerical data remains unchanged.
            """
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, (np.integer, np.int64)):
                        obj[key] = int(value)
                    elif isinstance(value, (np.floating, np.float64)):
                        obj[key] = float(value)
                    elif isinstance(value, (dict, list)):
                        obj[key] = convert_int64_to_int(value)
            elif isinstance(obj, list):
                for i, value in enumerate(obj):
                    if isinstance(value, (np.integer, np.int64)):
                        obj[i] = int(value)
                    elif isinstance(value, (np.floating, np.float64)):
                        obj[i] = float(value)
                    elif isinstance(value, (dict, list)):
                        obj[i] = convert_int64_to_int(value)
            return obj

        # File dialog setup
        options = QFileDialog.Options()
        default_path = get_permanent_directory("Load Plans")
        filename, _ = QFileDialog.getOpenFileName(
            parent,
            "Import Data",
            str(default_path),
            "JSON and Excel Files (*.json *.xlsx)",
            options=options
        )

        if filename:
            try:
                # Initialize a dict to hold all data
                data = {}

                # Load JSON or XLSX data into 'data' dict
                if filename.endswith('.json'):
                    with open(filename, 'r') as file:
                        data = json.load(file)

                elif filename.endswith('.xlsx'):
                    excel_file = pd.ExcelFile(filename, engine='openpyxl')
                    df_metadata = pd.read_excel(excel_file, sheet_name='Metadata')
                    df_containers = pd.read_excel(excel_file, sheet_name='Containers')
                    df_items = pd.read_excel(excel_file, sheet_name='Items')
                    df_packed_containers = pd.read_excel(excel_file, sheet_name='Packed Containers')

                    # Extract loading_plan_name and margin from 'Metadata'
                    if 'Loading Plan Name' in df_metadata.columns:
                        loading_plan_name = df_metadata['Loading Plan Name'].iloc[0]
                    else:
                        loading_plan_name = "Not Set"

                    if 'Margin (%)' in df_metadata.columns:
                        margin_val = df_metadata['Margin (%)'].iloc[0]
                    else:
                        margin_val = 0

                    # Convert the relevant sheets to dict format
                    containers_data = df_containers.to_dict(orient='records')
                    items_data = df_items.rename(
                        columns={
                            "SKU": "sku",
                            "Length": "length",
                            "Width": "width",
                            "Height": "height",
                            "Weight": "weight",
                            "Quantity": "quantity",
                            "Cartons": "cartons",
                            "Stackable": "stackable",
                            "Rotatable": "rotatable",
                            "Europallet": "europallet",
                            "Mixed Pallet": "mixed_pallet"
                        }
                    ).to_dict(orient="records")
                    packed_containers_data = df_packed_containers.to_dict(orient='records')

                    # Construct a single 'data' dict
                    data = {
                        "loading_plan_name": loading_plan_name,
                        "margin": margin_val,
                        "containers": containers_data,
                        "items": items_data,
                        "packed_containers": packed_containers_data
                    }

                # --- Use the helper function to convert numeric fields (np.int64, etc.) ---
                data = convert_int64_to_int(data)

                # Now proceed with loading the data into the application
                loading_plan_name = data.get("loading_plan_name", "Not Set")
                parent.set_loading_plan_name(loading_plan_name)

                self.data_manager.margin_percentage = data.get("margin", 0)
                parent.input_page.margin_input.setValue(self.data_manager.margin_percentage)

                containers = data.get("containers", [])
                if not containers:
                    QMessageBox.warning(parent, "Import Warning", "No containers found in the imported data.")
                else:
                    # Clear existing containers and the container table
                    self.data_manager.containers.clear()
                    parent.input_page.container_table.setRowCount(0)

                    for container in containers:
                        container_type = container.get("Container Type", "Unknown")
                        length = float(container.get("Length (cm)", 0))
                        width = float(container.get("Width (cm)", 0))
                        height = float(container.get("Height (cm)", 0))
                        max_weight = float(container.get("Max Weight (kg)", 0))

                        # Create the Container object
                        new_container = Container(
                            length=length,
                            width=width,
                            height=height,
                            max_weight=max_weight,
                            container_type=container_type
                        )
                        self.data_manager.containers.append(new_container)

                        # Insert into the container_table
                        row_position = parent.input_page.container_table.rowCount()
                        parent.input_page.container_table.insertRow(row_position)
                        parent.input_page.container_table.setItem(row_position, 0, QTableWidgetItem(container_type))
                        parent.input_page.container_table.setItem(row_position, 1, QTableWidgetItem(str(length)))
                        parent.input_page.container_table.setItem(row_position, 2, QTableWidgetItem(str(width)))
                        parent.input_page.container_table.setItem(row_position, 3, QTableWidgetItem(str(height)))

                        # Add a 'Delete' button
                        delete_button = QPushButton("Delete")
                        delete_button.setToolTip("Click to remove this container.")
                        delete_button.clicked.connect(
                            lambda checked, idx=len(self.data_manager.containers)-1: parent.input_page.delete_container(idx)
                        )
                        parent.input_page.container_table.setCellWidget(row_position, 4, delete_button)

                    # Emit signal that containers have been updated
                    parent.input_page.containers_updated.emit()

                items_data = data.get("items", [])
                if not items_data:
                    QMessageBox.warning(parent, "Import Warning", "No items found in the imported data.")
                else:
                    self.data_manager.items.clear()
                    for item in items_data:
                        europallet = item.get("europallet", False)
                        mixed_pallet = item.get("mixed_pallet", "")

                        # Handle potential NaN in 'mixed_pallet'
                        if isinstance(mixed_pallet, float) and np.isnan(mixed_pallet):
                            mixed_pallet = ""

                        loaded_item = Item(
                            sku=item["sku"],
                            length=item["length"],
                            width=item["width"],
                            height=item["height"],
                            weight=item["weight"],
                            quantity=item["quantity"],
                            cartons=item.get("cartons", 0),
                            stackable=item["stackable"],
                            rotatable=item.get("rotatable", True),
                            europallet=europallet,
                            mixed_pallet=mixed_pallet
                        )
                        self.data_manager.items.append(loaded_item)

                    # Assign colors to imported SKUs if not already assigned
                    for it in self.data_manager.items:
                        if it.sku not in self.data_manager.sku_color_map:
                            self.data_manager.sku_color_map[it.sku] = self.data_manager.generate_color_for_sku(it.sku)

                    # Update items table in GUI
                    parent.input_page.update_items_table(self.data_manager.items)

                # Successfully imported
                QMessageBox.information(parent, "Import Successful", "Load plan has been imported successfully.")

            except Exception as e:
                QMessageBox.critical(parent, "Import Error", f"An error occurred while importing data:\n{e}")
