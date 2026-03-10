# src/main.py

# Standard Library Imports
import sys
import logging

# Third-party Imports
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

# Local Application Imports
from src.gui.main_window import MainWindow
from src.utilities.logging import setup_logging


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    setup_logging()
    app = QApplication(sys.argv)

    screen = app.primaryScreen()
    dpi = screen.logicalDotsPerInch()
    screen_width = screen.size().width()

    scaling_factor = dpi / 96.0

    if screen_width < 1920:
        scaling_factor *= 1.1

    default_font = app.font()
    new_point_size = default_font.pointSizeF() / scaling_factor
    default_font.setPointSizeF(new_point_size)
    app.setFont(default_font)
    
    window = MainWindow()
    window.show()
    try:
        sys.exit(app.exec_())
    except Exception as e:
        logging.exception("Application crashed")


if __name__ == '__main__':
    main()

