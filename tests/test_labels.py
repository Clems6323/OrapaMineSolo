"""Tests du schéma d'étiquetage des bords (ui.theme) — sans pygame.

Grille 10×8 : chiffres 1–10 en haut, 11–18 à droite ; lettres A–H à gauche,
I–R en bas (continuité des lettres). Cohérent avec le vrai plateau (1–18 / A–R).
"""

from __future__ import annotations

from orapa_mine.model.gems import Direction, Position
from orapa_mine.ui import theme

W, H = 10, 8


def test_entry_labels_top_are_numbers_1_to_10():
    assert theme.entry_label(Position(0, 0), Direction.DOWN, W, H) == "1"
    assert theme.entry_label(Position(0, 9), Direction.DOWN, W, H) == "10"


def test_entry_labels_right_continue_numbers_11_to_18():
    assert theme.entry_label(Position(0, 9), Direction.LEFT, W, H) == "11"
    assert theme.entry_label(Position(7, 9), Direction.LEFT, W, H) == "18"


def test_entry_labels_left_are_letters_A_to_H():
    assert theme.entry_label(Position(0, 0), Direction.RIGHT, W, H) == "A"
    assert theme.entry_label(Position(7, 0), Direction.RIGHT, W, H) == "H"


def test_entry_labels_bottom_continue_letters_I_to_R():
    assert theme.entry_label(Position(7, 0), Direction.UP, W, H) == "I"
    assert theme.entry_label(Position(7, 9), Direction.UP, W, H) == "R"


def test_exit_labels_use_the_travel_edge():
    # Sortie vers le bas en colonne 0 -> bord bas -> lettre I.
    assert theme.exit_label(Position(7, 0), Direction.DOWN, W, H) == "I"
    # Sortie vers le haut en colonne 9 -> bord haut -> chiffre 10.
    assert theme.exit_label(Position(0, 9), Direction.UP, W, H) == "10"
    # Sortie vers la droite en ligne 0 -> bord droit -> chiffre 11.
    assert theme.exit_label(Position(0, 9), Direction.RIGHT, W, H) == "11"
