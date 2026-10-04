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


# --- Étiquetage des cases (question « Qu'y a-t-il en A1 ? ») ------------------


def test_cell_label_is_row_letter_then_column_number():
    # A1 = coin haut-gauche ; la lettre est la LIGNE, le chiffre la COLONNE.
    assert theme.cell_label(Position(0, 0)) == "A1"
    assert theme.cell_label(Position(2, 3)) == "C4"
    assert theme.cell_label(Position(7, 9)) == "H10"


def test_parse_cell_label_round_trips():
    for pos in (Position(0, 0), Position(2, 3), Position(7, 9)):
        assert theme.parse_cell_label(theme.cell_label(pos), W, H) == pos


def test_parse_cell_label_rejects_off_board():
    assert theme.parse_cell_label("A11", W, H) is None  # colonne 11 hors 10
    assert theme.parse_cell_label("I1", W, H) is None  # ligne I hors 8


def test_cell_and_edge_labels_do_not_collide():
    # Un libellé de bord (chiffre seul ou lettre seule) n'est jamais lu comme case.
    assert theme.looks_like_cell_label("5") is False
    assert theme.looks_like_cell_label("C") is False
    assert theme.looks_like_cell_label("18") is False
    assert theme.looks_like_cell_label("A1") is True
    assert theme.looks_like_cell_label("C4") is True
