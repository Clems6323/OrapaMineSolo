"""Sérialisation d'une partie (sauvegarde / chargement).

Logique pure (aucune I/O fichier, aucun pygame) : conversion partie <-> dict
JSON-compatible. Le fichier de sauvegarde contient toujours la « configuration
à deviner » (grille cachée), et **optionnellement** la progression du joueur
(historique des questions + pièces d'hypothèse posées).

Les résultats des tirs ne sont pas stockés : ils sont recalculés en rejouant
l'historique sur la grille cachée au chargement, ce qui garantit la cohérence.
"""

from __future__ import annotations

from dataclasses import dataclass

from orapa_mine.model.game import CellQuery, GameState, RayShot
from orapa_mine.model.gems import Direction, GemColor, Piece, PlacedGem, Position
from orapa_mine.model.grid import Grid
from orapa_mine.model import gems_catalog as cat

SAVE_VERSION = 1


def _gem_to_dict(gem: PlacedGem) -> dict:
    data = {
        "piece": gem.piece.name,
        "anchor": [gem.anchor.row, gem.anchor.col],
        "orient": gem.piece.variant_index(gem),
    }
    if gem.override_color is not None:  # couleur choisie (gemme mystère)
        data["color"] = gem.override_color.name
    return data


def _gem_from_dict(data: dict) -> PlacedGem:
    piece = cat.ALL_PIECES[data["piece"]]
    row, col = data["anchor"]
    color = GemColor[data["color"]] if "color" in data else None
    return piece.at(Position(row, col), data["orient"], color=color)


def _history_to_list(game: GameState) -> list[dict]:
    actions: list[dict] = []
    for action in game.history:
        if isinstance(action, RayShot):
            actions.append(
                {
                    "type": "shot",
                    "entry": [action.entry.row, action.entry.col],
                    "dir": action.direction.name,
                }
            )
        elif isinstance(action, CellQuery):
            actions.append(
                {"type": "query", "pos": [action.position.row, action.position.col]}
            )
    return actions


def to_dict(
    *,
    width: int,
    height: int,
    palette_pieces: list[Piece],
    hidden_grid: Grid,
    include_progress: bool,
    game: GameState | None = None,
    hypothesis_grid: Grid | None = None,
    timer_minutes: int = 0,
    max_proposals: int = 0,
    one_shot: bool = False,
    given_shots: list[tuple[Position, Direction]] | None = None,
    elapsed_seconds: float = 0.0,
) -> dict:
    """Sérialise une partie en dict. `include_progress` ajoute historique + board.

    `game` et `hypothesis_grid` ne sont requis que si `include_progress` est vrai
    (le mode créateur sauvegarde la configuration seule). `timer_minutes` (0 =
    désactivé) voyage avec la configuration pour être rejoué à l'identique.
    """
    if include_progress and (game is None or hypothesis_grid is None):
        raise ValueError("game et hypothesis_grid sont requis quand include_progress=True")
    data: dict = {
        "version": SAVE_VERSION,
        "width": width,
        "height": height,
        "palette": [p.name for p in palette_pieces],
        "hidden": [_gem_to_dict(g) for g in hidden_grid.gems],
        "progress": bool(include_progress),
        "timer": int(timer_minutes),
        "max_proposals": int(max_proposals),
        "one_shot": bool(one_shot),
    }
    if one_shot:  # tirs donnés d'avance : font partie du puzzle (toujours sauvés)
        data["given_shots"] = [
            {"entry": [e.row, e.col], "dir": d.name} for e, d in (given_shots or [])
        ]
    if include_progress:
        data["history"] = _history_to_list(game)
        data["hypothesis"] = [_gem_to_dict(g) for g in hypothesis_grid.gems]
        data["elapsed"] = round(float(elapsed_seconds), 3)
        data["invalid"] = int(game.invalid_submissions)  # pénalités de score (#45)
    return data


@dataclass
class LoadedGame:
    """Résultat d'un chargement, prêt à être branché dans l'UI."""

    width: int
    height: int
    palette_pieces: list[Piece]
    game: GameState
    hypothesis: Grid
    timer_minutes: int = 0
    max_proposals: int = 0
    one_shot: bool = False
    elapsed_seconds: float = 0.0


def from_dict(data: dict) -> LoadedGame:
    """Reconstruit une partie depuis un dict. Lève ValueError si invalide."""
    if data.get("version") != SAVE_VERSION:
        raise ValueError(f"Version de sauvegarde non supportée : {data.get('version')}")
    width = int(data["width"])
    height = int(data["height"])
    palette = [cat.ALL_PIECES[name] for name in data["palette"]]

    hidden = Grid(width=width, height=height)
    for gem_data in data["hidden"]:
        hidden.place_gem(_gem_from_dict(gem_data))

    max_proposals = int(data.get("max_proposals", 0))
    one_shot = bool(data.get("one_shot"))
    game = GameState(hidden_grid=hidden, max_proposals=max_proposals, one_shot=one_shot)
    for sh in data.get("given_shots", []):  # indices donnés du Coup Unique (#81)
        game.add_given_shot(Position(*sh["entry"]), Direction[sh["dir"]])
    hypothesis = Grid(width=width, height=height)
    if data.get("progress"):
        for action in data.get("history", []):
            if action["type"] == "shot":
                game.play_shot(Position(*action["entry"]), Direction[action["dir"]])
            elif action["type"] == "query":
                game.query_cell(Position(*action["pos"]))
        for gem_data in data.get("hypothesis", []):
            hypothesis.place_gem(_gem_from_dict(gem_data))
        game.invalid_submissions = int(data.get("invalid", 0))

    return LoadedGame(
        width, height, palette, game, hypothesis,
        int(data.get("timer", 0)), max_proposals, one_shot, float(data.get("elapsed", 0.0)),
    )
