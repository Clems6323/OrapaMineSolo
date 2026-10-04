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
__all__ = ["Direction", "BeamResult", "fire_beam", "COLOR_MIX_TABLE", "TELEPORT_SEGMENT"]

# Marqueur de segment « saut de trou de ver » dans `segment_colors` : ce segment
# relie les deux trous et ne doit pas être dessiné (le rayon se téléporte).
TELEPORT_SEGMENT = "__teleport__"


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
    - `path` : cases parcourues (utile pour les tests / usages grossiers).
    - `color_steps` : couleur accumulée **après** chaque case de `path`.
    - `vertices` : polyligne exacte du rayon en coordonnées de case
      (ligne, colonne) flottantes — centres de case aux virages, milieux de
      face aux rebonds 180°. C'est ce que l'UI doit dessiner.
    - `segment_colors` : couleur (nom, ou None si transparent) de chaque segment
      de `vertices` (longueur = len(vertices) - 1).
    """

    exit_point: Position | None
    color: str | None
    absorbed: bool = False
    exit_direction: Direction | None = None
    path: list[Position] = field(default_factory=list)
    color_steps: list[str | None] = field(default_factory=list)
    vertices: list[tuple[float, float]] = field(default_factory=list)
    segment_colors: list[str | None] = field(default_factory=list)


def _wormhole_partner(grid: Grid, gem) -> Position | None:
    """Position de l'autre trou de ver (chaque trou est une case 1×1)."""
    for position, owner in grid.owner.items():
        if owner.kind is GemKind.WORMHOLE and owner is not gem:
            return position
    return None


def fire_beam(grid: Grid, entry: Position, direction: Direction) -> BeamResult:
    """Simule un rayon entrant par la case de bordure `entry`, vers `direction`.

    Le rayon commence juste avant `entry` puis avance case par case : case vide
    -> il continue ; case occupée -> il interagit avec la gemme (déviation 90°
    sur une arête, renvoi 180° sur une face plate, absorption pour un corps
    noir) et prend éventuellement sa couleur (une fois par couleur distincte).
    """
    heading = direction
    colors: set[GemColor] = set()
    path: list[Position] = []
    color_steps: list[str | None] = []
    vertices: list[tuple[float, float]] = []
    segment_colors: list[str | None] = []
    last_inside = entry

    def collect(gem) -> None:
        if gem.kind is not GemKind.DIAMOND and gem.color is not None:
            colors.add(gem.color)

    def add_vertex(row: float, col: float, segment_color: str | None) -> None:
        vertices.append((row, col))
        segment_colors.append(segment_color)

    dr, dc = heading.value
    pos = Position(entry.row - dr, entry.col - dc)  # case fictive à l'extérieur
    # Premier sommet : demi-case avant l'entrée (le rayon arrive du bord).
    vertices.append((entry.row - dr * 0.5, entry.col - dc * 0.5))

    def result(exit_point, absorbed=False) -> BeamResult:
        return BeamResult(
            exit_point=exit_point,
            color=mix_colors(frozenset(colors)),
            absorbed=absorbed,
            exit_direction=heading if (exit_point is not None and not absorbed) else None,
            path=path,
            color_steps=color_steps,
            vertices=vertices,
            segment_colors=segment_colors,
        )

    # Garde-fou anti-boucle : borne large mais finie.
    max_steps = grid.width * grid.height * 8 + 16
    for _ in range(max_steps):
        dr, dc = heading.value
        nxt = pos + heading
        if not grid.is_inside(nxt):
            if grid.is_inside(pos):
                add_vertex(pos.row + dr * 0.5, pos.col + dc * 0.5, mix_colors(frozenset(colors)))
                return result(pos)
            return result(entry)  # rebond immédiat au bord (cas rare)

        half = grid.surface.get(nxt)
        if half is None:  # case vide : on avance jusqu'à son centre
            pos = nxt
            last_inside = nxt
            path.append(nxt)
            color_steps.append(mix_colors(frozenset(colors)))
            add_vertex(nxt.row, nxt.col, mix_colors(frozenset(colors)))
            continue

        gem = grid.owner[nxt]
        if gem.kind is GemKind.WORMHOLE:
            current = mix_colors(frozenset(colors))
            partner = _wormhole_partner(grid, gem)
            if partner is None:
                # Trou de ver orphelin (sans partenaire) : traversée simple.
                pos = nxt
                last_inside = nxt
                path.append(nxt)
                color_steps.append(current)
                add_vertex(nxt.row, nxt.col, current)
                continue
            # Entrée dans le trou `nxt`, sortie de l'autre trou `partner` dans la
            # même direction ; le segment de liaison n'est pas dessiné.
            add_vertex(nxt.row, nxt.col, current)
            add_vertex(partner.row, partner.col, TELEPORT_SEGMENT)
            path.append(nxt)
            path.append(partner)
            color_steps.append(current)
            color_steps.append(current)
            pos = partner
            last_inside = partner
            continue

        if gem.kind is GemKind.BLACK_BODY:
            add_vertex(pos.row + dr * 0.5, pos.col + dc * 0.5, mix_colors(frozenset(colors)))
            return result(None, absorbed=True)

        before = mix_colors(frozenset(colors))
        collect(gem)
        after = mix_colors(frozenset(colors))
        new_heading = half.reflect(heading)

        if new_heading is not heading.reverse():
            # Arête diagonale : le rayon entre dans la case et tourne à 90°.
            # Le segment d'arrivée garde l'ancienne couleur (teinte prise au virage).
            add_vertex(nxt.row, nxt.col, before)
            path.append(nxt)
            color_steps.append(after)
            heading = new_heading
            pos = nxt
            last_inside = nxt
            continue

        # Face plate : rebond 180° sur la face de `nxt` (le rayon n'y entre pas).
        add_vertex(pos.row + dr * 0.5, pos.col + dc * 0.5, before)  # arrivée = ancienne teinte
        if color_steps:
            color_steps[-1] = after
        heading = heading.reverse()
        # Si la case de rebroussement `pos` est elle-même un miroir (le rayon y
        # avait dévié), il doit y redévier au lieu de la traverser.
        pos_half = grid.surface.get(pos)
        if pos_half is not None:
            collect(grid.owner[pos])
            heading = pos_half.reflect(heading)
            add_vertex(pos.row, pos.col, after)  # segment de retour déjà teinté

    # Boucle infinie détectée : pas de sortie exploitable.
    return result(None)
