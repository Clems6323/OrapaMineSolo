"""Distance Earth Mover (Wasserstein W1) entre hypothèse et vérité (#45).

Second score (« proximité ») : déplacement moyen, en cases, pour amener les
gemmes devinées sur les vraies. 0 = parfait ; inf si une gemme manque.
"""

from __future__ import annotations

import math

import pytest

from orapa_mine.model import gems_catalog as cat
from orapa_mine.model.distance import board_distance, gem_distance
from orapa_mine.model.gems import GemColor, Position
from orapa_mine.model.grid import Grid


# --- Distance d'une gemme ----------------------------------------------------


def test_identity_is_zero():
    gem = cat.YELLOW.at(Position(2, 2))
    assert gem_distance(gem, gem) == 0.0


def test_pure_translation_equals_vector_length():
    # Translation de 3 colonnes -> distance 3 (exacte).
    a = cat.YELLOW.at(Position(2, 2))
    b = cat.YELLOW.at(Position(2, 5))
    assert gem_distance(a, b) == 3.0


def test_symmetric_orientations_match_at_zero():
    # Le losange blanc a une seule empreinte (symétrique) : toute "rotation"
    # occupe la même surface -> distance nulle.
    g = cat.WHITE_SMALL.at(Position(1, 1), orientation_index=0)
    assert gem_distance(g, g) == 0.0


# --- Distance d'un plateau ---------------------------------------------------


def _truth() -> Grid:
    grid = Grid(width=8, height=8)
    grid.place_gem(cat.YELLOW.at(Position(2, 2)))
    grid.place_gem(cat.BLUE.at(Position(4, 2)))
    return grid


def test_exact_guess_is_zero():
    truth = _truth()
    guess = _truth()
    score = board_distance(guess, truth)
    assert score.total == 0.0
    assert score.missing == 0


def test_shifted_guess_accumulates_distance():
    truth = _truth()
    guess = Grid(width=8, height=8)
    guess.place_gem(cat.YELLOW.at(Position(2, 3)))  # décalé d'une colonne
    guess.place_gem(cat.BLUE.at(Position(4, 2)))    # correct
    score = board_distance(guess, truth)
    assert score.total == pytest.approx(1.0)
    assert score.missing == 0


def test_missing_gem_is_infinite_and_counted():
    truth = _truth()
    guess = Grid(width=8, height=8)
    guess.place_gem(cat.YELLOW.at(Position(2, 2)))  # bleu manquant
    score = board_distance(guess, truth)
    assert math.isinf(score.total)
    assert score.missing == 1
    assert score.placed_total == 0.0  # la seule gemme posée est correcte


def test_mystery_wrong_color_uses_finite_penalty():
    truth = Grid(width=8, height=8)
    truth.place_gem(cat.MYSTERY.at(Position(3, 3), color=GemColor.BLUE))
    guess = Grid(width=8, height=8)
    guess.place_gem(cat.MYSTERY.at(Position(3, 3), color=GemColor.RED))  # bonne place, mauvaise couleur
    score = board_distance(guess, truth, mystery_color_penalty=1.0)
    assert score.total == 1.0
    # Bonne couleur -> distance nulle.
    good = Grid(width=8, height=8)
    good.place_gem(cat.MYSTERY.at(Position(3, 3), color=GemColor.BLUE))
    assert board_distance(good, truth, mystery_color_penalty=1.0).total == 0.0
