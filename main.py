"""Entry point for the Total Site Profile calculator (PyQt6 frontend).

Run with:  .venv/Scripts/python.exe main.py
"""

import sys

from PyQt6.QtWidgets import QApplication

from frontend.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Total Site Profile Calculator")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
