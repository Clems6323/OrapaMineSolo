"""Session de résolution d'**une** grille par un algorithme (issue #89).

Contrôleur mince et unique autorité des règles : il expose au participant les
verbes du jeu (lister les pièces, tirer un rayon, interroger une case, poser /
retirer une pièce, proposer), compte le score, impose les limites (5
propositions, plateau complet avant de proposer) et interdit toute fuite de la
grille cachée. Logique pure, testable sans aucune I/O (**aucun import pygame**).

L'arbitre (#91) parle le protocole fil et délègue toute la logique ici.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from orapa_mine.model import gems_catalog as cat
from orapa_mine.model.distance import board_distance
from orapa_mine.model.game import GameState
from orapa_mine.model.gems import Direction, GemKind, Position
from orapa_mine.model.grid import Grid
from orapa_mine.solver import naming

# Pénalité (en « cases ») d'une gemme mystère de bonne position mais mauvaise
# couleur dans la distance de scoring (issue #93). Isolée et documentée.
MYSTERY_COLOR_PENALTY = 1.0

# Nombre de propositions par grille (issue #88). Au-delà, la grille est perdue.
DEFAULT_MAX_PROPOSALS = 5


# --- Erreurs typées (traduites en « reject {reason} » par l'arbitre) ---------


class SolverError(Exception):
    """Erreur côté session, avec un `reason` court et stable."""

    reason = "error"


class UnknownPiece(SolverError):
    reason = "unknown_piece"


class IllegalMove(SolverError):
    reason = "illegal_move"


class IncompleteBoard(SolverError):
    reason = "incomplete_board"


class SessionFinished(SolverError):
    reason = "session_finished"


# --- Résultats renvoyés au participant (sérialisés par l'arbitre) ------------


@dataclass(frozen=True)
class OrientationShape:
    """Empreinte d'une orientation : cases (ligne, colonne, demi-case) ancrées
    au coin haut-gauche de la boîte englobante (anchor en (0,0))."""

    cells: tuple[tuple[int, int, str], ...]


@dataclass(frozen=True)
class InventoryItem:
    """Une pièce à poser : identifiant fil, quantité, orientations disponibles.

    L'index d'une orientation dans `orientations` est la valeur `orient` à
    passer à `place`. Aucune couleur n'apparaît (la mystère reste cachée)."""

    piece: str
    quantity: int
    orientations: tuple[OrientationShape, ...]


@dataclass(frozen=True)
class Inventory:
    items: tuple[InventoryItem, ...]


@dataclass(frozen=True)
class ShotResult:
    """Résultat d'un tir : point de sortie, couleur (token ASCII), absorption."""

    exit: Position | None
    color: str | None
    absorbed: bool


@dataclass(frozen=True)
class CellResult:
    """Réponse à une question de case : vide / couleur / nature d'extension."""

    occupied: bool
    color: str | None = None
    kind: str | None = None


@dataclass(frozen=True)
class SubmitResult:
    won: bool
    points: int
    remaining_proposals: int | None


class SolverSession:
    """Fait jouer un algorithme sur une grille cachée, en imposant les règles."""

    def __init__(self, grid: Grid, *, max_proposals: int = DEFAULT_MAX_PROPOSALS) -> None:
        self._truth = grid
        self._game = GameState(hidden_grid=grid, max_proposals=max_proposals)
        self._candidate = Grid(width=grid.width, height=grid.height)
        self._transcript: list[tuple] = []
        self._submission_distances: list[float] = []
        self._gave_up = False

    # --- État ----------------------------------------------------------------

    @property
    def finished(self) -> bool:
        """Partie terminée : gagnée, propositions épuisées, ou abandon."""
        return self._game.won or self._game.proposals_exhausted or self._gave_up

    @property
    def solved(self) -> bool:
        return self._game.won

    @property
    def points(self) -> int:
        """Score de requêtes courant (tirs + questions + propositions ratées)."""
        return self._game.request_score

    @property
    def remaining_proposals(self) -> int | None:
        return self._game.remaining_proposals

    @property
    def transcript(self) -> list[tuple]:
        """Journal ordonné des actions (audit interne ; jamais exposé au joueur)."""
        return list(self._transcript)

    def best_distance(self) -> float | None:
        """Meilleure (plus petite) distance à la vérité parmi les propositions
        **complètes** faites, ou None si aucune. Réservé au scoring (#93) :
        jamais exposé au joueur en cours de partie."""
        return min(self._submission_distances) if self._submission_distances else None

    def _ensure_active(self) -> None:
        if self.finished:
            raise SessionFinished("the session is already finished")

    # --- Verbes du jeu -------------------------------------------------------

    def pieces(self) -> Inventory:
        """Liste des pièces à poser (nom fil, quantité, orientations).

        La couleur de la gemme mystère n'apparaît pas (seulement sa géométrie).
        """
        counts = Counter(gem.piece.name for gem in self._truth.gems)
        items: list[InventoryItem] = []
        for name, quantity in counts.items():
            piece = cat.ALL_PIECES[name]
            orientations = tuple(
                OrientationShape(
                    tuple(sorted((p.row, p.col, hc.value) for p, hc in footprint))
                )
                for footprint in piece.orientations()
            )
            items.append(
                InventoryItem(
                    piece=naming.piece_id(name),
                    quantity=quantity,
                    orientations=orientations,
                )
            )
        items.sort(key=lambda it: it.piece)  # ordre déterministe (pas l'orient)
        return Inventory(tuple(items))

    def shoot(self, entry: Position, direction: Direction) -> ShotResult:
        """Envoie un rayon depuis une case de bordure (coûte 1 point)."""
        self._ensure_active()
        if not self._truth.is_border(entry):
            raise IllegalMove(f"entry {entry} is not a border cell")
        shot = self._game.play_shot(entry, direction)
        self._transcript.append(("shoot", entry, direction))
        res = shot.result
        return ShotResult(
            exit=res.exit_point,
            color=naming.ray_color_to_ascii(res.color),
            absorbed=res.absorbed,
        )

    def query(self, position: Position) -> CellResult:
        """Interroge une case : « qu'y a-t-il en `position` ? » (coûte 3 points)."""
        self._ensure_active()
        if not self._truth.is_inside(position):
            raise IllegalMove(f"cell {position} is off the board")
        content = self._game.query_cell(position).content
        self._transcript.append(("query", position))
        color = naming.color_to_ascii(content.color) if content.color is not None else None
        kind = naming.kind_to_ascii(content.kind) if content.kind is not None else None
        return CellResult(occupied=content.occupied, color=color, kind=kind)

    def place(
        self,
        piece_id: str,
        anchor: Position,
        orientation: int,
        color: str | None = None,
    ) -> None:
        """Pose une pièce sur le plateau candidat (gratuit).

        `color` n'est requis (et autorisé) que pour la gemme mystère : c'est la
        couleur **devinée**. Lève une erreur typée sur tout coup illégal.
        """
        self._ensure_active()
        piece = naming.piece_by_id(piece_id)
        if piece is None:
            raise UnknownPiece(f"unknown piece id: {piece_id!r}")

        if piece.kind is GemKind.MYSTERY:
            if color is None:
                raise IllegalMove("the mystery piece requires a guessed colour")
            gem_color = naming.ascii_to_color(color)
            if gem_color is None:
                raise IllegalMove(f"invalid colour: {color!r}")
        else:
            if color is not None:
                raise IllegalMove("colour is only allowed for the mystery piece")
            gem_color = None

        variants = piece.orientations()
        if not 0 <= orientation < len(variants):
            raise IllegalMove(
                f"orientation {orientation} out of range for {piece_id} "
                f"(0..{len(variants) - 1})"
            )

        gem = piece.at(anchor, orientation, color=gem_color)
        if not self._candidate.can_place(gem):
            raise IllegalMove("piece is off the board or overlaps another piece")

        placed = sum(1 for g in self._candidate.gems if g.piece.name == piece.name)
        expected = sum(1 for g in self._truth.gems if g.piece.name == piece.name)
        if placed >= expected:
            raise IllegalMove(f"all {expected} '{piece_id}' piece(s) are already placed")

        self._candidate.place_gem(gem)
        self._transcript.append(("place", piece_id, anchor, orientation, color))

    def remove(self, position: Position) -> None:
        """Retire la pièce du plateau candidat occupant `position`."""
        self._ensure_active()
        gem = self._candidate.gem_at(position)
        if gem is None:
            raise IllegalMove(f"no piece to remove at {position}")
        self._candidate.remove_gem(gem)
        self._transcript.append(("remove", position))

    def submit(self) -> SubmitResult:
        """Propose le plateau candidat. **Refusé si toutes les pièces ne sont
        pas posées** (plateau incomplet) — sans coût ni proposition consommée.
        Sinon compte comme une proposition (+5 au score si incorrecte)."""
        self._ensure_active()
        placed = Counter(g.piece.name for g in self._candidate.gems)
        expected = Counter(g.piece.name for g in self._truth.gems)
        if placed != expected:
            raise IncompleteBoard("every piece must be placed before submitting")

        # Distance de scoring figée au moment de la proposition (le candidat
        # peut ensuite changer). Plateau complet -> distance finie.
        distance = board_distance(
            self._candidate, self._truth, mystery_color_penalty=MYSTERY_COLOR_PENALTY
        ).total
        self._submission_distances.append(distance)

        won = self._game.submit_guess(list(self._candidate.gems))
        self._transcript.append(("submit", won))
        return SubmitResult(
            won=won,
            points=self._game.request_score,
            remaining_proposals=self._game.remaining_proposals,
        )

    def give_up(self) -> None:
        """Abandonne la grille (termine la session, non résolue)."""
        self._ensure_active()
        self._gave_up = True
        self._transcript.append(("give_up",))
