"""Écran de jeu Pygame : plateau, hypothèses, rayon animé, historique.

Deux façons de tirer, volontairement distinctes :

- **Cliquer un point d'entrée** envoie un rayon de *test* qui se réfléchit sur
  les pièces d'**hypothèse posées par le joueur** (aide à la déduction, non
  enregistré). Le trajet est animé.
- **Saisir une étiquette** dans la zone de texte (sous « Historique ») envoie
  la *vraie* question sur la grille cachée : seuls l'étiquette d'entrée, le
  point de sortie et la couleur sont enregistrés dans l'historique — le trajet
  réel n'est jamais dessiné (il révélerait les positions cachées).

Aucune règle de jeu ici : on appelle `fire_beam` / `GameState` et on affiche.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from orapa_mine.model.beam import BeamResult, fire_beam
from orapa_mine.model.game import GameState, RayShot
from orapa_mine.model.gems import Direction, Piece, PlacedGem, Position
from orapa_mine.model.grid import Grid
from orapa_mine.ui import board_render, theme
from orapa_mine.ui.board_render import darken as _darken
from orapa_mine.ui.board_render import lighten as _lighten
from orapa_mine.ui.board_render import piece_color as _piece_color

_RAY_SPEED = 620.0  # pixels par seconde pour l'animation du rayon


@dataclass
class EntryPoint:
    """Un point d'entrée cliquable sur la bordure du plateau."""

    entry: Position
    direction: Direction
    center: tuple[int, int]
    label: str


@dataclass
class Slot:
    """Une case de la palette : une pièce jouable et son rectangle écran."""

    piece: Piece
    rect: pygame.Rect


class GameScreen:
    """Gère l'affichage et les interactions de l'écran de jeu."""

    def __init__(self, game: GameState, palette_pieces: list[Piece]) -> None:
        self.game = game
        self.grid = game.hidden_grid  # cachée (debug uniquement)
        self.hypothesis = Grid(width=self.grid.width, height=self.grid.height)
        self.reveal = False

        # Sélection / pose de pièces.
        self.selected: Piece | None = None
        self.orientation_index = 0
        self.used_names: set[str] = set()
        self.hovered_entry: int | None = None
        self.hovered_cell: Position | None = None

        # Animation du rayon de test.
        self._ray_points: list[tuple[float, float]] = []
        self._ray_seg_colors: list[tuple[int, int, int]] = []
        self._ray_absorbed = False
        self._ray_total_len = 0.0
        self._ray_progress = 0.0
        self.last_test: str | None = None

        # Zone de proposition (texte) et résultat de soumission.
        self.input_text = ""
        self.input_active = False
        self.message: str | None = None
        self.message_color = theme.TEXT_DIM

        # Signal de fin de partie lu par l'app : ("win"|"giveup", score) ou None.
        self.finished: tuple[str, int] | None = None

        # Aide « comment jouer » (overlay).
        self.show_help = False

        pygame.font.init()
        self.font = pygame.font.SysFont("arial", 18)
        self.font_small = pygame.font.SysFont("arial", 15)
        self.font_big = pygame.font.SysFont("arial", 26, bold=True)

        self.entries = self._build_entries()
        self.entry_by_label = {ep.label: ep for ep in self.entries}
        self.slots = self._build_palette(palette_pieces)
        self._layout_panel()

    # --- Construction ------------------------------------------------------

    def _build_entries(self) -> list[EntryPoint]:
        entries: list[EntryPoint] = []
        w, h = self.grid.width, self.grid.height
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

    def _build_palette(self, pieces: list[Piece]) -> list[Slot]:
        slots: list[Slot] = []
        y = theme.palette_top(self.grid.height)
        slot_w, slot_h, gap = 82, theme.PALETTE_HEIGHT - 8, 10
        x = theme.BOARD_X
        for piece in pieces:
            slots.append(Slot(piece, pygame.Rect(x, y, slot_w, slot_h)))
            x += slot_w + gap
        return slots

    def _layout_panel(self) -> None:
        px = theme.BOARD_X + self.grid.width * theme.CELL + theme.PANEL_MARGIN
        self.panel_x = px
        self.panel = pygame.Rect(
            px, theme.BOARD_Y, theme.PANEL_WIDTH, self.grid.height * theme.CELL
        )
        inner = px + 18
        self.help_rect = pygame.Rect(px + theme.PANEL_WIDTH - 44, theme.BOARD_Y + 16, 28, 28)
        self.submit_rect = pygame.Rect(inner, theme.BOARD_Y + 92, 180, 34)
        self.abandon_rect = pygame.Rect(inner + 190, theme.BOARD_Y + 92, 92, 34)
        bottom = theme.BOARD_Y + self.grid.height * theme.CELL
        self.input_rect = pygame.Rect(inner, bottom - 92, theme.PANEL_WIDTH - 36, 32)

    # --- Événements --------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self.hovered_entry = self._entry_at(event.pos)
            self.hovered_cell = self._cell_at(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._on_click(event)
        elif event.type == pygame.KEYDOWN:
            self._on_key(event)

    def _on_click(self, event: pygame.event.Event) -> None:
        pos = event.pos
        if self.show_help:  # tout clic ferme l'aide
            if event.button == 1:
                self.show_help = False
            return
        if event.button == 3:  # clic droit : retirer une hypothèse
            self._remove_at(self._cell_at(pos))
            return
        if event.button != 1:
            return
        if self.help_rect.collidepoint(pos):
            self.show_help = True
            return
        # Zone de saisie ?
        if self.input_rect.collidepoint(pos):
            self.input_active = True
            return
        self.input_active = False
        if self.submit_rect.collidepoint(pos):
            self._submit()
            return
        if self.abandon_rect.collidepoint(pos):
            self.finished = ("giveup", self.game.score)
            return
        entry = self._entry_at(pos)
        if entry is not None:
            self._fire_test(self.entries[entry])
            return
        slot = self._slot_at(pos)
        if slot is not None:
            self._select_slot(slot)
            return
        cell = self._cell_at(pos)
        if cell is not None:
            self._place_or_remove(cell)

    def _on_key(self, event: pygame.event.Event) -> None:
        if self.show_help:
            if event.key in (pygame.K_h, pygame.K_ESCAPE):
                self.show_help = False
            return
        if self.input_active:
            self._input_key(event)
            return
        if event.key == pygame.K_h:
            self.show_help = True
        elif event.key == pygame.K_d:
            self.reveal = not self.reveal
        elif event.key == pygame.K_r and self.selected is not None:
            count = len(self.selected.orientations())
            self.orientation_index = (self.orientation_index + 1) % count
        elif event.key == pygame.K_ESCAPE:
            self.selected = None

    def _input_key(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_RETURN:
            self._ask_true()
        elif event.key == pygame.K_BACKSPACE:
            self.input_text = self.input_text[:-1]
        elif event.key == pygame.K_ESCAPE:
            self.input_active = False
        elif event.unicode.isalnum() and len(self.input_text) < 3:
            self.input_text += event.unicode.upper()

    # --- Actions -----------------------------------------------------------

    def _select_slot(self, index: int) -> None:
        piece = self.slots[index].piece
        if piece.name in self.used_names:
            return
        self.selected = piece
        self.orientation_index = 0

    def _place_or_remove(self, cell: Position) -> None:
        if self.selected is None:
            self._remove_at(cell)
            return
        orientation = self.selected.orientations()[self.orientation_index]
        gem = PlacedGem(piece=self.selected, anchor=cell, orientation=orientation)
        if self.hypothesis.can_place(gem):
            self.hypothesis.place_gem(gem)
            self.used_names.add(self.selected.name)
            self.selected = None

    def _remove_at(self, cell: Position | None) -> None:
        if cell is None:
            return
        gem = self.hypothesis.gem_at(cell)
        if gem is not None:
            self.hypothesis.remove_gem(gem)
            self.used_names.discard(gem.piece.name)

    def _fire_test(self, ep: EntryPoint) -> None:
        result = fire_beam(self.hypothesis, ep.entry, ep.direction)
        self._ray_points = self._build_ray_points(ep, result)
        self._ray_seg_colors = self._build_seg_colors(result, len(self._ray_points))
        self._ray_absorbed = result.absorbed
        self._ray_total_len = _polyline_length(self._ray_points)
        self._ray_progress = 0.0
        self.last_test = f"Test {ep.label} → {self._result_label(result)}"

    def _ask_true(self) -> None:
        label = self.input_text.strip().upper()
        self.input_text = ""
        ep = self.entry_by_label.get(label)
        if ep is None:
            self.message = f"Point « {label} » inconnu."
            self.message_color = theme.LOSE_COLOR
            return
        self.game.play_shot(ep.entry, ep.direction)
        self.message = None

    def _submit(self) -> None:
        won = self.game.submit_guess(list(self.hypothesis.gems))
        if won:
            self.finished = ("win", self.game.score)
        else:
            self.message = "Proposition incorrecte, réessaie."
            self.message_color = theme.LOSE_COLOR

    def _result_label(self, result: BeamResult) -> str:
        if result.absorbed:
            return "absorbé"
        if result.exit_point is None or result.exit_direction is None:
            return "?"
        label = theme.exit_label(
            result.exit_point, result.exit_direction, self.grid.width, self.grid.height
        )
        return f"{label} ({result.color or 'transparent'})"

    # --- Détection de zones ------------------------------------------------

    def _entry_at(self, pos: tuple[int, int]) -> int | None:
        for index, ep in enumerate(self.entries):
            if math.dist(pos, ep.center) <= 16:
                return index
        return None

    def _slot_at(self, pos: tuple[int, int]) -> int | None:
        for index, slot in enumerate(self.slots):
            if slot.rect.collidepoint(pos):
                return index
        return None

    def _cell_at(self, pos: tuple[int, int]) -> Position | None:
        x, y = pos
        col = (x - theme.BOARD_X) // theme.CELL
        row = (y - theme.BOARD_Y) // theme.CELL
        candidate = Position(int(row), int(col))
        return candidate if self.grid.is_inside(candidate) else None

    # --- Rayon (géométrie d'animation) -------------------------------------

    def _build_ray_points(self, ep: EntryPoint, result: BeamResult) -> list[tuple[float, float]]:
        drow, dcol = ep.direction.value
        ecx, ecy = theme.cell_center(ep.entry)
        points: list[tuple[float, float]] = [
            (ecx - dcol * theme.CELL / 2, ecy - drow * theme.CELL / 2)
        ]
        points += [theme.cell_center(p) for p in result.path]
        # Tronçon de sortie : dans la **vraie direction de sortie** (le rayon a
        # pu dévier sur la dernière case), sinon il traverserait la gemme.
        if (
            not result.absorbed
            and result.exit_point is not None
            and result.exit_direction is not None
        ):
            exr, exc = result.exit_direction.value
            cx, cy = theme.cell_center(result.exit_point)
            points.append((cx + exc * theme.CELL / 2, cy + exr * theme.CELL / 2))
        return points

    def _build_seg_colors(self, result: BeamResult, n_points: int) -> list[tuple[int, int, int]]:
        """Couleur RGB de chaque segment du rayon (transparent avant la 1re gemme)."""
        steps = result.color_steps
        colors: list[tuple[int, int, int]] = []
        for j in range(max(0, n_points - 1)):
            if j == 0:
                colors.append(theme.RAY_TRANSPARENT)  # entrée -> 1re case
            else:
                idx = min(j - 1, len(steps) - 1) if steps else -1
                name = steps[idx] if idx >= 0 else None
                colors.append(theme.ray_rgb(name))
        return colors

    def update(self, dt: float) -> None:
        if self._ray_progress < self._ray_total_len:
            self._ray_progress = min(self._ray_total_len, self._ray_progress + _RAY_SPEED * dt)

    # --- Rendu -------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BACKGROUND)
        board_render.draw_board(surface, self.grid)
        board_render.draw_gems(surface, self.hypothesis)
        if self.reveal:
            self._draw_hidden_outline(surface)
        self._draw_ghost(surface)
        self._draw_ray(surface)
        self._draw_entries(surface)
        self._draw_palette(surface)
        self._draw_panel(surface)
        if self.show_help:
            self._draw_help(surface)

    def _draw_hidden_outline(self, surface: pygame.Surface) -> None:
        for gem in self.grid.gems:
            for pos, half in gem.absolute_cells().items():
                pygame.draw.polygon(surface, (250, 90, 90), theme.half_cell_polygon(pos, half), width=2)

    def _draw_ghost(self, surface: pygame.Surface) -> None:
        if self.selected is None or self.hovered_cell is None:
            return
        orientation = self.selected.orientations()[self.orientation_index]
        gem = PlacedGem(piece=self.selected, anchor=self.hovered_cell, orientation=orientation)
        ok = self.hypothesis.can_place(gem)
        color = theme.GHOST_OK if ok else theme.GHOST_BAD
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        for pos, half in gem.absolute_cells().items():
            if self.grid.is_inside(pos):
                pygame.draw.polygon(overlay, (*color, 120), theme.half_cell_polygon(pos, half))
        surface.blit(overlay, (0, 0))

    def _draw_ray(self, surface: pygame.Surface) -> None:
        pts = self._ray_points
        if len(pts) < 2:
            return
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        remaining = self._ray_progress
        head = pts[0]
        head_rgb = self._ray_seg_colors[0] if self._ray_seg_colors else theme.RAY_TRANSPARENT
        drawn = False
        for i in range(len(pts) - 1):
            if remaining <= 0:
                break
            a, b = pts[i], pts[i + 1]
            seg = math.dist(a, b)
            if seg == 0:
                continue
            rgb = self._ray_seg_colors[i]
            end = b if remaining >= seg else (
                a[0] + (b[0] - a[0]) * remaining / seg,
                a[1] + (b[1] - a[1]) * remaining / seg,
            )
            self._glow_segment(overlay, a, end, rgb)
            head, head_rgb, drawn = end, rgb, True
            remaining -= seg
        if not drawn:
            return
        r, g, b = head_rgb
        for radius, alpha in ((14, 60), (8, 120), (4, 220)):
            pygame.draw.circle(overlay, (r, g, b, alpha), (int(head[0]), int(head[1])), radius)
        surface.blit(overlay, (0, 0))
        if self._ray_absorbed and self._ray_progress >= self._ray_total_len:
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

    def _draw_entries(self, surface: pygame.Surface) -> None:
        for index, ep in enumerate(self.entries):
            hot = index == self.hovered_entry
            color = theme.ENTRY_HOVER if hot else theme.ENTRY_IDLE
            pygame.draw.circle(surface, color, ep.center, 15 if hot else 12)
            pygame.draw.circle(surface, theme.BACKGROUND, ep.center, 15 if hot else 12, width=2)
            label = self.font_small.render(ep.label, True, theme.BACKGROUND if hot else theme.TEXT_DIM)
            surface.blit(label, label.get_rect(center=ep.center))

    def _draw_palette(self, surface: pygame.Surface) -> None:
        for slot in self.slots:
            used = slot.piece.name in self.used_names
            selected = slot.piece is self.selected
            bg = theme.SLOT_USED if used else theme.SLOT_BG
            pygame.draw.rect(surface, bg, slot.rect, border_radius=6)
            border = theme.SLOT_SELECTED if selected else theme.BOARD_BORDER
            pygame.draw.rect(surface, border, slot.rect, width=2 if selected else 1, border_radius=6)
            self._draw_slot_icon(surface, slot, faded=used)

    def _draw_slot_icon(self, surface: pygame.Surface, slot: Slot, faded: bool) -> None:
        cells = slot.piece.cells
        rows = max(p.row for p, _ in cells) + 1
        cols = max(p.col for p, _ in cells) + 1
        area = slot.rect.inflate(-16, -22)
        size = min(area.width / cols, area.height / rows)
        ox = slot.rect.centerx - cols * size / 2
        oy = slot.rect.top + 8
        base = _piece_color(slot.piece)
        if faded:
            base = _darken(base, 0.5)
        for pos, half in cells:
            pygame.draw.polygon(surface, base, theme.half_cell_polygon_at(pos, half, ox, oy, size))
        name = self.font_small.render(slot.piece.color.value if slot.piece.color else slot.piece.name, True, theme.TEXT_DIM)
        surface.blit(name, name.get_rect(centerx=slot.rect.centerx, bottom=slot.rect.bottom - 4))

    def _draw_panel(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, theme.PANEL_BG, self.panel, border_radius=8)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.panel, width=1, border_radius=8)
        x = self.panel_x + 18
        surface.blit(self.font_big.render("Orapa Mine", True, theme.TEXT), (x, theme.BOARD_Y + 12))
        # Bouton d'aide « ? ».
        pygame.draw.circle(surface, theme.SLOT_BG, self.help_rect.center, 14)
        pygame.draw.circle(surface, theme.BOARD_BORDER, self.help_rect.center, 14, width=1)
        q = self.font.render("?", True, theme.TEXT)
        surface.blit(q, q.get_rect(center=self.help_rect.center))
        surface.blit(
            self.font_small.render(self.last_test or "Clique un point d'entrée pour tester.", True, theme.TEXT_DIM),
            (x, theme.BOARD_Y + 54),
        )
        # Boutons Proposer / Abandonner.
        pygame.draw.rect(surface, (54, 120, 90), self.submit_rect, border_radius=6)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.submit_rect, width=1, border_radius=6)
        btn = self.font_small.render("Proposer la solution", True, theme.TEXT)
        surface.blit(btn, btn.get_rect(center=self.submit_rect.center))
        pygame.draw.rect(surface, (96, 54, 60), self.abandon_rect, border_radius=6)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.abandon_rect, width=1, border_radius=6)
        ab = self.font_small.render("Abandonner", True, theme.TEXT)
        surface.blit(ab, ab.get_rect(center=self.abandon_rect.center))

        y = theme.BOARD_Y + 142
        surface.blit(self.font.render("Historique", True, theme.TEXT), (x, y))
        y += 26
        for shot in self.game.shots[-9:]:
            self._draw_history_row(surface, x, y, shot)
            y += 22

        # Zone de proposition (saisie d'un point d'entrée à interroger).
        label = self.font_small.render("Proposer un point (ex. 5 ou C) :", True, theme.TEXT_DIM)
        surface.blit(label, (x, self.input_rect.top - 20))
        pygame.draw.rect(surface, theme.INPUT_BG, self.input_rect, border_radius=5)
        edge = theme.INPUT_ACTIVE if self.input_active else theme.BOARD_BORDER
        pygame.draw.rect(surface, edge, self.input_rect, width=2 if self.input_active else 1, border_radius=5)
        shown = self.input_text + ("|" if self.input_active else "")
        surface.blit(self.font.render(shown, True, theme.TEXT), (self.input_rect.x + 8, self.input_rect.y + 6))

        if self.message:
            msg = self.font_small.render(self.message, True, self.message_color)
            surface.blit(msg, (x, self.input_rect.bottom + 10))

        hint = "clic=choisir, clic plateau=poser, [R] tourner, clic droit=retirer, [H] aide, [D] debug"
        surface.blit(
            self.font_small.render(hint, True, theme.TEXT_DIM),
            (theme.BOARD_X, theme.board_bottom(self.grid.height) + theme.ENTRY_MARGIN + 4),
        )

    def _draw_help(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        backdrop = pygame.Surface((w, h), pygame.SRCALPHA)
        backdrop.fill((6, 8, 14, 210))
        surface.blit(backdrop, (0, 0))

        panel_w = min(660, w - 80)
        margin = 26
        # Pré-calcule les lignes pour dimensionner le panneau.
        lines: list[tuple[str, tuple[int, int, int]]] = []
        for heading, body in _HELP:
            lines.append((heading, theme.SLOT_SELECTED))
            for wrapped in _wrap(body, self.font_small, panel_w - 2 * margin):
                lines.append((wrapped, theme.TEXT))
            lines.append(("", theme.TEXT))
        panel_h = 92 + len(lines) * 22
        px = (w - panel_w) // 2
        py = (h - panel_h) // 2
        panel = pygame.Rect(px, py, panel_w, panel_h)
        pygame.draw.rect(surface, theme.PANEL_BG, panel, border_radius=12)
        pygame.draw.rect(surface, theme.BOARD_BORDER, panel, width=2, border_radius=12)

        surface.blit(self.font_big.render("Comment jouer", True, theme.TEXT), (px + margin, py + 20))
        y = py + 66
        for text, color in lines:
            if text:
                font = self.font if color == theme.SLOT_SELECTED else self.font_small
                surface.blit(font.render(text, True, color), (px + margin, y))
            y += 22
        close = self.font_small.render("[H] ou clic pour fermer", True, theme.TEXT_DIM)
        surface.blit(close, close.get_rect(centerx=panel.centerx, bottom=panel.bottom - 12))

    def _draw_history_row(self, surface: pygame.Surface, x: int, y: int, shot: RayShot) -> None:
        entry = theme.entry_label(shot.entry, shot.direction, self.grid.width, self.grid.height)
        if shot.result.absorbed:
            text, dot = f"{entry} → absorbé", theme.RAY_ABSORBED
        else:
            text = f"{entry} → {self._result_label(shot.result)}"
            dot = theme.ray_rgb(shot.result.color)
        pygame.draw.circle(surface, dot, (x + 6, y + 8), 6)
        surface.blit(self.font_small.render(text, True, theme.TEXT), (x + 20, y))


# --- Aide « comment jouer » --------------------------------------------------

_HELP: list[tuple[str, str]] = [
    ("But", "Localise la position exacte de toutes les gemmes cachées de la mine."),
    (
        "Poser des hypothèses",
        "Choisis une pièce dans la palette, puis clique sur le plateau pour la "
        "poser. [R] tourne/retourne la pièce, le clic droit la retire.",
    ),
    (
        "Tester ton hypothèse",
        "Clique un point d'entrée sur le bord : un rayon rebondit sur TES pièces "
        "posées. Il part transparent et se teinte en touchant les gemmes.",
    ),
    (
        "Interroger la mine",
        "Saisis un point (chiffre 1–18 ou lettre A–R) dans « Proposer un point » "
        "puis Entrée : la vraie sortie et la couleur s'ajoutent à l'Historique.",
    ),
    (
        "Déduire",
        "Rejoue les mêmes points sur tes hypothèses jusqu'à retrouver les vraies "
        "sorties et couleurs listées dans l'Historique.",
    ),
    (
        "Couleurs",
        "Le rayon mélange les couleurs comme de la peinture (rouge+jaune=orange, "
        "jaune+bleu=vert, rouge+bleu=violet…) ; le blanc éclaircit la teinte.",
    ),
    (
        "Gagner",
        "Quand tu es sûr de toi, clique « Proposer la solution ». Le score est le "
        "nombre de questions posées. Raccourcis : [H] aide, [D] debug.",
    ),
]


def _wrap(text: str, font: "pygame.font.Font", max_width: int) -> list[str]:
    """Découpe `text` en lignes qui tiennent dans `max_width` pixels."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if font.size(candidate)[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# --- Helpers géométrie du rayon ---------------------------------------------


def _polyline_length(points: list[tuple[float, float]]) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))
