"""Tests du formatage de l'horloge de jeu (ui.game_screen._mmss)."""

from __future__ import annotations

from orapa_mine.ui.game_screen import _mmss


def test_mmss_countdown_rounds_up():
    # Compte à rebours : on arrondit au-dessus pour n'atteindre 0:00 qu'à la fin.
    assert _mmss(300.0) == "5:00"
    assert _mmss(0.5) == "0:01"
    assert _mmss(0.0) == "0:00"


def test_mmss_elapsed_rounds_down():
    # Temps écoulé (compte croissant) : plancher sur la seconde entière.
    assert _mmss(0.9, ceil=False) == "0:00"
    assert _mmss(95.0, ceil=False) == "1:35"
    assert _mmss(119.9, ceil=False) == "1:59"
