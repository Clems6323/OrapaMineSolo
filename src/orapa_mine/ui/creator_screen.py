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

from orapa_mine.ai.generator import (
    DISALLOWED_EXTENSIONS_BY_SIZE,
    MAX_EXTENSIONS_BY_SIZE,
    configuration_problems,
    placement_is_legal,
)
from orapa_mine.model.gems import GemColor, GemKind, Piece, Position
from orapa_mine.model import gems_catalog as cat
from orapa_mine.model import serialization
from orapa_mine.model.grid import Grid
from orapa_mine.ui import board_render, dialogs, i18n, lang_toggle, theme, theme_toggle
from orapa_mine.ui.beam_test import RayTester
from orapa_mine.ui.game_screen import Slot
from orapa_mine.ui.timer_field import TimerField

_BASE_PIECES = [cat.RED, cat.YELLOW, cat.BLUE, cat.WHITE_BIG, cat.WHITE_SMALL]
# Panneau un peu plus large qu'en jeu : les boutons de taille de grille
# (« Standard 10×8 ») y tiennent confortablement.
_PANEL_WIDTH = theme.PANEL_WIDTH + theme.s(44)


class CreatorScreen:
    """Composition d'une grille cachée personnalisée (pose de gemmes).

    La taille de grille et les extensions se règlent directement ici : changer
    l'un ou l'autre reconstruit le plateau et la palette (et redimensionne la
    fenêtre via `pending_resize`, lu par l'app).
    """

    _SIZES = [("Petit", 8, 6), ("Standard", 10, 8), ("Grand", 12, 10)]
    # Extensions dans l'ordre d'affichage (compte + rognage au plafond — #75).
    _EXT_ATTRS = ("diamant", "corps_noir", "wormhole", "filter", "mystery")
    # Ordre de défilement de la couleur de la gemme mystère (touche [C]).
    _MYSTERY_CYCLE = (GemColor.BLUE, GemColor.RED, GemColor.YELLOW, GemColor.WHITE)

    def __init__(
        self,
        size_index: int = 1,
        diamant: bool = False,
        corps_noir: bool = False,
        wormhole: bool = False,
        filter: bool = False,
        mystery: bool = False,
        timer_minutes: int = 0,
    ) -> None:
        self.size_index = size_index
        self.diamant = diamant
        self.corps_noir = corps_noir
        self.wormhole = wormhole
        self.filter = filter
        self.mystery = mystery
        # Couleur choisie de la gemme mystère (touche [C]).
        self.mystery_color = GemColor.BLUE
        self.timer = TimerField(timer_minutes)  # minuteur optionnel (0 = désactivé)

        # Sélection / pose de pièces (même interaction que l'écran de jeu).
        self.selected: Piece | None = None
        self.orientation_index = 0
        self.placed_counts: dict[str, int] = {}
        self.hovered_cell: Position | None = None

        self.message: str | None = None
        self.message_color = theme.TEXT_DIM

        # Transitions lues par l'app.
        self.play: Grid | None = None  # « Jouer » : grille à utiliser
        self.back = False  # « Retour au menu »
        self.pending_resize = False  # demande de redimensionnement de la fenêtre

        self.font = theme.font(18)
        self.font_small = theme.font(15)
        self.font_big = theme.font(26, bold=True)

        self._enforce_ext_rules()  # borne les extensions reçues aux règles de la taille (#75)
        self.grid = Grid(width=10, height=8)  # remplacé par _rebuild
        self._rebuild(clear_gems=True)
        self.pending_resize = False  # la taille initiale est posée par l'app

    @property
    def timer_minutes(self) -> int:
        """Minutes du minuteur (lu par l'app pour lancer/sauvegarder la partie)."""
        return self.timer.minutes

    # --- Construction ------------------------------------------------------

    def _palette_pieces(self) -> list[Piece]:
        pieces = list(_BASE_PIECES)
        if self.diamant:
            pieces.append(cat.DIAMOND)
        if self.filter:
            pieces.append(cat.FILTER)
        if self.corps_noir:
            pieces.append(cat.BLACK_BODY)
        if self.wormhole:
            pieces.append(cat.WORMHOLE)
        if self.mystery:
            pieces.append(cat.MYSTERY)
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

        self.placed_counts = {}
        for gem in self.grid.gems:
            self.placed_counts[gem.piece.name] = self.placed_counts.get(gem.piece.name, 0) + 1
        self.selected = None
        old_size = getattr(self, "size", None)
        # Palette sur deux colonnes (classiques | extensions) dès qu'une extension
        # est présente → fenêtre plus large, icônes plus grandes.
        palette_cols = 2 if any(p.kind is not GemKind.NORMAL for p in self.palette_pieces) else 1
        self.size = theme.window_size(width, height, panel_width=_PANEL_WIDTH, palette_cols=palette_cols)
        self.ray = RayTester(width, height, self.font_small)
        self.slots = self._build_palette(self.palette_pieces)
        self._layout_panel()
        # Ne redemander une recréation de fenêtre (set_mode) que si la taille change
        # vraiment : (dé)cocher une extension garde la même fenêtre — sans ça, le
        # set_mode inutile provoquait un bref flash noir (#38).
        self.pending_resize = self.size != old_size

    # --- Construction ------------------------------------------------------

    def _build_palette(self, pieces: list[Piece]) -> list[Slot]:
        base = [p for p in pieces if p.kind is GemKind.NORMAL]
        ext = [p for p in pieces if p.kind is not GemKind.NORMAL]
        counts = [len(base), len(ext)] if ext else [len(base)]
        columns = theme.palette_columns(counts)
        pairs = list(zip(base, columns[0]))
        if ext:
            pairs += list(zip(ext, columns[1]))
        return [Slot(piece, rect) for piece, rect in pairs]

    def _layout_panel(self) -> None:
        s = theme.s
        self.panel = theme.PANEL.copy()
        px = self.panel.x
        self.panel_x = px
        inner = px + s(18)
        bw = self.panel.width - s(36)
        top = self.panel.top

        # Réglages (haut du panneau) : taille de grille + extensions.
        self.size_label_y = top + s(46)
        sgap = s(8)
        sbw = (bw - 2 * sgap) // 3
        self.size_rects = [
            pygame.Rect(inner + i * (sbw + sgap), top + s(66), sbw, s(32)) for i in range(3)
        ]
        self.ext_label_y = top + s(104)
        self.diamant_rect = pygame.Rect(inner, top + s(126), s(20), s(20))
        self.corps_rect = pygame.Rect(inner, top + s(150), s(20), s(20))
        self.wormhole_rect = pygame.Rect(inner, top + s(174), s(20), s(20))
        self.filter_rect = pygame.Rect(inner, top + s(198), s(20), s(20))
        self.mystery_rect = pygame.Rect(inner, top + s(222), s(20), s(20))
        # Ligne cliquable (case + libellé) : largeur ajustée au texte réel pour
        # ne pas offrir une zone de clic démesurée (#65).
        self._build_ext_rows()
        # Minuteur : colonne de droite (aligné sur les extensions) pour ne pas
        # allonger le panneau. Label + stepper − valeur + (éditable au clavier).
        rx = inner + s(176)
        self.timer_label_x = rx
        self.timer_label_y = self.ext_label_y
        self.timer.set_rects(
            pygame.Rect(rx, top + s(126), s(26), s(26)),
            pygame.Rect(rx + s(30), top + s(126), s(68), s(26)),
            pygame.Rect(rx + s(102), top + s(126), s(26), s(26)),
        )
        self.status_y = top + s(250)

        # Actions (bas du panneau).
        self.save_rect = pygame.Rect(inner, self.panel.bottom - s(152), bw, s(40))
        self.play_rect = pygame.Rect(inner, self.panel.bottom - s(106), bw, s(40))
        self.back_rect = pygame.Rect(inner, self.panel.bottom - s(54), bw, s(40))

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
        if theme_toggle.hit(pos):  # bascule mode sombre / clair
            theme_toggle.toggle()
            return
        if lang_toggle.handle_click(pos, self.size[0]):  # drapeaux FR / UK
            self._build_ext_rows()  # le texte change de langue → recalc des zones (#65)
            return
        if self.timer.handle_click(pos):  # − / + / case du minuteur (valide la saisie)
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
        if self.diamant_row.collidepoint(pos):
            self._toggle_ext("diamant")
            return
        if self.corps_row.collidepoint(pos):
            self._toggle_ext("corps_noir")
            return
        if self.wormhole_row.collidepoint(pos):
            self._toggle_ext("wormhole")
            return
        if self.filter_row.collidepoint(pos):
            self._toggle_ext("filter")
            return
        if self.mystery_row.collidepoint(pos):
            self._toggle_ext("mystery")
            return
        for i, rect in enumerate(self.size_rects):
            if rect.collidepoint(pos):
                if i != self.size_index:
                    self.size_index = i
                    self._enforce_ext_rules()  # une grille plus petite restreint les extensions (#75)
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
            self._place_or_pick(cell)

    def _on_key(self, event: pygame.event.Event) -> None:
        if self.timer.handle_key(event):  # saisie du minuteur au clavier
            return
        if event.key == pygame.K_r and self.selected is not None:
            count = len(self.selected.orientations())
            self.orientation_index = (self.orientation_index + 1) % count
        elif event.key == pygame.K_c and self.mystery:
            i = self._MYSTERY_CYCLE.index(self.mystery_color)
            self.mystery_color = self._MYSTERY_CYCLE[(i + 1) % len(self._MYSTERY_CYCLE)]
        elif event.key == pygame.K_ESCAPE:
            self.selected = None

    # --- Extensions : plafond par taille de grille (#75) -------------------

    def _max_ext(self) -> int:
        """Nombre maximum d'extensions activables pour la taille courante."""
        return MAX_EXTENSIONS_BY_SIZE[self.size_index]

    def _ext_count(self) -> int:
        """Nombre d'extensions actuellement cochées."""
        return sum(getattr(self, attr) for attr in self._EXT_ATTRS)

    def _ext_allowed(self, attr: str) -> bool:
        """Cette extension est-elle disponible pour la taille de grille courante ? (#75)"""
        return attr not in DISALLOWED_EXTENSIONS_BY_SIZE[self.size_index]

    def _ext_disabled(self, attr: str) -> bool:
        """Case non cliquable : extension interdite, ou plafond atteint et non cochée."""
        if not self._ext_allowed(attr):
            return True
        return self._ext_count() >= self._max_ext() and not getattr(self, attr)

    def _toggle_ext(self, attr: str) -> None:
        """(Dé)coche une extension (refus si interdite/au plafond) puis reconstruit la palette."""
        if not getattr(self, attr) and self._ext_disabled(attr):
            return
        setattr(self, attr, not getattr(self, attr))
        self._rebuild(clear_gems=False)

    def _enforce_ext_rules(self) -> None:
        """Rétablit des extensions valides pour la taille courante (après resize) : #75.

        Décoche d'abord les extensions interdites, puis rogne l'excédent au-delà
        du plafond (en conservant les premières dans l'ordre d'affichage).
        """
        for attr in DISALLOWED_EXTENSIONS_BY_SIZE[self.size_index]:
            setattr(self, attr, False)
        limit = self._max_ext()
        kept = 0
        for attr in self._EXT_ATTRS:
            if getattr(self, attr):
                kept += 1
                if kept > limit:
                    setattr(self, attr, False)

    # --- Actions -----------------------------------------------------------

    def _select_slot(self, index: int) -> None:
        piece = self.slots[index].piece
        if self.placed_counts.get(piece.name, 0) >= piece.quantity:
            return
        self.selected = piece
        self.orientation_index = 0

    def _place_or_pick(self, cell: Position) -> None:
        """Clic gauche : poser la pièce tenue, sinon reprendre celle de la case.

        Le retrait pur reste réservé au clic droit (`_remove_at`).
        """
        if self.selected is None:
            self._pick_up(cell)
            return
        color = self.mystery_color if self.selected.kind is GemKind.MYSTERY else None
        gem = self.selected.at(cell, self.orientation_index, color=color)
        # Blocage DUR uniquement sur bornes/chevauchement ; une gemme côte à côte
        # reste posable mais signalée en rouge (aperçu) et bloque Sauver/Jouer.
        if self.grid.can_place(gem):
            self.grid.place_gem(gem)
            name = self.selected.name
            self.placed_counts[name] = self.placed_counts.get(name, 0) + 1
            if self.placed_counts[name] >= self.selected.quantity:
                self.selected = None
            self.message = None

    def _pick_up(self, cell: Position | None) -> None:
        """Reprend la gemme posée en `cell` pour la redéplacer (clic gauche)."""
        if cell is None:
            return
        gem = self.grid.gem_at(cell)
        if gem is None:
            return
        self.grid.remove_gem(gem)
        self.placed_counts[gem.piece.name] = max(0, self.placed_counts.get(gem.piece.name, 0) - 1)
        self.selected = gem.piece
        self.orientation_index = gem.piece.variant_index(gem)
        if gem.kind is GemKind.MYSTERY and gem.color is not None:
            self.mystery_color = gem.color
        self.message = None

    def _remove_at(self, cell: Position | None) -> None:
        if cell is None:
            return
        gem = self.grid.gem_at(cell)
        if gem is not None:
            self.grid.remove_gem(gem)
            name = gem.piece.name
            self.placed_counts[name] = max(0, self.placed_counts.get(name, 0) - 1)
            self.message = None

    def _missing_pieces(self) -> list[str]:
        """Pièces de la palette dont il manque des exemplaires sur le plateau."""
        counts: dict[str, int] = {}
        for gem in self.grid.gems:
            counts[gem.piece.name] = counts.get(gem.piece.name, 0) + 1
        missing: list[str] = []
        for piece in self.palette_pieces:
            remaining = piece.quantity - counts.get(piece.name, 0)
            if remaining > 0:
                label = i18n.piece(piece.color.value if piece.color else piece.name)
                missing.append(label + (f" (×{remaining})" if piece.quantity > 1 else ""))
        return missing

    def _blocking_problem(self) -> str | None:
        """Raison empêchant de jouer/partager, ou None si tout va bien."""
        missing = self._missing_pieces()
        if missing:
            names = ", ".join(missing)
            return i18n.t(f"Place toutes les gemmes (manque : {names}).",
                          f"Place all gems (missing: {names}).")
        problems = configuration_problems(self.grid)
        if problems:
            code, gem = problems[0]
            label = i18n.piece(gem.color.value if gem.color else gem.piece.name)
            if code == "touche":
                return i18n.t(f"La gemme {label} touche une autre gemme.",
                              f"The {label} gem touches another gem.")
            return i18n.t(f"La gemme {label} est entièrement cachée.",
                          f"The {label} gem is entirely hidden.")
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
            timer_minutes=self.timer_minutes,
        )
        try:
            dialogs.write_json(path, data)
        except OSError as exc:
            self.message = i18n.t("Échec de la sauvegarde : ", "Save failed: ") + str(exc)
            self.message_color = theme.LOSE_COLOR
            return
        self.message = i18n.t("Configuration enregistrée.", "Configuration saved.")
        self.message_color = theme.WIN_COLOR

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
        theme_toggle.draw(surface)
        lang_toggle.draw(surface)
        board_render.draw_board(surface, self.grid)
        self.ray.draw_beam(surface)  # rayon SOUS les gemmes
        board_render.draw_gems(surface, self.grid)
        self._draw_ghost(surface)
        self.ray.draw_entries(surface)
        self._draw_palette(surface)
        self._draw_panel(surface)
        hint = i18n.t(
            "clic=choisir/poser, clic sur une pièce=reprendre, [R] tourner, [C] couleur mystère, clic droit=retirer, point d'entrée=tester le rayon, [Échap] désélectionner",
            "click=select/place, click a piece=pick up, [R] rotate, [C] mystery color, right-click=remove, entry point=test the beam, [Esc] deselect",
        )
        surface.blit(
            self.font_small.render(hint, True, theme.TEXT_DIM),
            (theme.PALETTE.x, self.size[1] - theme.s(24)),
        )

    def _draw_ghost(self, surface: pygame.Surface) -> None:
        if self.selected is None or self.hovered_cell is None:
            return
        color = self.mystery_color if self.selected.kind is GemKind.MYSTERY else None
        gem = self.selected.at(self.hovered_cell, self.orientation_index, color=color)
        ok = placement_is_legal(self.grid, gem)
        board_render.draw_ghost(surface, gem, ok, self.grid.is_inside)

    def _draw_palette(self, surface: pygame.Surface) -> None:
        title = self.font_small.render(i18n.t("Pièces", "Pieces"), True, theme.TEXT_DIM)
        surface.blit(title, (theme.PALETTE.x + theme.s(4), theme.PALETTE.y - theme.s(22)))
        ext_slots = [sl for sl in self.slots if sl.piece.kind is not GemKind.NORMAL]
        if ext_slots:  # en-tête de la 2e colonne
            head = self.font_small.render(i18n.t("Extensions", "Extensions"), True, theme.TEXT_DIM)
            surface.blit(head, (ext_slots[0].rect.x + theme.s(1), theme.PALETTE.y - theme.s(22)))
        for slot in self.slots:
            override = self.mystery_color if slot.piece.kind is GemKind.MYSTERY else None
            board_render.draw_palette_slot(
                surface, slot.rect, slot.piece,
                selected=slot.piece is self.selected,
                placed=self.placed_counts.get(slot.piece.name, 0),
                font=self.font_small,
                override_color=override,
            )

    def _draw_panel(self, surface: pygame.Surface) -> None:
        s = theme.s
        pygame.draw.rect(surface, theme.PANEL_BG, self.panel, border_radius=8)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.panel, width=1, border_radius=8)
        x = self.panel_x + s(18)
        surface.blit(self.font_big.render(i18n.t("Mode créateur", "Creator mode"), True, theme.TEXT), (x, self.panel.top + s(14)))

        # Réglages : taille de grille.
        surface.blit(self.font_small.render(i18n.t("Taille de la grille", "Grid size"), True, theme.TEXT), (x, self.size_label_y))
        for i, rect in enumerate(self.size_rects):
            selected = i == self.size_index
            bg = theme.SLOT_SELECTED if selected else theme.SLOT_BG
            pygame.draw.rect(surface, bg, rect, border_radius=6)
            pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1, border_radius=6)
            name, w, h = self._SIZES[i]
            fg = theme.ON_ACCENT if selected else theme.TEXT
            label = self.font_small.render(f"{i18n.size_name(name)} {w}×{h}", True, fg)
            surface.blit(label, label.get_rect(center=rect.center))

        # Réglages : extensions (plafonnées selon la taille de grille — #75).
        ext_header = i18n.t("Extensions", "Extensions") + f"  ({self._ext_count()}/{self._max_ext()})"
        surface.blit(self.font_small.render(ext_header, True, theme.TEXT), (x, self.ext_label_y))
        d_txt, c_txt, w_txt, f_txt, r_txt = self._ext_label_texts()
        # Cases grisées : extension interdite pour la taille, ou plafond atteint (#75).
        self._checkbox(surface, self.diamant_rect, self.diamant, d_txt, disabled=self._ext_disabled("diamant"))
        self._checkbox(surface, self.corps_rect, self.corps_noir, c_txt, disabled=self._ext_disabled("corps_noir"))
        self._checkbox(surface, self.wormhole_rect, self.wormhole, w_txt, disabled=self._ext_disabled("wormhole"))
        self._checkbox(surface, self.filter_rect, self.filter, f_txt, disabled=self._ext_disabled("filter"))
        self._checkbox(surface, self.mystery_rect, self.mystery, r_txt, disabled=self._ext_disabled("mystery"))

        # Minuteur (optionnel), colonne de droite.
        surface.blit(self.font_small.render(i18n.t("Minuteur", "Timer"), True, theme.TEXT),
                     (self.timer_label_x, self.timer_label_y))
        self.timer.draw(surface, self.font_small, i18n.t("Désactivé", "Off"))

        # État de validité en direct.
        placed = len(self.grid.gems)
        problem = self._blocking_problem()
        if problem is None:
            status = i18n.t(f"Configuration valide ({placed} gemme(s)).", f"Valid configuration ({placed} gem(s)).")
            color = theme.WIN_COLOR
        else:
            status = i18n.t(f"Attention : {problem}", f"Warning: {problem}")
            color = theme.LOSE_COLOR
        status_lines = _wrap(status, self.font_small, self.panel.width - s(40))
        for i, text in enumerate(status_lines):
            surface.blit(self.font_small.render(text, True, color), (x, self.status_y + i * s(18)))

        # Résultat du dernier rayon de test (sous l'état, position dynamique).
        ray_y = self.status_y + len(status_lines) * s(18) + s(10)
        ray_line = self.ray.last_test or i18n.t("Clique un point d'entrée pour tester le rayon.",
                                                "Click an entry point to test the beam.")
        for i, text in enumerate(_wrap(ray_line, self.font_small, self.panel.width - s(40))):
            surface.blit(self.font_small.render(text, True, theme.TEXT_DIM), (x, ray_y + i * s(18)))

        self._button(surface, self.save_rect, theme.BTN_SAVE,
                     i18n.t("Sauvegarder la configuration", "Save configuration"), text_color=theme.BTN_TEXT)
        can_play = problem is None
        self._button(
            surface,
            self.play_rect,
            theme.BTN_GREEN if can_play else theme.SLOT_USED,
            i18n.t("Jouer cette configuration", "Play this configuration"),
            dim=not can_play,
            text_color=theme.BTN_TEXT if can_play else None,
        )
        self._button(surface, self.back_rect, theme.SLOT_BG, i18n.t("Retour au menu", "Back to menu"))

        if self.message:
            for i, text in enumerate(_wrap(self.message, self.font_small, self.panel.width - s(40))):
                surface.blit(self.font_small.render(text, True, self.message_color), (x, self.save_rect.top - s(46) + i * s(18)))

    def _button(self, surface: pygame.Surface, rect: pygame.Rect, bg, text: str, dim: bool = False, text_color=None) -> None:
        pygame.draw.rect(surface, bg, rect, border_radius=8)
        pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1, border_radius=8)
        color = text_color or (theme.TEXT_DIM if dim else theme.TEXT)
        label = self.font_small.render(text, True, color)
        surface.blit(label, label.get_rect(center=rect.center))

    def _ext_label_texts(self) -> list[str]:
        """Libellés des extensions (source unique pour le rendu et les zones cliquables)."""
        return [
            i18n.t("Diamant", "Diamond"),
            i18n.t("Corps noir", "Black body"),
            i18n.t("Trou de ver (×2)", "Wormhole (×2)"),
            i18n.t("Filtre", "Filter"),
            i18n.t("Mystère", "Mystery"),
        ]

    def _build_ext_rows(self) -> None:
        """Zones cliquables des extensions, ajustées à la largeur du texte (#65)."""
        s = theme.s
        gap, pad = s(10), s(10)  # écart case→texte (cf. _checkbox) + marge droite
        boxes = [
            self.diamant_rect, self.corps_rect, self.wormhole_rect,
            self.filter_rect, self.mystery_rect,
        ]
        rows = [
            pygame.Rect(cb.x, cb.y - s(2), cb.width + gap + self.font_small.size(text)[0] + pad, s(24))
            for cb, text in zip(boxes, self._ext_label_texts())
        ]
        (self.diamant_row, self.corps_row, self.wormhole_row,
         self.filter_row, self.mystery_row) = rows

    def _checkbox(self, surface: pygame.Surface, rect: pygame.Rect, on: bool, text: str, disabled: bool = False) -> None:
        pygame.draw.rect(surface, theme.INPUT_BG, rect, border_radius=4)
        pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1, border_radius=4)
        if on:
            pygame.draw.rect(surface, theme.SLOT_SELECTED, rect.inflate(theme.s(-8), theme.s(-8)), border_radius=2)
        label = self.font_small.render(text, True, theme.TEXT_DIM if disabled else theme.TEXT)
        surface.blit(label, (rect.right + theme.s(10), rect.y + theme.s(2)))


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
