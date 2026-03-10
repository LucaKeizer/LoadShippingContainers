# test_product_settings.py

import pytest
from unittest.mock import MagicMock, patch, mock_open
import pandas as pd
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox

from src.data_io.product_settings import PandasModel, ProductSettingsPage

@pytest.fixture
def sample_dataframe():
    """Creates a sample DataFrame for testing."""
    data = {
        'ProductCode': ['P001', 'P002', 'P003'],
        'Product Name': ['Widget', 'Gadget', 'Thingamajig'],
        'Width (W) [mm]': [100.0, 150.0, 200.0],
        'Height (H) [mm]': [50.0, 75.0, 100.0],
        'Total length (L) [mm]': [200.0, 250.0, 300.0],
        'Weight [g]': [500.0, 750.0, 1000.0],
        'Category': ['A', 'B', 'C'],
        'Rotatable': [True, False, True],
        'Stackable': [False, True, False]
    }
    df = pd.DataFrame(data)
    return df

@pytest.fixture
def mock_parent():
    """Creates a mock parent object for ProductSettingsPage."""
    parent = MagicMock()
    parent.data_manager.reload_product_data = MagicMock()
    parent.refresh_ui_after_product_update = MagicMock()
    parent.show_input_page = MagicMock()
    return parent

@pytest.fixture
def product_settings_page(mock_parent):
    """Initializes the ProductSettingsPage with a mocked parent."""
    with patch('src.data_io.product_settings.get_permanent_directory') as mock_get_dir:
        mock_get_dir.return_value = "/fake/data/path"
        with patch('src.data_io.product_settings.pd.read_excel') as mock_read_excel:
            mock_read_excel.return_value = sample_dataframe()
            page = ProductSettingsPage(parent=mock_parent)
            return page

class TestPandasModel:
    """Tests for the PandasModel class."""

    def test_initialization(self, sample_dataframe):
        """Test initializing the PandasModel with a DataFrame."""
        model = PandasModel(df=sample_dataframe)
        assert model.rowCount() == 3
        assert model.columnCount() == 9
        pd.testing.assert_frame_equal(model.get_dataframe(), sample_dataframe)

    def test_data_retrieval(self, sample_dataframe):
        """Test data retrieval from the model."""
        model = PandasModel(df=sample_dataframe)
        index = model.index(0, 0)  # First row, first column
        assert model.data(index, Qt.DisplayRole) == 'P001'
        index = model.index(1, 1)  # Second row, second column
        assert model.data(index, Qt.DisplayRole) == 'Gadget'

    def test_header_data(self, sample_dataframe):
        """Test header data with header mapping."""
        header_mapping = {
            "ProductCode": "Product Code",
            "Product Name": "Product Name",
            "Width (W) [mm]": "Width (mm)",
            "Height (H) [mm]": "Height (mm)",
            "Total length (L) [mm]": "Total length (mm)",
            "Weight [g]": "Weight (g)",
            "Rotatable": "Rotatable",
            "Stackable": "Stackable"
        }
        model = PandasModel(df=sample_dataframe, header_mapping=header_mapping)
        assert model.headerData(0, Qt.Horizontal, Qt.DisplayRole) == "Product Code"
        assert model.headerData(1, Qt.Horizontal, Qt.DisplayRole) == "Product Name"
        assert model.headerData(0, Qt.Vertical, Qt.DisplayRole) == '0'

    def test_flags_read_only(self, sample_dataframe):
        """Test that read-only columns are not editable."""
        read_only = ["ProductCode", "Product Name"]
        model = PandasModel(df=sample_dataframe, read_only_columns=read_only)
        index = model.index(0, 0)  # ProductCode
        assert not (model.flags(index) & Qt.ItemIsEditable)
        index = model.index(0, 2)  # Width (W) [mm]
        assert model.flags(index) & Qt.ItemIsEditable

    def test_set_data_valid(self, sample_dataframe):
        """Test setting valid data in editable columns."""
        model = PandasModel(df=sample_dataframe, read_only_columns=["ProductCode", "Product Name"])
        index = model.index(0, 2)  # Width (W) [mm]
        success = model.setData(index, "120.0", Qt.EditRole)
        assert success
        assert model.get_dataframe().at[0, 'Width (W) [mm]'] == 120.0

    def test_set_data_invalid(self, sample_dataframe, mocker):
        """Test setting invalid data (e.g., exceeding max values)."""
        model = PandasModel(df=sample_dataframe, read_only_columns=["ProductCode", "Product Name"])
        index = model.index(0, 2)  # Width (W) [mm]
        # Patch QMessageBox.warning
        mock_warning = mocker.patch('src.data_io.product_settings.QMessageBox.warning')
        # Attempt to set an excessively high value
        success = model.setData(index, "20000", Qt.EditRole)  # Max is 10000
        assert not success
        mock_warning.assert_called_with(
            None,
            "Invalid Input",
            "Cannot set value '20000' for 'Width (W) [mm]': 'Width (W) [mm]' exceeds the maximum allowed value of 10000."
        )

    def test_set_data_read_only(self, sample_dataframe, mocker):
        """Test attempting to set data in a read-only column."""
        model = PandasModel(df=sample_dataframe, read_only_columns=["ProductCode", "Product Name"])
        index = model.index(0, 0)  # ProductCode
        # Patch QMessageBox.warning
        mock_warning = mocker.patch('src.data_io.product_settings.QMessageBox.warning')
        success = model.setData(index, "P999", Qt.EditRole)
        assert not success
        # Since the method returns False without showing a warning, ensure warning is not called
        mock_warning.assert_not_called()

    def test_set_data_boolean(self, sample_dataframe, mocker):
        """Test setting boolean values with different input representations."""
        model = PandasModel(df=sample_dataframe, read_only_columns=["ProductCode", "Product Name"])
        index = model.index(0, 7)  # Rotatable
        mock_warning = mocker.patch('src.data_io.product_settings.QMessageBox.warning')
        # Valid inputs
        assert model.setData(index, "yes", Qt.EditRole)
        assert model.get_dataframe().at[0, 'Rotatable'] is True
        assert model.setData(index, "f", Qt.EditRole)
        assert model.get_dataframe().at[0, 'Rotatable'] is False
        # Invalid input
        success = model.setData(index, "maybe", Qt.EditRole)
        assert not success
        mock_warning.assert_called_with(
            None,
            "Invalid Input",
            "Cannot set value 'maybe' for 'Rotatable': Invalid input for 'Rotatable': maybe"
        )

class TestProductSettingsPage:
    """Tests for the ProductSettingsPage class."""

    @patch('src.data_io.product_settings.QMessageBox.critical')
    @patch('src.data_io.product_settings.pd.read_excel')
    @patch('src.data_io.product_settings.get_permanent_directory')
    def test_load_product_data_success(self, mock_get_dir, mock_read_excel, mock_critical, mock_parent):
        """Test successful loading of product data."""
        mock_get_dir.return_value = "/fake/data/path"
        mock_read_excel.return_value = pd.DataFrame({
            'ProductCode': ['P001'],
            'Product Name': ['Widget'],
            'Width (W) [mm]': [100.0],
            'Height (H) [mm]': [50.0],
            'Total length (L) [mm]': [200.0],
            'Weight [g]': [500.0],
            'Category': ['A'],
            'Rotatable': [True],
            'Stackable': [False]
        })

        page = ProductSettingsPage(parent=mock_parent)
        assert not page.isEnabled() == False  # Page should be enabled since data is loaded

    @patch('src.data_io.product_settings.QMessageBox.critical')
    @patch('src.data_io.product_settings.pd.read_excel')
    @patch('src.data_io.product_settings.get_permanent_directory')
    def test_load_product_data_file_not_found(self, mock_get_dir, mock_read_excel, mock_critical, mock_parent):
        """Test loading product data when the file does not exist."""
        mock_get_dir.return_value = "/fake/data/path"
        # Simulate file not existing by making read_excel raise FileNotFoundError
        mock_read_excel.side_effect = FileNotFoundError("File not found")

        page = ProductSettingsPage(parent=mock_parent)
        mock_critical.assert_called_with(page, "Error", "Product data is empty or failed to load.")
        assert page.isEnabled() == False

    @patch('src.data_io.product_settings.QMessageBox.critical')
    @patch('src.data_io.product_settings.pd.read_excel')
    @patch('src.data_io.product_settings.get_permanent_directory')
    def test_load_product_data_excel_failure(self, mock_get_dir, mock_read_excel, mock_critical, mock_parent):
        """Test loading product data when pd.read_excel fails."""
        mock_get_dir.return_value = "/fake/data/path"
        mock_read_excel.side_effect = Exception("Excel read error")

        page = ProductSettingsPage(parent=mock_parent)
        mock_critical.assert_called_with(page, "Error", "Product data is empty or failed to load.")
        assert page.isEnabled() == False

    @patch('src.data_io.product_settings.QMessageBox.information')
    @patch('src.data_io.product_settings.QMessageBox.warning')
    def test_search_products_no_input(self, mock_warning, mock_information, product_settings_page, mock_parent):
        """Test searching with empty input."""
        product_settings_page.search_input.text.return_value = ""
        product_settings_page.search_products()
        mock_information.assert_called_with(product_settings_page, "Empty Search", "Please enter a search term.")

    @patch('src.data_io.product_settings.QMessageBox.information')
    @patch('src.data_io.product_settings.QMessageBox.warning')
    def test_search_products_no_match(self, mock_warning, mock_information, product_settings_page, mock_parent):
        """Test searching with no matching products."""
        product_settings_page.search_input.text.return_value = "NonExistent"
        product_settings_page.product_data_df = pd.DataFrame({
            'ProductCode': ['P001', 'P002'],
            'Product Name': ['Widget', 'Gadget']
        })
        product_settings_page.search_products()
        mock_information.assert_called_with(product_settings_page, "No Match", "No matching Product Code or Product Name found.")

    @patch('src.data_io.product_settings.QMessageBox.information')
    def test_search_products_with_matches(self, mock_information, product_settings_page, mock_parent):
        """Test searching with matching products."""
        product_settings_page.search_input.text.return_value = "P001"
        product_settings_page.product_data_df = pd.DataFrame({
            'ProductCode': ['P001', 'P002', 'P001'],
            'Product Name': ['Widget', 'Gadget', 'WidgetPro']
        })
        product_settings_page.search_products()
        assert product_settings_page.match_indices == [0, 2]
        assert product_settings_page.current_match == 0
        # Further calls to search_products should cycle through matches
        product_settings_page.search_products()
        assert product_settings_page.current_match == 1
        product_settings_page.search_products()
        assert product_settings_page.current_match == 0

    @patch('src.data_io.product_settings.QMessageBox.information')
    @patch('src.data_io.product_settings.QMessageBox.critical')
    @patch('src.data_io.product_settings.pd.DataFrame.to_excel')
    def test_confirm_changes_success(self, mock_to_excel, mock_critical, mock_information, product_settings_page, mock_parent):
        """Test confirming changes successfully saves to Excel."""
        product_settings_page.model.get_dataframe.return_value = pd.DataFrame({
            'ProductCode': ['P001'],
            'Product Name': ['Widget'],
            'Width (W) [mm]': [120.0],
            'Height (H) [mm]': [60.0],
            'Total length (L) [mm]': [240.0],
            'Weight [g]': [600.0],
            'Category': ['A'],
            'Rotatable': [True],
            'Stackable': [False]
        })

        product_settings_page.confirm_changes()
        mock_to_excel.assert_called_with("/fake/data/path/Product data.xlsx", index=False)
        mock_information.assert_called_with(product_settings_page, "Success", "Product data has been successfully updated.")
        mock_parent.data_manager.reload_product_data.assert_called_once()
        mock_parent.refresh_ui_after_product_update.assert_called_once()
        mock_parent.show_input_page.assert_called_once()

    @patch('src.data_io.product_settings.QMessageBox.critical')
    @patch('src.data_io.product_settings.pd.DataFrame.to_excel')
    def test_confirm_changes_save_failure(self, mock_to_excel, mock_critical, product_settings_page, mock_parent):
        """Test confirming changes when saving to Excel fails."""
        mock_to_excel.side_effect = Exception("Save error")
        product_settings_page.confirm_changes()
        mock_critical.assert_called_with(product_settings_page, "Save Error", "Failed to save Product data:\nSave error")

    @patch('src.data_io.product_settings.QMessageBox.question')
    @patch('src.data_io.product_settings.QMessageBox.information')
    def test_reject_changes_confirm_yes(self, mock_information, mock_question, product_settings_page, mock_parent):
        """Test rejecting changes and confirming the discard."""
        mock_question.return_value = QMessageBox.Yes
        product_settings_page.reject_changes()
        mock_parent.data_manager.reload_product_data.assert_called_once()
        mock_parent.refresh_ui_after_product_update.assert_called_once()
        mock_parent.show_input_page.assert_called_once()

    @patch('src.data_io.product_settings.QMessageBox.question')
    def test_reject_changes_confirm_no(self, mock_question, product_settings_page, mock_parent):
        """Test rejecting changes and declining the discard."""
        mock_question.return_value = QMessageBox.No
        product_settings_page.reject_changes()
        mock_parent.data_manager.reload_product_data.assert_not_called()
        mock_parent.refresh_ui_after_product_update.assert_not_called()
        mock_parent.show_input_page.assert_not_called()

    @patch('src.data_io.product_settings.QMessageBox.warning')
    def test_table_view_initialization(self, mock_warning, product_settings_page, mock_parent):
        """Test that the table view is initialized correctly."""
        # Verify that the 'Category' column is hidden
        category_col_index = product_settings_page.product_data_df.columns.get_loc("Category")
        product_settings_page.table_view.hideColumn.assert_called_with(category_col_index)

    @patch('src.data_io.product_settings.QMessageBox.warning')
    def test_table_view_hide_category_missing(self, mock_warning, product_settings_page, mock_parent):
        """Test hiding the 'Category' column when it does not exist."""
        product_settings_page.product_data_df = pd.DataFrame({
            'ProductCode': ['P001'],
            'Product Name': ['Widget'],
            # 'Category' column is missing
        })
        with patch.object(product_settings_page, 'load_product_data', return_value=product_settings_page.product_data_df):
            # Reinitialize the table view
            product_settings_page.table_view = MagicMock()
            product_settings_page.product_data_df.columns = ['ProductCode', 'Product Name']
            product_settings_page.table_view.hideColumn.side_effect = lambda x: None
            product_settings_page.table_view.hideColumn.reset_mock()
            product_settings_page.adjust_column_widths()
            # Since 'Category' is missing, hideColumn should not be called
            product_settings_page.table_view.hideColumn.assert_not_called()
            mock_warning.assert_called_with(product_settings_page, "Warning", "The 'Category' column was not found and cannot be hidden.")

