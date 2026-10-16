"""Distance de Wasserstein (Earth Mover) entre une configuration devinée et la vérité.

Idée
----
Chaque gemme posée est vue comme une **mesure uniforme sur son aire** (le
« tas de matière » qu'elle occupe). La distance entre une gemme devinée et sa
vraie position est le coût de transport optimal W1 pour déplacer l'une sur
l'autre, normalisé par l'aire : c'est la **distance moyenne (en cases) que doit
parcourir chaque brin de matière**.

Propriétés utiles :
- 0 si et seulement si les deux placements occupent exactement la même
  surface (deux orientations indiscernables d'une pièce symétrique, comme le
  losange blanc tourné de 90°, donnent donc bien 0) ;
- pour une simple translation de vecteur t, la distance vaut exactement |t| ;
- rotations / retournements / décalages sont mesurés dans la même unité (la
  case), sans avoir à pondérer « position » contre « orientation » ;
- elle ne sature pas : contrairement à l'IoU, elle continue de décroître
  quand les deux gemmes sont disjointes.

Discrétisation : une demi-case `RA_*` devient un atome de masse 0,5 à son
centroïde (à 1/3 des deux cathètes depuis l'angle droit) ; une case `FULL`
devient deux atomes de masse 0,5 en son centre. Toutes les masses étant égales
(0,5), le transport optimal est un problème d'**affectation** : résolu ici par
un Hungarian en Python pur (au plus 8 atomes), donc aucune dépendance ajoutée.

Score total = somme des distances par gemme ; `math.inf` si une gemme de la
vérité n'a pas de contrepartie sur le plateau deviné.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from orapa_mine.model.gems import GemColor, HalfCell, PlacedGem, Position
from orapa_mine.model.grid import Grid

Atom = tuple[float, float]  # (x = colonne, y = ligne), en unités de case

_ONE_THIRD = 1.0 / 3.0

# Position (x, y) du centroïde d'une demi-case dans sa case, origine au coin
# haut-gauche. Un triangle rectangle a son centroïde à 1/3 des cathètes depuis
# l'angle droit.
_CENTROID: dict[HalfCell, tuple[float, float]] = {
    HalfCell.FULL: (0.5, 0.5),
    HalfCell.RA_NW: (_ONE_THIRD, _ONE_THIRD),
    HalfCell.RA_NE: (1 - _ONE_THIRD, _ONE_THIRD),
    HalfCell.RA_SW: (_ONE_THIRD, 1 - _ONE_THIRD),
    HalfCell.RA_SE: (1 - _ONE_THIRD, 1 - _ONE_THIRD),
}


def gem_atoms(gem: PlacedGem) -> list[Atom]:
    """Atomes de masse 0,5 représentant l'aire de `gem` (coordonnées absolues)."""
    atoms: list[Atom] = []
    for pos, half in gem.absolute_cells().items():
        cx, cy = _CENTROID[half]
        atom = (pos.col + cx, pos.row + cy)
        atoms.append(atom)
        if half is HalfCell.FULL:  # aire 1 = deux atomes de 0,5
            atoms.append(atom)
    return atoms


def _hungarian(cost: list[list[float]]) -> float:
    """Coût minimal d'une affectation parfaite sur une matrice carrée n×n."""
    n = len(cost)
    inf = float("inf")
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    match = [0] * (n + 1)  # match[j] = ligne affectée à la colonne j
    way = [0] * (n + 1)
    for i in range(1, n + 1):
        match[0] = i
        j0 = 0
        minv = [inf] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = match[j0], inf, 0
            for j in range(1, n + 1):
                if used[j]:
                    continue
                cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j], way[j] = cur, j0
                if minv[j] < delta:
                    delta, j1 = minv[j], j
            for j in range(n + 1):
                if used[j]:
                    u[match[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if match[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            match[j0] = match[j1]
            j0 = j1
    return sum(cost[match[j] - 1][j - 1] for j in range(1, n + 1))


def gem_distance(guess: PlacedGem, truth: PlacedGem) -> float:
    """W1 entre deux gemmes de même pièce, en cases (déplacement moyen par brin
    de matière). Les deux gemmes doivent avoir la même aire."""
    a, b = gem_atoms(guess), gem_atoms(truth)
    if len(a) != len(b):
        raise ValueError("Gemmes d'aires différentes : pièces non comparables")
    cost = [[math.dist(p, q) for q in b] for p in a]
    return _hungarian(cost) / len(a)  # masses égales -> moyenne des déplacements


@dataclass(frozen=True)
class GemMatch:
    """Résultat détaillé pour une gemme de la vérité."""

    truth: PlacedGem
    guess: PlacedGem | None  # None : gemme absente du plateau deviné
    distance: float  # math.inf si guess est None


@dataclass(frozen=True)
class Score:
    """Distance globale entre un plateau deviné et la vérité."""

    matches: tuple[GemMatch, ...]

    @property
    def total(self) -> float:
        """Somme des distances ; `inf` si au moins une gemme manque."""
        return sum(m.distance for m in self.matches)

    @property
    def missing(self) -> int:
        return sum(1 for m in self.matches if m.guess is None)

    @property
    def placed_total(self) -> float:
        """Somme restreinte aux gemmes posées : toujours finie, donc utile
        comme indicateur de progression pendant qu'on construit sa réponse."""
        return sum(m.distance for m in self.matches if m.guess is not None)


def _identity(gem: PlacedGem) -> tuple[str, GemColor | None]:
    # La couleur ne distingue que le mystère (couleur catalogue = None).
    return gem.piece.name, gem.piece.color


def board_distance(
    guess: Grid,
    truth: Grid,
    *,
    mystery_color_penalty: float = math.inf,
) -> Score:
    """Compare le plateau deviné à la vérité, gemme par gemme.

    Les gemmes sont appariées par pièce (`piece.name`). Quand plusieurs
    exemplaires identiques existent (trous de ver ×2), l'appariement qui
    minimise la somme des distances est retenu. Une gemme vraie sans
    contrepartie donne `inf`. Pour une gemme mystère de mauvaise couleur on
    ajoute `mystery_color_penalty` (par défaut `inf` : proposition fausse).
    """
    truth_by: dict[tuple, list[PlacedGem]] = defaultdict(list)
    guess_by: dict[tuple, list[PlacedGem]] = defaultdict(list)
    for g in truth.gems:
        truth_by[_identity(g)].append(g)
    for g in guess.gems:
        guess_by[_identity(g)].append(g)

    matches: list[GemMatch] = []
    for key, t_list in truth_by.items():
        g_list = guess_by.get(key, [])
        matches.extend(_match_group(g_list, t_list, mystery_color_penalty))
    return Score(tuple(matches))


def _pair_cost(g: PlacedGem, t: PlacedGem, color_penalty: float) -> float:
    d = gem_distance(g, t)
    if t.color is not None and g.color != t.color:  # n'arrive que pour le mystère
        d += color_penalty
    return d


def _match_group(
    guesses: list[PlacedGem], truths: list[PlacedGem], color_penalty: float
) -> list[GemMatch]:
    """Appariement optimal d'un groupe de pièces identiques (taille 1 le plus
    souvent, 2 pour les trous de ver : on teste simplement les permutations)."""
    from itertools import permutations

    k = min(len(guesses), len(truths))
    if k == 0:
        return [GemMatch(t, None, math.inf) for t in truths]

    best: tuple[float, list[GemMatch]] | None = None
    for chosen in permutations(range(len(guesses)), k):
        pairs = [
            GemMatch(t, guesses[gi], _pair_cost(guesses[gi], t, color_penalty))
            for t, gi in zip(truths[:k], chosen)
        ]
        total = sum(m.distance for m in pairs)
        if best is None or total < best[0]:
            best = (total, pairs)
    assert best is not None
    result = best[1]
    result.extend(GemMatch(t, None, math.inf) for t in truths[k:])
    return result


__all__ = ["Position", "gem_atoms", "gem_distance", "board_distance", "Score", "GemMatch"]
