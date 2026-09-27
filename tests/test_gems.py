"""Tests de la géométrie des pièces (gems.py + gems_catalog.py)."""

from __future__ import annotations

from orapa_mine.model.gems import HalfCell, Position
from orapa_mine.model import gems_catalog as cat


def _area(cells) -> float:
    """Aire d'une empreinte : 1 par case pleine, 0.5 par demi-case."""
    return sum(1.0 if hc is HalfCell.FULL else 0.5 for _, hc in cells)


def test_piece_areas_match_expected():
    assert _area(cat.RED.cells) == 2
    assert _area(cat.BLUE.cells) == 4
    assert _area(cat.WHITE_BIG.cells) == 4
    assert _area(cat.YELLOW.cells) == 2
    assert _area(cat.WHITE_SMALL.cells) == 2  # carré à 45°, boîte 2×2
    assert _area(cat.DIAMOND.cells) == 1
    assert _area(cat.BLACK_BODY.cells) == 2  # rectangle plein 1×2


def test_yellow_rasterization_exact():
    assert dict(cat.YELLOW.cells) == {
        Position(0, 0): HalfCell.FULL,
        Position(0, 1): HalfCell.RA_NW,
        Position(1, 0): HalfCell.RA_NW,
    }


def test_red_parallelogram_rasterization_exact():
    assert dict(cat.RED.cells) == {
        Position(0, 0): HalfCell.RA_SE,
        Position(0, 1): HalfCell.FULL,
        Position(0, 2): HalfCell.RA_NW,
    }


def test_white_small_is_45deg_square():
    # Losange : 4 demi-cases, une hypoténuse par arête, aucune face plate.
    assert dict(cat.WHITE_SMALL.cells) == {
        Position(0, 0): HalfCell.RA_SE,
        Position(0, 1): HalfCell.RA_SW,
        Position(1, 0): HalfCell.RA_NE,
        Position(1, 1): HalfCell.RA_NW,
    }


def test_black_body_is_1x2_rectangle():
    assert dict(cat.BLACK_BODY.cells) == {
        Position(0, 0): HalfCell.FULL,
        Position(0, 1): HalfCell.FULL,
    }


def test_red_flip_yields_opposite_chirality():
    # Le retournement doit produire une empreinte absente des seules rotations.
    orients = cat.RED.orientations()
    diagonals = {
        frozenset(hc for _, hc in o if hc is not HalfCell.FULL) for o in orients
    }
    # On retrouve bien les deux chiralités : {RA_SE, RA_NW} et {RA_NE, RA_SW}.
    assert frozenset({HalfCell.RA_SE, HalfCell.RA_NW}) in diagonals
    assert frozenset({HalfCell.RA_NE, HalfCell.RA_SW}) in diagonals


def test_rotations_preserve_area():
    for piece in cat.full_set():
        for orient in piece.orientations():
            assert _area(orient) == _area(piece.cells)


def test_distinct_orientation_counts():
    # Parallélogramme : retournement autorisé -> 2 chiralités × 2 rotations = 4.
    assert len(cat.RED.orientations()) == 4
    # Petit carré plein : invariant par rotation/symétrie, 1 seule orientation.
    assert len(cat.WHITE_SMALL.orientations()) == 1
    # Triangle rectangle isocèle : 4 orientations (un coin par rotation).
    assert len(cat.YELLOW.orientations()) == 4
    # Triangle isocèle base 4 : 4 orientations.
    assert len(cat.BLUE.orientations()) == 4
    # Corps noir : rectangle 1×2 -> 2 orientations (horizontale, verticale).
    assert len(cat.BLACK_BODY.orientations()) == 2
