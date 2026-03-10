# visualization_left_panel.py

# Standard Library Imports
from datetime import datetime
import os
import subprocess
import sys
import re

# Third-party Imports
from PyQt5.QtCore import Qt, QRectF, QLineF
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QBrush
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QTableWidget, 
    QTableWidgetItem, QLabel, QHeaderView, QMessageBox, QSizePolicy, 
    QFileDialog, QApplication
)

# Local Application Imports
from src.utilities.utils import get_permanent_directory, open_folder
from src.visualization.summary_exporter import SummaryExporter


class GravityCenterWidget(QWidget):
    """
    Custom widget to display the gravity center of the cargo within the container.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.container_length = 1.0  # Default length in cm
        self.container_width = 1.0   # Default width in cm
        # Container center (normalized [0,1] range)
        self.container_center = (0.5, 0.5)
        # Gravity center of cargo (normalized [0,1] range)
        self.cargo_center = (0.5, 0.5)
        self.setFixedSize(200, 100)  # Reduced height for less vertical space

    def set_data(self, container_length, container_width, cargo_center_x, cargo_center_y):
        """Sets the container dimensions and cargo gravity center."""
        self.container_length = container_length
        self.container_width = container_width
        # Normalize cargo center to [0,1] range
        if container_length > 0 and container_width > 0:
            self.cargo_center = (cargo_center_x / container_length, cargo_center_y / container_width)
        else:
            self.cargo_center = (0.5, 0.5)  # Default to center if dimensions are invalid
        self.update()  # Trigger a repaint

    def paintEvent(self, event):
        """Handles the painting of the widget."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = self.width()
        h = self.height()

        # Determine aspect ratio of container
        if self.container_width == 0:
            aspect_ratio = 1.0
        else:
            aspect_ratio = self.container_length / self.container_width

        # Determine rectangle size based on aspect ratio
        if aspect_ratio >= 1:
            rect_width = w - 20.0  # Padding of 10 pixels on each side
            rect_height = rect_width / aspect_ratio
            if rect_height > (h - 20.0):
                rect_height = h - 20.0
                rect_width = rect_height * aspect_ratio
        else:
            rect_height = h - 20.0
            rect_width = rect_height * aspect_ratio
            if rect_width > (w - 20.0):
                rect_width = w - 20.0
                rect_height = rect_width / aspect_ratio

        rect_x = (w - rect_width) / 2.0
        rect_y = (h - rect_height) / 2.0

        # Draw container boundary
        pen = QPen(Qt.black, 2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(rect_x, rect_y, rect_width, rect_height))

        # Container center (red dot)
        cx = rect_x + rect_width * self.container_center[0]
        cy = rect_y + rect_height * self.container_center[1]
        painter.setBrush(QBrush(Qt.red, Qt.SolidPattern))
        painter.drawEllipse(QRectF(cx - 3, cy - 3, 6, 6))  # 6x6 pixels circle

        # Cargo center (green dot)
        gx = rect_x + rect_width * self.cargo_center[0]
        gy = rect_y + rect_height * self.cargo_center[1]
        painter.setBrush(QBrush(Qt.green, Qt.SolidPattern))
        painter.drawEllipse(QRectF(gx - 3, gy - 3, 6, 6))  # 6x6 pixels circle

        # Draw cross lines through cargo center (green dot)
        cross_pen = QPen(Qt.darkGreen, 1, Qt.DashLine)
        painter.setPen(cross_pen)
        # Vertical line through cargo center
        line_vert = QLineF(gx, rect_y, gx, rect_y + rect_height)
        painter.drawLine(line_vert)
        # Horizontal line through cargo center
        line_horiz = QLineF(rect_x, gy, rect_x + rect_width, gy)
        painter.drawLine(line_horiz)


class LeftPanel(QWidget):
    """
    Left panel containing overviews like Packed Items and Loading Order.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent  # Reference to VisualizationPage
        self.summary_exporter = SummaryExporter(self.parent)  # Pass VisualizationPage instead of LeftPanel
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(5)  # Reduced spacing between widgets
        layout.setContentsMargins(10, 10, 10, 10)  # Tightened margins
        self.setLayout(layout)

        navigation_layout = QHBoxLayout()
        self.prev_button = QPushButton("Previous Container")
        self.prev_button.clicked.connect(self.parent.on_prev_clicked)
        self.next_button = QPushButton("Next Container")
        self.next_button.clicked.connect(self.parent.on_next_clicked)
        self.container_label = QLabel("Container 0 of 0")
        self.container_label.setAlignment(Qt.AlignCenter)
        self.container_label.setFont(QFont("Arial", 12, QFont.Bold))
        navigation_layout.addWidget(self.prev_button)
        navigation_layout.addWidget(self.container_label)
        navigation_layout.addWidget(self.next_button)
        layout.addLayout(navigation_layout)

        title_label = QLabel("<b>Packed Items Overview</b>")
        title_label.setFont(QFont("Arial", 14))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        self.items_table = QTableWidget()
        self.items_table.setColumnCount(6)
        self.items_table.setHorizontalHeaderLabels(["SKU", "Dimensions", "Weight", "Quantity", "Cartons", "Color"])
        header = self.items_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.items_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.items_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.items_table.setSelectionMode(QTableWidget.SingleSelection)
        self.items_table.itemSelectionChanged.connect(self.parent.on_items_table_selection_changed)
        layout.addWidget(self.items_table)

        separator = QLabel("<hr>")
        layout.addWidget(separator)

        loading_order_title = QLabel("<b>Loading Order</b>")
        loading_order_title.setFont(QFont("Arial", 14))
        loading_order_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(loading_order_title)

        self.loading_order_table = QTableWidget()
        self.loading_order_table.setColumnCount(5)
        self.loading_order_table.setHorizontalHeaderLabels(["Order", "SKU", "Position", "Dimensions", "Weight"])
        self.loading_order_table.verticalHeader().setVisible(False)
        loading_order_header = self.loading_order_table.horizontalHeader()
        loading_order_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        loading_order_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        loading_order_header.setSectionResizeMode(2, QHeaderView.Stretch)
        loading_order_header.setSectionResizeMode(3, QHeaderView.Stretch)
        loading_order_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.loading_order_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.loading_order_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.loading_order_table.setSelectionMode(QTableWidget.SingleSelection)
        self.loading_order_table.itemSelectionChanged.connect(self.parent.on_loading_order_selection_changed)
        layout.addWidget(self.loading_order_table, stretch=1)
        self.loading_order_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.loading_order_table.setMinimumHeight(200)

        self.space_used_label = QLabel("Space Used: 0.00%")
        self.space_used_label.setFont(QFont("Arial", 12))
        self.space_remaining_label = QLabel("Space Remaining: 0.00 m³")
        self.space_remaining_label.setFont(QFont("Arial", 12))
        layout.addWidget(self.space_used_label)
        layout.addWidget(self.space_remaining_label)

        self.weight_used_label = QLabel("Weight Used: 0.00 / 0.00 kg")
        self.weight_used_label.setFont(QFont("Arial", 12))
        layout.addWidget(self.weight_used_label)

        # Gravity Center Visualization
        self.gravity_widget = GravityCenterWidget(self)
        layout.addWidget(self.gravity_widget)

        # Minimal spacer
        spacer = QWidget()
        spacer.setFixedHeight(10)  # Minimal space
        layout.addWidget(spacer)

        # Screenshot Buttons
        screenshot_layout = QHBoxLayout()
        self.take_screenshot_button = QPushButton("Take Screenshot")
        self.take_screenshot_button.setToolTip("Take a screenshot of the current viewpoint.")
        self.take_screenshot_button.clicked.connect(self.take_screenshot)

        self.multi_angle_button = QPushButton("Take Multi-Angle Shots")
        self.multi_angle_button.setToolTip("Take multiple angle screenshots of every container.")
        self.multi_angle_button.clicked.connect(self.take_multi_angle_shots)

        screenshot_layout.addWidget(self.take_screenshot_button)
        screenshot_layout.addWidget(self.multi_angle_button)
        layout.addLayout(screenshot_layout)

        self.create_istia_export_button = QPushButton("Create Istia Export")
        self.create_istia_export_button.clicked.connect(self.summary_exporter.create_istia_export)
        layout.addWidget(self.create_istia_export_button)

        # Export Loading Summary Button
        self.export_summary_button = QPushButton("Export Loading Summary")
        self.export_summary_button.clicked.connect(self.summary_exporter.export_loading_summary)
        layout.addWidget(self.export_summary_button)

        # Back Button
        self.back_button = QPushButton("Back to Input")
        self.back_button.clicked.connect(self.parent.show_input_page)
        layout.addWidget(self.back_button)

    def update_aggregated_table(self, packed_items, sku_color_map, parent_items):
        self.items_table.setRowCount(0)
        
        # Count occurrences of each SKU in packed_items
        sku_counts = {}
        for packed_item in packed_items:
            base_sku = self.parent.get_base_sku(packed_item.sku)
            if base_sku in sku_counts:
                sku_counts[base_sku] += 1
            else:
                sku_counts[base_sku] = 1
        
        # Build a dictionary of original items by SKU with their quantities and carton info
        original_items_dict = {}
        for item in parent_items:
            base_sku = self.parent.get_base_sku(item.sku)
            if base_sku in original_items_dict:
                original_items_dict[base_sku]['original_quantity'] += item.quantity
                original_items_dict[base_sku]['cartons'] += getattr(item, 'cartons', 0)
            else:
                original_items_dict[base_sku] = {
                    'original_quantity': item.quantity,
                    'cartons': getattr(item, 'cartons', 0),
                    'is_carton_item': getattr(item, 'is_carton_item', False),
                    'dimensions': f"{int(item.length)} x {int(item.width)} x {int(item.height)}",
                    'color': sku_color_map.get(base_sku, (0, 0, 0, 1))
                }
        
        # Aggregate packed items with their colors and weights
        aggregated_items = {}
        for packed_item in packed_items:
            base_sku = self.parent.get_base_sku(packed_item.sku)
            
            if base_sku in aggregated_items:
                aggregated_items[base_sku]['total_weight'] += packed_item.weight
            else:
                # Get the original item info when available
                original_info = original_items_dict.get(base_sku, {})
                
                # Use the count from sku_counts for display_quantity
                display_quantity = sku_counts.get(base_sku, 1)
                
                aggregated_items[base_sku] = {
                    'dimensions': f"{int(packed_item.size[0])} x {int(packed_item.size[1])} x {int(packed_item.size[2])}",
                    'total_weight': packed_item.weight,
                    'color': sku_color_map.get(base_sku, (0, 0, 0, 1)),
                    'display_quantity': display_quantity,
                    'display_cartons': original_info.get('cartons', 0),
                    'is_carton_item': original_info.get('is_carton_item', False)
                }
        
        # Populate the table
        for base_sku, details in aggregated_items.items():
            row_position = self.items_table.rowCount()
            self.items_table.insertRow(row_position)
            
            # SKU
            sku_item = QTableWidgetItem(base_sku)
            self.items_table.setItem(row_position, 0, sku_item)
            
            # Dimensions
            dimensions_item = QTableWidgetItem(details['dimensions'])
            self.items_table.setItem(row_position, 1, dimensions_item)
            
            # Total Weight
            weight_item = QTableWidgetItem(f"{details['total_weight']:.2f}")
            self.items_table.setItem(row_position, 2, weight_item)
            
            # Display Quantity (now uses the counted occurrences)
            quantity_item = QTableWidgetItem(str(details['display_quantity']))
            self.items_table.setItem(row_position, 3, quantity_item)
            
            # Cartons
            cartons_item = QTableWidgetItem(str(details['display_cartons']))
            self.items_table.setItem(row_position, 4, cartons_item)
            
            # Color
            color = details['color']
            color_qcolor = QColor.fromRgbF(color[0], color[1], color[2], 1.0)
            color_item = QTableWidgetItem()
            color_item.setBackground(QBrush(color_qcolor))
            self.items_table.setItem(row_position, 5, color_item)
        
        self.items_table.resizeRowsToContents()

    def update_loading_order_table(self, packed_items):
        self.loading_order_table.setRowCount(0)
        sorted_items = sorted(
            packed_items,
            key=lambda item: (item.position[0], item.position[1], item.position[2])
        )
        for idx, packed_item in enumerate(sorted_items):
            row_position = self.loading_order_table.rowCount()
            self.loading_order_table.insertRow(row_position)
            order_item = QTableWidgetItem(str(idx + 1))
            self.loading_order_table.setItem(row_position, 0, order_item)
            sku_item = QTableWidgetItem(packed_item.sku)
            self.loading_order_table.setItem(row_position, 1, sku_item)
            x, y, z = packed_item.position
            position_text = f"({int(x)}, {int(y)}, {int(z)})"
            position_item = QTableWidgetItem(position_text)
            self.loading_order_table.setItem(row_position, 2, position_item)
            dimensions_text = f"{int(packed_item.size[0])} x {int(packed_item.size[1])} x {int(packed_item.size[2])}"
            dimensions_item = QTableWidgetItem(dimensions_text)
            self.loading_order_table.setItem(row_position, 3, dimensions_item)
            weight_item = QTableWidgetItem(f"{packed_item.weight:.2f}")
            self.loading_order_table.setItem(row_position, 4, weight_item)
            sku_item.setData(Qt.UserRole, id(packed_item))
        self.loading_order_table.resizeRowsToContents()

    def update_space_metrics(self, container, packed_items):
        if container:
            container_volume = container.length * container.width * container.height
            total_packed_volume_cm3 = sum(
                pi.size[0] * pi.size[1] * pi.size[2] for pi in packed_items
            )
            percentage_used = (total_packed_volume_cm3 / container_volume) * 100 if container_volume > 0 else 0
            remaining_volume_cm3 = container_volume - total_packed_volume_cm3
            remaining_volume_m3 = remaining_volume_cm3 / 1_000_000
            self.space_used_label.setText(f"Space Used: {percentage_used:.2f}%")
            self.space_remaining_label.setText(f"Space Remaining: {remaining_volume_m3:.2f} m³")
        else:
            self.space_used_label.setText("Space Used: 0.00%")
            self.space_remaining_label.setText("Space Remaining: 0.00 m³")

    def update_weight_used(self, container, packed_items):
        if container:
            total_weight = sum(pi.weight for pi in packed_items)
            max_weight = container.max_weight
            self.weight_used_label.setText(f"Weight Used: {total_weight:.2f} / {max_weight:.2f} kg")
        else:
            self.weight_used_label.setText("Weight Used: 0.00 / 0.00 kg")

    def sanitize_filename(self, name):
        """Sanitize the loading_plan_name to make it safe for filenames."""
        return re.sub(r'[^a-zA-Z0-9_\-]', '_', name)

    def take_screenshot(self):
        """Take a screenshot of the current viewpoint and open the folder."""
        screenshots_dir = get_permanent_directory("Screenshots")
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir, exist_ok=True)

        # Access the loading_plan_name
        loading_plan_name = getattr(self.parent.parent, 'loading_plan_name', None)

        # Grab the current framebuffer from the GL view
        img = self.parent.right_panel.view.grabFramebuffer()

        # Create a filename with timestamp, and include loading_plan_name if available
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        if loading_plan_name:
            sanitized_name = self.sanitize_filename(loading_plan_name)
            filename = os.path.join(screenshots_dir, f"screenshot_{sanitized_name}_{timestamp}.png")
        else:
            filename = os.path.join(screenshots_dir, f"screenshot_{timestamp}.png")

        # Save individual container image if available
        try:
            current_container_id = sorted(self.parent.containers_packed_items.keys())[self.parent.current_container_index]
            if loading_plan_name:
                container_image_path = os.path.join(screenshots_dir, f"container_{sanitized_name}_{current_container_id}_{timestamp}.png")
            else:
                container_image_path = os.path.join(screenshots_dir, f"container_{current_container_id}_{timestamp}.png")
            img.save(container_image_path, "PNG")
        except IndexError:
            QMessageBox.warning(self, "Error", "No containers available to take a screenshot of.")

        # Open the folder after saving
        open_folder(screenshots_dir)

    def take_multi_angle_shots(self):
        """Take multiple angle screenshots of every container from predefined angles."""
        screenshots_dir = get_permanent_directory("Screenshots")
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir, exist_ok=True)

        # Access and sanitize the loading_plan_name
        loading_plan_name = getattr(self.parent.parent, 'loading_plan_name', None)
        if not loading_plan_name:
            # Use current timestamp if loading_plan_name is empty
            loading_plan_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        sanitized_name = self.sanitize_filename(loading_plan_name)

        # Create a subfolder for this session using loading_plan_name
        session_dir = os.path.join(screenshots_dir, f"MultiAngleShots_{sanitized_name}")
        os.makedirs(session_dir, exist_ok=True)

        # Predefined angles (elevation, azimuth, name)
        angles = [
            (30,   0,  "front"),
            (30,  90,  "side"),
            (90,   0,  "top"),
            (45,  45,  "diagonal1"),
            (45, -45,  "diagonal2")
        ]

        # For each container, display it and take a shot from each angle
        total_containers = self.parent.total_containers
        if total_containers == 0:
            QMessageBox.information(self, "No Containers", "No containers to take shots of.")
            return

        container_ids = sorted(self.parent.containers_packed_items.keys())

        for idx, container_id in enumerate(container_ids, start=1):
            self.parent.display_container(container_id)
            QApplication.processEvents()

            for elevation, azimuth, angle_name in angles:
                # Adjust camera for top angle
                if angle_name == "top":
                    elevation = 85  # Slightly lower elevation for better top view
                    distance = 1500  # Increased distance for top view
                else:
                    distance = 1200  # Default distance

                # Adjust camera
                self.parent.right_panel.view.setCameraPosition(
                    elevation=elevation,
                    azimuth=azimuth,
                    distance=distance
                )
                QApplication.processEvents()

                self.parent.right_panel.update_wall_visibility()
                QApplication.processEvents()

                # Grab image
                img = self.parent.right_panel.view.grabFramebuffer()

                # Create filenames using loading_plan_name
                filename = os.path.join(session_dir, f"container_{sanitized_name}_{idx}_{angle_name}.png")
                img.save(filename, "PNG")

        # After finishing all, open the session folder
        open_folder(session_dir)

    def update_gravity_center(self, container, packed_items):
        """Updates the gravity center visualization."""
        """Compute cargo gravity center based on packed items."""
        if not packed_items or container is None:
            # Default to container center
            cx = container.length / 2 if container else 0.5
            cy = container.width / 2 if container else 0.5
        else:
            sum_x = 0
            sum_y = 0
            n = len(packed_items)
            for pi in packed_items:
                # pi.position is (x, y, z)
                # We'll consider (x, y) to compute horizontal gravity center
                # Assuming container (0,0) at one corner:
                sum_x += pi.position[0] + pi.size[0] / 2.0
                sum_y += pi.position[1] + pi.size[1] / 2.0
            cx = sum_x / n
            cy = sum_y / n

        # Update the gravity_widget
        if container:
            self.gravity_widget.set_data(container.length, container.width, cx, cy)
        else:
            self.gravity_widget.set_data(1.0, 1.0, 0.5, 0.5)  # Default values
