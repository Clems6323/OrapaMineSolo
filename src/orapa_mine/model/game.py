"""État de la partie solo : actions, historique, score, victoire.

Deux types d'action (règles officielles) :
- **tir** : envoyer un rayon depuis un point de bordure (`play_shot`) ;
- **question de case** : « Qu'y a-t-il en X ? » (`query_cell`).

Score solo = nombre d'actions (tirs + questions) avant une proposition
correcte : moins il y en a, mieux c'est (voir docs/RULES.md, « Variantes
solo »). La proposition de solution (`submit_guess`) ne compte pas dans le
score.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from orapa_mine.model.beam import BeamResult, fire_beam
from orapa_mine.model.gems import Direction, GemColor, GemKind, PlacedGem, Position
from orapa_mine.model.grid import Grid


@dataclass(frozen=True)
class CellContent:
    """Réponse à « Qu'y a-t-il en [case] ? ».

    - vide -> `occupied=False` ;
    - gemme normale -> `color` renseignée ;
    - diamant -> `kind=DIAMOND`, `color=None` ;
    - corps noir -> `absorbed=True` (« Le signal a été absorbé »).
    """

    occupied: bool
    color: GemColor | None = None
    kind: GemKind | None = None
    absorbed: bool = False


@dataclass(frozen=True)
class RayShot:
    """Un tir de rayon et son résultat."""

    entry: Position
    direction: Direction
    result: BeamResult


@dataclass(frozen=True)
class CellQuery:
    """Une question de case et sa réponse."""

    position: Position
    content: CellContent


@dataclass
class GameState:
    """État complet d'une partie solo.

    `hidden_grid` est la grille générée par l'ordinateur : ne jamais l'exposer
    à l'UI hors mode debug.
    """

    hidden_grid: Grid
    history: list[RayShot | CellQuery] = field(default_factory=list)
    won: bool = False

    def play_shot(self, entry: Position, direction: Direction) -> RayShot:
        """Envoie un rayon, enregistre le tir dans l'historique, le retourne."""
        result = fire_beam(self.hidden_grid, entry, direction)
        shot = RayShot(entry=entry, direction=direction, result=result)
        self.history.append(shot)
        return shot

    def query_cell(self, position: Position) -> CellQuery:
        """Répond à « Qu'y a-t-il en `position` ? » et l'enregistre."""
        gem = self.hidden_grid.gem_at(position)
        if gem is None:
            content = CellContent(occupied=False)
        elif gem.kind is GemKind.BLACK_BODY:
            content = CellContent(occupied=True, kind=GemKind.BLACK_BODY, absorbed=True)
        else:
            content = CellContent(occupied=True, color=gem.color, kind=gem.kind)
        query = CellQuery(position=position, content=content)
        self.history.append(query)
        return query

    def submit_guess(self, guessed_gems: list[PlacedGem]) -> bool:
        """Compare la proposition à la grille cachée. Met à jour `won`.

        Correspondance exacte requise : position, forme, orientation ET
        couleur/nature de chaque gemme (via la signature par case).
        """
        self.won = _signature(guessed_gems) == _signature(self.hidden_grid.gems)
        return self.won

    @property
    def score(self) -> int:
        """Score = nombre d'actions (tirs + questions de case)."""
        return len(self.history)

    @property
    def shots(self) -> list[RayShot]:
        return [a for a in self.history if isinstance(a, RayShot)]

    @property
    def queries(self) -> list[CellQuery]:
        return [a for a in self.history if isinstance(a, CellQuery)]


def _signature(
    gems: list[PlacedGem],
) -> dict[Position, tuple[object, GemColor | None, GemKind]]:
    """Empreinte par case : position -> (géométrie, couleur, nature).

    Capture à la fois la position, la forme, l'orientation et la couleur.
    """
    signature: dict[Position, tuple[object, GemColor | None, GemKind]] = {}
    for gem in gems:
        for position, half in gem.absolute_cells().items():
            signature[position] = (half, gem.color, gem.kind)
    return signature
