import re
import math
import numpy as np
import OpenGL.GL as GL
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush, QPainterPath
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from pyqtgraph.opengl import GLViewWidget, GLGridItem, MeshData, GLMeshItem


class CustomGLMeshItem(GLMeshItem):
    """
    Custom GLMeshItem that allows dynamic setting of edge line width and edge color.
    """
    def __init__(self, *args, edgeWidth=1.0, edgeColor=(0, 0, 0, 1), glOptions='opaque', **kwargs):
        super().__init__(*args, **kwargs)
        self.edgeWidth = edgeWidth
        self.edgeColor = edgeColor
        self.opts['edgeColor'] = edgeColor
        self.setGLOptions(glOptions)

    def set_edge_color(self, color):
        """Sets the edge color and updates the mesh item."""
        self.edgeColor = color
        self.opts['edgeColor'] = color
        self.update()

    def set_edge_width(self, width):
        """Sets the edge line width and updates the mesh item."""
        self.edgeWidth = width
        self.update()

    def paint(self):
        """Overrides the paint method to set and restore the OpenGL line width."""
        current_line_width = GL.glGetFloatv(GL.GL_LINE_WIDTH)
        GL.glLineWidth(self.edgeWidth)
        super().paint()
        GL.glLineWidth(current_line_width)


class CustomGLViewWidget(GLViewWidget):
    """
    Custom GLViewWidget that manages camera constraints and updates related UI elements.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.minimum_elevation = 0    # Minimum elevation angle in degrees
        self.maximum_elevation = 90   # Maximum elevation angle in degrees
        self.opts['elevation'] = 30    # Initial elevation angle
        self.parent_widget = parent   # Reference to the parent widget (RightPanel)

    def mouseMoveEvent(self, ev):
        """Handles mouse movement events to constrain camera elevation and update UI elements."""
        super().mouseMoveEvent(ev)
        # Constrain elevation angle
        if self.opts['elevation'] < self.minimum_elevation:
            self.opts['elevation'] = self.minimum_elevation
            self.update()
        elif self.opts['elevation'] > self.maximum_elevation:
            self.opts['elevation'] = self.maximum_elevation
            self.update()
        # Update wall visibility and compass
        self.parent_widget.update_wall_visibility()
        self.parent_widget.update_compass()

    def wheelEvent(self, ev):
        """Handles mouse wheel events to update wall visibility and compass."""
        super().wheelEvent(ev)
        self.parent_widget.update_wall_visibility()
        self.parent_widget.update_compass()

    def mousePressEvent(self, ev):
        """
        Handles mouse press events to update wall visibility and compass.
        """
        super().mousePressEvent(ev)
        self.parent_widget.update_wall_visibility()
        self.parent_widget.update_compass()

    def mouseReleaseEvent(self, ev):
        """
        Handles mouse release events to update wall visibility and compass.
        """
        super().mouseReleaseEvent(ev)
        self.parent_widget.update_wall_visibility()
        self.parent_widget.update_compass()

    def keyPressEvent(self, ev):
        """
        Handles key press events to update wall visibility and compass.
        """
        super().keyPressEvent(ev)
        self.parent_widget.update_wall_visibility()
        self.parent_widget.update_compass()

    def keyReleaseEvent(self, ev):
        """
        Handles key release events to update wall visibility and compass.
        """
        super().keyReleaseEvent(ev)
        self.parent_widget.update_wall_visibility()
        self.parent_widget.update_compass()


class CompassWidget(QWidget):
    """
    Widget that displays a compass indicating the current azimuth direction.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.azimuth = 0  # Current azimuth angle in degrees
        self.setAttribute(Qt.WA_TranslucentBackground)  # Make background transparent
        self.setFixedSize(80, 80)  # Fixed size for the compass

    def setAzimuth(self, angle):
        """
        Updates the azimuth angle and repaints the compass.
        """
        self.azimuth = angle
        self.update()

    def paintEvent(self, event):
        """
        Paints the compass graphic.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Define center and radius
        center = self.rect().center()
        radius = 35

        # Draw outer circle
        painter.setPen(QPen(Qt.black, 2))
        painter.setBrush(QBrush(Qt.white))
        painter.drawEllipse(center, radius, radius)

        # Translate and rotate painter for the needle
        painter.translate(center)
        painter.rotate(-self.azimuth)

        # Define needle path
        path = QPainterPath()
        path.moveTo(0, -radius + 5)
        path.lineTo(-5, 0)
        path.lineTo(5, 0)
        path.closeSubpath()

        # Draw needle
        painter.setBrush(QBrush(Qt.red))
        painter.drawPath(path)


class RightPanel(QWidget):
    """
    Right panel containing the 3D visualization and compass.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent  # Reference to the main VisualizationPage
        self.setup_ui()

    def setup_ui(self):
        """
        Sets up the user interface components of the right panel.
        """
        # Main vertical layout
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Initialize the custom GL view widget
        self.view = CustomGLViewWidget(self)
        self.view.setCameraPosition(distance=1200, elevation=30)
        layout.addWidget(self.view)

        # Set background color to light grey
        self.view.setBackgroundColor(QColor(200, 200, 200))

        # Add grid item for reference (floor)
        grid = GLGridItem()
        grid.setSize(2000, 2000)        # Grid size
        grid.setSpacing(100, 100)       # Grid spacing
        grid.setColor(QColor(150, 150, 150))  # Grid color
        grid.translate(0, 0, 0)         # Position grid at Z=0
        self.view.addItem(grid)

        # Initialize lists and dictionaries to track visual items
        self.packed_visual_items = []    # List to store packed items
        self.container_walls = {}        # Dictionary to store container walls
        self.visible_walls = set()       # Set to track currently visible walls

        # Initialize compass widget
        self.compass = CompassWidget(self)
        self.compass.raise_()  # Ensure compass is on top

        # Disable navigation buttons initially
        self.parent.left_panel.prev_button.setEnabled(False)
        self.parent.left_panel.next_button.setEnabled(False)

    def resizeEvent(self, event):
        """
        Handles the resize event to reposition the compass widget.
        """
        super().resizeEvent(event)
        # Position compass at the top-right corner with a 10-pixel margin
        x = self.width() - self.compass.width() - 10
        y = 10
        self.compass.move(x, y)

    def clear_visualization(self):
        """
        Clears all packed items and container walls from the visualization.
        """
        # Remove packed items from the view
        for item in self.packed_visual_items:
            self.view.removeItem(item)
        self.packed_visual_items = []

        # Remove container walls from the view
        for wall_mesh in self.container_walls.values():
            if wall_mesh in self.view.items:
                self.view.removeItem(wall_mesh)
        self.container_walls = {}
        self.visible_walls = set()

    def draw_container(self, container):
        """
        Draws the container in the 3D view using separate walls.
        """
        # Extract container dimensions
        L, W, H = container.length, container.width, container.height
        x0, x1 = -L / 2, L / 2
        y0, y1 = -W / 2, W / 2
        z0, z1 = 0, H

        # Define vertices for each wall of the container
        walls = {
            'bottom': np.array([
                [x0, y0, z0],
                [x0, y1, z0],
                [x1, y1, z0],
                [x1, y0, z0],
            ]),
            'top': np.array([
                [x0, y0, z1],
                [x1, y0, z1],
                [x1, y1, z1],
                [x0, y1, z1],
            ]),
            'front': np.array([
                [x0, y0, z0],
                [x0, y0, z1],
                [x1, y0, z1],
                [x1, y0, z0],
            ]),
            'back': np.array([
                [x0, y1, z0],
                [x1, y1, z0],
                [x1, y1, z1],
                [x0, y1, z1],
            ]),
            'left': np.array([
                [x0, y0, z0],
                [x0, y0, z1],
                [x0, y1, z1],
                [x0, y1, z0],
            ]),
            'right': np.array([
                [x1, y0, z0],
                [x1, y0, z1],
                [x1, y1, z1],
                [x1, y1, z0],
            ]),
        }

        # Create and add mesh items for each wall
        for wall_name, vertices in walls.items():
            faces = np.array([
                [0, 1, 2],
                [0, 2, 3],
            ])
            edges = np.array([
                [0, 1],
                [1, 2],
                [2, 3],
                [3, 0],
            ])  # Define only the outer edges to avoid diagonal lines

            meshdata = MeshData(vertexes=vertices, faces=faces, edges=edges)

            wall_mesh = CustomGLMeshItem(
                meshdata=meshdata,
                smooth=False,
                color=(0.5, 0.5, 0.5, 1.0),    # Opaque grey color
                edgeColor=(0, 0, 0, 1),        # Solid black edges
                drawEdges=True,
                drawFaces=True,
                edgeWidth=2.0,
                glOptions='opaque'             # Make walls opaque
            )

            # Add the wall mesh to the view and tracking structures
            self.view.addItem(wall_mesh)
            self.container_walls[wall_name] = wall_mesh
            self.visible_walls.add(wall_name)  # Initially, all walls are visible

        # Update wall visibility based on initial camera position
        self.update_wall_visibility()

    def draw_packed_item(self, packed_item, sku_color_map, container):
        """
        Draws a packed item (e.g., a box) in the 3D view.
        """
        # Extract packed item properties
        position = packed_item.position
        size = packed_item.size
        sku = packed_item.sku

        # Assign color based on SKU
        color = self.get_color_for_sku(sku, sku_color_map)
        color = color[:3] + (1.0,)  # Ensure alpha is 1.0 for opaque rendering

        # Shift position to align with container centered at origin
        offset_x = -container.length / 2
        offset_y = -container.width / 2

        adjusted_position = (
            position[0] + offset_x,
            position[1] + offset_y,
            position[2]
        )

        # Define the 8 corners of the packed item
        L, W, H = size
        x, y, z = adjusted_position
        corners = np.array([
            [x,         y,         z],        # 0
            [x + L,     y,         z],        # 1
            [x + L,     y + W,     z],        # 2
            [x,         y + W,     z],        # 3
            [x,         y,         z + H],    # 4
            [x + L,     y,         z + H],    # 5
            [x + L,     y + W,     z + H],    # 6
            [x,         y + W,     z + H],    # 7
        ])

        # Define the faces (triangles) of the box
        faces = np.array([
            [0, 1, 2], [0, 2, 3],  # Bottom
            [4, 5, 6], [4, 6, 7],  # Top
            [0, 1, 5], [0, 5, 4],  # Front
            [1, 2, 6], [1, 6, 5],  # Right
            [2, 3, 7], [2, 7, 6],  # Back
            [3, 0, 4], [3, 4, 7],  # Left
        ])

        # Define edges explicitly to remove diagonal lines
        edges = np.array([
            [0, 1],
            [1, 2],
            [2, 3],
            [3, 0],
            [4, 5],
            [5, 6],
            [6, 7],
            [7, 4],
            [0, 4],
            [1, 5],
            [2, 6],
            [3, 7],
        ])

        # Create MeshData object with explicit edges
        meshdata = MeshData(vertexes=corners, faces=faces, edges=edges)

        # Create CustomGLMeshItem for the packed item
        packed_mesh = CustomGLMeshItem(
            meshdata=meshdata,
            smooth=True,              # Enable smooth shading
            color=color,              # Assigned color
            edgeColor=(0, 0, 0, 1),   # Black edges
            drawEdges=True,
            drawFaces=True,
            edgeWidth=2.0,            # Set edge line width
            glOptions='opaque'        # Render as opaque
        )

        # Store reference to the packed item
        packed_mesh.packed_item = packed_item

        # Store default edge properties for resetting later
        packed_mesh.default_edge_color = packed_mesh.edgeColor
        packed_mesh.default_edge_width = packed_mesh.edgeWidth

        # Add the packed item mesh to the view and tracking list
        self.view.addItem(packed_mesh)
        self.packed_visual_items.append(packed_mesh)

        return packed_mesh  # Return the mesh for potential mapping

    def update_wall_visibility(self):
        """Updates the visibility of container walls based on the current camera position."""
        # Get camera position and focal point
        camera_pos = np.array(self.view.cameraPosition())
        center = np.array(self.view.opts['center'])
        view_vector = center - camera_pos

        # Normalize the view vector
        norm = np.linalg.norm(view_vector)
        if norm == 0:
            norm = 1
        view_vector /= norm

        # Define normals for each wall
        wall_normals = {
            'front': np.array([0, -1, 0]),
            'back': np.array([0, 1, 0]),
            'left': np.array([-1, 0, 0]),
            'right': np.array([1, 0, 0]),
            'top': np.array([0, 0, 1]),
            'bottom': np.array([0, 0, -1]),
        }

        # Iterate through each wall to determine visibility
        for wall_name, normal in wall_normals.items():
            if wall_name == 'bottom':
                # Ensure the bottom wall is always visible
                if wall_name not in self.visible_walls:
                    wall_mesh = self.container_walls[wall_name]
                    self.view.addItem(wall_mesh)
                    self.visible_walls.add(wall_name)
                continue  # Skip visibility toggling for the bottom wall

            # Calculate the dot product between view vector and wall normal
            dot_product = np.dot(view_vector, normal)
            wall_mesh = self.container_walls[wall_name]

            if dot_product < 0:
                # Wall is facing the camera; hide it by removing from view
                if wall_name in self.visible_walls:
                    self.view.removeItem(wall_mesh)
                    self.visible_walls.remove(wall_name)
            else:
                # Wall is facing away from the camera; show it by adding to view
                if wall_name not in self.visible_walls:
                    self.view.addItem(wall_mesh)
                    self.visible_walls.add(wall_name)

    def get_color_for_sku(self, sku, sku_color_map):
        """Retrieves the assigned color for a given SKU. Defaults to black if the SKU is not found."""
        return sku_color_map.get(sku, (0, 0, 0, 1))

    def highlight_packed_item_by_sku(self, sku):
        """Highlights all packed items that match the given SKU."""
        # Reset all highlights to default
        self.reset_highlights()

        # Retrieve the base SKU for comparison
        base_sku = self.parent.get_base_sku(sku)

        # Iterate through all packed items to apply highlighting
        for mesh in self.packed_visual_items:
            mesh_sku = self.parent.get_base_sku(mesh.packed_item.sku)
            if mesh_sku == base_sku:
                # Highlight by setting edge color to bright yellow and increasing edge width
                mesh.set_edge_color((1, 1, 0, 1))  # Bright yellow
                mesh.set_edge_width(5.0)
            else:
                # Optionally, other items can be dimmed or left unchanged
                pass  # No change for non-matching items

    def highlight_packed_item(self, packed_item_id):
        """Highlights a single packed item based on its unique identifier."""
        # Reset all highlights to default
        self.reset_highlights()

        # Iterate through packed items to find the matching ID
        for mesh in self.packed_visual_items:
            if id(mesh.packed_item) == packed_item_id:
                # Highlight by setting edge color to bright yellow and increasing edge width
                mesh.set_edge_color((1, 1, 0, 1))  # Bright yellow
                mesh.set_edge_width(5.0)
                break  # Exit loop after finding the item

    def reset_highlights(self):
        """
        Resets all packed items to their default appearance."""
        for mesh in self.packed_visual_items:
            # Reset edge color and width to their default values
            mesh.set_edge_color(mesh.default_edge_color)
            mesh.set_edge_width(mesh.default_edge_width)

    def update_compass(self):
        """Updates the compass widget based on the current azimuth angle."""
        # Retrieve the current azimuth angle from the view options
        azimuth = self.view.opts.get('azimuth', 0) % 360

        # Update the compass widget with the new azimuth
        self.compass.setAzimuth(azimuth)
