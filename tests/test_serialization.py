"""Tests de sauvegarde / chargement (model.serialization)."""

from __future__ import annotations

import pytest

from orapa_mine.model import gems_catalog as cat
from orapa_mine.model import serialization
from orapa_mine.model.game import GameState
from orapa_mine.model.gems import Direction, Position
from orapa_mine.model.grid import Grid


def _sig(grid: Grid) -> set:
    return {serialization._gem_to_dict(g)["piece"] + str(serialization._gem_to_dict(g)["anchor"]) + str(serialization._gem_to_dict(g)["orient"]) for g in grid.gems}


def _setup():
    hidden = Grid(width=10, height=8)
    hidden.place_gem(cat.YELLOW.at(Position(2, 2)))
    hidden.place_gem(cat.BLUE.at(Position(4, 4)))
    game = GameState(hidden_grid=hidden)
    game.play_shot(Position(0, 0), Direction.DOWN)
    game.query_cell(Position(2, 2))
    hypothesis = Grid(width=10, height=8)
    hypothesis.place_gem(cat.RED.at(Position(1, 1)))
    palette = cat.base_set()
    return hidden, game, hypothesis, palette


def test_round_trip_with_progress():
    hidden, game, hypothesis, palette = _setup()
    data = serialization.to_dict(
        width=10, height=8, palette_pieces=palette, hidden_grid=hidden,
        include_progress=True, game=game, hypothesis_grid=hypothesis,
    )
    loaded = serialization.from_dict(data)
    assert (loaded.width, loaded.height) == (10, 8)
    assert [p.name for p in loaded.palette_pieces] == [p.name for p in palette]
    assert _sig(loaded.game.hidden_grid) == _sig(hidden)
    assert _sig(loaded.hypothesis) == _sig(hypothesis)
    # historique rejoué : mêmes actions et mêmes résultats recalculés
    assert loaded.game.score == 2
    assert len(loaded.game.shots) == 1
    assert len(loaded.game.queries) == 1
    assert loaded.game.shots[0].result.exit_point == game.shots[0].result.exit_point
    assert loaded.game.queries[0].content.color == game.queries[0].content.color


def test_round_trip_configuration_only():
    hidden, game, hypothesis, palette = _setup()
    data = serialization.to_dict(
        width=10, height=8, palette_pieces=palette, hidden_grid=hidden,
        include_progress=False, game=game, hypothesis_grid=hypothesis,
    )
    assert "history" not in data and "hypothesis" not in data
    loaded = serialization.from_dict(data)
    assert _sig(loaded.game.hidden_grid) == _sig(hidden)  # config préservée
    assert loaded.game.history == []  # aucune progression
    assert loaded.hypothesis.gems == []


def test_round_trip_with_wormholes():
    hidden = Grid(width=10, height=8)
    hidden.place_gem(cat.WORMHOLE.at(Position(1, 1)))
    hidden.place_gem(cat.WORMHOLE.at(Position(4, 5)))
    palette = cat.base_set() + [cat.WORMHOLE]
    data = serialization.to_dict(
        width=10, height=8, palette_pieces=palette, hidden_grid=hidden,
        include_progress=False,
    )
    loaded = serialization.from_dict(data)
    worms = [g for g in loaded.game.hidden_grid.gems if g.piece.name == "trou-de-ver"]
    assert len(worms) == 2
    assert [p.name for p in loaded.palette_pieces] == [p.name for p in palette]


def test_round_trip_preserves_timer():
    hidden, game, hypothesis, palette = _setup()
    data = serialization.to_dict(
        width=10, height=8, palette_pieces=palette, hidden_grid=hidden,
        include_progress=False, timer_minutes=5,
    )
    assert data["timer"] == 5
    assert serialization.from_dict(data).timer_minutes == 5


def test_timer_defaults_to_zero_when_absent():
    # Compatibilité : une sauvegarde sans champ « timer » charge sans minuteur.
    loaded = serialization.from_dict(
        {"version": 1, "width": 10, "height": 8, "palette": [], "hidden": [], "progress": False}
    )
    assert loaded.timer_minutes == 0


def test_unknown_version_is_rejected():
    with pytest.raises(ValueError):
        serialization.from_dict({"version": 999, "width": 10, "height": 8, "palette": [], "hidden": []})
