# Load Shipping Containers

A desktop application that solves the **3D bin packing problem** for real-world logistics — optimally loading shipping containers with full visualization and export.

## What it does

Given a list of items (with real-world constraints like weight limits, stackability, and rotation rules), the app determines the optimal arrangement inside a shipping container and renders the result as an interactive 3D visualization.

**Supported container types:** 20 ft, 40 ft, 40 ft high-cube, 13.6 m trailer

## Technical highlights

- **Custom 3D packing algorithm** — heuristic approach placing heaviest items first (bottom-back-left), with intelligent item rotation to maximize volumetric efficiency
- **Constraint satisfaction** — enforces stackability rules, per-item and total weight limits, and pallet grouping logic (europallets, mixed, combined)
- **Threaded execution** — packing runs in a background worker thread (`QThread`) to keep the GUI responsive on large loads
- **Result caching** — identical scenarios are cached to avoid redundant computation
- **Interactive 3D visualization** — built with Matplotlib, supports free rotation, color-coded items, and multi-angle screenshot export
- **Data layer** — imports from Excel and JSON; exports loading plans, step-by-step instructions, and structured JSON for external system integration

## Architecture

```text
src/
├── algorithms/     # Packing logic and heuristics
├── models/         # Data models and background worker
├── gui/            # PyQt5 UI (input, options, main window)
├── visualization/  # 3D rendering and export
├── data_io/        # Excel/JSON import, product database
└── utilities/      # Logging, shared utils
```

## Stack

Python · PyQt5 · Matplotlib · openpyxl · PyInstaller (packaged as standalone `.exe`)

## Running locally

```bash
pip install -r requirements.txt
python main.py
```
