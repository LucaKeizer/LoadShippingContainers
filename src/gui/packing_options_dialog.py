# packing_options_dialog.py

# Third-party Imports
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QLabel, QRadioButton, 
    QButtonGroup, QGroupBox, QCheckBox
)


class PackingOptionsDialog(QDialog):
    """
    Dialog for selecting packing options.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Packing Options")
        self.setFixedSize(400, 320)  # Increased size to accommodate new checkbox
        # Remove only the Context Help button while keeping the Close ('X') button
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setup_ui()

    def setup_ui(self):
        """Sets up the dialog's user interface."""
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Instruction Label
        instruction_label = QLabel("Select Packing Method:")
        instruction_label.setAlignment(Qt.AlignCenter)
        instruction_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        main_layout.addWidget(instruction_label)

        # Packing Method Group
        method_group_box = QGroupBox("Packing Method")
        method_layout = QVBoxLayout()
        
        self.vertical_loading_radio = QRadioButton("Vertical Loading")
        self.floor_loading_radio = QRadioButton("Floor Loading")
        self.vertical_loading_radio.setChecked(True)

        self.method_button_group = QButtonGroup(self)
        self.method_button_group.addButton(self.vertical_loading_radio)
        self.method_button_group.addButton(self.floor_loading_radio)

        method_layout.addWidget(self.vertical_loading_radio)
        method_layout.addWidget(self.floor_loading_radio)
        method_group_box.setLayout(method_layout)
        main_layout.addWidget(method_group_box)

        # Add Cache Checkbox
        self.use_cache_checkbox = QCheckBox("Use cached result")
        self.use_cache_checkbox.setChecked(True)
        main_layout.addWidget(self.use_cache_checkbox)

        # Add Combined Pallets Checkbox
        self.combined_pallets_checkbox = QCheckBox("Combined Pallets")
        self.combined_pallets_checkbox.setChecked(True)  # Default to True
        main_layout.addWidget(self.combined_pallets_checkbox)

        # Buttons Layout
        buttons_layout = QVBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        buttons_layout.addWidget(self.ok_button)
        buttons_layout.addWidget(self.cancel_button)
        main_layout.addLayout(buttons_layout)

    def get_selected_option(self):
        """Returns the selected packing method and cache option."""
        options = {
            'floor_loading': self.floor_loading_radio.isChecked(),
            'vertical_loading': self.vertical_loading_radio.isChecked(),
            'use_cache': self.use_cache_checkbox.isChecked(),
            'combined_pallets': self.combined_pallets_checkbox.isChecked()
        }
        return options
