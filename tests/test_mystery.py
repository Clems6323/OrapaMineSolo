"""Tests de la gemme mystère (issue #77).

Même forme que le diamant, mais d'une couleur **cachée** : elle dévie et
**teinte** le rayon comme une gemme normale de cette couleur. La couleur est
fixée par `PlacedGem.override_color` (aléatoire à la génération, choisie en
jeu/créateur), révélée par une question de case et à l'écran de fin.
"""

from __future__ import annotations

import random

from orapa_mine.ai.generator import Difficulty, generate_hidden_grid
from orapa_mine.model import gems_catalog as cat
from orapa_mine.model.beam import Direction, fire_beam
from orapa_mine.model.game import GameState
from orapa_mine.model.gems import GemColor, GemKind, Position
from orapa_mine.model.grid import Grid
from orapa_mine.model.serialization import from_dict, to_dict


# --- Catalogue / modèle ------------------------------------------------------


def test_mystery_has_diamond_shape_and_no_catalog_color():
    assert cat.MYSTERY.kind is GemKind.MYSTERY
    assert cat.MYSTERY.color is None
    # Même empreinte (jeu d'orientations) que le diamant.
    assert cat.MYSTERY.cells == cat.DIAMOND.cells
    assert len(cat.MYSTERY.orientations()) == len(cat.DIAMOND.orientations())


def test_placed_mystery_carries_chosen_color():
    gem = cat.MYSTERY.at(Position(2, 2), color=GemColor.RED)
    assert gem.color is GemColor.RED
    assert gem.override_color is GemColor.RED
    # Sans couleur -> None (on retombe sur la couleur de la pièce, None ici).
    assert cat.MYSTERY.at(Position(2, 2)).color is None


# --- Rayon : dévie comme le diamant mais teinte de sa couleur ----------------


def test_mystery_deviates_and_tints_with_its_color():
    grid = Grid(width=8, height=8)
    grid.place_gem(cat.MYSTERY.at(Position(3, 3), color=GemColor.BLUE))
    result = fire_beam(grid, entry=Position(3, 0), direction=Direction.RIGHT)
    # Même trajectoire que le diamant (RA_SE dévie vers le haut)…
    assert result.exit_point == Position(0, 3)
    # …mais teintée de la couleur de la gemme.
    assert result.color == "bleu"


def test_mystery_color_changes_the_ray():
    grid = Grid(width=8, height=8)
    grid.place_gem(cat.MYSTERY.at(Position(3, 3), color=GemColor.YELLOW))
    result = fire_beam(grid, entry=Position(3, 0), direction=Direction.RIGHT)
    assert result.color == "jaune"


# --- Question de case : révèle la vraie couleur (pas le nom) -----------------


def test_cell_query_reveals_the_true_color():
    grid = Grid(width=8, height=8)
    grid.place_gem(cat.MYSTERY.at(Position(3, 3), color=GemColor.RED))
    game = GameState(hidden_grid=grid)
    answer = game.query_cell(Position(3, 3))
    assert answer.content.occupied
    assert answer.content.color is GemColor.RED  # couleur, pas « mystère »


# --- Validation : il faut proposer la bonne couleur --------------------------


def _hidden_with_mystery(color: GemColor) -> Grid:
    grid = Grid(width=8, height=8)
    grid.place_gem(cat.MYSTERY.at(Position(3, 3), color=color))
    return grid


def test_submit_requires_the_right_mystery_color():
    game = GameState(hidden_grid=_hidden_with_mystery(GemColor.BLUE))
    # Bonne position mais mauvaise couleur -> refusé.
    wrong = [cat.MYSTERY.at(Position(3, 3), color=GemColor.RED)]
    assert game.submit_guess(wrong) is False
    # Bonne couleur -> accepté.
    right = [cat.MYSTERY.at(Position(3, 3), color=GemColor.BLUE)]
    assert game.submit_guess(right) is True


# --- Sérialisation -----------------------------------------------------------


def test_serialization_round_trips_the_mystery_color():
    for color in (GemColor.RED, GemColor.YELLOW, GemColor.BLUE, GemColor.WHITE):
        grid = _hidden_with_mystery(color)
        data = to_dict(
            width=grid.width, height=grid.height,
            palette_pieces=[cat.MYSTERY], hidden_grid=grid, include_progress=False,
        )
        loaded = from_dict(data)
        assert loaded.game.hidden_grid.gems[0].color is color


def test_serialization_round_trips_mystery_in_hypothesis():
    hidden = _hidden_with_mystery(GemColor.YELLOW)
    hypothesis = Grid(width=8, height=8)
    hypothesis.place_gem(cat.MYSTERY.at(Position(5, 5), color=GemColor.WHITE))
    game = GameState(hidden_grid=hidden)
    data = to_dict(
        width=8, height=8, palette_pieces=[cat.MYSTERY], hidden_grid=hidden,
        include_progress=True, game=game, hypothesis_grid=hypothesis,
    )
    loaded = from_dict(data)
    assert loaded.hypothesis.gems[0].color is GemColor.WHITE


# --- Génération --------------------------------------------------------------


def test_generator_places_a_valid_mystery_with_a_base_color():
    difficulty = Difficulty(pieces=[*cat.base_set(), cat.MYSTERY], width=10, height=8)
    grid = generate_hidden_grid(difficulty=difficulty, rng=random.Random(5))
    mysteries = [g for g in grid.gems if g.kind is GemKind.MYSTERY]
    assert len(mysteries) == 1
    assert mysteries[0].color in (
        GemColor.RED, GemColor.YELLOW, GemColor.BLUE, GemColor.WHITE
    )
