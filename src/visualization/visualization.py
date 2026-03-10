# visualization.py

# Standard Library Imports
import re  # For regular expressions

# Third-party Imports
import numpy as np
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QBrush
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QMessageBox, QSplitter

# Local Application Imports
from src.visualization.visualization_left_panel import LeftPanel
from src.visualization.visualization_right_panel import RightPanel


class VisualizationPage(QWidget):
    """
    Page for displaying the 3D visualization of the packed containers.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent  # Reference to MainWindow
        self.containers = {}  # Store container dimensions per container_id
        self.containers_packed_items = {}  # Map container_id to packed items
        self.sku_color_map = {}  # Store SKU color mapping
        self.current_container_index = 0  # Index of the currently displayed container
        self.total_containers = 0  # Total number of containers
        self.items = []  # Reference to MainWindow's items
        self.setup_ui()

    def setup_ui(self):
        """Sets up the UI components."""
        # Main horizontal layout to hold the splitter
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins for more space
        self.setLayout(main_layout)

        # Create a splitter to allow resizing between panels
        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)

        # Instantiate Left and Right Panels
        self.left_panel = LeftPanel(parent=self)
        self.right_panel = RightPanel(parent=self)

        # Add panels to the splitter
        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.right_panel)
        
        # Set initial sizes for the panels (e.g., 30% left, 70% right)
        self.splitter.setSizes([400, 600])  # These are proportional values
        
        # Set minimum width for the left panel
        self.left_panel.setMinimumWidth(300)  # Prevent it from becoming too small
        
        # Set stretch factors for the panels
        self.splitter.setStretchFactor(0, 0)  # Left panel (don't stretch)
        self.splitter.setStretchFactor(1, 1)  # Right panel (stretch to fill space)
        
        # Add a handle width for easier grabbing
        self.splitter.setHandleWidth(8)
        
        # Set stylesheet for the splitter handle to make it more visible
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #ccc;
                border: 1px solid #999;
            }
            QSplitter::handle:hover {
                background-color: #aaa;
            }
        """)

    # All other methods remain unchanged
    def show_input_page(self):
        """Switches to the Input Page by calling the MainWindow's method."""
        if hasattr(self.parent, 'show_input_page'):
            self.parent.show_input_page()
        else:
            QMessageBox.warning(self, "Error", "Main window does not have 'show_input_page' method.")

    def clear_visualization(self):
        """Clears all packed items and container walls from the visualization."""
        self.right_panel.clear_visualization()

        # Clear the side panel tables
        self.left_panel.items_table.setRowCount(0)
        self.left_panel.loading_order_table.setRowCount(0)

        # Reset Space Labels
        self.left_panel.space_used_label.setText("Space Used: 0.00%")
        self.left_panel.space_remaining_label.setText("Space Remaining: 0.00 m³")

        # Reset Weight Used Label
        self.left_panel.weight_used_label.setText("Weight Used: 0.00 / 0.00 kg")

        # Reset Gravity Center Visualization
        self.left_panel.gravity_widget.set_data(1.0, 1.0, 0.5, 0.5)  # Default to center

    def display_packed_items(self, containers, packed_items, sku_color_map):
        """
        Displays the containers and packed items in the 3D view and updates the side panel.
        :param containers: A dictionary mapping container_id to Container objects
        :param packed_items: A list of packed items
        :param sku_color_map: A mapping of SKU to color
        """
        self.clear_visualization()
        self.containers = containers  # Store container dimensions per container_id
        self.sku_color_map = sku_color_map  # Store SKU color mapping
        
        # Store the reference to the items in MainWindow's data_manager
        self.items = self.parent.data_manager.items
        
        # Group packed items by container_id
        self.containers_packed_items = {}
        for packed_item in packed_items:
            container_id = packed_item.container_id
            if container_id not in self.containers_packed_items:
                self.containers_packed_items[container_id] = []
            self.containers_packed_items[container_id].append(packed_item)

        # Update container count
        self.total_containers = len(self.containers_packed_items)
        if self.total_containers == 0:
            QMessageBox.warning(self, "No Containers", "No containers were packed.")
            self.left_panel.container_label.setText("Container 0 of 0")
            self.left_panel.prev_button.setEnabled(False)
            self.left_panel.next_button.setEnabled(False)
            return

        # Initialize current container index
        self.current_container_index = 0

        # Update container label
        self.left_panel.container_label.setText(f"Container {self.current_container_index + 1} of {self.total_containers}")

        # Enable or disable navigation buttons based on container count
        self.update_navigation_buttons()

        # Display the first container
        first_container_id = sorted(self.containers_packed_items.keys())[0]
        self.display_container(first_container_id)

    def display_container(self, container_id):
        """Displays the specified container and its packed items."""
        self.right_panel.clear_visualization()

        # Retrieve the container dimensions for this container_id
        container = self.containers.get(container_id)
        if not container:
            QMessageBox.warning(self, "Error", f"Container ID {container_id} not found.")
            return

        # Draw the container
        self.right_panel.draw_container(container)

        # Draw the packed items in this container
        packed_items = self.containers_packed_items.get(container_id, [])

        # Store a mapping from packed_item_id to the mesh for highlighting
        self.packed_item_mesh_map = {}

        for packed_item in packed_items:
            mesh = self.right_panel.draw_packed_item(packed_item, self.sku_color_map, container)
            self.packed_item_mesh_map[id(packed_item)] = mesh

        # Update Side Panel with Packed Items in this container
        self.left_panel.update_aggregated_table(packed_items, self.sku_color_map, self.items)
        self.left_panel.update_loading_order_table(packed_items)
        self.left_panel.update_space_metrics(container, packed_items)
        self.left_panel.update_weight_used(container, packed_items)

        # Update Gravity Center Visualization
        self.left_panel.update_gravity_center(container, packed_items)

    def update_navigation_buttons(self):
        """Enables or disables navigation buttons based on current container index."""
        # Previous button enabled only if not on the first container
        if self.current_container_index > 0:
            self.left_panel.prev_button.setEnabled(True)
        else:
            self.left_panel.prev_button.setEnabled(False)

        # Next button enabled only if not on the last container
        if self.current_container_index < self.total_containers - 1:
            self.left_panel.next_button.setEnabled(True)
        else:
            self.left_panel.next_button.setEnabled(False)

    def on_prev_clicked(self):
        """Handles the Previous Container button click."""
        if self.current_container_index > 0:
            self.current_container_index -= 1
            self.left_panel.container_label.setText(f"Container {self.current_container_index + 1} of {self.total_containers}")
            self.update_navigation_buttons()
            container_id = sorted(self.containers_packed_items.keys())[self.current_container_index]
            self.display_container(container_id)

    def on_next_clicked(self):
        """Handles the Next Container button click."""
        if self.current_container_index < self.total_containers - 1:
            self.current_container_index += 1
            self.left_panel.container_label.setText(f"Container {self.current_container_index + 1} of {self.total_containers}")
            self.update_navigation_buttons()
            container_id = sorted(self.containers_packed_items.keys())[self.current_container_index]
            self.display_container(container_id)

    def on_items_table_selection_changed(self):
        """Handles highlighting of items when a row in the Aggregated Packed Items table is selected."""
        selected_items = self.left_panel.items_table.selectedItems()
        if selected_items:
            # Assuming selection behavior is SelectRows and SingleSelection
            # SKU is in column 0
            sku_item = selected_items[0]  # First item in the row
            sku = sku_item.text()
            # Highlight items with this SKU
            self.right_panel.highlight_packed_item_by_sku(sku)
        else:
            # No selection, reset highlights
            self.right_panel.reset_highlights()

    def on_loading_order_selection_changed(self):
        """Handles highlighting of items when a row in the Loading Order table is selected."""
        selected_items = self.left_panel.loading_order_table.selectedItems()
        if selected_items:
            # Assuming selection behavior is SelectRows and SingleSelection
            # SKU is in column 1
            row = self.left_panel.loading_order_table.currentRow()
            sku_item = self.left_panel.loading_order_table.item(row, 1)
            # Get the packed_item id stored in the SKU item's data
            packed_item_id = sku_item.data(Qt.UserRole)
            # Highlight the corresponding packed item
            self.right_panel.highlight_packed_item(packed_item_id)
        else:
            # No selection, reset highlights
            self.right_panel.reset_highlights()

    def get_base_sku(self, sku):
        """Extracts the base SKU by removing any numeric prefix."""
        match = re.match(r'^(\d+)-(.*)$', sku)
        if match:
            return match.group(2)
        else:
            return sku