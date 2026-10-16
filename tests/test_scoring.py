"""Score « requêtes » pondéré (#45) : tirs, questions de case, pénalités.

Barème (plus bas = meilleur) : tir de rayon = SHOT_COST, question de case =
CELL_QUERY_COST, proposition incorrecte = INVALID_SUBMISSION_COST.
"""

from __future__ import annotations

from orapa_mine.model import gems_catalog as cat
from orapa_mine.model.game import (
    CELL_QUERY_COST,
    INVALID_SUBMISSION_COST,
    SHOT_COST,
    GameState,
)
from orapa_mine.model.gems import Direction, Position
from orapa_mine.model.grid import Grid
from orapa_mine.model.serialization import from_dict, to_dict


def _game() -> GameState:
    grid = Grid(width=8, height=8)
    grid.place_gem(cat.YELLOW.at(Position(2, 2)))
    return GameState(hidden_grid=grid)


def test_shot_and_cell_query_are_weighted_differently():
    game = _game()
    game.play_shot(Position(2, 0), Direction.RIGHT)   # 1 tir
    game.query_cell(Position(5, 5))                   # 1 question de case
    assert game.request_score == SHOT_COST + CELL_QUERY_COST
    assert game.score == 2  # décompte brut inchangé


def test_cell_query_costs_more_than_a_shot():
    assert CELL_QUERY_COST > SHOT_COST


def test_invalid_submission_adds_penalty():
    game = _game()
    game.play_shot(Position(2, 0), Direction.RIGHT)   # 1 tir
    before = game.request_score
    assert game.submit_guess([]) is False             # proposition vide -> incorrecte
    assert game.invalid_submissions == 1
    assert game.request_score == before + INVALID_SUBMISSION_COST
    # Une seconde proposition fausse pénalise encore.
    game.submit_guess([cat.YELLOW.at(Position(0, 0))])
    assert game.invalid_submissions == 2
    assert game.request_score == before + 2 * INVALID_SUBMISSION_COST


def test_correct_submission_does_not_penalize():
    game = _game()
    assert game.submit_guess([cat.YELLOW.at(Position(2, 2))]) is True
    assert game.invalid_submissions == 0


def test_invalid_submissions_round_trip_through_save():
    game = _game()
    game.play_shot(Position(2, 0), Direction.RIGHT)
    game.submit_guess([])  # une proposition fausse
    hypothesis = Grid(width=8, height=8)
    data = to_dict(
        width=8, height=8, palette_pieces=[cat.YELLOW], hidden_grid=game.hidden_grid,
        include_progress=True, game=game, hypothesis_grid=hypothesis,
    )
    loaded = from_dict(data)
    assert loaded.game.invalid_submissions == 1
    assert loaded.game.request_score == game.request_score
