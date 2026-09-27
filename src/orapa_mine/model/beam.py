"""Simulation de la trajectoire d'un rayon dans la grille (modèle tangram).

Module le plus sensible aux règles : lire docs/RULES.md et la skill
`orapa-mine-rules` avant de le modifier. La géométrie de réflexion vit dans
`gems.HalfCell.reflect` ; ici on ne fait que **marcher de case en case** le long
d'une piste (centre de ligne/colonne) et accumuler les couleurs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from orapa_mine.model.gems import Direction, GemColor, GemKind, Position
from orapa_mine.model.grid import Grid

# Direction est ré-exporté ici par commodité (l'API historique et l'UI
# l'importent depuis beam).
__all__ = ["Direction", "BeamResult", "fire_beam", "COLOR_MIX_TABLE"]


# Couleur finale du rayon en fonction de l'ensemble des couleurs distinctes
# collectées. Isolé ici volontairement (voir docs/RULES.md, "Mélange des
# couleurs").
#
# ✅ Table complète et confirmée (livret + carte "aide de jeu", validée par
# l'utilisateur) : mélange façon peinture (soustractif), le blanc éclaircissant
# la teinte. R+J+B donne du noir, que le blanc éclaircit en gris.
_R, _J, _B, _W = GemColor.RED, GemColor.YELLOW, GemColor.BLUE, GemColor.WHITE
COLOR_MIX_TABLE: dict[frozenset[GemColor], str] = {
    # Une seule couleur
    frozenset({_R}): "rouge",
    frozenset({_B}): "bleu",
    frozenset({_J}): "jaune",
    frozenset({_W}): "blanc",
    # Deux couleurs, sans blanc
    frozenset({_R, _J}): "orange",
    frozenset({_J, _B}): "vert",
    frozenset({_R, _B}): "violet",
    # Deux couleurs, avec blanc
    frozenset({_R, _W}): "rose",
    frozenset({_J, _W}): "jaune clair",
    frozenset({_B, _W}): "bleu clair",
    # Trois couleurs
    frozenset({_R, _J, _B}): "noir",
    frozenset({_J, _B, _W}): "vert clair",
    frozenset({_R, _J, _W}): "orange clair",
    frozenset({_R, _B, _W}): "violet clair",
    # Les quatre
    frozenset({_R, _J, _B, _W}): "gris",
}


def mix_colors(colors: frozenset[GemColor]) -> str | None:
    """Couleur finale du rayon pour un ensemble de couleurs collectées.

    Retourne None si le rayon n'a touché aucune couleur (rayon transparent).
    """
    if not colors:
        return None
    return COLOR_MIX_TABLE.get(colors)


@dataclass(frozen=True)
class BeamResult:
    """Résultat de l'envoi d'un rayon.

    - `exit_point` : case de bordure de sortie, ou None si absorbé (corps noir)
      ou si le rayon boucle indéfiniment.
    - `color` : couleur annoncée (None si aucune gemme colorée touchée).
    - `absorbed` : True si le rayon a été absorbé par un corps noir.
    - `exit_direction` : direction de trajet à la sortie (pour étiqueter le
      bord de sortie côté UI) ; None si absorbé/bouclé.
    - `path` : cases parcourues (utile pour l'animation UI et les tests).
    - `color_steps` : couleur accumulée du rayon **après** chaque case de
      `path` (parallèle à `path`) ; permet à l'UI de teinter le rayon segment
      par segment au fur et à mesure qu'il touche des gemmes.
    """

    exit_point: Position | None
    color: str | None
    absorbed: bool = False
    exit_direction: Direction | None = None
    path: list[Position] = field(default_factory=list)
    color_steps: list[str | None] = field(default_factory=list)


def fire_beam(grid: Grid, entry: Position, direction: Direction) -> BeamResult:
    """Simule un rayon entrant par la case de bordure `entry`, vers `direction`.

    Le rayon commence juste avant `entry` puis avance case par case : case vide
    -> il continue ; case occupée -> il interagit avec la gemme (déviation 90°
    sur une arête, renvoi 180° sur une face plate, absorption pour un corps
    noir) et prend éventuellement sa couleur (une fois par couleur distincte).
    """
    pos = entry - direction  # case fictive juste à l'extérieur de l'entrée
    heading = direction
    colors: set[GemColor] = set()
    path: list[Position] = []
    color_steps: list[str | None] = []
    last_inside = entry

    def record(cell: Position) -> None:
        path.append(cell)
        color_steps.append(mix_colors(frozenset(colors)))

    # Garde-fou anti-boucle : borne large mais finie.
    max_steps = grid.width * grid.height * 8 + 16
    for _ in range(max_steps):
        nxt = pos + heading
        if not grid.is_inside(nxt):
            return BeamResult(
                exit_point=last_inside,
                color=mix_colors(frozenset(colors)),
                exit_direction=heading,
                path=path,
                color_steps=color_steps,
            )

        half = grid.surface.get(nxt)
        if half is None:  # case vide : on avance
            pos = nxt
            last_inside = nxt
            record(nxt)
            continue

        gem = grid.owner[nxt]
        if gem.kind is GemKind.BLACK_BODY:
            return BeamResult(
                exit_point=None, color=None, absorbed=True, path=path, color_steps=color_steps
            )

        if gem.kind is not GemKind.DIAMOND and gem.color is not None:
            colors.add(gem.color)

        new_heading = half.reflect(heading)
        if new_heading is heading.reverse():
            # Face plate : renvoi à 180°, le rayon n'entre pas dans la case.
            heading = new_heading
        else:
            # Arête diagonale : le rayon entre dans la case et tourne à 90°.
            heading = new_heading
            pos = nxt
            last_inside = nxt
            record(nxt)

    # Boucle infinie détectée : pas de sortie exploitable.
    return BeamResult(
        exit_point=None,
        color=mix_colors(frozenset(colors)),
        path=path,
        color_steps=color_steps,
    )
