"""Nombre maximum de propositions (#45) : 0 = illimité, sinon fin au bout de N.

Chaque proposition **incorrecte** consomme un essai ; une proposition correcte
gagne. Une fois les essais épuisés sans trouver, la partie est perdue.
"""

from __future__ import annotations

from orapa_mine.model import gems_catalog as cat
from orapa_mine.model.game import GameState
from orapa_mine.model.gems import Position
from orapa_mine.model.grid import Grid
from orapa_mine.model.serialization import from_dict, to_dict


def _hidden() -> Grid:
    grid = Grid(width=8, height=8)
    grid.place_gem(cat.YELLOW.at(Position(2, 2)))
    return grid


def test_unlimited_by_default():
    game = GameState(hidden_grid=_hidden())
    assert game.max_proposals == 0
    assert game.remaining_proposals is None
    assert game.proposals_exhausted is False
    # Même après plusieurs propositions fausses, jamais « épuisé ».
    for _ in range(5):
        game.submit_guess([])
    assert game.proposals_exhausted is False
    assert game.remaining_proposals is None


def test_single_attempt_exhausts_after_one_wrong_guess():
    game = GameState(hidden_grid=_hidden(), max_proposals=1)
    assert game.remaining_proposals == 1
    assert game.submit_guess([]) is False  # 1 essai utilisé, faux
    assert game.remaining_proposals == 0
    assert game.proposals_exhausted is True


def test_remaining_decreases_with_each_wrong_guess():
    game = GameState(hidden_grid=_hidden(), max_proposals=3)
    game.submit_guess([])
    assert game.remaining_proposals == 2
    game.submit_guess([])
    assert game.remaining_proposals == 1
    assert game.proposals_exhausted is False
    game.submit_guess([])
    assert game.remaining_proposals == 0
    assert game.proposals_exhausted is True


def test_correct_guess_wins_and_is_not_exhausted():
    game = GameState(hidden_grid=_hidden(), max_proposals=1)
    assert game.submit_guess([cat.YELLOW.at(Position(2, 2))]) is True
    assert game.won is True
    assert game.proposals_exhausted is False  # gagné, pas « perdu »


def test_max_proposals_round_trips_through_save():
    game = GameState(hidden_grid=_hidden(), max_proposals=2)
    hypothesis = Grid(width=8, height=8)
    data = to_dict(
        width=8, height=8, palette_pieces=[cat.YELLOW], hidden_grid=game.hidden_grid,
        include_progress=True, game=game, hypothesis_grid=hypothesis, max_proposals=2,
    )
    loaded = from_dict(data)
    assert loaded.game.max_proposals == 2
    assert loaded.max_proposals == 2
