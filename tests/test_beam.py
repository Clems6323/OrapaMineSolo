"""Tests de model.beam.fire_beam (modèle tangram fidèle).

Scénarios dérivés des règles (docs/RULES.md) et vérifiés à la main à partir de
la géométrie des pièces du catalogue.
"""

from __future__ import annotations

from orapa_mine.model.beam import Direction, fire_beam, mix_colors
from orapa_mine.model.gems import GemColor, Position
from orapa_mine.model.grid import Grid
from orapa_mine.model import gems_catalog as cat


# --- Table de mélange des couleurs -------------------------------------------


def test_color_mix_table_confirmed_entries():
    R, J, B, W = GemColor.RED, GemColor.YELLOW, GemColor.BLUE, GemColor.WHITE
    assert mix_colors(frozenset()) is None
    assert mix_colors(frozenset({R})) == "rouge"
    assert mix_colors(frozenset({R, J})) == "orange"
    assert mix_colors(frozenset({J, B})) == "vert"
    assert mix_colors(frozenset({R, B})) == "violet"
    assert mix_colors(frozenset({R, W})) == "rose"
    assert mix_colors(frozenset({J, W})) == "jaune clair"
    assert mix_colors(frozenset({B, W})) == "bleu clair"
    assert mix_colors(frozenset({R, J, B})) == "noir"
    assert mix_colors(frozenset({J, B, W})) == "vert clair"
    assert mix_colors(frozenset({R, J, W})) == "orange clair"
    assert mix_colors(frozenset({R, B, W})) == "violet clair"
    assert mix_colors(frozenset({R, J, B, W})) == "gris"


# --- Trajectoires ------------------------------------------------------------


def test_beam_without_any_gem_goes_straight_through():
    grid = Grid(width=5, height=5)
    result = fire_beam(grid, entry=Position(0, 2), direction=Direction.DOWN)
    assert result.exit_point == Position(4, 2)
    assert result.exit_direction is Direction.DOWN
    assert result.color is None
    assert not result.absorbed


def test_beam_hitting_flat_face_returns_to_entry():
    # Colonne 2 traverse la case pleine (FULL) du jaune en (2,2) -> renvoi 180°.
    grid = Grid(width=6, height=6)
    grid.place_gem(cat.YELLOW.at(Position(2, 2)))
    result = fire_beam(grid, entry=Position(0, 2), direction=Direction.DOWN)
    assert result.exit_point == Position(0, 2)
    assert result.color == "jaune"


def test_beam_deviated_90_degrees_by_diagonal_edge():
    # Rayon venant de droite sur l'arête du jaune en (2,3) -> dévié vers le bas.
    grid = Grid(width=6, height=6)
    grid.place_gem(cat.YELLOW.at(Position(2, 2)))
    result = fire_beam(grid, entry=Position(2, 5), direction=Direction.LEFT)
    assert result.exit_point == Position(5, 3)  # sort par le bas, colonne 3
    assert result.color == "jaune"


def test_beam_two_deviations_mixes_two_colors():
    # Jaune dévie le rayon vers le bas, puis le bleu le dévie vers la droite.
    grid = Grid(width=8, height=8)
    grid.place_gem(cat.YELLOW.at(Position(2, 2)))
    grid.place_gem(cat.BLUE.at(Position(5, 1)))
    result = fire_beam(grid, entry=Position(2, 7), direction=Direction.LEFT)
    assert result.color == "vert"  # jaune + bleu
    assert result.exit_point == Position(5, 7)


def test_beam_records_color_steps_and_exit_direction():
    # Reproduit le scénario du bug d'affichage : tir en colonne 0 vers le bas
    # qui dévie à gauche sur le parallélogramme rouge et sort en D (ligne 3).
    grid = Grid(width=6, height=6)
    grid.place_gem(cat.RED.at(Position(3, 0)))
    result = fire_beam(grid, entry=Position(0, 0), direction=Direction.DOWN)
    assert result.exit_point == Position(3, 0)
    assert result.exit_direction is Direction.LEFT
    assert result.color == "rouge"
    # Étapes de couleur parallèles au trajet : transparent avant la gemme,
    # rouge une fois touchée.
    assert len(result.color_steps) == len(result.path)
    assert result.color_steps[0] is None
    assert result.color_steps[-1] == "rouge"


def test_bounce_colors_pivot_cell_at_contact():
    # Rebond 180° sur une face plate rouge : la couleur doit être prise dès la
    # case de rebroussement, pas un segment plus loin.
    grid = Grid(width=6, height=6)
    grid.place_gem(cat.RED.at(Position(3, 0)))  # case pleine rouge en (3,1)
    result = fire_beam(grid, entry=Position(0, 1), direction=Direction.DOWN)
    assert result.exit_point == Position(0, 1)  # revient à l'entrée
    assert result.color == "rouge"
    # path = [(0,1),(1,1),(2,1),(1,1),(0,1)] ; le pivot (2,1) est l'index 2.
    assert result.path[2] == Position(2, 1)
    assert result.color_steps[2] == "rouge"  # couleur prise au contact


def test_beam_absorbed_by_black_body_has_no_exit():
    grid = Grid(width=8, height=8)
    grid.place_gem(cat.BLACK_BODY.at(Position(3, 3)))
    result = fire_beam(grid, entry=Position(3, 0), direction=Direction.RIGHT)
    assert result.exit_point is None
    assert result.absorbed
    assert result.color is None


def test_diamond_deviates_without_tinting():
    grid = Grid(width=8, height=8)
    grid.place_gem(cat.DIAMOND.at(Position(3, 3)))
    result = fire_beam(grid, entry=Position(3, 0), direction=Direction.RIGHT)
    # L'arête RA_SE dévie le rayon vers le haut, mais sans couleur.
    assert result.exit_point == Position(0, 3)
    assert result.color is None


def test_beam_touching_same_color_twice_counts_once():
    # Deux gemmes blanches sur le trajet -> couleur "blanc" comptée une fois.
    grid = Grid(width=8, height=8)
    grid.place_gem(cat.WHITE_BIG.at(Position(2, 2)))
    grid.place_gem(cat.WHITE_SMALL.at(Position(2, 0)))
    result = fire_beam(grid, entry=Position(0, 3), direction=Direction.DOWN)
    assert result.color == "blanc"
