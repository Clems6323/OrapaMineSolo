"""Tir de rayon de **test** : points d'entrée, simulation et animation.

Composant d'UI partagé par l'écran de jeu (rayon sur les hypothèses) et le mode
créateur (rayon sur la configuration en cours). Il ne contient aucune règle : la
trajectoire est calculée par `model.beam.fire_beam`, on se contente d'animer le
résultat (`vertices` + `segment_colors`) et de dessiner les points d'entrée.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from orapa_mine.model.beam import BeamResult, TELEPORT_SEGMENT, fire_beam
from orapa_mine.model.gems import Direction, Position
from orapa_mine.model.grid import Grid
from orapa_mine.ui import i18n, theme
from orapa_mine.ui.board_render import lighten as _lighten

_RAY_SPEED = 620.0  # pixels par seconde pour l'animation du rayon


@dataclass
class EntryPoint:
    """Un point d'entrée cliquable sur la bordure du plateau."""

    entry: Position
    direction: Direction
    center: tuple[int, int]
    label: str


class RayTester:
    """Points d'entrée + rayon de test animé pour un plateau donné."""

    def __init__(self, width: int, height: int, font: pygame.font.Font) -> None:
        self.width = width
        self.height = height
        self.font = font
        self.entries = self._build_entries()
        self.entry_by_label = {ep.label: ep for ep in self.entries}
        self.hovered_entry: int | None = None
        self.last_test: str | None = None

        self._points: list[tuple[float, float]] = []
        self._seg_colors: list[tuple[int, int, int]] = []
        self._seg_skip: list[bool] = []  # segment de téléportation (non dessiné)
        self._absorbed = False
        self._total_len = 0.0
        self._progress = 0.0

    # --- Construction ------------------------------------------------------

    def _build_entries(self) -> list[EntryPoint]:
        entries: list[EntryPoint] = []
        w, h = self.width, self.height
        off = theme.ENTRY_MARGIN * 0.55

        def make(pos: Position, direction: Direction, center: tuple[int, int]) -> None:
            label = theme.entry_label(pos, direction, w, h)
            entries.append(EntryPoint(pos, direction, center, label))

        for col in range(w):
            cx, _ = theme.cell_center(Position(0, col))
            make(Position(0, col), Direction.DOWN, (int(cx), int(theme.BOARD_Y - off)))
            bottom = theme.board_bottom(h) + off
            make(Position(h - 1, col), Direction.UP, (int(cx), int(bottom)))
        for row in range(h):
            _, cy = theme.cell_center(Position(row, 0))
            make(Position(row, 0), Direction.RIGHT, (int(theme.BOARD_X - off), int(cy)))
            right = theme.BOARD_X + w * theme.CELL + off
            make(Position(row, w - 1), Direction.LEFT, (int(right), int(cy)))
        return entries

    # --- Interaction -------------------------------------------------------

    def entry_at(self, pos: tuple[int, int]) -> int | None:
        for index, ep in enumerate(self.entries):
            if math.dist(pos, ep.center) <= 16:
                return index
        return None

    def hover(self, pos: tuple[int, int]) -> None:
        self.hovered_entry = self.entry_at(pos)

    def fire(self, grid: Grid, ep: EntryPoint) -> BeamResult:
        """Tire un rayon sur `grid` depuis `ep` et lance l'animation."""
        result = fire_beam(grid, ep.entry, ep.direction)
        self._points = [theme.point_px(r, c) for r, c in result.vertices]
        self._seg_colors = [theme.ray_rgb(name) for name in result.segment_colors]
        self._seg_skip = [name == TELEPORT_SEGMENT for name in result.segment_colors]
        self._absorbed = result.absorbed
        # Longueur animée : on ignore les sauts de trou de ver (téléportation).
        self._total_len = sum(
            0.0 if self._seg_skip[i] else math.dist(self._points[i], self._points[i + 1])
            for i in range(len(self._points) - 1)
        )
        self._progress = 0.0
        self.last_test = f"Test {ep.label} → {self.result_label(result)}"
        return result

    def result_label(self, result: BeamResult) -> str:
        if result.absorbed:
            return i18n.color("absorbé")
        if result.exit_point is None or result.exit_direction is None:
            return "?"
        label = theme.exit_label(result.exit_point, result.exit_direction, self.width, self.height)
        return f"{label} ({i18n.color(result.color)})"

    def update(self, dt: float) -> None:
        if self._progress < self._total_len:
            self._progress = min(self._total_len, self._progress + _RAY_SPEED * dt)

    # --- Rendu -------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        self.draw_beam(surface)
        self.draw_entries(surface)

    def draw_beam(self, surface: pygame.Surface) -> None:
        """Dessine uniquement le rayon (à placer SOUS les gemmes : la réflexion a
        lieu dans la case d'une gemme, qui masque ainsi le coude au lieu de le
        laisser déborder sur la pièce)."""
        self._draw_ray(surface)

    def draw_entries(self, surface: pygame.Surface) -> None:
        """Dessine les points d'entrée cliquables (à placer au-dessus)."""
        self._draw_entries(surface)

    def _draw_ray(self, surface: pygame.Surface) -> None:
        pts = self._points
        if len(pts) < 2:
            return
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        remaining = self._progress
        head = pts[0]
        head_rgb = self._seg_colors[0] if self._seg_colors else theme.RAY_TRANSPARENT
        drawn = False
        prev_dir: tuple[int, int] | None = None  # direction du segment précédent dessiné
        _sign = lambda t: (t > 0) - (t < 0)  # noqa: E731
        for i in range(len(pts) - 1):
            if remaining <= 0:
                break
            a, b = pts[i], pts[i + 1]
            if i < len(self._seg_skip) and self._seg_skip[i]:
                head = b  # saut de trou de ver : téléportation instantanée, non tracée
                prev_dir = None  # la téléportation coupe la continuité
                continue
            seg = math.dist(a, b)
            if seg == 0:
                continue
            rgb = self._seg_colors[i]
            end = b if remaining >= seg else (
                a[0] + (b[0] - a[0]) * remaining / seg,
                a[1] + (b[1] - a[1]) * remaining / seg,
            )
            cur_dir = (_sign(b[0] - a[0]), _sign(b[1] - a[1]))
            self._glow_segment(overlay, a, end, rgb)
            if prev_dir is not None and prev_dir != cur_dir:
                # Vrai changement de direction (coude à 90°) : pastille concentrique
                # pour arrondir le coude du rayon ET de son halo (pas d'encoche).
                self._fillet(overlay, a, rgb)
            head, head_rgb, drawn = end, rgb, True
            prev_dir = cur_dir
            remaining -= seg
        if not drawn:
            return
        r, g, b = head_rgb
        for radius, alpha in ((14, 60), (8, 120), (4, 220)):
            pygame.draw.circle(overlay, (r, g, b, alpha), (int(head[0]), int(head[1])), radius)
        surface.blit(overlay, (0, 0))
        if self._absorbed and self._progress >= self._total_len:
            pygame.draw.circle(surface, (30, 30, 40), (int(head[0]), int(head[1])), 12)
            pygame.draw.circle(surface, (90, 90, 110), (int(head[0]), int(head[1])), 12, width=2)

    def _glow_segment(
        self,
        overlay: pygame.Surface,
        a: tuple[float, float],
        b: tuple[float, float],
        rgb: tuple[int, int, int],
    ) -> None:
        r, g, bl = rgb
        for width, alpha in ((16, 34), (9, 70), (4, 150)):
            pygame.draw.line(overlay, (r, g, bl, alpha), a, b, width)
        pygame.draw.line(overlay, (*_lighten(rgb, 0.5), 235), a, b, 2)

    def _fillet(
        self, overlay: pygame.Surface, point: tuple[float, float], rgb: tuple[int, int, int]
    ) -> None:
        """Pastilles concentriques à un coude pour l'arrondir (rayon + halo).

        Les rayons/alphas reprennent la coupe transversale d'un segment (demi-
        largeurs 8/4/2) afin que le coude ait exactement le même dégradé que le
        trait droit, sans encoche ni chevauchement des bouts plats de ligne.
        """
        r, g, bl = rgb
        px, py = int(point[0]), int(point[1])
        for radius, alpha in ((8, 34), (4, 70), (2, 150)):
            pygame.draw.circle(overlay, (r, g, bl, alpha), (px, py), radius)
        pygame.draw.circle(overlay, (*_lighten(rgb, 0.5), 235), (px, py), 1)

    def _draw_entries(self, surface: pygame.Surface) -> None:
        for index, ep in enumerate(self.entries):
            hot = index == self.hovered_entry
            color = theme.ENTRY_HOVER if hot else theme.ENTRY_IDLE
            pygame.draw.circle(surface, color, ep.center, 15 if hot else 12)
            pygame.draw.circle(surface, theme.BACKGROUND, ep.center, 15 if hot else 12, width=2)
            label = self.font.render(ep.label, True, theme.ON_ACCENT if hot else theme.TEXT_DIM)
            surface.blit(label, label.get_rect(center=ep.center))
