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

from dataclasses import dataclass

import pygame

from orapa_mine.model.beam import mix_colors
from orapa_mine.model.game import GameState, RayShot
from orapa_mine.model.gems import GemColor, Piece, PlacedGem, Position
from orapa_mine.model import serialization
from orapa_mine.model.grid import Grid
from orapa_mine.ui import board_render, dialogs, theme
from orapa_mine.ui.beam_test import RayTester
from orapa_mine.ui.board_render import piece_color as _piece_color

_HISTORY_ROW_H = 22  # hauteur d'une ligne d'historique (px)


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
        self.palette_pieces = palette_pieces
        self.hypothesis = Grid(width=self.grid.width, height=self.grid.height)
        self.reveal = False
        self.save_progress = True  # sauver aussi historique + pièces posées

        # Sélection / pose de pièces.
        self.selected: Piece | None = None
        self.orientation_index = 0
        self.used_names: set[str] = set()
        self.hovered_cell: Position | None = None

        # Zone de proposition (texte) et résultat de soumission.
        self.input_text = ""
        self.input_active = False
        self.message: str | None = None
        self.message_color = theme.TEXT_DIM

        # Signal de fin de partie lu par l'app : ("win"|"giveup", score) ou None.
        self.finished: tuple[str, int] | None = None

        # Aide « comment jouer » (overlay paginé).
        self.show_help = False
        self.help_page = 0

        # Défilement de l'historique (offset en pixels depuis le haut).
        self.history_scroll = 0.0
        self.history_stick_bottom = True

        pygame.font.init()
        self.font = pygame.font.SysFont("arial", 18)
        self.font_small = pygame.font.SysFont("arial", 15)
        self.font_big = pygame.font.SysFont("arial", 26, bold=True)

        # Mise en page adaptative (taille de case + positions selon l'écran).
        self.size = theme.window_size(self.grid.width, self.grid.height)
        self.ray = RayTester(self.grid.width, self.grid.height, self.font_small)
        self.slots = self._build_palette(palette_pieces)
        self._layout_panel()

    # --- Construction ------------------------------------------------------

    def _build_palette(self, pieces: list[Piece]) -> list[Slot]:
        rects = theme.palette_slots(len(pieces))
        return [Slot(piece, rect) for piece, rect in zip(pieces, rects)]

    def _layout_panel(self) -> None:
        self.panel = theme.PANEL.copy()
        px = self.panel.x
        self.panel_x = px
        inner = px + 18
        top = self.panel.top
        self.help_rect = pygame.Rect(px + theme.PANEL_WIDTH - 44, top + 16, 28, 28)
        self.submit_rect = pygame.Rect(inner, top + 92, 180, 34)
        self.abandon_rect = pygame.Rect(inner + 190, top + 92, 92, 34)
        # Ligne sauvegarde : case « progression » + bouton Sauvegarder.
        self.progress_toggle_rect = pygame.Rect(inner, top + 136, 20, 20)
        self.save_rect = pygame.Rect(inner + 150, top + 132, 132, 28)
        self.input_rect = pygame.Rect(inner, self.panel.bottom - 92, theme.PANEL_WIDTH - 36, 32)

        # Zone d'historique : s'étire entre l'en-tête et la zone de saisie,
        # donc s'adapte à la hauteur du panneau.
        self.history_header_y = top + 174
        content_top = self.history_header_y + 24
        content_bottom = self.input_rect.top - 28  # laisse la place au libellé
        self.history_rect = pygame.Rect(
            inner, content_top, theme.PANEL_WIDTH - 36, max(48, content_bottom - content_top)
        )

    # --- Événements --------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self.ray.hover(event.pos)
            self.hovered_cell = self._cell_at(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._on_click(event)
        elif event.type == pygame.MOUSEWHEEL:
            if not self.show_help and self.history_rect.collidepoint(pygame.mouse.get_pos()):
                self._scroll_history(event.y)
        elif event.type == pygame.KEYDOWN:
            self._on_key(event)

    def _scroll_history(self, dy: int) -> None:
        content_h = len(self.game.shots) * _HISTORY_ROW_H + 8
        max_scroll = max(0.0, content_h - self.history_rect.height)
        if max_scroll <= 0:
            return
        # Molette vers le haut (dy > 0) -> remonter dans l'historique.
        self.history_scroll = min(max_scroll, max(0.0, self.history_scroll - dy * _HISTORY_ROW_H * 2))
        self.history_stick_bottom = self.history_scroll >= max_scroll - 1

    def _on_click(self, event: pygame.event.Event) -> None:
        pos = event.pos
        if self.show_help:  # navigation dans l'aide, sinon fermeture
            if event.button == 1:
                layout = self._help_layout(pygame.display.get_surface().get_size())
                if layout["prev"].collidepoint(pos):
                    self.help_page = max(0, self.help_page - 1)
                elif layout["next"].collidepoint(pos):
                    self.help_page = min(len(layout["pages"]) - 1, self.help_page + 1)
                else:
                    self.show_help = False
            return
        if event.button == 3:  # clic droit : retirer une hypothèse
            self._remove_at(self._cell_at(pos))
            return
        if event.button != 1:
            return
        if self.help_rect.collidepoint(pos):
            self.show_help = True
            self.help_page = 0
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
        if self.progress_toggle_rect.collidepoint(pos):
            self.save_progress = not self.save_progress
            return
        if self.save_rect.collidepoint(pos):
            self._save()
            return
        entry = self.ray.entry_at(pos)
        if entry is not None:
            self.ray.fire(self.hypothesis, self.ray.entries[entry])
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
            elif event.key == pygame.K_LEFT:
                self.help_page = max(0, self.help_page - 1)
            elif event.key == pygame.K_RIGHT:
                pages = self._help_layout(pygame.display.get_surface().get_size())["pages"]
                self.help_page = min(len(pages) - 1, self.help_page + 1)
            return
        if self.input_active:
            self._input_key(event)
            return
        if event.key == pygame.K_h:
            self.show_help = True
            self.help_page = 0
        elif event.key == pygame.K_s:
            self._save()
        elif event.key == pygame.K_d and event.mod & pygame.KMOD_SHIFT:
            # Maj+D (et non D seul) : la touche D jouxte R et provoquait des
            # révélations accidentelles de la solution.
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

    def _ask_true(self) -> None:
        label = self.input_text.strip().upper()
        self.input_text = ""
        ep = self.ray.entry_by_label.get(label)
        if ep is None:
            self.message = f"Point « {label} » inconnu."
            self.message_color = theme.LOSE_COLOR
            return
        self.game.play_shot(ep.entry, ep.direction)
        self.message = None

    def _save(self) -> None:
        path = dialogs.ask_save_path()
        if not path:
            return
        data = serialization.to_dict(
            width=self.grid.width,
            height=self.grid.height,
            palette_pieces=self.palette_pieces,
            hidden_grid=self.grid,
            include_progress=self.save_progress,
            game=self.game,
            hypothesis_grid=self.hypothesis,
        )
        try:
            dialogs.write_json(path, data)
        except OSError as exc:
            self.message, self.message_color = f"Échec de la sauvegarde : {exc}", theme.LOSE_COLOR
            return
        kind = "avec progression" if self.save_progress else "configuration seule"
        self.message, self.message_color = f"Partie sauvegardée ({kind}).", theme.WIN_COLOR

    def _submit(self) -> None:
        won = self.game.submit_guess(list(self.hypothesis.gems))
        if won:
            self.finished = ("win", self.game.score)
        else:
            self.message = "Proposition incorrecte, réessaie."
            self.message_color = theme.LOSE_COLOR

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

    def update(self, dt: float) -> None:
        self.ray.update(dt)

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BACKGROUND)
        board_render.draw_board(surface, self.grid)
        board_render.draw_gems(surface, self.hypothesis)
        if self.reveal:
            self._draw_hidden_outline(surface)
        self._draw_ghost(surface)
        self.ray.draw(surface)
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
        base = board_render.faded_piece_color(slot.piece) if faded else _piece_color(slot.piece)
        for pos, half in cells:
            pygame.draw.polygon(surface, base, theme.half_cell_polygon_at(pos, half, ox, oy, size))
        name = self.font_small.render(slot.piece.color.value if slot.piece.color else slot.piece.name, True, theme.TEXT_DIM)
        surface.blit(name, name.get_rect(centerx=slot.rect.centerx, bottom=slot.rect.bottom - 4))

    def _draw_panel(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, theme.PANEL_BG, self.panel, border_radius=8)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.panel, width=1, border_radius=8)
        x = self.panel_x + 18
        surface.blit(self.font_big.render("Orapa Mine", True, theme.TEXT), (x, self.panel.top + 12))
        # Bouton d'aide « ? ».
        pygame.draw.circle(surface, theme.SLOT_BG, self.help_rect.center, 14)
        pygame.draw.circle(surface, theme.BOARD_BORDER, self.help_rect.center, 14, width=1)
        q = self.font.render("?", True, theme.TEXT)
        surface.blit(q, q.get_rect(center=self.help_rect.center))
        surface.blit(
            self.font_small.render(self.ray.last_test or "Clique un point d'entrée pour tester.", True, theme.TEXT_DIM),
            (x, self.panel.top + 54),
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

        # Ligne sauvegarde : case « progression » + bouton Sauvegarder.
        pygame.draw.rect(surface, theme.INPUT_BG, self.progress_toggle_rect, border_radius=4)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.progress_toggle_rect, width=1, border_radius=4)
        if self.save_progress:
            pygame.draw.rect(surface, theme.SLOT_SELECTED, self.progress_toggle_rect.inflate(-8, -8), border_radius=2)
        surface.blit(
            self.font_small.render("Progression", True, theme.TEXT),
            (self.progress_toggle_rect.right + 8, self.progress_toggle_rect.y + 2),
        )
        pygame.draw.rect(surface, theme.SLOT_BG, self.save_rect, border_radius=6)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.save_rect, width=1, border_radius=6)
        sv = self.font_small.render("Sauvegarder", True, theme.TEXT)
        surface.blit(sv, sv.get_rect(center=self.save_rect.center))

        surface.blit(self.font.render("Historique", True, theme.TEXT), (x, self.history_header_y))
        self._draw_history(surface)

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

        hint = "clic=choisir, clic plateau=poser, [R] tourner, clic droit=retirer, [H] aide, [Maj+D] debug"
        surface.blit(
            self.font_small.render(hint, True, theme.TEXT_DIM),
            (theme.PALETTE.x, self.size[1] - 24),
        )

    # --- Aide paginée ------------------------------------------------------

    _TITLE_H = 52
    _FOOTER_H = 42
    _MARGIN = 26

    def _help_rows(self, content_width: int) -> list[tuple[int, "object"]]:
        """Construit la liste des lignes de l'aide (hauteur, fonction de dessin)."""
        rows: list[tuple[int, object]] = []

        def heading_draw(text: str):
            return lambda s, x, y, t=text: s.blit(self.font.render(t, True, theme.SLOT_SELECTED), (x, y))

        def line_draw(text: str):
            return lambda s, x, y, t=text: s.blit(self.font_small.render(t, True, theme.TEXT), (x, y))

        for head, body in _HELP:
            if head == "Couleurs":
                # La légende des couleurs forme un bloc insécable : une seule
                # « ligne » composite qui ne se coupe jamais entre deux pages
                # (mais partage une page avec ce qui précède si ça tient).
                block: list[tuple[int, object]] = [
                    (28, heading_draw(head)),
                    (22, line_draw("Le rayon se teinte au contact ; mélange peinture, le blanc éclaircit.")),
                    (22, line_draw("Aucune gemme touchée → rayon transparent.")),
                ]
                col_w = content_width // 2  # deux colonnes de combinaisons
                for i in range(0, len(_COLOR_COMBOS), 2):
                    left = _COLOR_COMBOS[i]
                    right = _COLOR_COMBOS[i + 1] if i + 1 < len(_COLOR_COMBOS) else None
                    block.append((26, self._combo_pair_drawer(left, right, col_w)))
                rows.append((sum(h for h, _ in block), _group_drawer(block)))
            else:
                rows.append((28, heading_draw(head)))
                for wrapped in _wrap(body, self.font_small, content_width):
                    rows.append((22, line_draw(wrapped)))
            rows.append((12, _spacer))  # espace entre sections
        return rows

    def _combo_pair_drawer(self, left: frozenset, right: frozenset | None, col_w: int):
        """Dessine deux combinaisons de couleurs côte à côte (deux colonnes)."""
        draw_left = self._combo_drawer(left)
        draw_right = self._combo_drawer(right) if right is not None else None

        def draw(surface: pygame.Surface, x: int, y: int) -> None:
            draw_left(surface, x, y)
            if draw_right is not None:
                draw_right(surface, x + col_w, y)

        return draw

    def _combo_drawer(self, combo: frozenset):
        """Retourne une fonction dessinant une ligne « couleurs = résultat »."""

        def draw(surface: pygame.Surface, x: int, y: int) -> None:
            cx = x
            inputs = [c for c in _COLOR_ORDER if c in combo]
            for i, gem_color in enumerate(inputs):
                if i > 0:
                    surface.blit(self.font_small.render("+", True, theme.TEXT_DIM), (cx, y + 1))
                    cx += 13
                _swatch(surface, cx, y, theme.GEM_FILL[gem_color])
                cx += 20
            surface.blit(self.font_small.render("=", True, theme.TEXT_DIM), (cx, y + 1))
            cx += 18
            name = mix_colors(combo) or "transparent"
            _swatch(surface, cx, y, theme.ray_rgb(mix_colors(combo)))
            cx += 24
            surface.blit(self.font_small.render(name, True, theme.TEXT), (cx, y + 1))

        return draw

    def _help_layout(self, size: tuple[int, int]) -> dict:
        w, h = size
        panel_w = min(680, w - 80)
        max_panel_h = h - 60
        content_w = panel_w - 2 * self._MARGIN
        max_content_h = max_panel_h - self._TITLE_H - self._FOOTER_H

        rows = self._help_rows(content_w)
        pages = _paginate(rows, max_content_h)
        content_h = max((sum(rh for rh, _ in pg) for pg in pages), default=0)
        panel_h = self._TITLE_H + content_h + self._FOOTER_H
        px = (w - panel_w) // 2
        py = (h - panel_h) // 2
        panel = pygame.Rect(px, py, panel_w, panel_h)
        prev_rect = pygame.Rect(px + self._MARGIN, panel.bottom - 36, 40, 28)
        next_rect = pygame.Rect(panel.right - self._MARGIN - 40, panel.bottom - 36, 40, 28)
        return {"panel": panel, "pages": pages, "prev": prev_rect, "next": next_rect}

    def _draw_help(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        backdrop = pygame.Surface((w, h), pygame.SRCALPHA)
        backdrop.fill((6, 8, 14, 214))
        surface.blit(backdrop, (0, 0))

        layout = self._help_layout((w, h))
        panel, pages = layout["panel"], layout["pages"]
        self.help_page = max(0, min(self.help_page, len(pages) - 1))
        pygame.draw.rect(surface, theme.PANEL_BG, panel, border_radius=12)
        pygame.draw.rect(surface, theme.BOARD_BORDER, panel, width=2, border_radius=12)

        surface.blit(self.font_big.render("Comment jouer", True, theme.TEXT), (panel.x + self._MARGIN, panel.y + 16))

        y = panel.y + self._TITLE_H
        x = panel.x + self._MARGIN
        for row_h, draw in pages[self.help_page]:
            draw(surface, x, y)
            y += row_h

        # Pied de page : navigation.
        prev_rect, next_rect = layout["prev"], layout["next"]
        multi = len(pages) > 1
        self._nav_button(surface, prev_rect, "<", enabled=self.help_page > 0 and multi)
        self._nav_button(surface, next_rect, ">", enabled=self.help_page < len(pages) - 1)
        footer = f"Page {self.help_page + 1}/{len(pages)}   ·   ←/→ pages   ·   [H] fermer"
        label = self.font_small.render(footer, True, theme.TEXT_DIM)
        surface.blit(label, label.get_rect(centerx=panel.centerx, centery=prev_rect.centery))

    def _nav_button(self, surface: pygame.Surface, rect: pygame.Rect, glyph: str, enabled: bool) -> None:
        bg = theme.SLOT_BG if enabled else theme.PANEL_BG
        pygame.draw.rect(surface, bg, rect, border_radius=6)
        pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1, border_radius=6)
        color = theme.TEXT if enabled else theme.TEXT_DIM
        g = self.font.render(glyph, True, color)
        surface.blit(g, g.get_rect(center=rect.center))

    def _draw_history(self, surface: pygame.Surface) -> None:
        rect = self.history_rect
        pygame.draw.rect(surface, theme.INPUT_BG, rect, border_radius=6)
        pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1, border_radius=6)

        shots = self.game.shots
        if not shots:
            empty = self.font_small.render("Aucune question posée.", True, theme.TEXT_DIM)
            surface.blit(empty, (rect.x + 12, rect.y + 10))
            return

        content_h = len(shots) * _HISTORY_ROW_H + 8
        max_scroll = max(0.0, content_h - rect.height)
        if self.history_stick_bottom:
            self.history_scroll = max_scroll
        else:
            self.history_scroll = min(self.history_scroll, max_scroll)

        previous_clip = surface.get_clip()
        surface.set_clip(rect.inflate(-3, -3))
        y0 = rect.y + 6 - self.history_scroll
        for i, shot in enumerate(shots):
            ry = y0 + i * _HISTORY_ROW_H
            if ry + _HISTORY_ROW_H >= rect.y and ry <= rect.bottom:
                self._draw_history_row(surface, rect.x + 8, int(ry), shot)
        surface.set_clip(previous_clip)

        # Barre de défilement (si le contenu déborde).
        if max_scroll > 0:
            thumb_h = max(24.0, rect.height * rect.height / content_h)
            thumb_y = rect.y + (self.history_scroll / max_scroll) * (rect.height - thumb_h)
            thumb = pygame.Rect(rect.right - 7, int(thumb_y), 4, int(thumb_h))
            pygame.draw.rect(surface, theme.BOARD_BORDER, thumb, border_radius=2)

    def _draw_history_row(self, surface: pygame.Surface, x: int, y: int, shot: RayShot) -> None:
        entry = theme.entry_label(shot.entry, shot.direction, self.grid.width, self.grid.height)
        if shot.result.absorbed:
            text, dot = f"{entry} → absorbé", theme.RAY_ABSORBED
        else:
            text = f"{entry} → {self.ray.result_label(shot.result)}"
            dot = theme.ray_rgb(shot.result.color)
        pygame.draw.circle(surface, dot, (x + 6, y + 8), 6)
        surface.blit(self.font_small.render(text, True, theme.TEXT), (x + 20, y))


# --- Aide « comment jouer » --------------------------------------------------

# Ordre d'affichage des couleurs sources et liste de toutes les combinaisons.
_COLOR_ORDER = (GemColor.RED, GemColor.YELLOW, GemColor.BLUE, GemColor.WHITE)
_R, _J, _B, _W = _COLOR_ORDER
_COLOR_COMBOS: list[frozenset] = [
    frozenset({_R}), frozenset({_J}), frozenset({_B}), frozenset({_W}),
    frozenset({_R, _J}), frozenset({_R, _B}), frozenset({_J, _B}),
    frozenset({_R, _W}), frozenset({_J, _W}), frozenset({_B, _W}),
    frozenset({_R, _J, _B}), frozenset({_R, _J, _W}),
    frozenset({_R, _B, _W}), frozenset({_J, _B, _W}),
    frozenset({_R, _J, _B, _W}),
]

_HELP: list[tuple[str, str]] = [
    ("But", "Localise la position exacte de toutes les gemmes cachées de la mine."),
    (
        "Poser des hypothèses",
        "Choisis une pièce dans la palette, puis clique sur le plateau pour la "
        "poser.",
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
        "Gagner",
        "Quand tu es sûr de toi, clique « Proposer la solution ». Le score est le "
        "nombre de questions posées.",
    ),
    (
        "Sauvegarder / charger",
        "« Sauvegarder » enregistre la partie ; coche « Progression » pour y "
        "inclure l'historique et tes pièces posées. Recharge-la depuis le menu "
        "de départ (« Charger une partie… »).",
    ),
    (
        "Couleurs",
        "Le rayon mélange les couleurs comme de la peinture (rouge+jaune=orange, "
        "jaune+bleu=vert, rouge+bleu=violet…) ; le blanc éclaircit la teinte.",
    ),
    (
        "Raccourcis",
        "[H] aide, [S] sauvegarder, [Maj+D] debug. [R] tourne/retourne la pièce, le clic droit la retire."
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


def _swatch(surface: pygame.Surface, x: int, y: int, rgb: tuple[int, int, int], size: int = 16) -> None:
    """Dessine un petit carré de couleur (avec liseré) pour la légende des couleurs."""
    rect = pygame.Rect(x, y, size, size)
    pygame.draw.rect(surface, rgb, rect, border_radius=3)
    pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1, border_radius=3)


def _spacer(surface: "pygame.Surface", x: int, y: int) -> None:
    """Ligne vide : sert uniquement d'espacement vertical entre sections."""


def _group_drawer(block: list[tuple[int, object]]):
    """Dessine un bloc insécable de lignes empilées à partir de (x, y)."""

    def draw(surface: "pygame.Surface", x: int, y: int) -> None:
        yy = y
        for height, sub_draw in block:
            sub_draw(surface, x, yy)
            yy += height

    return draw


def _paginate(rows: list, max_height: int) -> list[list]:
    """Répartit les lignes (hauteur, dessin) en pages qui tiennent dans `max_height`.

    Les lignes d'espacement (`_spacer`) ne commencent jamais une page et ne sont
    pas reportées sur la page suivante — ce qui évite de créer une page quasi
    vide. Un bloc trop grand pour une page entière est placé tel quel (il peut
    déborder plutôt que disparaître).
    """
    pages: list[list] = []
    current: list = []
    used = 0
    for row_h, draw in rows:
        is_spacer = draw is _spacer
        if is_spacer and not current:
            continue  # ne pas commencer une page par un espace
        if current and used + row_h > max_height:
            if is_spacer:
                continue  # espace de fin de page : on le laisse tomber
            pages.append(current)
            current, used = [], 0
        current.append((row_h, draw))
        used += row_h
    if current:
        pages.append(current)
    return pages or [[]]
