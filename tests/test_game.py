"""Tests de model.game : actions, historique, score, victoire."""

from __future__ import annotations

from orapa_mine.model.game import GameState
from orapa_mine.model.gems import Direction, GemColor, GemKind, Position
from orapa_mine.model.grid import Grid
from orapa_mine.model import gems_catalog as cat


def _grid_with_pieces() -> tuple[Grid, list]:
    grid = Grid(width=10, height=8)
    gems = [
        cat.YELLOW.at(Position(2, 2)),
        cat.BLACK_BODY.at(Position(5, 5)),
        cat.DIAMOND.at(Position(0, 6)),
    ]
    for gem in gems:
        grid.place_gem(gem)
    return grid, gems


def test_play_shot_records_and_scores():
    grid, _ = _grid_with_pieces()
    game = GameState(hidden_grid=grid)
    shot = game.play_shot(Position(0, 0), Direction.DOWN)
    assert shot.result.exit_point == Position(7, 0)  # colonne libre
    assert game.score == 1
    assert len(game.shots) == 1


def test_query_empty_cell():
    grid, _ = _grid_with_pieces()
    game = GameState(hidden_grid=grid)
    answer = game.query_cell(Position(0, 0))
    assert answer.content.occupied is False
    assert game.score == 1
    assert len(game.queries) == 1


def test_query_normal_gem_reveals_color():
    grid, _ = _grid_with_pieces()
    game = GameState(hidden_grid=grid)
    answer = game.query_cell(Position(2, 2))  # case pleine du jaune
    assert answer.content.occupied is True
    assert answer.content.color is GemColor.YELLOW


def test_query_black_body_is_absorbed():
    grid, _ = _grid_with_pieces()
    game = GameState(hidden_grid=grid)
    answer = game.query_cell(Position(5, 5))
    assert answer.content.absorbed is True
    assert answer.content.kind is GemKind.BLACK_BODY


def test_query_diamond_has_no_color():
    grid, _ = _grid_with_pieces()
    game = GameState(hidden_grid=grid)
    answer = game.query_cell(Position(0, 6))
    assert answer.content.occupied is True
    assert answer.content.kind is GemKind.DIAMOND
    assert answer.content.color is None


def test_query_wormhole_reports_its_kind():
    # Extension trou de ver : interrogée, la case révèle sa nature (pas de couleur).
    grid = Grid(width=10, height=8)
    grid.place_gem(cat.WORMHOLE.at(Position(1, 1)))
    game = GameState(hidden_grid=grid)
    answer = game.query_cell(Position(1, 1))
    assert answer.content.occupied is True
    assert answer.content.kind is GemKind.WORMHOLE
    assert answer.content.color is None


def test_query_half_filled_cell_reports_the_color():
    # Une case seulement à moitié occupée (triangle) répond quand même la couleur.
    from orapa_mine.model.gems import HalfCell

    grid = Grid(width=10, height=8)
    gem = cat.RED.at(Position(3, 3))  # parallélogramme : contient des triangles
    grid.place_gem(gem)
    half_cell = next(
        pos for pos, hc in gem.absolute_cells().items() if hc is not HalfCell.FULL
    )
    game = GameState(hidden_grid=grid)
    answer = game.query_cell(half_cell)
    assert answer.content.occupied is True
    assert answer.content.color is GemColor.RED


def test_submit_correct_guess_wins():
    grid, gems = _grid_with_pieces()
    game = GameState(hidden_grid=grid)
    assert game.submit_guess(gems) is True
    assert game.won is True


def test_submit_wrong_guess_loses():
    grid, gems = _grid_with_pieces()
    game = GameState(hidden_grid=grid)
    wrong = [
        cat.YELLOW.at(Position(3, 3)),  # mauvaise position
        cat.BLACK_BODY.at(Position(5, 5)),
        cat.DIAMOND.at(Position(0, 6)),
    ]
    assert game.submit_guess(wrong) is False
    assert game.won is False


def test_submit_does_not_count_in_score():
    grid, gems = _grid_with_pieces()
    game = GameState(hidden_grid=grid)
    game.play_shot(Position(0, 0), Direction.DOWN)
    game.query_cell(Position(1, 1))
    game.submit_guess(gems)
    assert game.score == 2  # 1 tir + 1 question, la proposition ne compte pas
