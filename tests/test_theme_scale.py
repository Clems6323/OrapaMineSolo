"""Mise à l'échelle DPI (ui.theme). En headless l'échelle vaut 1 (inchangé)."""

from __future__ import annotations

from orapa_mine.ui import theme


def test_headless_scale_is_identity():
    # Sous SDL dummy (tests), aucune mise à l'échelle : comportement d'origine.
    assert theme.UI_SCALE == 1.0
    assert theme.s(0) == 0
    assert theme.s(10) == 10
    assert theme.s(37) == 37


def test_s_rounds_to_int():
    assert isinstance(theme.s(15), int)


def test_font_is_cached():
    assert theme.font(18) is theme.font(18)
    assert theme.font(18, bold=True) is not theme.font(18)
