"""Tests de la pièce Filtre (#62) : dévie comme le losange et remet à transparent."""

from __future__ import annotations

import random

from orapa_mine.ai.generator import Difficulty, generate_hidden_grid
from orapa_mine.model import gems_catalog as cat
from orapa_mine.model.beam import fire_beam
from orapa_mine.model.gems import Direction, GemKind, Position
from orapa_mine.model.grid import Grid


def _all_entries(w: int, h: int):
    ents = []
    for c in range(w):
        ents.append((Position(0, c), Direction.DOWN))
        ents.append((Position(h - 1, c), Direction.UP))
    for r in range(h):
        ents.append((Position(r, 0), Direction.RIGHT))
        ents.append((Position(r, w - 1), Direction.LEFT))
    return ents


def test_filter_shape_matches_white_square():
    # Même empreinte (losange 2×2) que le petit carré blanc.
    assert cat.FILTER.cells == cat.WHITE_SMALL.cells
    assert cat.FILTER.kind is GemKind.FILTER


def test_filter_never_tints_and_deflects():
    grid = Grid(width=10, height=8)
    grid.place_gem(cat.FILTER.at(Position(3, 4)))
    turned = False
    for entry, direction in _all_entries(10, 8):
        result = fire_beam(grid, entry, direction)
        assert result.color is None          # le filtre ne teinte jamais
        if len(result.vertices) >= 3:         # un sommet intermédiaire = déviation
            turned = True
    assert turned                             # il dévie bien le rayon (comme le losange)


def test_filter_resets_a_collected_color():
    # Il existe une configuration où le rayon prend la couleur blanche (losange
    # blanc) puis la perd (transparent) en traversant le filtre.
    entries = _all_entries(10, 8)
    for fr in range(8):
        for fc in range(10):
            grid = Grid(width=10, height=8)
            grid.place_gem(cat.WHITE_SMALL.at(Position(1, 1)))
            fpos = Position(fr, fc)
            try:
                grid.place_gem(cat.FILTER.at(fpos))
            except ValueError:
                continue
            for entry, direction in entries:
                r = fire_beam(grid, entry, direction)
                if "blanc" in r.color_steps and r.color is None:
                    return  # couleur collectée puis effacée -> OK
    raise AssertionError("aucune configuration filtre-après-blanc trouvée")


def test_generation_places_the_filter():
    diff = Difficulty(pieces=cat.base_set() + [cat.FILTER], width=10, height=8)
    grid = generate_hidden_grid(difficulty=diff, rng=random.Random(4))
    assert any(g.piece.name == "filtre" for g in grid.gems)
    assert len(grid.gems) == 6  # 5 base + 1 filtre
