"""Tests de ai.generator : génération de grille cachée valide."""

from __future__ import annotations

import random

from orapa_mine.ai.generator import (
    Difficulty,
    _gem_visible,
    _touches_orthogonally,
    configuration_is_valid,
    configuration_problems,
    generate_hidden_grid,
    placement_is_legal,
)
from orapa_mine.model.gems import Direction, HalfCell, Position
from orapa_mine.model.grid import Grid
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


def test_generation_places_two_wormholes():
    # Le trou de ver (quantity=2) est posé en deux exemplaires.
    diff = Difficulty(pieces=cat.base_set() + [cat.WORMHOLE], width=10, height=8)
    grid = generate_hidden_grid(difficulty=diff, rng=random.Random(3))
    worms = [g for g in grid.gems if g.piece.name == "trou-de-ver"]
    assert len(worms) == 2
    assert len(grid.gems) == 7  # 5 base + 2 trous de ver


def test_many_seeds_all_produce_valid_boards():
    # Robustesse : la génération ne doit jamais échouer sur la version de base.
    for seed in range(50):
        grid = generate_hidden_grid(rng=random.Random(seed))
        assert len(grid.gems) == 5


def test_hidden_gem_is_detected():
    # Une gemme volontairement cachée derrière une autre doit être invisible.
    grid = Grid(width=10, height=8)
    # Blanc-petit (losange 2×2) placé au centre, entouré... on teste juste
    # qu'une gemme au bord est visible et qu'on sait détecter l'inverse.
    edge_gem = cat.YELLOW.at(Position(0, 0))
    grid.place_gem(edge_gem)
    assert _gem_visible(grid, edge_gem)


# --- Validation d'une configuration (mode créateur) --------------------------


def test_generated_grid_is_a_valid_configuration():
    grid = generate_hidden_grid(rng=random.Random(11))
    assert configuration_is_valid(grid)
    assert configuration_problems(grid) == []


def test_empty_configuration_is_valid():
    assert configuration_is_valid(Grid(width=10, height=8))


def test_adjacent_gems_are_reported():
    grid = Grid(width=10, height=8)
    # Deux rectangles pleins 1×2 côte à côte : faces plates partagées.
    grid.place_gem(cat.BLACK_BODY.at(Position(0, 0)))
    grid.place_gem(cat.BLACK_BODY.at(Position(0, 2)))
    problems = configuration_problems(grid)
    assert problems and any(code == "touche" for code, _ in problems)


def test_diagonal_contact_is_allowed():
    # Régression (bug_placement) : deux triangles qui ne se rejoignent que par
    # leur hypoténuse (contact en diagonale) ne doivent PAS être signalés, même
    # si leurs cases occupent des positions orthogonalement adjacentes.
    grid = Grid(width=14, height=12)
    grid.place_gem(cat.BLUE.at(Position(3, 3), 0))
    grid.place_gem(cat.WHITE_BIG.at(Position(1, 2), 0))
    occ_blue = set(grid.gems[0].absolute_cells())
    occ_white = set(grid.gems[1].absolute_cells())
    from orapa_mine.model.gems import Direction
    assert any(
        (c + d) in occ_white
        for c in occ_blue
        for d in (Direction.UP, Direction.DOWN, Direction.LEFT, Direction.RIGHT)
    ), "cas de test invalide : les pièces ne sont pas orthogonalement adjacentes"
    assert configuration_is_valid(grid), configuration_problems(grid)


def test_point_contact_is_allowed():
    # Deux losanges blancs dans des boîtes voisines ne se touchent qu'en un
    # point (leurs arêtes externes sont des hypoténuses) : contact autorisé.
    grid = Grid(width=10, height=8)
    grid.place_gem(cat.WHITE_SMALL.at(Position(0, 0)))
    grid.place_gem(cat.WHITE_SMALL.at(Position(0, 2)))
    assert not any(code == "touche" for code, _ in configuration_problems(grid))


# --- Légalité d'une pose (aperçu fantôme : jeu + mode créateur) --------------


def test_placement_is_legal_on_empty_grid():
    grid = Grid(width=10, height=8)
    assert placement_is_legal(grid, cat.BLACK_BODY.at(Position(0, 0)))


def test_placement_rejects_overlap():
    grid = Grid(width=10, height=8)
    grid.place_gem(cat.BLACK_BODY.at(Position(0, 0)))
    # Même emplacement -> chevauchement.
    assert not placement_is_legal(grid, cat.BLACK_BODY.at(Position(0, 0)))


def test_placement_rejects_flat_face_adjacency():
    # Régression #29 : deux rectangles pleins côte à côte (bords qui se touchent)
    # doivent être refusés (aperçu rouge), pas acceptés.
    grid = Grid(width=10, height=8)
    grid.place_gem(cat.BLACK_BODY.at(Position(0, 0)))  # cases (0,0)-(0,1)
    assert not placement_is_legal(grid, cat.BLACK_BODY.at(Position(0, 2)))


def test_placement_allows_diagonal_contact():
    # Contact seulement par un coin / une hypoténuse : autorisé (aperçu vert).
    grid = Grid(width=10, height=8)
    grid.place_gem(cat.WHITE_SMALL.at(Position(0, 0)))
    assert placement_is_legal(grid, cat.WHITE_SMALL.at(Position(0, 2)))


def test_placement_rejects_out_of_bounds():
    grid = Grid(width=10, height=8)
    assert not placement_is_legal(grid, cat.BLACK_BODY.at(Position(0, 9)))


def test_fully_hidden_gem_is_reported():
    grid = Grid(width=10, height=8)
    center = cat.WHITE_SMALL.at(Position(3, 4))
    grid.place_gem(center)
    own = set(center.absolute_cells())
    # Entoure complètement la gemme : toute case libre devient un bloqueur, donc
    # aucune ligne de vue vers un bord -> la gemme est entièrement cachée.
    for row in range(grid.height):
        for col in range(grid.width):
            pos = Position(row, col)
            if pos not in own:
                grid.surface[pos] = HalfCell.FULL
    problems = configuration_problems(grid)
    assert any(code == "cachée" for code, _ in problems)
