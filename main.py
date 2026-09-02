"""Entry point for the Total Site Profile calculator (PyQt6 frontend).

Run with:  .venv/Scripts/python.exe main.py
"""

import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from frontend.main_window import MainWindow

# In the frozen exe the assets live inside the bundle (_MEIPASS); when run
# from source they live next to main.py in the project's assets folder.
ASSET_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "assets"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Total Site Profile Calculator")
    icon = ASSET_DIR / "app_icon.png"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
