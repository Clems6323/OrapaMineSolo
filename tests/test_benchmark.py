"""Génération et validation des grilles du hackathon (issue #92)."""

from __future__ import annotations

import pytest

from orapa_mine.model import gems_catalog as cat
from orapa_mine.model.gems import GemKind, Position
from orapa_mine.model.grid import Grid
from orapa_mine.solver import benchmark as bm


def _sig(grid: Grid):
    return sorted((g.piece.name, g.anchor.row, g.anchor.col, str(g.color)) for g in grid.gems)


# --- Génération : tailles, extensions, déterminisme --------------------------


def test_generate_respects_tier_size_and_extension_budget():
    for tier in bm.TIERS:
        t = bm.TIERS[tier]
        grid, spec, pieces = bm.generate(tier, seed=3)
        assert grid.width == t.width and grid.height == t.height
        assert spec.tier == tier
        assert 0 <= len(spec.extensions) <= t.max_extensions
        # La palette = 5 de base + les extensions choisies.
        assert len(pieces) == 5 + len(spec.extensions)


def test_generation_is_deterministic_by_seed():
    g1, s1, _ = bm.generate("standard", seed=7)
    g2, s2, _ = bm.generate("standard", seed=7)
    assert _sig(g1) == _sig(g2)
    assert s1 == s2


def test_pinned_extensions_are_used():
    grid, spec, pieces = bm.generate("standard", seed=3, extensions=["mystery"])
    assert spec.extensions == ("mystery",)
    assert any(g.kind is GemKind.MYSTERY for g in grid.gems)


def test_extension_count_is_respected():
    _, spec, _ = bm.generate("large", seed=5, extension_count=2)
    assert len(spec.extensions) == 2


def test_too_many_extensions_is_rejected():
    with pytest.raises(ValueError):
        bm.generate("small", seed=1, extensions=["diamond", "filter", "mystery"])  # max 2


def test_unknown_tier_and_extension_are_rejected():
    with pytest.raises(ValueError):
        bm.generate("huge", seed=1)
    with pytest.raises(ValueError):
        bm.generate("small", seed=1, extensions=["sapphire"])


# --- Validation --------------------------------------------------------------


def test_generated_valid_grids_pass_the_validator():
    for tier in bm.TIERS:
        grid, spec, pieces = bm.generate_valid(tier, seed=1)
        assert bm.is_valid(grid, pieces)
        assert bm.grid_problems(grid, pieces) == []


def test_single_gem_grid_is_unambiguous():
    grid = Grid(width=10, height=8)
    grid.place_gem(cat.YELLOW.at(Position(2, 2)))
    assert bm.is_valid(grid, [cat.YELLOW])


def test_validator_flags_a_genuinely_ambiguous_grid():
    # Cas connu : deux configurations coïncident sur questions ET rayons.
    grid, spec, pieces = bm.generate("large", seed=20)
    assert "ambiguous" in bm.grid_problems(grid, pieces)


def test_ray_signature_is_stable():
    grid, _, _ = bm.generate("small", seed=2)
    assert bm.ray_signature(grid) == bm.ray_signature(grid)


# --- Jeu officiel ------------------------------------------------------------


def test_official_set_is_nine_valid_grids_three_per_tier():
    grids = bm.official_set(master_seed=2027)
    assert len(grids) == 9
    by_tier = {}
    for grid, spec, pieces in grids:
        by_tier.setdefault(spec.tier, 0)
        by_tier[spec.tier] += 1
        assert grid.width == spec.width and grid.height == spec.height
        assert bm.is_valid(grid, pieces)
    assert by_tier == {"small": 3, "standard": 3, "large": 3}


# --- Sauvegarde / rechargement ----------------------------------------------


def test_save_and_load_round_trip(tmp_path):
    grid, spec, pieces = bm.generate_valid("standard", seed=4)
    path = tmp_path / "grid.json"
    bm.save_grid(path, grid, spec, pieces)
    loaded_grid, loaded_pieces, meta = bm.load_grid(path)
    assert _sig(loaded_grid) == _sig(grid)
    assert {p.name for p in loaded_pieces} == {p.name for p in pieces}
    assert meta["tier"] == spec.tier and meta["seed"] == spec.seed
    assert meta["extensions"] == list(spec.extensions)
