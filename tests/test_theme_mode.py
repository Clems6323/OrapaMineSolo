"""Tests de la bascule mode sombre / clair (ui.theme)."""

from __future__ import annotations

from orapa_mine.model.gems import GemColor
from orapa_mine.ui import theme


def test_toggle_switches_palette_and_back():
    try:
        theme.set_mode("dark")
        dark_bg = theme.BACKGROUND
        dark_white = theme.GEM_FILL[GemColor.WHITE]

        theme.toggle_mode()
        assert theme.MODE == "light"
        assert theme.BACKGROUND != dark_bg            # fond éclairci
        assert theme.GEM_FILL[GemColor.WHITE] != dark_white  # blanc adapté (visible)
        # Le fond clair est nettement plus lumineux que le fond sombre.
        assert sum(theme.BACKGROUND) > sum(dark_bg)

        theme.toggle_mode()
        assert theme.MODE == "dark"
        assert theme.BACKGROUND == dark_bg
    finally:
        theme.set_mode("dark")  # ne pas polluer l'état des autres tests


def test_set_mode_defaults_to_dark_on_unknown():
    try:
        theme.set_mode("banana")
        assert theme.MODE == "dark"
    finally:
        theme.set_mode("dark")
