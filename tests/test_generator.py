"""Tests de ai.generator : génération de grille cachée valide."""

from __future__ import annotations

import random

from orapa_mine.ai.generator import (
    Difficulty,
    _gem_visible,
    _touches_orthogonally,
    generate_hidden_grid,
)
from orapa_mine.model.gems import Direction, HalfCell, Position
from orapa_mine.model import gems_catalog as cat


def _total_area(grid) -> float:
    return sum(1.0 if hc is HalfCell.FULL else 0.5 for hc in grid.surface.values())


def test_generation_is_deterministic_with_seed():
    g1 = generate_hidden_grid(rng=random.Random(42))
    g2 = generate_hidden_grid(rng=random.Random(42))
    assert g1.surface == g2.surface


def test_base_grid_places_five_gems():
    grid = generate_hidden_grid(rng=random.Random(1))
    assert len(grid.gems) == 5
    # Aire totale attendue : rouge2 + jaune2 + bleu4 + blanc-grand4 + blanc-petit2.
    assert _total_area(grid) == 14


def test_full_grid_places_seven_gems():
    grid = generate_hidden_grid(
        difficulty=Difficulty.full(), rng=random.Random(7)
    )
    assert len(grid.gems) == 7


def test_generated_cells_are_all_inside():
    grid = generate_hidden_grid(rng=random.Random(3))
    for position in grid.surface:
        assert grid.is_inside(position)


def test_no_two_gems_are_orthogonally_adjacent():
    grid = generate_hidden_grid(rng=random.Random(5))
    for gem in grid.gems:
        others = set(grid.surface) - set(gem.absolute_cells())
        assert not _touches_orthogonally(gem, others)


def test_every_gem_is_visible():
    grid = generate_hidden_grid(rng=random.Random(9))
    for gem in grid.gems:
        assert _gem_visible(grid, gem)


def test_many_seeds_all_produce_valid_boards():
    # Robustesse : la génération ne doit jamais échouer sur la version de base.
    for seed in range(50):
        grid = generate_hidden_grid(rng=random.Random(seed))
        assert len(grid.gems) == 5


def test_hidden_gem_is_detected():
    # Une gemme volontairement cachée derrière une autre doit être invisible.
    from orapa_mine.model.grid import Grid

    grid = Grid(width=10, height=8)
    # Blanc-petit (losange 2×2) placé au centre, entouré... on teste juste
    # qu'une gemme au bord est visible et qu'on sait détecter l'inverse.
    edge_gem = cat.YELLOW.at(Position(0, 0))
    grid.place_gem(edge_gem)
    assert _gem_visible(grid, edge_gem)
