"""Tests de la gemme arc-en-ciel (carré 2×2 multicolore, issue #72).

Comportement retenu : toutes les faces sont plates -> le rayon rebondit à 180°
et prend la couleur de la **case touchée**. Les couleurs sont positionnelles :
4 rotations distinctes, pas de retournement.

Disposition canonique (offsets ligne, col) :
    (0,0) blanc | (0,1) bleu
    (1,0) jaune | (1,1) rouge
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


def _grid_with_rainbow(anchor=Position(2, 2), orient=0, size=6) -> Grid:
    grid = Grid(width=size, height=size)
    grid.place_gem(cat.RAINBOW.at(anchor, orient))
    return grid


# --- Disposition et orientations ---------------------------------------------


def test_canonical_colors_are_placed_as_specified():
    gem = cat.RAINBOW.at(Position(2, 2))
    colors = gem.absolute_colors()
    assert colors[Position(2, 2)] is GemColor.WHITE   # haut-gauche
    assert colors[Position(2, 3)] is GemColor.BLUE    # haut-droit
    assert colors[Position(3, 2)] is GemColor.YELLOW  # bas-gauche
    assert colors[Position(3, 3)] is GemColor.RED     # bas-droit


def test_four_distinct_rotations_no_flip():
    variants = cat.RAINBOW.oriented_variants()
    assert len(variants) == 4  # 4 rotations, pas de retournement
    # Même empreinte géométrique (carré 2×2 plein) pour toutes…
    footprints = {fp for fp, _ in variants}
    assert len(footprints) == 1
    # …mais 4 cartes de couleurs distinctes.
    color_maps = {colors for _, colors in variants}
    assert len(color_maps) == 4


def test_rotation_moves_colors_clockwise():
    # 90° CW : le blanc haut-gauche passe en haut-droit.
    gem = cat.RAINBOW.at(Position(2, 2), orientation_index=1)
    colors = gem.absolute_colors()
    assert colors[Position(2, 3)] is GemColor.WHITE


# --- Rayon : rebond 180° + couleur de la case touchée ------------------------


def test_ray_reflects_180_and_takes_touched_cell_color():
    grid = _grid_with_rainbow()  # (2,2)=B blanc, (2,3)=bleu, (3,2)=jaune, (3,3)=rouge
    cases = [
        (Position(2, 0), Direction.RIGHT, "blanc"),   # rangée haute par la gauche -> blanc
        (Position(3, 0), Direction.RIGHT, "jaune"),   # rangée basse par la gauche -> jaune
        (Position(2, 5), Direction.LEFT, "bleu"),     # rangée haute par la droite -> bleu
        (Position(3, 5), Direction.LEFT, "rouge"),    # rangée basse par la droite -> rouge
        (Position(0, 2), Direction.DOWN, "blanc"),    # colonne gauche par le haut -> blanc
        (Position(0, 3), Direction.DOWN, "bleu"),     # colonne droite par le haut -> bleu
        (Position(5, 2), Direction.UP, "jaune"),      # colonne gauche par le bas -> jaune
        (Position(5, 3), Direction.UP, "rouge"),      # colonne droite par le bas -> rouge
    ]
    for entry, direction, expected in cases:
        result = fire_beam(grid, entry=entry, direction=direction)
        assert result.color == expected, (entry, direction)
        assert result.exit_point == entry  # rebond 180° : ressort par l'entrée
        assert result.exit_direction is direction.reverse()
        assert not result.absorbed


def test_rotation_changes_the_color_a_ray_reads():
    # Même rayon, pièce tournée de 90° CW -> la case haut-gauche devient jaune.
    grid = _grid_with_rainbow(orient=1)
    result = fire_beam(grid, entry=Position(2, 0), direction=Direction.RIGHT)
    assert result.color == "jaune"


def test_rainbow_color_mixes_with_other_gems():
    # Rayon qui lit le bleu de l'arc-en-ciel puis touche une gemme jaune au retour
    # donnerait du vert ; ici on vérifie juste qu'une seule case = une seule couleur.
    grid = _grid_with_rainbow()
    result = fire_beam(grid, entry=Position(2, 5), direction=Direction.LEFT)
    assert result.color == "bleu"  # bleu seul, pas de mélange parasite


# --- Sérialisation -----------------------------------------------------------


def test_cell_query_reveals_the_quadrant_color():
    grid = _grid_with_rainbow()  # (2,2)=blanc, (2,3)=bleu, (3,2)=jaune, (3,3)=rouge
    game = GameState(hidden_grid=grid)
    assert game.query_cell(Position(2, 2)).content.color is GemColor.WHITE
    assert game.query_cell(Position(2, 3)).content.color is GemColor.BLUE
    assert game.query_cell(Position(3, 2)).content.color is GemColor.YELLOW
    assert game.query_cell(Position(3, 3)).content.color is GemColor.RED


def test_serialization_round_trips_rotation_and_colors():
    for orient in range(4):
        grid = _grid_with_rainbow(orient=orient)
        data = to_dict(
            width=grid.width, height=grid.height,
            palette_pieces=[cat.RAINBOW], hidden_grid=grid, include_progress=False,
        )
        loaded = from_dict(data)
        reloaded = loaded.game.hidden_grid.gems[0]
        original = grid.gems[0]
        assert reloaded.absolute_colors() == original.absolute_colors()


def test_serialization_round_trips_rainbow_in_hypothesis():
    hidden = _grid_with_rainbow(size=8)
    hypothesis = Grid(width=8, height=8)
    hypothesis.place_gem(cat.RAINBOW.at(Position(4, 4), orientation_index=2))
    game = GameState(hidden_grid=hidden)
    data = to_dict(
        width=8, height=8, palette_pieces=[cat.RAINBOW], hidden_grid=hidden,
        include_progress=True, game=game, hypothesis_grid=hypothesis,
    )
    loaded = from_dict(data)
    assert loaded.hypothesis.gems[0].absolute_colors() == \
        hypothesis.gems[0].absolute_colors()


# --- Génération --------------------------------------------------------------


def test_generator_places_a_valid_rainbow():
    difficulty = Difficulty(pieces=[*cat.base_set(), cat.RAINBOW], width=10, height=8)
    grid = generate_hidden_grid(difficulty=difficulty, rng=random.Random(3))
    rainbows = [g for g in grid.gems if g.kind is GemKind.RAINBOW]
    assert len(rainbows) == 1
    # 4 cases, une par couleur de base.
    assert set(rainbows[0].absolute_colors().values()) == {
        GemColor.WHITE, GemColor.BLUE, GemColor.YELLOW, GemColor.RED
    }
