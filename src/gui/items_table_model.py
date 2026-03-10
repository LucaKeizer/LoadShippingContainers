# src/gui/items_table_model.py

# Standard Library Imports
import math
import re

# Third-party Imports
from PyQt5.QtCore import (
    Qt, QTimer, pyqtSignal, QAbstractTableModel, QModelIndex, QEvent
)
import pandas as pd
from PyQt5.QtGui import QColor, QBrush
from PyQt5.QtWidgets import (
    QLineEdit, QSpinBox, QDoubleSpinBox, QStyledItemDelegate, QCompleter, 
    QMessageBox, QPushButton, QStyle, QStyleOptionButton, QApplication
)

# Local Application Imports
from src.data_io.data_manager import DataManager
from src.models.models import Item


# *** Subclasses for Selectable Widgets ***

class SelectableLineEdit(QLineEdit):
    """QLineEdit subclass that selects all text when focused."""
    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)  # Schedule selectAll after event processing


class SelectableSpinBox(QSpinBox):
    """QSpinBox subclass that selects all text when focused."""
    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.lineEdit().selectAll)  # Schedule selectAll after event processing


class SelectableDoubleSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox subclass that selects all text when focused."""
    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.lineEdit().selectAll)  # Schedule selectAll after event processing


class MixedPalletDelegate(QStyledItemDelegate):
    """Delegate for Mixed Pallet column with auto-completion."""
    def __init__(self, mixed_pallet_list, parent=None):
        super().__init__(parent)
        self.mixed_pallet_list = mixed_pallet_list

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        completer = QCompleter(self.mixed_pallet_list, parent)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setFilterMode(Qt.MatchContains)
        editor.setCompleter(completer)
        return editor


# *** Button Delegate for Split and Delete Buttons ***

class ButtonDelegate(QStyledItemDelegate):
    """A delegate that places a fully functioning button in every cell of the column to which it's applied."""
    clicked = pyqtSignal(int)  # row index

    def __init__(self, parent=None, button_type="Split"):
        super().__init__(parent)
        self.button_type = button_type

    def paint(self, painter, option, index):
        button = QStyleOptionButton()
        button.rect = option.rect.adjusted(5, 5, -5, -5)  # Adjusted for better padding
        button.text = self.button_type

        # Set the state based on the table's state
        if option.state & QStyle.State_Selected:
            button.state = QStyle.State_Enabled | QStyle.State_Raised | QStyle.State_MouseOver
        else:
            button.state = QStyle.State_Enabled | QStyle.State_Raised

        # Handle hover state
        if option.state & QStyle.State_MouseOver:
            button.state |= QStyle.State_MouseOver

        QApplication.style().drawControl(QStyle.CE_PushButton, button, painter)

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.MouseButtonRelease:
            if event.button() == Qt.LeftButton:
                self.clicked.emit(index.row())
                return True
        return super().editorEvent(event, model, option, index)


# *** Issue Delegate for Issue Column ***

class IssueDelegate(QStyledItemDelegate):
    issueClicked = pyqtSignal(int, str)  # row, issue_type

    def paint(self, painter, option, index):
        item = index.model().items[index.row()]
        painter.save()
        if item.has_missing_dimension_issue:
            painter.setPen(QColor('blue'))
            painter.drawText(option.rect, Qt.AlignCenter, "i")
        elif item.has_carton_issue:
            painter.setPen(QColor('red'))
            painter.drawText(option.rect, Qt.AlignCenter, "!")
        elif item.has_remainder_issue:
            painter.setPen(QColor('orange'))
            painter.drawText(option.rect, Qt.AlignCenter, "?")
        painter.restore()

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            item = model.items[index.row()]
            if item.has_missing_dimension_issue:
                self.issueClicked.emit(index.row(), 'missing_dimension')
                return True
            elif item.has_carton_issue:
                self.issueClicked.emit(index.row(), 'carton')
                return True
            elif item.has_remainder_issue:
                self.issueClicked.emit(index.row(), 'remainder')
                return True
        return False


# *** Custom Table Model ***

class ItemsTableModel(QAbstractTableModel):
    """Custom model for the items table."""

    itemsDataChanged = pyqtSignal()  # Signal to notify when items data has changed
    cartonQuantityIssue = pyqtSignal(str, int, int, int)  # sku, quantity, cartons, ideal_cartons
    splitRequested = pyqtSignal(int)  # row index
    deleteRequested = pyqtSignal(int)  # row index

    def __init__(self, items, data_manager, mixed_pallet_list, mixed_pallet_model, parent=None):
        super().__init__(parent)
        self.items = items  # List of Item instances
        self.data_manager = data_manager
        self.mixed_pallet_list = mixed_pallet_list
        self.mixed_pallet_model = mixed_pallet_model
        # Updated headers with separate "Split" and "Delete" columns
        self.headers = [
            "Product Code", "Length (cm)", "Width (cm)", "Height (cm)",
            "Weight (kg)", "Quantity", "Cartons", "Mixed Pallet", "Stackable",
            "Rotatable", "Europallet", "Split", "Delete", "Issue"  # "Split" and "Delete" added
        ]

    def rowCount(self, parent=QModelIndex()):
        return len(self.items)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        item = self.items[index.row()]
        column = index.column()

        if role == Qt.DisplayRole:
            if column == 0:
                return item.sku
            elif column == 1:  # Length
                return "N/A" if math.isnan(item.length) else f"{item.length:.1f}"
            elif column == 2:  # Width
                return "N/A" if math.isnan(item.width) else f"{item.width:.1f}"
            elif column == 3:  # Height
                return "N/A" if math.isnan(item.height) else f"{item.height:.1f}"
            elif column == 4:  # Weight
                return "N/A" if math.isnan(item.weight) else f"{item.weight:.2f}"
            elif column == 5:
                return str(item.quantity)
            elif column == 6:
                return str(getattr(item, 'cartons', 0))
            elif column == 7:
                return getattr(item, 'mixed_pallet', "")
            elif column == 8:
                return "Yes" if item.stackable else "No"
            elif column == 9:
                return "Yes" if item.rotatable else "No"
            elif column == 10:
                return "Yes" if getattr(item, 'europallet', False) else "No"
            elif column == 11:
                return "Split"
            elif column == 12:
                return "Delete"
            elif column == 13:
                return ""

        elif role == Qt.ForegroundRole and column == 13:
            # Color logic: Red for carton, Orange for remainder, Blue for missing dimension
            if item.has_carton_issue:
                return QBrush(QColor('red'))
            elif item.has_remainder_issue:
                return QBrush(QColor('orange'))
            elif item.has_missing_dimension_issue:
                # Use blue color for missing dimension
                return QBrush(QColor('blue'))

        elif role == Qt.TextAlignmentRole:
            if column in [1, 2, 3, 4, 5, 6, 10, 13]:
                return Qt.AlignCenter

        elif role == Qt.ToolTipRole:
            if column == 0:  # Product Code column
                # Get product name for tooltip
                product_name = self.get_product_name(item.sku)
                if product_name:
                    return f"Product Name: {product_name}"
            elif column == 13:
                # Keep existing tooltips for Issue column
                if item.has_carton_issue:
                    return "Carton quantity is not ideal. Click to view details."
                elif item.has_remainder_issue:
                    return "There is unused space in cartons. Click to view details."
                elif item.has_missing_dimension_issue:
                    return "Some dimensions or weight are missing (N/A). Click for more info."

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            if section < len(self.headers):
                return self.headers[section]
            else:
                return None
        else:
            return str(section + 1)

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags

        # Make all columns except "Split", "Delete", and "Issue" editable
        if index.column() not in [11, 12, 13]:  # "Split", "Delete", and "Issue" columns
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable

        # For "Split", "Delete", and "Issue" columns
        if index.column() in [11, 12, 13]:
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled

        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid() or role != Qt.EditRole:
            return False

        item = self.items[index.row()]
        column = index.column()

        try:
            if column == 0:
                # Product Code
                old_sku = item.sku
                if value:
                    item.sku = value
                    # Update SKU Color Mapping
                    if item.sku not in self.data_manager.sku_color_map:
                        self.data_manager.sku_color_map[item.sku] = self.data_manager.generate_color_for_sku(item.sku)
                    # Remove old SKU from color map if necessary
                    if not any(existing_item.sku == old_sku for existing_item in self.items):
                        del self.data_manager.sku_color_map[old_sku]
                else:
                    raise ValueError("Product Code cannot be empty.")
            elif column == 1:
                # Length
                length = float(value)
                if length > 0:
                    item.length = length
                else:
                    raise ValueError("Length must be greater than zero.")
            elif column == 2:
                # Width
                width = float(value)
                if width > 0:
                    item.width = width
                else:
                    raise ValueError("Width must be greater than zero.")
            elif column == 3:
                # Height
                height = float(value)
                if height > 0:
                    item.height = height
                else:
                    raise ValueError("Height must be greater than zero.")
            elif column == 4:
                # Weight
                weight = float(value)
                if weight > 0:
                    item.weight = weight
                else:
                    raise ValueError("Weight must be greater than zero.")
            elif column == 5:
                # Quantity
                quantity = int(value)
                if quantity > 0:
                    item.quantity = quantity
                    if getattr(item, 'cartons', 0) > 0:
                        # Recalculate ideal cartons
                        qty_per_carton = self.data_manager.get_qty_per_carton(item.sku)
                        if qty_per_carton is None or qty_per_carton <= 0:
                            raise ValueError(f"QTY Per Carton not found or invalid for SKU '{item.sku}'.")
                        ideal_cartons = math.ceil(quantity / qty_per_carton)
                        if item.cartons < ideal_cartons:
                            item.has_carton_issue = True
                            item.has_remainder_issue = False
                            self.cartonQuantityIssue.emit(item.sku, quantity, item.cartons, ideal_cartons)
                        else:
                            item.has_carton_issue = False
                            total_capacity = item.cartons * qty_per_carton
                            if total_capacity > quantity:
                                item.has_remainder_issue = True
                            else:
                                item.has_remainder_issue = False
                    else:
                        item.has_carton_issue = False
                        item.has_remainder_issue = False
                else:
                    raise ValueError("Quantity must be at least 1.")
            elif column == 6:
                # Cartons
                cartons = int(value)
                if cartons >= 0:
                    item.cartons = cartons
                    if cartons > 0:
                        # Update dimensions from carton dimensions file
                        self.data_manager.update_item_carton_dimensions(item)
                        # Recalculate ideal cartons
                        qty_per_carton = self.data_manager.get_qty_per_carton(item.sku)
                        if qty_per_carton is None or qty_per_carton <= 0:
                            raise ValueError(f"QTY Per Carton not found or invalid for SKU '{item.sku}'.")
                        ideal_cartons = math.ceil(item.quantity / qty_per_carton)
                        if cartons < ideal_cartons:
                            item.has_carton_issue = True
                            item.has_remainder_issue = False
                            self.cartonQuantityIssue.emit(item.sku, item.quantity, cartons, ideal_cartons)
                        else:
                            item.has_carton_issue = False
                            total_capacity = cartons * qty_per_carton
                            if total_capacity > item.quantity:
                                item.has_remainder_issue = True
                            else:
                                item.has_remainder_issue = False
                    else:
                        item.has_carton_issue = False
                        item.has_remainder_issue = False
                else:
                    raise ValueError("Cartons must be 0 or a positive integer.")
            elif column == 7:
                # Mixed Pallet
                old_mixed_pallet = item.mixed_pallet
                item.mixed_pallet = value.strip()  # Assign new mixed_pallet value

                # Update autocompletion list
                if item.mixed_pallet and item.mixed_pallet not in self.mixed_pallet_list:
                    self.mixed_pallet_list.append(item.mixed_pallet)
                    self.mixed_pallet_model.setStringList(self.mixed_pallet_list)

                # Remove old Mixed Pallet if necessary
                if old_mixed_pallet != item.mixed_pallet and old_mixed_pallet in self.mixed_pallet_list:
                    if not any(i.mixed_pallet == old_mixed_pallet for i in self.items):
                        self.mixed_pallet_list.remove(old_mixed_pallet)
                        self.mixed_pallet_model.setStringList(self.mixed_pallet_list)

                if item.mixed_pallet:
                    # If mixed_pallet is now set, override dimensions
                    item.length = 120.0
                    item.width = 80.0
                    item.height = 50.0
                    # Set Cartons to 0 as mixed pallets do not use cartons
                    item.cartons = 0
                    item.has_carton_issue = False
                    item.has_remainder_issue = False
                else:
                    # If mixed_pallet is cleared, dimensions need to be re-entered manually
                    pass  # No action needed
            elif column == 8:
                # Stackable
                if any(sub in str(value).lower() for sub in ["yes", "ye", "y", "true", "tru", "t", "1"]):
                    item.stackable = True
                elif any(sub in str(value).lower() for sub in ["no", "n", "false", "f", "0"]):
                    item.stackable = False
                else:
                    raise ValueError("Stackable must be a version of 'Yes' or 'No'.")
            elif column == 9:
                # Rotatable
                if any(sub in str(value).lower() for sub in ["yes", "ye", "y", "true", "tru", "t", "1"]):
                    item.rotatable = True
                elif any(sub in str(value).lower() for sub in ["no", "n", "false", "f", "0"]):
                    item.rotatable = False
                else:
                    raise ValueError("Rotatable must be a version of 'Yes' or 'No'.")
            elif column == 10:
                # Europallet
                if any(sub in str(value).lower() for sub in ["yes", "ye", "y", "true", "tru", "t", "1"]):
                    item.europallet = True
                elif any(sub in str(value).lower() for sub in ["no", "n", "false", "f", "0"]):
                    item.europallet = False
                else:
                    raise ValueError("Europallet must be a version of 'Yes' or 'No'.")
            elif column == 11:
                # Split button clicked
                self.splitRequested.emit(index.row())
                return False  # No need to set data
            elif column == 12:
                # Delete button clicked
                self.deleteRequested.emit(index.row())
                return False  # No need to set data
            elif column == 13:
                # Issue column - not editable
                return False
            else:
                # Unknown column
                return False

            self.dataChanged.emit(index, index, [Qt.DisplayRole])
            self.itemsDataChanged.emit()  # Emit the custom signal
            return True
        except ValueError as ve:
            QMessageBox.warning(None, "Input Error", str(ve))
            return False

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            if section < len(self.headers):
                return self.headers[section]
            else:
                return None
        else:
            return str(section + 1)

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags

        # Make all columns except "Split", "Delete", and "Issue" editable
        if index.column() not in [11, 12, 13]:  # "Split", "Delete", and "Issue" columns
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable

        # For "Split", "Delete", and "Issue" columns
        if index.column() in [11, 12, 13]:
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled

        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid() or role != Qt.EditRole:
            return False

        item = self.items[index.row()]
        column = index.column()

        try:
            if column == 0:
                # Product Code
                old_sku = item.sku
                if value:
                    item.sku = value
                    # Update SKU Color Mapping
                    if item.sku not in self.data_manager.sku_color_map:
                        self.data_manager.sku_color_map[item.sku] = self.data_manager.generate_color_for_sku(item.sku)
                    # Remove old SKU from color map if necessary
                    if not any(existing_item.sku == old_sku for existing_item in self.items):
                        del self.data_manager.sku_color_map[old_sku]
                else:
                    raise ValueError("Product Code cannot be empty.")
            elif column == 1:
                # Length
                length = float(value)
                if length > 0:
                    item.length = length
                else:
                    raise ValueError("Length must be greater than zero.")
            elif column == 2:
                # Width
                width = float(value)
                if width > 0:
                    item.width = width
                else:
                    raise ValueError("Width must be greater than zero.")
            elif column == 3:
                # Height
                height = float(value)
                if height > 0:
                    item.height = height
                else:
                    raise ValueError("Height must be greater than zero.")
            elif column == 4:
                # Weight
                weight = float(value)
                if weight > 0:
                    item.weight = weight
                else:
                    raise ValueError("Weight must be greater than zero.")
            elif column == 5:
                # Quantity
                quantity = int(value)
                if quantity > 0:
                    item.quantity = quantity
                    if getattr(item, 'cartons', 0) > 0:
                        # Recalculate ideal cartons
                        qty_per_carton = self.data_manager.get_qty_per_carton(item.sku)
                        if qty_per_carton is None or qty_per_carton <= 0:
                            raise ValueError(f"QTY Per Carton not found or invalid for SKU '{item.sku}'.")
                        ideal_cartons = math.ceil(quantity / qty_per_carton)
                        if item.cartons < ideal_cartons:
                            item.has_carton_issue = True
                            item.has_remainder_issue = False
                            self.cartonQuantityIssue.emit(item.sku, quantity, item.cartons, ideal_cartons)
                        else:
                            item.has_carton_issue = False
                            total_capacity = item.cartons * qty_per_carton
                            if total_capacity > quantity:
                                item.has_remainder_issue = True
                            else:
                                item.has_remainder_issue = False
                    else:
                        item.has_carton_issue = False
                        item.has_remainder_issue = False
                else:
                    raise ValueError("Quantity must be at least 1.")
            elif column == 6:
                # Cartons
                cartons = int(value)
                if cartons >= 0:
                    item.cartons = cartons
                    if cartons > 0:
                        # Do NOT update dimensions from carton dimensions file
                        # Recalculate ideal cartons
                        qty_per_carton = self.data_manager.get_qty_per_carton(item.sku)
                        if qty_per_carton is None or qty_per_carton <= 0:
                            raise ValueError(f"QTY Per Carton not found or invalid for SKU '{item.sku}'.")
                        ideal_cartons = math.ceil(item.quantity / qty_per_carton)
                        if cartons < ideal_cartons:
                            item.has_carton_issue = True
                            item.has_remainder_issue = False
                            self.cartonQuantityIssue.emit(item.sku, item.quantity, cartons, ideal_cartons)
                        else:
                            item.has_carton_issue = False
                            total_capacity = cartons * qty_per_carton
                            if total_capacity > item.quantity:
                                item.has_remainder_issue = True
                            else:
                                item.has_remainder_issue = False
                    else:
                        item.has_carton_issue = False
                        item.has_remainder_issue = False
                else:
                    raise ValueError("Cartons must be 0 or a positive integer.")
            elif column == 7:
                # Mixed Pallet
                old_mixed_pallet = item.mixed_pallet
                item.mixed_pallet = value.strip()  # Assign new mixed_pallet value

                # Update autocompletion list
                if item.mixed_pallet and item.mixed_pallet not in self.mixed_pallet_list:
                    self.mixed_pallet_list.append(item.mixed_pallet)
                    self.mixed_pallet_model.setStringList(self.mixed_pallet_list)

                # Remove old Mixed Pallet if necessary
                if old_mixed_pallet != item.mixed_pallet and old_mixed_pallet in self.mixed_pallet_list:
                    if not any(i.mixed_pallet == old_mixed_pallet for i in self.items):
                        self.mixed_pallet_list.remove(old_mixed_pallet)
                        self.mixed_pallet_model.setStringList(self.mixed_pallet_list)

                if item.mixed_pallet:
                    # If mixed_pallet is now set, override dimensions
                    item.length = 120.0
                    item.width = 80.0
                    item.height = 50.0
                    # Set Cartons to 0 as mixed pallets do not use cartons
                    item.cartons = 0
                    item.has_carton_issue = False
                    item.has_remainder_issue = False
                else:
                    # If mixed_pallet is cleared, dimensions need to be re-entered manually
                    pass  # No action needed
            elif column == 8:
                # Stackable
                if any(sub in str(value).lower() for sub in ["yes", "ye", "y", "true", "tru", "t", "1"]):
                    item.stackable = True
                elif any(sub in str(value).lower() for sub in ["no", "n", "false", "f", "0"]):
                    item.stackable = False
                else:
                    raise ValueError("Stackable must be a version of 'Yes' or 'No'.")
            elif column == 9:
                # Rotatable
                if any(sub in str(value).lower() for sub in ["yes", "ye", "y", "true", "tru", "t", "1"]):
                    item.rotatable = True
                elif any(sub in str(value).lower() for sub in ["no", "n", "false", "f", "0"]):
                    item.rotatable = False
                else:
                    raise ValueError("Rotatable must be a version of 'Yes' or 'No'.")
            elif column == 10:
                # Europallet
                if any(sub in str(value).lower() for sub in ["yes", "ye", "y", "true", "tru", "t", "1"]):
                    item.europallet = True
                elif any(sub in str(value).lower() for sub in ["no", "n", "false", "f", "0"]):
                    item.europallet = False
                else:
                    raise ValueError("Europallet must be a version of 'Yes' or 'No'.")
            elif column == 11:
                # Split button clicked
                self.splitRequested.emit(index.row())
                return False  # No need to set data
            elif column == 12:
                # Delete button clicked
                self.deleteRequested.emit(index.row())
                return False  # No need to set data
            elif column == 13:
                # Issue column - not editable
                return False
            else:
                # Unknown column
                return False

            self.dataChanged.emit(index, index, [Qt.DisplayRole])
            self.itemsDataChanged.emit()  # Emit the custom signal
            return True
        except ValueError as ve:
            QMessageBox.warning(None, "Input Error", str(ve))
            return False

    def get_product_name(self, sku):
        """Retrieves the product name for a given SKU from the product data."""
        try:
            # Extract base SKU by removing any numeric prefix
            base_sku = self.data_manager.get_base_sku(sku)
            
            # Find the row with matching ProductCode
            matched_rows = self.data_manager.product_data_df[
                self.data_manager.product_data_df['ProductCode'] == base_sku
            ]
            
            if not matched_rows.empty and 'Product Name' in matched_rows.columns:
                product_name = matched_rows['Product Name'].iloc[0]
                if not pd.isna(product_name):  # Check for NaN values
                    return str(product_name)
        except Exception as e:
            pass
        
        return None