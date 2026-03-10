# src/data_io/data_manager.py

# Standard Library Imports
import colorsys
import math
import os
import random
import re
import shutil
import sys

# Third-party Imports
import pandas as pd
from PyQt5.QtWidgets import QMessageBox

# Local Application Imports
from src.models.models import Item, Container
from src.utilities.utils import get_permanent_directory, resource_path

# Typing Imports
from typing import List, Tuple, Optional


class DataManager:
    def __init__(self):
        # Initialize data structures
        self.items = []
        self.containers = []
        self.combined_pallets = []
        self.packed_containers = []
        self.margin_percentage = 0

        # Initialize SKU to Color mapping
        self.sku_color_map = {}
        self.assigned_hues = []

        # Initialize current hue using the golden angle
        self.golden_angle = 137.5  # degrees
        self.current_hue = random.uniform(0, 360)  # Start at a random hue

        # Load carton dimensions
        self.carton_dimensions_df = pd.DataFrame()
        self.items_per_pallet_df = pd.DataFrame()

        # Set up directories
        self.load_plans_dir = resource_path('Data/Load Plans')

        # Ensure Product data.xlsx is loaded from the permanent directory
        permanent_dir = get_permanent_directory("DataFiles")
        self.product_data_path = os.path.join(permanent_dir, "Product data.xlsx")

        # Load product data
        self.load_product_data(self.product_data_path)

    def load_product_data(self, filepath):
        """Loads product data from the given Excel file."""
        try:
            self.product_data_df = pd.read_excel(
                filepath,  # Use the absolute path passed in
                dtype={'ProductCode': str, 'Category': str}
            )
        except FileNotFoundError:
            QMessageBox.warning(None, "File Not Found", f"Could not find the file: {filepath}")
            self.product_data_df = pd.DataFrame()
        except Exception as e:
            QMessageBox.warning(None, "Error Loading File", f"An error occurred while loading Product Data: {e}")
            self.product_data_df = pd.DataFrame()

    def load_carton_dimensions(self, filepath):
        """Loads carton dimensions from an Excel file."""
        try:
            self.carton_dimensions_df = pd.read_excel(
                filepath,  # Use the absolute path passed in
                usecols=['Product Code', 'Length', 'Width', 'Height', 'QTY Per Carton', 'Carton Weight']
            )
            self.carton_dimensions_df['Product Code'] = self.carton_dimensions_df['Product Code'].astype(str)
        except Exception as e:
            QMessageBox.critical(
                None, "Error",
                f"An error occurred while loading carton dimensions:\n{e}"
            )
            self.carton_dimensions_df = pd.DataFrame()  # Empty DataFrame if failed

    def load_collections(self, filepath):
        """Loads product data from the given Excel file."""
        try:
            self.collections_df = pd.read_excel(
                filepath,  # Use the absolute path passed in
                dtype={'productId': str, 'productcode': str, 'quantity': int}
            )
        except FileNotFoundError:
            QMessageBox.warning(None, "File Not Found", f"Could not find the file: {filepath}")
            self.collections_df = pd.DataFrame()
        except Exception as e:
            QMessageBox.warning(None, "Error Loading File", f"An error occurred while loading Product Data: {e}")
            self.collections_df = pd.DataFrame()

    def reload_product_data(self):
        """Reloads the product data from Product data.xlsx."""
        try:
            self.load_product_data(self.product_data_path)
        except Exception as e:
            QMessageBox.critical(
                None,
                "Reload Error",
                f"An error occurred while reloading product data:\n{e}"
            )

    def save_product_data(self):
        """Saves the current product_data_df to Product data.xlsx."""
        try:
            self.product_data_df.to_excel(self.product_data_path, index=False)
        except Exception as e:
            QMessageBox.critical(
                None,
                "Save Error",
                f"Failed to save Product data:\n{e}"
            )

    def reset_product_data_to_default(self):
        """Resets product_data_df to default by copying the original file from resources."""
        original_product_data = resource_path(r'Data\Product data.xlsx')
        try:
            shutil.copyfile(original_product_data, self.product_data_path)
            self.load_product_data(self.product_data_path)
        except Exception as e:
            QMessageBox.critical(
                None,
                "Reset Error",
                f"Failed to reset Product data:\n{e}"
            )

    def get_product_codes(self):
        """Returns a list of product codes from the product data."""
        if hasattr(self, 'product_data_df') and 'ProductCode' in self.product_data_df.columns:
            return self.product_data_df['ProductCode'].dropna().astype(str).unique().tolist()
        else:
            return []

    def get_dimensions_for_product_code(self, product_code):
        """Returns dimensions, weight, rotatable, stackable, and europallet for the given product code.
        Missing numeric values return 0, and missing boolean values return False.
        """
        if hasattr(self, 'product_data_df'):
            df = self.product_data_df
            df = df[df['ProductCode'] == product_code]
            if not df.empty:
                length_mm = df['Total length (L) [mm]'].iloc[0]
                width_mm = df['Width (W) [mm]'].iloc[0]
                height_mm = df['Height (H) [mm]'].iloc[0]
                weight_g = df['Weight [g]'].iloc[0]
                rotatable = df['Rotatable'].iloc[0]
                stackable = df['Stackable'].iloc[0]
                europallet = df['Europallet'].iloc[0]

                def to_num(v, factor=1.0):
                    return 0.0 if pd.isna(v) else float(v) / factor

                def to_bool(v):
                    if isinstance(v, str):
                        return v.strip().lower() == 'true'
                    return False if pd.isna(v) else bool(v)

                length = to_num(length_mm, 10.0)
                width = to_num(width_mm, 10.0)
                height = to_num(height_mm, 10.0)
                weight = to_num(weight_g, 1000.0)
                rotatable = to_bool(rotatable)
                stackable = to_bool(stackable)
                europallet = to_bool(europallet)

                return {
                    'length': length,
                    'width': width,
                    'height': height,
                    'weight': weight,
                    'rotatable': rotatable,
                    'stackable': stackable,
                    'europallet': europallet
                }
        return None

    def get_items_per_pallet(self, sku):
        """Returns the Items per Pallet for the given SKU based on its Category."""
        matched_row = self.product_data_df[self.product_data_df['ProductCode'] == sku]
        if not matched_row.empty:
            category = matched_row['Category'].iloc[0]
            if category in ['S7', 'S8', 'S9']:
                return 2
            else:
                return None  # Default value if category doesn't match
        else:
            return None  # SKU not found in product data

    def get_base_sku(self, sku):
        """Extracts the base SKU by removing any numeric prefix."""
        match = re.match(r'^(\d+)-(.*)$', sku)
        if match:
            base_sku = match.group(2)
        else:
            base_sku = sku
        return base_sku

    def get_next_prefix_number(self, base_sku):
        """Finds the next available prefix number for the given base SKU to avoid duplicate SKUs."""
        pattern = re.compile(r'^(\d+)-' + re.escape(base_sku) + r'$')
        prefixes = []
        for item in self.items:
            match = pattern.match(item.sku)
            if match:
                prefix_number = int(match.group(1))
                prefixes.append(prefix_number)
        # Also check if base SKU exists without prefix
        if any(item.sku == base_sku for item in self.items):
            prefixes.append(0)  # Consider base SKU as prefix 0
        if prefixes:
            next_number = max(prefixes) + 1
        else:
            next_number = 1
        return next_number

    def generate_color_for_sku(self, sku):
        """Generates a unique and distinct color for a given SKU, avoiding yellow hues."""
        if sku in self.sku_color_map:
            return self.sku_color_map[sku]

        max_attempts = 1000  # Prevent infinite loops
        attempts = 0

        # Define the exclusion range around yellow
        EXCLUSION_START = 45   # degrees
        EXCLUSION_END = 75     # degrees

        # Start with initial min_hue_diff
        min_hue_diff = 20  # degrees

        while attempts < max_attempts:
            # Increment hue by the golden angle
            self.current_hue = (self.current_hue + self.golden_angle) % 360

            # Skip hues within the exclusion range (45° to 75°)
            if EXCLUSION_START <= self.current_hue <= EXCLUSION_END:
                self.current_hue = (self.current_hue + 16) % 360  # Skip further to exit exclusion range

            # Check for minimum hue difference from existing hues
            is_distinct = True
            for assigned_hue in self.assigned_hues:
                # Calculate the shortest distance between hues on the color wheel
                hue_diff = min(abs(self.current_hue - assigned_hue), 360 - abs(self.current_hue - assigned_hue))
                if hue_diff < min_hue_diff:
                    is_distinct = False
                    break

            if is_distinct:
                # Assign hue to SKU
                self.assigned_hues.append(self.current_hue)

                # Convert hue to RGB
                h_norm = self.current_hue / 360.0  # Normalize hue to [0, 1]
                saturation = 0.8  # High saturation for vivid colors
                value = 0.9       # Bright colors
                r, g, b = colorsys.hsv_to_rgb(h_norm, saturation, value)
                color = (r, g, b, 0.6)  # Alpha value for transparency

                # Assign color to SKU
                self.sku_color_map[sku] = color
                return color

            attempts += 1

            # **After every 100 attempts, reduce min_hue_diff**
            if attempts % 100 == 0:
                min_hue_diff *= 0.8  # Reduce min_hue_diff by 20%

        # **Fallback: Assign a random color if no distinct hue is found**
        h_norm = random.uniform(0, 1)
        saturation = 0.8
        value = 0.9
        r, g, b = colorsys.hsv_to_rgb(h_norm, saturation, value)
        color = (r, g, b, 0.6)
        self.sku_color_map[sku] = color
        return color

    def calculate_cartons(self, quantity, qty_per_carton):
        """Calculates the number of cartons needed based on quantity and QTY Per Carton."""
        if qty_per_carton <= 0:
            return 0
        return math.ceil(quantity / qty_per_carton)

    def get_qty_per_carton(self, sku):
        """Retrieves the QTY Per Carton for a given SKU. Returns 0 if the SKU is not found."""
        base_sku = self.get_base_sku(sku)

        matched_row = self.carton_dimensions_df[
            self.carton_dimensions_df['Product Code'] == base_sku
        ]
        if not matched_row.empty:
            return matched_row['QTY Per Carton'].iloc[0]
        else:
            # Return 0 if QTY Per Carton not found
            return 0

    def get_carton_dimensions(self, item):
        """Returns carton dimensions for an item without modifying the item. If SKU is not found, returns default dimensions."""
        if self.carton_dimensions_df.empty:
            # Return default dimensions
            return {
                'length': 42.0,  # cm
                'width': 57.0,   # cm
                'height': 23.0,  # cm
            }

        # Extract base SKU by removing any numeric prefix
        base_sku = self.get_base_sku(item.sku)

        # Match base SKU with 'Product Code' in the DataFrame
        matched_row = self.carton_dimensions_df[
            self.carton_dimensions_df['Product Code'] == base_sku
        ]

        def to_float(value):
            # Convert to string, remove all non-numeric except dot, then convert to float
            cleaned = re.sub(r'[^0-9.]', '', str(value))
            return float(cleaned) if cleaned else 0.0

        if not matched_row.empty:
            # Return carton dimensions with cleaned, numeric-only values
            return {
                'length': to_float(matched_row['Length'].iloc[0]),
                'width': to_float(matched_row['Width'].iloc[0]),
                'height': to_float(matched_row['Height'].iloc[0]),
            }
        else:
            # Return default dimensions
            return {
                'length': 42.0,  # cm
                'width': 57.0,   # cm
                'height': 23.0,  # cm
            }
            
    def create_item(self, sku: str, length: float, width: float, height: float, weight: float, quantity: int,
                   stackable: bool, rotatable: bool, europallet: bool = False, mixed_pallet: str = "",
                   items_per_pallet: Optional[int] = None) -> Item:
        return Item(
            sku=sku,
            length=length,
            width=width,
            height=height,
            weight=weight,
            quantity=quantity,
            stackable=stackable,
            rotatable=rotatable,
            europallet=europallet,
            mixed_pallet=mixed_pallet,
            items_per_pallet=items_per_pallet
        )

    def create_europallet_item(
        self, 
        sku: str, 
        weight: float, 
        stackable: bool, 
        rotatable: bool, 
        quantity: int = 1
    ) -> Item:
        total_weight = (weight * quantity) + 25.0  # Total weight for all quantities plus pallet
        return self.create_item(
            sku=sku,
            length=120.0,    # Fixed length for europallet
            width=80.0,    # Fixed width for europallet
            height=50.0,    # Fixed height for europallet
            weight=total_weight,
            quantity=quantity,
            stackable=stackable,
            rotatable=rotatable,
            europallet=True
        )
    
    def create_mixed_pallet_item(self, mixed_pallet: str, total_weight: float, stackable: bool,
                                 rotatable: bool) -> Item:
        return self.create_item(
            sku=f"MIXED-{mixed_pallet}",
            length=120.0,   # Fixed length for mixed pallet
            width=80.0,     # Fixed width for mixed pallet
            height=50.0,    # Fixed height for mixed pallet
            weight=total_weight + 25.0,
            quantity=1,
            stackable=stackable,
            rotatable=rotatable,
            mixed_pallet=mixed_pallet
        )