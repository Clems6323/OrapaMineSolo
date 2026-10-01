"""Écran « mode créateur » : composer et sauvegarder une configuration.

L'utilisateur pose librement les gemmes de la palette sur le plateau pour
dessiner sa propre énigme, puis :

- **Sauvegarde** la configuration (format de partie, sans progression) — le
  fichier peut être partagé puis chargé depuis le menu de départ ;
- **Joue** sa configuration (démarre une vraie partie dessus).

Aucune règle de jeu ici : la validation du placement est déléguée à
`ai/generator.configuration_problems`, le rendu à `ui/board_render` et `theme`.
"""

from __future__ import annotations

import pygame

from orapa_mine.ai.generator import configuration_problems
from orapa_mine.model.gems import Piece, PlacedGem, Position
from orapa_mine.model import gems_catalog as cat
from orapa_mine.model import serialization
from orapa_mine.model.grid import Grid
from orapa_mine.ui import board_render, dialogs, theme
from orapa_mine.ui.beam_test import RayTester
from orapa_mine.ui.board_render import darken as _darken
from orapa_mine.ui.board_render import piece_color as _piece_color
from orapa_mine.ui.game_screen import Slot

_BASE_PIECES = [cat.RED, cat.YELLOW, cat.BLUE, cat.WHITE_BIG, cat.WHITE_SMALL]
# Panneau un peu plus large qu'en jeu : les boutons de taille de grille
# (« Standard 10×8 ») y tiennent confortablement.
_PANEL_WIDTH = theme.PANEL_WIDTH + 44


class CreatorScreen:
    """Composition d'une grille cachée personnalisée (pose de gemmes).

    La taille de grille et les extensions se règlent directement ici : changer
    l'un ou l'autre reconstruit le plateau et la palette (et redimensionne la
    fenêtre via `pending_resize`, lu par l'app).
    """

    _SIZES = [("Petit", 8, 6), ("Standard", 10, 8), ("Grand", 12, 10)]

    def __init__(self, size_index: int = 1, diamant: bool = False, corps_noir: bool = False) -> None:
        self.size_index = size_index
        self.diamant = diamant
        self.corps_noir = corps_noir

        # Sélection / pose de pièces (même interaction que l'écran de jeu).
        self.selected: Piece | None = None
        self.orientation_index = 0
        self.used_names: set[str] = set()
        self.hovered_cell: Position | None = None

        self.message: str | None = None
        self.message_color = theme.TEXT_DIM

        # Transitions lues par l'app.
        self.play: Grid | None = None  # « Jouer » : grille à utiliser
        self.back = False  # « Retour au menu »
        self.pending_resize = False  # demande de redimensionnement de la fenêtre

        pygame.font.init()
        self.font = pygame.font.SysFont("arial", 18)
        self.font_small = pygame.font.SysFont("arial", 15)
        self.font_big = pygame.font.SysFont("arial", 26, bold=True)

        self.grid = Grid(width=10, height=8)  # remplacé par _rebuild
        self._rebuild(clear_gems=True)
        self.pending_resize = False  # la taille initiale est posée par l'app

    # --- Construction ------------------------------------------------------

    def _palette_pieces(self) -> list[Piece]:
        pieces = list(_BASE_PIECES)
        if self.diamant:
            pieces.append(cat.DIAMOND)
        if self.corps_noir:
            pieces.append(cat.BLACK_BODY)
        return pieces

    def _rebuild(self, clear_gems: bool) -> None:
        """Reconstruit plateau, palette et mise en page après un changement.

        `clear_gems=True` repart d'un plateau vide (changement de taille) ; sinon
        on conserve les gemmes compatibles (toujours dans la grille et dont la
        pièce reste dans la palette — utile lors d'un (dé)cochage d'extension).
        """
        _, width, height = self._SIZES[self.size_index]
        kept = [] if clear_gems else list(self.grid.gems)
        self.palette_pieces = self._palette_pieces()
        palette_names = {p.name for p in self.palette_pieces}

        self.grid = Grid(width=width, height=height)
        for gem in kept:
            if gem.piece.name in palette_names and self.grid.can_place(gem):
                self.grid.place_gem(gem)

        self.used_names = {gem.piece.name for gem in self.grid.gems}
        self.selected = None
        self.size = theme.window_size(width, height, panel_width=_PANEL_WIDTH)
        self.ray = RayTester(width, height, self.font_small)
        self.slots = self._build_palette(self.palette_pieces)
        self._layout_panel()
        self.pending_resize = True

    # --- Construction ------------------------------------------------------

    def _build_palette(self, pieces: list[Piece]) -> list[Slot]:
        rects = theme.palette_slots(len(pieces))
        return [Slot(piece, rect) for piece, rect in zip(pieces, rects)]

    def _layout_panel(self) -> None:
        self.panel = theme.PANEL.copy()
        px = self.panel.x
        self.panel_x = px
        inner = px + 18
        bw = self.panel.width - 36
        top = self.panel.top

        # Réglages (haut du panneau) : taille de grille + extensions.
        self.size_label_y = top + 46
        sgap = 8
        sbw = (bw - 2 * sgap) // 3
        self.size_rects = [
            pygame.Rect(inner + i * (sbw + sgap), top + 66, sbw, 32) for i in range(3)
        ]
        self.ext_label_y = top + 104
        self.diamant_rect = pygame.Rect(inner, top + 126, 20, 20)
        self.corps_rect = pygame.Rect(inner, top + 150, 20, 20)
        self.status_y = top + 178

        # Actions (bas du panneau).
        self.save_rect = pygame.Rect(inner, self.panel.bottom - 152, bw, 40)
        self.play_rect = pygame.Rect(inner, self.panel.bottom - 106, bw, 40)
        self.back_rect = pygame.Rect(inner, self.panel.bottom - 54, bw, 40)

    # --- Événements --------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self.hovered_cell = self._cell_at(event.pos)
            self.ray.hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._on_click(event)
        elif event.type == pygame.KEYDOWN:
            self._on_key(event)

    def _on_click(self, event: pygame.event.Event) -> None:
        pos = event.pos
        if event.button == 3:  # clic droit : retirer une gemme
            self._remove_at(self._cell_at(pos))
            return
        if event.button != 1:
            return
        if self.save_rect.collidepoint(pos):
            self._save()
            return
        if self.play_rect.collidepoint(pos):
            self._start_play()
            return
        if self.back_rect.collidepoint(pos):
            self.back = True
            return
        if self.diamant_rect.collidepoint(pos):
            self.diamant = not self.diamant
            self._rebuild(clear_gems=False)
            return
        if self.corps_rect.collidepoint(pos):
            self.corps_noir = not self.corps_noir
            self._rebuild(clear_gems=False)
            return
        for i, rect in enumerate(self.size_rects):
            if rect.collidepoint(pos):
                if i != self.size_index:
                    self.size_index = i
                    self._rebuild(clear_gems=True)
                    self.message = None
                return
        entry = self.ray.entry_at(pos)
        if entry is not None:  # tester un rayon sur la configuration en cours
            self.ray.fire(self.grid, self.ray.entries[entry])
            return
        slot = self._slot_at(pos)
        if slot is not None:
            self._select_slot(slot)
            return
        cell = self._cell_at(pos)
        if cell is not None:
            self._place_or_remove(cell)

    def _on_key(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_r and self.selected is not None:
            count = len(self.selected.orientations())
            self.orientation_index = (self.orientation_index + 1) % count
        elif event.key == pygame.K_ESCAPE:
            self.selected = None

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
        if self.grid.can_place(gem):
            self.grid.place_gem(gem)
            self.used_names.add(self.selected.name)
            self.selected = None
            self.message = None

    def _remove_at(self, cell: Position | None) -> None:
        if cell is None:
            return
        gem = self.grid.gem_at(cell)
        if gem is not None:
            self.grid.remove_gem(gem)
            self.used_names.discard(gem.piece.name)
            self.message = None

    def _missing_pieces(self) -> list[Piece]:
        """Pièces de la palette pas encore posées sur le plateau."""
        placed = {gem.piece.name for gem in self.grid.gems}
        return [piece for piece in self.palette_pieces if piece.name not in placed]

    def _blocking_problem(self) -> str | None:
        """Raison empêchant de jouer/partager, ou None si tout va bien."""
        missing = self._missing_pieces()
        if missing:
            names = ", ".join(piece.name for piece in missing)
            return f"Place toutes les gemmes (manque : {names})."
        problems = configuration_problems(self.grid)
        if problems:
            return problems[0]
        return None

    def _save(self) -> None:
        problem = self._blocking_problem()
        if problem:
            self.message, self.message_color = problem, theme.LOSE_COLOR
            return
        path = dialogs.ask_save_path()
        if not path:
            return
        data = serialization.to_dict(
            width=self.grid.width,
            height=self.grid.height,
            palette_pieces=self.palette_pieces,
            hidden_grid=self.grid,
            include_progress=False,
            game=None,
            hypothesis_grid=None,
        )
        try:
            dialogs.write_json(path, data)
        except OSError as exc:
            self.message, self.message_color = f"Échec de la sauvegarde : {exc}", theme.LOSE_COLOR
            return
        self.message, self.message_color = "Configuration enregistrée.", theme.WIN_COLOR

    def _start_play(self) -> None:
        problem = self._blocking_problem()
        if problem:
            self.message, self.message_color = problem, theme.LOSE_COLOR
            return
        self.play = self.grid

    def update(self, dt: float) -> None:
        self.ray.update(dt)

    # --- Détection de zones ------------------------------------------------

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

    # --- Rendu -------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BACKGROUND)
        # caption = self.font.render("Compose ta configuration cachée :", True, theme.TEXT_DIM)
        # surface.blit(caption, (theme.BOARD_X, theme.BOARD_Y - 34))
        board_render.draw_board(surface, self.grid)
        board_render.draw_gems(surface, self.grid)
        self._draw_ghost(surface)
        self.ray.draw(surface)
        self._draw_palette(surface)
        self._draw_panel(surface)
        hint = "clic=choisir, clic plateau=poser, [R] tourner, clic droit=retirer, point d'entrée=tester le rayon, [Échap] désélectionner"
        surface.blit(
            self.font_small.render(hint, True, theme.TEXT_DIM),
            (theme.PALETTE.x, self.size[1] - 24),
        )

    def _draw_ghost(self, surface: pygame.Surface) -> None:
        if self.selected is None or self.hovered_cell is None:
            return
        orientation = self.selected.orientations()[self.orientation_index]
        gem = PlacedGem(piece=self.selected, anchor=self.hovered_cell, orientation=orientation)
        ok = self.grid.can_place(gem)
        color = theme.GHOST_OK if ok else theme.GHOST_BAD
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        for pos, half in gem.absolute_cells().items():
            if self.grid.is_inside(pos):
                pygame.draw.polygon(overlay, (*color, 120), theme.half_cell_polygon(pos, half))
        surface.blit(overlay, (0, 0))

    def _draw_palette(self, surface: pygame.Surface) -> None:
        title = self.font_small.render("Pièces", True, theme.TEXT_DIM)
        surface.blit(title, (theme.PALETTE.x + 4, theme.PALETTE.y - 22))
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
        name = slot.piece.color.value if slot.piece.color else slot.piece.name
        label = self.font_small.render(name, True, theme.TEXT_DIM)
        surface.blit(label, label.get_rect(centerx=slot.rect.centerx, bottom=slot.rect.bottom - 4))

    def _draw_panel(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, theme.PANEL_BG, self.panel, border_radius=8)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.panel, width=1, border_radius=8)
        x = self.panel_x + 18
        surface.blit(self.font_big.render("Mode créateur", True, theme.TEXT), (x, self.panel.top + 14))

        # Réglages : taille de grille.
        surface.blit(self.font_small.render("Taille de la grille", True, theme.TEXT), (x, self.size_label_y))
        for i, rect in enumerate(self.size_rects):
            selected = i == self.size_index
            bg = theme.SLOT_SELECTED if selected else theme.SLOT_BG
            pygame.draw.rect(surface, bg, rect, border_radius=6)
            pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1, border_radius=6)
            name, w, h = self._SIZES[i]
            fg = theme.BACKGROUND if selected else theme.TEXT
            label = self.font_small.render(f"{name} {w}×{h}", True, fg)
            surface.blit(label, label.get_rect(center=rect.center))

        # Réglages : extensions.
        surface.blit(self.font_small.render("Extensions", True, theme.TEXT), (x, self.ext_label_y))
        self._checkbox(surface, self.diamant_rect, self.diamant, "Diamant")
        self._checkbox(surface, self.corps_rect, self.corps_noir, "Corps noir")

        # État de validité en direct.
        placed = len(self.grid.gems)
        problem = self._blocking_problem()
        if problem is None:
            status, color = f"Configuration valide ({placed} gemme(s)).", theme.WIN_COLOR
        else:
            status, color = f"Attention : {problem}", theme.LOSE_COLOR
        for i, text in enumerate(_wrap(status, self.font_small, self.panel.width - 40)):
            surface.blit(self.font_small.render(text, True, color), (x, self.status_y + i * 18))

        # Résultat du dernier rayon de test (clic sur un point d'entrée).
        ray_line = self.ray.last_test or "Clique un point d'entrée pour tester le rayon."
        for i, text in enumerate(_wrap(ray_line, self.font_small, self.panel.width - 40)):
            surface.blit(self.font_small.render(text, True, theme.TEXT_DIM), (x, self.status_y + 66 + i * 18))

        self._button(surface, self.save_rect, (54, 96, 120), "Sauvegarder la configuration")
        can_play = problem is None
        self._button(
            surface,
            self.play_rect,
            (54, 120, 90) if can_play else theme.SLOT_USED,
            "Jouer cette configuration",
            dim=not can_play,
        )
        self._button(surface, self.back_rect, theme.SLOT_BG, "Retour au menu")

        if self.message:
            for i, text in enumerate(_wrap(self.message, self.font_small, self.panel.width - 40)):
                surface.blit(self.font_small.render(text, True, self.message_color), (x, self.save_rect.top - 46 + i * 18))

    def _button(self, surface: pygame.Surface, rect: pygame.Rect, bg, text: str, dim: bool = False) -> None:
        pygame.draw.rect(surface, bg, rect, border_radius=8)
        pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1, border_radius=8)
        color = theme.TEXT_DIM if dim else theme.TEXT
        label = self.font_small.render(text, True, color)
        surface.blit(label, label.get_rect(center=rect.center))

    def _checkbox(self, surface: pygame.Surface, rect: pygame.Rect, on: bool, text: str) -> None:
        pygame.draw.rect(surface, theme.INPUT_BG, rect, border_radius=4)
        pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1, border_radius=4)
        if on:
            pygame.draw.rect(surface, theme.SLOT_SELECTED, rect.inflate(-8, -8), border_radius=2)
        label = self.font_small.render(text, True, theme.TEXT)
        surface.blit(label, (rect.right + 10, rect.y + 2))


def _wrap(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Découpe `text` en lignes tenant dans `max_width` pixels."""
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
