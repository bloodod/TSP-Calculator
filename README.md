# TSP Calculator — Total Site Profile Calculator

A desktop tool for **Total Site heat integration analysis**, built with Python and PyQt6. Enter the site's hot and cold streams, and the program builds the composite curves, problem table, grand composite curve, total site profiles and the site utility grand composite curve (SUGCC) with its cogeneration targets.

## Features
- **Stream input** — inlet/outlet temperatures plus either the duty (kW) or the heat capacity flow rate (kW/°C); the other value is derived automatically.
- **Composite curves** — hot/cold composite curves with ΔTmin, QH,min / QC,min arrows, point coordinate labels, and a points table in the side panel.
- **Problem Table Algorithm (PTA)** — hot, cold and combined problem tables with the pinch and utility targets.
- **Grand Composite Curve (GCC)** — heat cascade with pinch and utility targets shown on the curve.
- **Total Site Profile (TSP)** — source/sink profiles mirrored on the energy axis, utility streams, TSP shift.
- **SUGCC & cogeneration** — expansion zones and W = η·ΔT·Q targets in a results table.
- Every figure can be resized, fit to the tab, exported as PNG/JPG, and every button works with the keyboard (Tab + Enter).

## Requirements
- Windows 10/11 (the app is packaged and tested on Windows)
- Python **3.11+** (only needed to run from source)

## Getting started (from source)
```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```
Then either double-click `run.bat` or run:
```bat
.venv\Scripts\python.exe main.py
```
> If you use `uv` instead: `uv venv .venv --python 3.11` then `uv pip install --python .venv\Scripts\python.exe -r requirements.txt`.

## Tests
```bat
.venv\Scripts\python.exe -m pytest tests
```

## Building a standalone exe
No Python needed on the target machine — the exe bundles everything:
```bat
.venv\Scripts\python.exe -m pip install pyinstaller
.venv\Scripts\pyinstaller.exe --noconfirm --clean --windowed --onefile ^
  --name TSP --icon assets/app.ico ^
  --add-data "assets/app.ico;assets" --add-data "assets/app_icon.png;assets" ^
  main.py
```
The single-file executable is written to `dist\TSP.exe`. Copy it to any Windows PC and double-click — nothing else needs to be installed (SmartScreen may ask to "Run anyway" on first launch).

## Project layout
| Path | Purpose |
|------|---------|
| `frontend/` | PyQt6 UI pages (one module per tab) |
| `backend/` | Calculation engine: streams, composites, PTA, GCC, TSP, SUGCC |
| `assets/` | Application icon |
| `tests/` | Unit + GUI tests (pytest) |
| `main.py` | Application entry point |
