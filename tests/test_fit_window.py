"""Fenêtre rétrécie pour tenir à l'écran (#86).

La fenêtre « naturelle » d'un écran est réduite uniformément si elle dépasse
le bureau disponible, pour ne jamais être rognée sur un petit portable.
"""

from __future__ import annotations

from orapa_mine.ui import theme


def test_window_that_fits_is_unchanged():
    assert theme.fit_window((800, 600), (1366, 768)) == (800, 600)


def test_exact_fit_is_unchanged():
    assert theme.fit_window((1366, 768), (1366, 768)) == (1366, 768)


def test_too_tall_window_is_scaled_down_to_fit():
    win = theme.fit_window((760, 846), (1300, 700))
    assert win[0] <= 1300 and win[1] <= 700
    # Ratio conservé (à 1 px près, arrondi entier).
    assert abs(win[0] / win[1] - 760 / 846) < 0.01


def test_too_wide_window_is_scaled_down_to_fit():
    win = theme.fit_window((2000, 500), (1000, 800))
    assert win[0] <= 1000 and win[1] <= 800
    assert abs(win[0] / win[1] - 2000 / 500) < 0.02


def test_scaling_is_limited_by_the_tighter_dimension():
    # Trop large ET trop haut : on prend le facteur le plus contraignant.
    win = theme.fit_window((1600, 1200), (800, 900))
    assert win[0] <= 800 and win[1] <= 900
    assert win == (800, 600)  # facteur 0.5 imposé par la largeur


def test_usable_desktop_is_positive():
    w, h = theme.usable_desktop()
    assert w > 0 and h > 0
