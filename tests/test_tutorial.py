# tests/test_tutorial.py

import pytest
from unittest.mock import patch, MagicMock
from PyQt5.QtWidgets import QApplication, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from src.utilities.tutorial import TutorialWindow
from src.utilities.utils import resource_path
import sys
import os
import tempfile

@pytest.fixture(scope="session")
def app():
    """Fixture to create a QApplication instance."""
    app = QApplication(sys.argv)
    yield app
    app.quit()

@pytest.fixture
def tutorial_window(qtbot):
    """Fixture to create and return a TutorialWindow instance with mocked images."""
    # Create temporary images to mock tutorial images
    with tempfile.TemporaryDirectory() as tmpdirname:
        image_paths = []
        for i in range(1, 6):
            img_path = os.path.join(tmpdirname, f'image{i}.png')
            # Create empty image files
            with open(img_path, 'wb') as f:
                f.write(b'\x89PNG\r\n\x1a\n')  # Minimal PNG header
            image_paths.append(img_path)

        # Mock resource_path to return paths to temporary images
        with patch('src.utilities.tutorial.resource_path') as mock_resource_path:
            # Map specific image paths based on the requested file
            def side_effect(path):
                basename = os.path.basename(path)
                if basename.startswith('image'):
                    index = int(basename[5].split('.')[0]) - 1
                    if 0 <= index < len(image_paths):
                        return image_paths[index]
                elif basename == 'placeholder.png':
                    # Create a placeholder image
                    placeholder_path = os.path.join(tmpdirname, 'placeholder.png')
                    with open(placeholder_path, 'wb') as f:
                        f.write(b'\x89PNG\r\n\x1a\n')  # Minimal PNG header
                    return placeholder_path
                return path  # Default behavior

            mock_resource_path.side_effect = side_effect

            window = TutorialWindow()
            qtbot.addWidget(window)
            window.show()
            yield window  # Provide the window to the test
            window.close()

def test_initialization(tutorial_window, qtbot):
    """Test that the TutorialWindow initializes correctly."""
    window = tutorial_window
    assert window.windowTitle() == "Tutorial"
    assert window.geometry().width() == 1000
    assert window.geometry().height() == 700
    assert window.current_page == 0
    assert window.total_pages == 5

    # Verify that the first page content is loaded
    first_page = window.tutorial_pages[0]
    pixmap = window.image_label.pixmap()
    assert pixmap is not None
    assert not pixmap.isNull()
    assert window.text_label.text() == first_page['text']
    assert window.page_indicator.text() == "Page 1 of 5"

def test_navigation_buttons(tutorial_window, qtbot):
    """Test navigating through tutorial pages using Next and Previous buttons."""
    window = tutorial_window

    # Initially on page 1
    assert window.current_page == 0
    assert window.prev_button.isEnabled() is False
    assert window.next_button.text() == "Next"

    # Click 'Next' to go to page 2
    qtbot.mouseClick(window.next_button, Qt.LeftButton)
    assert window.current_page == 1
    assert window.prev_button.isEnabled() is True
    assert window.next_button.text() == "Next"
    second_page = window.tutorial_pages[1]
    assert window.text_label.text() == second_page['text']

    # Click 'Next' to go to page 3
    qtbot.mouseClick(window.next_button, Qt.LeftButton)
    assert window.current_page == 2
    third_page = window.tutorial_pages[2]
    assert window.text_label.text() == third_page['text']

    # Click 'Previous' to go back to page 2
    qtbot.mouseClick(window.prev_button, Qt.LeftButton)
    assert window.current_page == 1
    assert window.text_label.text() == second_page['text']

    # Navigate to the last page
    qtbot.mouseClick(window.next_button, Qt.LeftButton)  # Page 2 -> 3
    qtbot.mouseClick(window.next_button, Qt.LeftButton)  # Page 3 -> 4
    qtbot.mouseClick(window.next_button, Qt.LeftButton)  # Page 4 -> 5
    assert window.current_page == 4
    assert window.next_button.text() == "Finish"
    last_page = window.tutorial_pages[4]
    assert window.text_label.text() == last_page['text']

    # Click 'Finish' to close the tutorial
    with patch.object(QMessageBox, 'information') as mock_info:
        qtbot.mouseClick(window.next_button, Qt.LeftButton)
        mock_info.assert_not_called()  # No info message expected
        assert not window.isVisible()  # The dialog should be closed

def test_close_button(tutorial_window, qtbot):
    """Test that clicking the Close button closes the tutorial."""
    window = tutorial_window

    # Ensure the window is visible
    assert window.isVisible()

    # Click 'Close' button
    qtbot.mouseClick(window.close_button, Qt.LeftButton)
    assert not window.isVisible()

def test_keyboard_navigation(tutorial_window, qtbot):
    """Test navigating through tutorial pages using keyboard arrows."""
    window = tutorial_window

    # Initially on page 1
    assert window.current_page == 0

    # Press Right Arrow to go to page 2
    qtbot.keyPress(window, Qt.Key_Right)
    assert window.current_page == 1

    # Press Right Arrow to go to page 3
    qtbot.keyPress(window, Qt.Key_Right)
    assert window.current_page == 2

    # Press Left Arrow to go back to page 2
    qtbot.keyPress(window, Qt.Key_Left)
    assert window.current_page == 1

    # Press Right Arrow to go to page 3
    qtbot.keyPress(window, Qt.Key_Right)
    assert window.current_page == 2

    # Navigate to the last page using keyboard
    qtbot.keyPress(window, Qt.Key_Right)  # Page 3 -> 4
    qtbot.keyPress(window, Qt.Key_Right)  # Page 4 -> 5
    assert window.current_page == 4
    assert window.next_button.text() == "Finish"

    # Press Right Arrow to finish
    with patch.object(QMessageBox, 'information') as mock_info:
        qtbot.keyPress(window, Qt.Key_Right)
        mock_info.assert_not_called()  # No info message expected
        assert not window.isVisible()  # The dialog should be closed

def test_image_loading(tutorial_window, qtbot):
    """Test that images are loaded correctly and handle missing images."""
    window = tutorial_window

    # Verify that all images are loaded correctly for each page
    for i in range(window.total_pages):
        window.current_page = i
        window.update_content()
        pixmap = window.image_label.pixmap()
        if pixmap:
            assert not pixmap.isNull(), f"Image for page {i+1} failed to load."
        else:
            # If no pixmap, ensure that an error message is displayed
            assert window.image_label.text() in ["Unable to load image.", "Image not found.", "Image not found."]

    # Test missing image by mocking resource_path to return a non-existent path
    with patch('src.utilities.tutorial.resource_path', return_value='non_existent_image.png'):
        window.current_page = 0
        window.update_content()
        assert window.image_label.text() == "Image not found."

def test_tutorial_completion(tutorial_window, qtbot):
    """Test that completing the tutorial marks it as completed."""
    window = tutorial_window

    # Mock accept method to verify it gets called on Finish
    with patch.object(window, 'accept') as mock_accept:
        # Navigate to the last page
        for _ in range(4):
            qtbot.mouseClick(window.next_button, Qt.LeftButton)
        assert window.current_page == 4
        assert window.next_button.text() == "Finish"

        # Click 'Finish' button
        qtbot.mouseClick(window.next_button, Qt.LeftButton)
        mock_accept.assert_called_once()
        assert not window.isVisible()

def test_placeholder_image(tutorial_window, qtbot):
    """Test that a placeholder image is shown when the main image is missing."""
    window = tutorial_window

    # Mock resource_path to return the placeholder image for a specific page
    with patch('src.utilities.tutorial.resource_path') as mock_resource_path:
        # Assume page 3's image is missing
        def side_effect(path):
            if 'image3.png' in path:
                return 'missing_image.png'  # Non-existent image
            return window.tutorial_pages[window.current_page]['image']
        mock_resource_path.side_effect = side_effect

        window.current_page = 2  # Page 3
        window.update_content()

        # Verify that the placeholder image is attempted to be loaded
        placeholder_pixmap = window.image_label.pixmap()
        if placeholder_pixmap:
            assert not placeholder_pixmap.isNull(), "Placeholder image failed to load."
        else:
            # If no pixmap, ensure that an error message is displayed
            assert window.image_label.text() == "Image not found."

