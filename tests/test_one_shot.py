"""Mode « Coup Unique » (#81).

Grille aléatoire + un jeu de tirs donnés d'avance (indices figés), aucune
nouvelle requête, une seule proposition, score = distance. Sérialisable et
créable en mode créateur.
"""

from __future__ import annotations

import random

import pygame

from orapa_mine.ai.generator import Difficulty, generate_hidden_grid, random_edge_shots
from orapa_mine.model import gems_catalog as cat
from orapa_mine.model.game import GameState
from orapa_mine.model.gems import Direction, Position
from orapa_mine.model.grid import Grid
from orapa_mine.model.serialization import from_dict, to_dict
from orapa_mine.ui.config_screen import ConfigScreen
from orapa_mine.ui.creator_screen import CreatorScreen


# --- Génération des tirs donnés ----------------------------------------------


def test_random_edge_shots_are_distinct_and_bounded():
    shots = random_edge_shots(10, 8, 15, random.Random(0))
    assert len(shots) == 15
    assert len(set(shots)) == 15  # pas de doublon (entrée + direction)
    for entry, direction in shots:
        assert 0 <= entry.row < 8 and 0 <= entry.col < 10
        assert direction in (Direction.UP, Direction.DOWN, Direction.LEFT, Direction.RIGHT)


def test_random_edge_shots_capped_by_available_edges():
    # 8×6 -> 2*8 + 2*6 = 28 entrées possibles ; demander plus en rend 28.
    shots = random_edge_shots(8, 6, 100, random.Random(0))
    assert len(shots) == 28


# --- GameState : indices donnés, hors score, pas d'historique joué ----------


def _grid() -> Grid:
    g = Grid(width=10, height=8)
    g.place_gem(cat.YELLOW.at(Position(2, 2)))
    return g


def test_given_shots_are_clues_not_played_history():
    game = GameState(hidden_grid=_grid(), one_shot=True, max_proposals=1)
    for entry, direction in random_edge_shots(10, 8, 10, random.Random(1)):
        game.add_given_shot(entry, direction)
    assert len(game.given_shots) == 10
    assert len(game.clues) == 10          # affichés comme indices
    assert len(game.history) == 0         # le joueur n'a rien joué
    assert game.request_score == 0        # les indices ne coûtent rien


def test_normal_mode_clues_are_the_played_history():
    game = GameState(hidden_grid=_grid())  # mode normal
    game.play_shot(Position(2, 0), Direction.RIGHT)
    assert game.clues == game.history
    assert len(game.given_shots) == 0


# --- Sérialisation : les indices font partie du puzzle (toujours sauvés) -----


def test_one_shot_serialization_round_trip():
    rng = random.Random(3)
    grid = generate_hidden_grid(difficulty=Difficulty(pieces=cat.base_set(), width=10, height=8), rng=rng)
    shots = random_edge_shots(10, 8, 12, rng)
    game = GameState(hidden_grid=grid, one_shot=True, max_proposals=1)
    for e, d in shots:
        game.add_given_shot(e, d)
    data = to_dict(
        width=10, height=8, palette_pieces=cat.base_set(), hidden_grid=grid,
        include_progress=False, one_shot=True, given_shots=shots,
    )
    assert data["one_shot"] is True
    assert len(data["given_shots"]) == 12
    loaded = from_dict(data)
    assert loaded.one_shot is True
    assert loaded.game.one_shot is True
    assert len(loaded.game.given_shots) == 12
    # Mêmes indices (entrée, direction, résultat) après rechargement.
    assert [(s.entry, s.direction, s.result.color) for s in loaded.game.given_shots] == \
           [(s.entry, s.direction, s.result.color) for s in game.given_shots]


# --- Écran de configuration : le mode Coup Unique ----------------------------


def test_config_one_shot_difficulty():
    cfg = ConfigScreen()
    cfg.one_shot = True
    cfg.tests.value = 18
    d = cfg._difficulty()
    assert d.one_shot is True
    assert d.num_tests == 18
    assert d.timer_minutes == 0      # pas de minuteur en Coup Unique
    assert d.max_proposals == 1      # une seule proposition


def test_config_mode_toggle_click():
    cfg = ConfigScreen()
    assert cfg.one_shot is False
    cfg.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=cfg.oneshot_rect.center))
    assert cfg.one_shot is True
    cfg.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=cfg.normal_rect.center))
    assert cfg.one_shot is False


def test_creator_exposes_one_shot_settings():
    cr = CreatorScreen(size_index=1, one_shot=True, num_tests=22)
    assert cr.one_shot is True
    assert cr.num_tests == 22


# --- Écran de jeu : aucune nouvelle requête en Coup Unique -------------------


def test_game_screen_blocks_input_in_one_shot():
    from orapa_mine.ui.game_screen import GameScreen

    game = GameState(hidden_grid=_grid(), one_shot=True, max_proposals=1)
    for e, d in random_edge_shots(10, 8, 8, random.Random(2)):
        game.add_given_shot(e, d)
    gs = GameScreen(game, [*cat.base_set()], timer_minutes=0)
    assert gs.one_shot is True
    # Cliquer là où serait la zone de saisie n'active aucune saisie.
    gs.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=gs.input_rect.center))
    assert gs.input_active is False
