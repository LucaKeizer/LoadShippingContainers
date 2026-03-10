# tutorial.py

# Standard Library Imports
import os
import sys

# Third-party Imports
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, 
    QApplication, QDialog, QMessageBox
)

# Local Application Imports
from src.utilities.utils import resource_path


class TutorialWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tutorial")
        self.setGeometry(100, 100, 1000, 700)  # Reduced window size to 1000x700
        self.setModal(True)  # Make the tutorial window modal

        self.img_dir = resource_path('Data/Img')

        # Define tutorial pages with images and text
        self.tutorial_pages = [
            {
                'image': os.path.join(self.img_dir, 'image1.png'),
                'text': (
                    "<h2>Welcome to Sort Shipping Containers!</h2>"
                    "<p>Hello and welcome! We're thrilled to have you onboard. "
                    "This tutorial will guide you through the main features of our application, "
                    "helping you efficiently manage and visualize your shipping containers.</p>"
                    "<p>Let's get started!</p>"
                )
            },
            {
                'image': os.path.join(self.img_dir, 'image2.png'),
                'text': (
                    "<h2>Navigating the Input Page</h2>"
                    "<p>The Input Page is where you begin by entering your order codes. "
                    "Simply input one or multiple order codes separated by commas or new lines.</p>"
                    "<ul>"
                    "<li><strong>Item Input:</strong> Easily input and manage your order codes.</li>"
                    "<li><strong>Item Management:</strong> Review and edit item details before finalizing.</li>"
                    "<li><strong>Data Import:</strong> Seamlessly import fetched data with a single click.</li>"
                    "</ul>"
                )
            },
            {
                'image': os.path.join(self.img_dir, 'image3.png'),
                'text': (
                    "<h2>Importing data from Istia</h2>"
                    "<p>The Import Istia page allows you to fetch orders from the order monitor in istia."
                    "<ul>"
                    "<li><strong>Order Codes:</strong> You can enter multiple order codes at a time, and fetch their data using the Fetch Data button</li>"
                    "<li><strong>Fetched Order Data:</strong> Overview of all the items imported from istia, including their dimensions and quantity.</li>"
                    "</ul>"
                )
            },
            {
                'image': os.path.join(self.img_dir, 'image4.png'),
                'text': (
                    "<h2>Exploring the Visualization Page</h2>"
                    "<p>The Visualization Page provides a graphical representation of your shipping containers "
                    "and the items packed within them.</p>"
                    "<ul>"
                    "<li><strong>Packed Item Overview:</strong> Overview of all the items in each container.</li>"
                    "<li><strong>Container Visualization:</strong> Zoom, pan, and interact with the container layouts for detailed insights.</li>"
                    "<li><strong>Loading Order:</strong> A recommendation of how the items should be loaded into a shipping container.</li>"
                    "</ul>"
                    "<p>This visual tool helps you optimize space and ensure that your shipments are organized efficiently.</p>"
                )
            },
            {
                'image': os.path.join(self.img_dir, 'image5.png'),
                'text': (
                    "<h2>You're All Set!</h2>"
                    "<p>Congratulations on completing the tutorial. You're now ready to leverage the full potential of Sort Shipping Containers to optimize your shipping operations.</p>"
                    "<p>Start by entering your first order code and experience seamless data management and visualization.</p>"
                    "<p>Happy Packing!</p>"
                )
            }
        ]

        self.current_page = 0
        self.total_pages = len(self.tutorial_pages)

        self.setup_ui()
        self.update_content()

    def setup_ui(self):
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Image Label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.image_label)

        # Text Label with Increased Font Size
        self.text_label = QLabel()
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setWordWrap(True)
        font = QFont("Arial")
        font.setPointSize(12)  # Slightly increased font size for better readability
        self.text_label.setFont(font)
        self.layout.addWidget(self.text_label)

        # Page Indicator Label
        self.page_indicator = QLabel()
        self.page_indicator.setAlignment(Qt.AlignCenter)
        self.page_indicator.setStyleSheet("font-size: 16px; font-weight: bold;")  # Larger font for visibility
        self.layout.addWidget(self.page_indicator)

        # Navigation Buttons
        button_layout = QHBoxLayout()
        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self.show_previous_page)
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.show_next_page)
        button_layout.addWidget(self.prev_button)
        button_layout.addWidget(self.next_button)

        # Optional: Close Button
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.reject)  # Close the tutorial without marking as completed
        button_layout.addWidget(self.close_button)

        self.layout.addLayout(button_layout)

    def update_content(self):
        page = self.tutorial_pages[self.current_page]

        # Load Image
        image_path = page['image']
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                # Handle cases where the image file is corrupted or unreadable
                self.image_label.setText("Unable to load image.")
            else:
                # Calculate maximum dimensions based on window size
                max_width = int(self.width() * 0.7)  # 70% of window width
                max_height = int(self.height() * 0.9)  # 90% of window height

                # Scale pixmap while maintaining aspect ratio
                scaled_pixmap = pixmap.scaled(
                    max_width,
                    max_height,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
        else:
            # Optional: Provide a default placeholder image
            placeholder_path = os.path.join(self.img_dir, 'placeholder.png')
            if os.path.exists(placeholder_path):
                pixmap = QPixmap(placeholder_path)
                if pixmap.isNull():
                    self.image_label.setText("Placeholder image is unreadable.")
                else:
                    # Calculate maximum dimensions based on window size
                    max_width = self.width() * 0.9  # 90% of window width
                    max_height = self.height() * 0.4  # 40% of window height

                    # Scale pixmap while maintaining aspect ratio
                    scaled_pixmap = pixmap.scaled(
                        max_width,
                        max_height,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    self.image_label.setPixmap(scaled_pixmap)
            else:
                self.image_label.setText("Image not found.")

        # Update Text
        self.text_label.setText(page['text'])

        # Update Page Indicator
        self.page_indicator.setText(f"Page {self.current_page + 1} of {self.total_pages}")

        # Update Buttons
        self.prev_button.setEnabled(self.current_page > 0)
        if self.current_page == self.total_pages - 1:
            self.next_button.setText("Finish")
        else:
            self.next_button.setText("Next")

    def show_previous_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_content()

    def show_next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_content()
        else:
            # Tutorial finished
            self.accept()  # Close the tutorial window and mark as completed

    def keyPressEvent(self, event):
        """Handles keyboard shortcuts for navigating the tutorial."""
        if event.key() == Qt.Key_Right:
            self.show_next_page()
        elif event.key() == Qt.Key_Left:
            self.show_previous_page()
        else:
            super().keyPressEvent(event)

    # Removed resizeEvent since images are now scaled appropriately

if __name__ == "__main__":
    app = QApplication(sys.argv)
    data_directory = os.path.dirname(os.path.abspath(__file__))  # Example data directory
    tutorial = TutorialWindow(data_directory)
    tutorial.exec_()
