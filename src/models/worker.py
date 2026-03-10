# src/models/worker.py

# Standard Library Imports
import traceback  # For exception handling

# Third-party Imports
from PyQt5.QtCore import QObject, pyqtSignal

# Local Application Imports
from src.algorithms.packing_algorithm import run_packing_algorithm


class Worker(QObject):
    finished = pyqtSignal(list)  # Emits a list of packed containers
    progress = pyqtSignal(int)
    
    def __init__(self, items, containers, packing_method):
        super().__init__()
        self.items = items
        self.containers = containers
        self.packing_method = packing_method  # This is a string
        self._is_running = True
    
    def run(self):
        def progress_callback(progress):
            if not self._is_running:
                raise OperationCanceledException("Operation canceled")
            self.progress.emit(progress)

        try:
            packed_containers = run_packing_algorithm(
                self.items,
                self.containers,
                packing_method=self.packing_method,
                progress_callback=progress_callback
            )
            self.finished.emit(packed_containers)
        except OperationCanceledException:
            self.finished.emit([])
        except Exception as e:
            print(f"Exception in Worker.run(): {e}")
            traceback.print_exc()
            self.finished.emit([])

    def stop(self):
        self._is_running = False

class OperationCanceledException(Exception):
    """Custom exception to indicate operation cancellation."""
    pass


