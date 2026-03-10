# src/utilities/logging.py

import logging
import sys
import os
from datetime import datetime
from src.utilities.utils import get_permanent_directory


class CustomFileHandler(logging.FileHandler):
    """
    Custom file handler to add an empty line after each log entry.
    """
    def emit(self, record):
        super().emit(record)
        self.stream.write("\n")  # Add an extra newline after each log entry


def setup_logging():
    log_dir = get_permanent_directory("Error Logs")
    os.makedirs(log_dir, exist_ok=True)

    # Generate a unique log file name based on the timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_file = os.path.join(log_dir, f'application_{timestamp}.log')

    logging.basicConfig(
        level=logging.ERROR,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            CustomFileHandler(log_file),  # Use custom handler for the file
            logging.StreamHandler(sys.stderr)  # Use stderr to align with excepthook
        ]
    )

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception
