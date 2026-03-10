# tests/test_istia_import.py

import pytest
from unittest.mock import MagicMock, patch, mock_open
from PyQt5.QtWidgets import QApplication, QMessageBox, QWidget
from src.utilities.istia_import import IstiaImportPage, DataFetchThread
from src.data_io.data_manager import DataManager
from src.models.models import Item, Container
import pandas as pd
import tempfile
import os

# Minimal MockInputPage
class MockInputPage(QWidget):
    def __init__(self):
        super().__init__()
        self.back_to_visualization_button = MagicMock()

    def update_items_table(self, items):
        pass

# TestParent with MockInputPage
class TestParent(QWidget):
    def __init__(self):
        super().__init__()
        self.input_page = MockInputPage()
        self.data_manager = MagicMock(spec=DataManager)
        self.data_manager.sku_color_map = {}
        self.data_manager.generate_color_for_sku.return_value = (0, 0, 0)

    def show_input_page(self):
        pass

# Fixtures
@pytest.fixture(scope="session")
def app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

@pytest.fixture
def parent(qtbot):
    parent = TestParent()
    qtbot.addWidget(parent)
    return parent

@pytest.fixture
def istia_import_page(parent):
    page = IstiaImportPage(parent=parent)
    return page

# Test Cases
def test_import_data_success(istia_import_page, parent, monkeypatch):
    sample_order_monitor = pd.DataFrame({
        'Transport_order_number': ['TO123'],
        'Order_number': ['O123'],
        'ProductCode': ['P123'],
        'Qty_ordered': [10]
    })

    sample_product_data = pd.DataFrame({
        'ProductCode': ['P123'],
        'Width (W) [mm]': [500],
        'Height (H) [mm]': [1000],
        'Total length (L) [mm]': [2000],
        'Weight [g]': [1500],
        'Rotatable': ['YES'],
        'Stackable': ['NO']
    })

    with patch('pymssql.connect') as mock_connect, \
         patch('pandas.read_excel', return_value=sample_product_data), \
         patch('PyQt5.QtWidgets.QMessageBox') as mock_msg:
        
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.execute.return_value = None
        mock_conn.cursor.return_value.fetchall.return_value = sample_order_monitor.values.tolist()
        mock_conn.close.return_value = None

        istia_import_page.fetch_data()

        # Simulate data fetched
        istia_import_page.on_data_fetched(pd.merge(sample_order_monitor, sample_product_data, on='ProductCode'))

        assert parent.data_manager.sku_color_map['P123'] == (0, 0, 0)
        mock_msg.information.assert_called_once()

def test_import_data_missing_columns(istia_import_page, parent, monkeypatch):
    incomplete_product_data = pd.DataFrame({
        'ProductCode': ['P123'],
        'Width (W) [mm]': [500],
        # Missing 'Height (H) [mm]', 'Total length (L) [mm]', etc.
    })

    with patch('pymssql.connect') as mock_connect, \
         patch('pandas.read_excel', return_value=incomplete_product_data), \
         patch('PyQt5.QtWidgets.QMessageBox') as mock_msg:
        
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.execute.return_value = None
        mock_conn.cursor.return_value.fetchall.return_value = pd.DataFrame({
            'Transport_order_number': ['TO123'],
            'Order_number': ['O123'],
            'ProductCode': ['P123'],
            'Qty_ordered': [10]
        }).values.tolist()
        mock_conn.close.return_value = None

        istia_import_page.fetch_data()

        # Simulate error during data fetched
        istia_import_page.on_error("Excel file is missing one or more required columns")

        mock_msg.critical.assert_called_once_with(
            istia_import_page,
            "Error",
            "An error occurred while fetching data:\nExcel file is missing one or more required columns: ['ProductCode', 'Width (W) [mm]', 'Height (H) [mm]', 'Total length (L) [mm]', 'Weight [g]', 'Rotatable', 'Stackable']"
        )

def test_import_data_invalid_excel_path(istia_import_page, parent, monkeypatch):
    with patch('pymssql.connect') as mock_connect, \
         patch('pandas.read_excel', side_effect=FileNotFoundError("Excel file not found")), \
         patch('PyQt5.QtWidgets.QMessageBox') as mock_msg:
        
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.close.return_value = None

        istia_import_page.fetch_data()

        # Simulate error during data fetched
        istia_import_page.on_error("Excel file not found at path: /invalid/path/Product data.xlsx")

        mock_msg.critical.assert_called_once_with(
            istia_import_page,
            "Error",
            "An error occurred while fetching data:\nExcel file not found at path: /invalid/path/Product data.xlsx"
        )
