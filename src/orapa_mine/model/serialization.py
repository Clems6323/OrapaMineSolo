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
from orapa_mine.model.gems import Direction, Piece, PlacedGem, Position
from orapa_mine.model.grid import Grid
from orapa_mine.model import gems_catalog as cat

SAVE_VERSION = 1


def _gem_to_dict(gem: PlacedGem) -> dict:
    return {
        "piece": gem.piece.name,
        "anchor": [gem.anchor.row, gem.anchor.col],
        "orient": gem.piece.orientations().index(gem.orientation),
    }


def _gem_from_dict(data: dict) -> PlacedGem:
    piece = cat.ALL_PIECES[data["piece"]]
    row, col = data["anchor"]
    return piece.at(Position(row, col), data["orient"])


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
    game: GameState,
    hypothesis_grid: Grid,
) -> dict:
    """Sérialise une partie en dict. `include_progress` ajoute historique + board."""
    data: dict = {
        "version": SAVE_VERSION,
        "width": width,
        "height": height,
        "palette": [p.name for p in palette_pieces],
        "hidden": [_gem_to_dict(g) for g in hidden_grid.gems],
        "progress": bool(include_progress),
    }
    if include_progress:
        data["history"] = _history_to_list(game)
        data["hypothesis"] = [_gem_to_dict(g) for g in hypothesis_grid.gems]
    return data


@dataclass
class LoadedGame:
    """Résultat d'un chargement, prêt à être branché dans l'UI."""

    width: int
    height: int
    palette_pieces: list[Piece]
    game: GameState
    hypothesis: Grid


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

    game = GameState(hidden_grid=hidden)
    hypothesis = Grid(width=width, height=height)
    if data.get("progress"):
        for action in data.get("history", []):
            if action["type"] == "shot":
                game.play_shot(Position(*action["entry"]), Direction[action["dir"]])
            elif action["type"] == "query":
                game.query_cell(Position(*action["pos"]))
        for gem_data in data.get("hypothesis", []):
            hypothesis.place_gem(_gem_from_dict(gem_data))

    return LoadedGame(width, height, palette, game, hypothesis)
