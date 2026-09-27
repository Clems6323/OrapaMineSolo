"""Tests de model.grid.Grid (modèle tangram)."""

from __future__ import annotations

import pytest

from orapa_mine.model.gems import Position
from orapa_mine.model.grid import Grid
from orapa_mine.model import gems_catalog as cat


def test_default_grid_is_10x8():
    grid = Grid()
    assert (grid.width, grid.height) == (10, 8)


def test_position_inside_grid():
    grid = Grid()  # 10x8
    assert grid.is_inside(Position(0, 0))
    assert grid.is_inside(Position(7, 9))
    assert not grid.is_inside(Position(8, 0))
    assert not grid.is_inside(Position(0, 10))
    assert not grid.is_inside(Position(-1, 0))


def test_border_positions():
    grid = Grid()  # 10x8 -> lignes 0..7, colonnes 0..9
    assert grid.is_border(Position(0, 3))
    assert grid.is_border(Position(3, 0))
    assert grid.is_border(Position(7, 3))
    assert grid.is_border(Position(3, 9))
    assert not grid.is_border(Position(3, 3))


def test_place_gem_then_read_it_back():
    grid = Grid()
    gem = cat.YELLOW.at(Position(2, 2))
    grid.place_gem(gem)
    # Le jaune occupe (2,2), (2,3), (3,2).
    assert grid.gem_at(Position(2, 2)) is gem
    assert grid.gem_at(Position(2, 3)) is gem
    assert grid.gem_at(Position(3, 2)) is gem
    assert grid.gem_at(Position(0, 0)) is None


def test_cannot_place_two_gems_overlapping():
    grid = Grid()
    grid.place_gem(cat.YELLOW.at(Position(2, 2)))
    # Le petit carré blanc en (2,2) entre en collision avec le jaune.
    with pytest.raises(ValueError):
        grid.place_gem(cat.WHITE_SMALL.at(Position(2, 2)))


def test_cannot_place_gem_out_of_bounds():
    grid = Grid(width=5, height=5)
    with pytest.raises(ValueError):
        grid.place_gem(cat.BLUE.at(Position(4, 4)))  # déborde la grille


def test_can_place_reports_conflicts():
    grid = Grid()
    grid.place_gem(cat.YELLOW.at(Position(2, 2)))
    assert grid.can_place(cat.WHITE_SMALL.at(Position(0, 0)))
    assert not grid.can_place(cat.WHITE_SMALL.at(Position(2, 3)))


def test_remove_gem_frees_its_cells():
    grid = Grid()
    gem = cat.YELLOW.at(Position(2, 2))
    grid.place_gem(gem)
    grid.remove_gem(gem)
    assert grid.gems == []
    assert grid.gem_at(Position(2, 2)) is None
    assert grid.surface == {}
    # On peut de nouveau placer une pièce à cet endroit.
    grid.place_gem(cat.WHITE_SMALL.at(Position(2, 2)))
    assert grid.gem_at(Position(2, 2)) is not None
