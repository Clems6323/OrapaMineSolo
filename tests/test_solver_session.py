"""Session de résolution d'une grille (issue #89).

Barème, limites (5 propositions, plateau complet avant de proposer), noms ASCII
stables, aucune fuite de la grille cachée. Logique pure (aucun pygame).
"""

from __future__ import annotations

import pytest

from orapa_mine.model import gems_catalog as cat
from orapa_mine.model.gems import Direction, GemColor, Position
from orapa_mine.model.grid import Grid
from orapa_mine.solver import naming
from orapa_mine.solver.session import (
    IllegalMove,
    IncompleteBoard,
    InventoryItem,
    SessionFinished,
    ShotResult,
    SolverSession,
    UnknownPiece,
)


def _grid(*gems) -> Grid:
    g = Grid(width=10, height=8)
    for gem in gems:
        g.place_gem(gem)
    return g


def _yellow_truth() -> Grid:
    return _grid(cat.YELLOW.at(Position(2, 2)))


# --- Noms ASCII stables : aller-retour ---------------------------------------


def test_piece_ids_round_trip_for_every_catalogue_piece():
    for wire_id, name in naming.PIECE_ID_TO_NAME.items():
        piece = naming.piece_by_id(wire_id)
        assert piece is not None
        assert piece.name == name
        assert naming.piece_id(name) == wire_id
    # Couverture exacte du catalogue (le garde-fou du module l'impose aussi).
    assert set(naming.NAME_TO_PIECE_ID) == set(cat.ALL_PIECES)


def test_unknown_piece_id_is_rejected():
    assert naming.piece_by_id("banana") is None
    session = SolverSession(_yellow_truth())
    with pytest.raises(UnknownPiece):
        session.place("banana", Position(0, 0), 0)


# --- Inventaire : quantités, mystère caché -----------------------------------


def test_inventory_lists_pieces_with_quantities():
    truth = _grid(
        cat.WORMHOLE.at(Position(1, 1)),
        cat.WORMHOLE.at(Position(1, 5)),
        cat.YELLOW.at(Position(4, 4)),
    )
    inv = {item.piece: item for item in SolverSession(truth).pieces().items}
    assert inv["wormhole"].quantity == 2
    assert inv["yellow"].quantity == 1
    # orient index = position dans la liste des orientations.
    assert len(inv["yellow"].orientations) == len(cat.YELLOW.orientations())


def test_inventory_never_reveals_the_mystery_colour():
    truth = _grid(cat.MYSTERY.at(Position(3, 3), 0, color=GemColor.RED))
    item = SolverSession(truth).pieces().items[0]
    assert item.piece == "mystery"
    assert not hasattr(item, "color")  # aucune couleur exposée
    assert "red" not in repr(item).lower() and "rouge" not in repr(item).lower()


# --- Barème des points -------------------------------------------------------


def test_point_accounting_shot_query_and_wrong_submit():
    session = SolverSession(_yellow_truth())
    session.shoot(Position(0, 3), Direction.DOWN)      # +1
    assert session.points == 1
    session.query(Position(2, 2))                      # +3
    assert session.points == 4
    session.place("yellow", Position(5, 5), 0)         # plateau complet mais faux
    result = session.submit()                          # +5 (incorrect)
    assert result.won is False
    assert session.points == 9


# --- Proposition : plateau complet requis, 5 essais max ----------------------


def test_incomplete_board_submit_is_rejected_without_cost():
    session = SolverSession(_yellow_truth())
    with pytest.raises(IncompleteBoard):
        session.submit()
    assert session.points == 0                 # aucune pénalité
    assert session.remaining_proposals == 5    # aucune proposition consommée


def test_five_proposals_then_session_finished():
    session = SolverSession(_yellow_truth())
    session.place("yellow", Position(5, 5), 0)  # complet mais faux
    for expected_left in (4, 3, 2, 1, 0):
        result = session.submit()
        assert result.won is False
        assert result.remaining_proposals == expected_left
    assert session.finished is True
    with pytest.raises(SessionFinished):
        session.submit()
    with pytest.raises(SessionFinished):
        session.shoot(Position(0, 0), Direction.DOWN)


# --- Victoire et distance ----------------------------------------------------


def test_exact_submission_wins_with_zero_distance():
    session = SolverSession(_yellow_truth())
    session.place("yellow", Position(2, 2), 0)
    result = session.submit()
    assert result.won is True
    assert session.solved is True
    assert session.best_distance() == 0.0
    assert session.finished is True


def test_mystery_right_place_wrong_colour_scores_one():
    truth = _grid(cat.MYSTERY.at(Position(3, 3), 0, color=GemColor.RED))
    session = SolverSession(truth)
    session.place("mystery", Position(3, 3), 0, color="blue")  # bonne place, mauvaise couleur
    result = session.submit()
    assert result.won is False
    assert session.best_distance() == pytest.approx(1.0)  # MYSTERY_COLOR_PENALTY


def test_best_distance_keeps_the_closest_submission():
    session = SolverSession(_yellow_truth())
    session.place("yellow", Position(6, 6), 0)  # loin
    session.submit()
    far = session.best_distance()
    session.remove(Position(6, 6))
    session.place("yellow", Position(2, 3), 0)  # proche de la vérité (2,2)
    session.submit()
    assert session.best_distance() < far


# --- Placements illégaux -----------------------------------------------------


def test_placement_out_of_bounds_is_illegal():
    session = SolverSession(_yellow_truth())
    with pytest.raises(IllegalMove):
        session.place("yellow", Position(7, 9), 0)  # déborde la grille 10x8


def test_overlap_is_illegal():
    truth = _grid(cat.WORMHOLE.at(Position(1, 1)), cat.WORMHOLE.at(Position(1, 5)))
    session = SolverSession(truth)
    session.place("wormhole", Position(3, 3), 0)
    with pytest.raises(IllegalMove):
        session.place("wormhole", Position(3, 3), 0)  # même case


def test_out_of_range_orientation_is_illegal():
    session = SolverSession(_yellow_truth())
    with pytest.raises(IllegalMove):
        session.place("yellow", Position(2, 2), 99)


def test_placing_more_than_inventory_is_illegal():
    session = SolverSession(_yellow_truth())
    session.place("yellow", Position(2, 2), 0)
    with pytest.raises(IllegalMove):
        session.place("yellow", Position(5, 5), 0)  # une seule jaune attendue


def test_colour_rules_for_place():
    truth = _grid(cat.YELLOW.at(Position(2, 2)))
    session = SolverSession(truth)
    with pytest.raises(IllegalMove):
        session.place("yellow", Position(2, 2), 0, color="red")  # couleur interdite

    mystery_truth = _grid(cat.MYSTERY.at(Position(3, 3), 0, color=GemColor.RED))
    s2 = SolverSession(mystery_truth)
    with pytest.raises(IllegalMove):
        s2.place("mystery", Position(3, 3), 0)  # couleur requise
    with pytest.raises(IllegalMove):
        s2.place("mystery", Position(3, 3), 0, color="green")  # couleur invalide


# --- Questions de case : couleur / nature / vide -----------------------------


def test_query_reveals_colour_kind_or_empty():
    truth = _grid(
        cat.YELLOW.at(Position(2, 2)),
        cat.DIAMOND.at(Position(5, 5)),
        cat.BLACK_BODY.at(Position(6, 1)),
        cat.MYSTERY.at(Position(1, 7), 0, color=GemColor.RED),
    )
    session = SolverSession(truth)

    empty = session.query(Position(0, 0))
    assert empty.occupied is False and empty.color is None and empty.kind is None

    yellow = session.query(Position(2, 2))  # (2,2) est la case pleine du triangle
    assert yellow.occupied is True and yellow.color == "yellow" and yellow.kind is None

    diamond_cell = next(iter(truth.gems[1].absolute_cells()))
    diamond = session.query(diamond_cell)
    assert diamond.occupied is True and diamond.kind == "diamond" and diamond.color is None

    bb_cell = next(iter(truth.gems[2].absolute_cells()))
    black = session.query(bb_cell)
    assert black.occupied is True and black.kind == "black-body" and black.color is None

    mystery_cell = next(iter(truth.gems[3].absolute_cells()))
    mystery = session.query(mystery_cell)
    assert mystery.occupied is True and mystery.color == "red" and mystery.kind is None


# --- Tir : bordure requise, compte un point ----------------------------------


def test_shoot_requires_a_border_entry():
    session = SolverSession(_yellow_truth())
    with pytest.raises(IllegalMove):
        session.shoot(Position(3, 3), Direction.RIGHT)  # pas une bordure


def test_shoot_returns_a_result_and_costs_one_point():
    session = SolverSession(_yellow_truth())
    result = session.shoot(Position(2, 0), Direction.RIGHT)
    assert isinstance(result, ShotResult)
    assert result.exit is None or isinstance(result.exit, Position)
    assert session.points == 1


# --- Aucune fuite de la vérité -----------------------------------------------


def test_session_does_not_expose_the_hidden_grid():
    session = SolverSession(_yellow_truth())
    public = {name for name in dir(session) if not name.startswith("_")}
    for leaky in ("hidden_grid", "truth", "hidden"):
        assert leaky not in public
    # L'inventaire est bien une liste d'InventoryItem sans couleur.
    assert all(isinstance(it, InventoryItem) for it in session.pieces().items)
