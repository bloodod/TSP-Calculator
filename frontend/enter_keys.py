"""Keyboard-activation conventions for buttons.

Qt push buttons activate on the Enter key only while they hold keyboard
focus AND are auto-default buttons. Most of our buttons accept neither by
default, so Enter does nothing on them. :func:`make_buttons_enter_activatable`
gives every push button under a window a strong focus policy (Tab and mouse
clicks can focus it) and marks it as an auto-default button, so pressing
Enter on any button activates it. (Outside dialogs, Enter still goes to the
focused widget, so this never hijacks Enter typed in text fields.)

Convention for the future: call this helper once on every top-level window
*after* its UI (and any later-added pages or dialogs) is built, so every
new button automatically follows the same rule.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton, QWidget


def make_buttons_enter_activatable(root: QWidget) -> int:
    """Make every push button under ``root`` accept Enter activation.

    Returns the number of buttons updated. Run once per window after its UI
    is built; run it again after adding more buttons (for example when a
    dialog is created later).
    """
    count = 0
    for button in root.findChildren(QPushButton):
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        button.setAutoDefault(True)
        count += 1
    return count
