# src/utils.py

# Standard Library Imports
from datetime import datetime
import json
import os
import subprocess
import sys


def resource_path(relative_path):
    """Return the absolute path to a resource, handling PyInstaller builds."""
    try:
        base_path = sys._MEIPASS  # PyInstaller temp folder
    except AttributeError:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    return os.path.join(base_path, relative_path)


def get_permanent_directory(folder_name):
    """Return a user-writable directory for storing persistent data."""
    if sys.platform == 'win32':
        permanent_dir = os.path.join(os.getenv('APPDATA'), "LoadShippingContainers", folder_name)
    else:
        permanent_dir = os.path.join(os.path.expanduser('~'), ".LoadShippingContainers", folder_name)
    
    os.makedirs(permanent_dir, exist_ok=True)
    return permanent_dir


def get_version_file_path():
    """Return the path to the version tracking file."""
    return os.path.join(get_permanent_directory("Version Control"), "product_data_versions.json")


def check_product_data_version(version_flag):
    """Check if a product data update is needed based on the version flag."""
    version_file = get_version_file_path()

    if os.path.exists(version_file):
        try:
            with open(version_file, 'r') as f:
                versions = json.load(f)
        except json.JSONDecodeError:
            versions = {}
    else:
        versions = {}
        os.makedirs(os.path.dirname(version_file), exist_ok=True)
        with open(version_file, 'w') as f:
            json.dump(versions, f, indent=4)

    if version_flag not in versions:
        versions[version_flag] = {"applied": True, "date_applied": datetime.now().isoformat()}
        with open(version_file, 'w') as f:
            json.dump(versions, f, indent=4)
        return True

    return False


def open_folder(folder_path):
    """Open the specified folder in the system's file explorer."""
    try:
        if sys.platform.startswith('darwin'):
            subprocess.call(['open', folder_path])
        elif os.name == 'nt':
            os.startfile(folder_path)
        elif os.name == 'posix':
            subprocess.call(['xdg-open', folder_path])
        return True
    except Exception as ex:
        return False
