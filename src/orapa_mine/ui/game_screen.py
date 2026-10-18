"""Écran de jeu Pygame : plateau, hypothèses, rayon animé, historique.

Deux façons de tirer, volontairement distinctes :

- **Cliquer un point d'entrée** envoie un rayon de *test* qui se réfléchit sur
  les pièces d'**hypothèse posées par le joueur** (aide à la déduction, non
  enregistré). Le trajet est animé.
- **Saisir une étiquette** dans la zone de texte (sous « Historique ») envoie
  la *vraie* question sur la grille cachée. Deux formats :
  - un point de bord (chiffre 1–18 ou lettre A–R) → tir réel : seuls l'entrée,
    le point de sortie et la couleur sont enregistrés (le trajet n'est jamais
    dessiné, il révélerait les positions cachées) ;
  - une case « colonne-lettre + ligne-numéro » (ex. A1) → question de case :
    la réponse (vide, couleur, ou nom d'extension) est enregistrée.

Aucune règle de jeu ici : on appelle `fire_beam` / `GameState` et on affiche.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from orapa_mine.ai.generator import placement_is_legal
from orapa_mine.model.beam import mix_colors
from orapa_mine.model.game import CellContent, CellQuery, GameState, RayShot
from orapa_mine.model.gems import GemColor, GemKind, Piece, Position
from orapa_mine.model import serialization
from orapa_mine.model.grid import Grid
from orapa_mine.ui import board_render, dialogs, i18n, lang_toggle, theme, theme_toggle
from orapa_mine.ui.beam_test import RayTester

_HISTORY_ROW_H = theme.s(22)  # hauteur d'une ligne d'historique (px, échelle DPI)
_DOUBLE_CLICK_MS = 400  # fenêtre max entre deux clics pour un double-clic (#84)

# Extensions : on annonce le NOM de la pièce (et non une couleur) en réponse à
# une question de case. Clés = libellés français, traduits par `i18n.piece`.
_KIND_PIECE_NAME: dict[GemKind, str] = {
    GemKind.DIAMOND: "diamant",
    GemKind.FILTER: "filtre",
    GemKind.BLACK_BODY: "corps-noir",
    GemKind.WORMHOLE: "trou-de-ver",
}
# La gemme mystère est volontairement absente : une question de case révèle sa
# vraie COULEUR (et non son nom), comme une gemme normale (issue #77).

# Ordre de défilement de la couleur de la gemme mystère (touche [C]).
_MYSTERY_CYCLE = (GemColor.BLUE, GemColor.RED, GemColor.YELLOW, GemColor.WHITE)


@dataclass
class Slot:
    """Une case de la palette : une pièce jouable et son rectangle écran."""

    piece: Piece
    rect: pygame.Rect


class GameScreen:
    """Gère l'affichage et les interactions de l'écran de jeu."""

    def __init__(
        self, game: GameState, palette_pieces: list[Piece], timer_minutes: int = 0
    ) -> None:
        self.game = game
        self.one_shot = game.one_shot  # Coup Unique (#81) : indices figés, pas de requêtes
        self.grid = game.hidden_grid  # cachée (debug uniquement)
        self.palette_pieces = palette_pieces
        self.hypothesis = Grid(width=self.grid.width, height=self.grid.height)
        # Croix « pas de gemme ici » posées par le joueur (aide à la déduction, #84).
        self.crosses: set[Position] = set()
        self._last_click_cell: Position | None = None  # suivi du double-clic
        self._last_click_ms = 0
        self.reveal = False
        self.save_progress = True  # sauver aussi historique + pièces posées

        # Minuteur (optionnel) et temps écoulé (en secondes).
        self.timer_minutes = max(0, int(timer_minutes))
        self.time_limit = self.timer_minutes * 60.0  # 0 = pas de limite
        self.elapsed = 0.0

        # Sélection / pose de pièces.
        self.selected: Piece | None = None
        self.orientation_index = 0
        self.placed_counts: dict[str, int] = {}  # nom de pièce -> nb d'exemplaires posés
        self.hovered_cell: Position | None = None
        # Couleur « devinée » de la gemme mystère (choisie au clavier [C]) ;
        # elle teinte l'aperçu, la pièce posée et le rayon de test.
        self.mystery_color = GemColor.BLUE
        self._has_mystery = any(p.kind is GemKind.MYSTERY for p in palette_pieces)

        # Zone de proposition (texte) et résultat de soumission.
        self.input_text = ""
        self.input_active = False
        self.message: str | None = None
        self.message_color = theme.TEXT_DIM

        # Signal de fin de partie lu par l'app : ("win"|"giveup"|"timeout", score) ou None.
        self.finished: tuple[str, int] | None = None
        # Retour au menu (sans révéler la solution), lu par l'app.
        self.back_to_menu = False
        self.show_leave_prompt = False  # popup « sauvegarder avant de quitter ? »

        # Aide « comment jouer » (overlay paginé).
        self.show_help = False
        self.help_page = 0

        # Défilement de l'historique (offset en pixels depuis le haut).
        self.history_scroll = 0.0
        self.history_stick_bottom = True
        self._dragging_scroll = False  # glissement de la barre de défilement (#79)
        self._drag_grab_dy = 0.0       # décalage clic→haut du pouce pendant le glissement

        self.font = theme.font(20)
        self.font_small = theme.font(15)
        self.font_big = theme.font(26, bold=True)
        self.font_clock = theme.font(28, bold=True)  # horloge bien lisible

        # Mise en page adaptative : palette sur deux colonnes (classiques |
        # extensions) dès qu'une extension est présente → fenêtre plus large,
        # icônes plus grandes.
        palette_cols = 2 if any(p.kind is not GemKind.NORMAL for p in palette_pieces) else 1
        self.size = theme.window_size(self.grid.width, self.grid.height, palette_cols=palette_cols)
        self.ray = RayTester(self.grid.width, self.grid.height, self.font_small)
        self.slots = self._build_palette(palette_pieces)
        self._layout_panel()

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
        # Le panneau n'est aussi haut que le plateau : on l'étire dans l'espace
        # libre sous lui (côté droit, sans points d'entrée) pour agrandir
        # l'historique (#79). On garde une marge pour la ligne d'indices du bas.
        self.panel.height = max(self.panel.height, self.size[1] - self.panel.top - s(34))
        px = self.panel.x
        self.panel_x = px
        inner = px + s(18)
        top = self.panel.top
        bw = theme.PANEL_WIDTH - s(36)
        self.help_rect = pygame.Rect(px + theme.PANEL_WIDTH - s(44), top + s(16), s(28), s(28))
        self.submit_rect = pygame.Rect(inner, top + s(92), s(180), s(34))
        self.abandon_rect = pygame.Rect(inner + s(190), top + s(92), s(92), s(34))
        # Ligne sauvegarde : case « progression » + bouton Sauvegarder.
        self.progress_toggle_rect = pygame.Rect(inner, top + s(136), s(20), s(20))
        # Zone cliquable case + libellé « Progression » (bornée avant Sauvegarder).
        self.progress_row = pygame.Rect(inner, top + s(134), s(140), s(24))
        self.save_rect = pygame.Rect(inner + s(150), top + s(132), s(132), s(28))
        # Bouton « Retour au menu » (ouvre le popup de sauvegarde avant de quitter).
        self.menu_rect = pygame.Rect(inner, top + s(170), bw, s(30))
        # Zone de saisie ancrée en bas du panneau (laisse la place au message dessous).
        self.input_rect = pygame.Rect(inner, self.panel.bottom - s(62), bw, s(32))

        # Zone d'historique : s'étire entre l'en-tête et la zone de saisie,
        # donc profite de toute la hauteur gagnée par le panneau agrandi.
        self.history_header_y = top + s(208)
        content_top = self.history_header_y + s(24)
        content_bottom = self.input_rect.top - s(28)  # laisse la place au libellé
        self.history_rect = pygame.Rect(
            inner, content_top, bw, max(s(48), content_bottom - content_top)
        )

    # --- Événements --------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            if self._dragging_scroll:  # glissement de la barre de défilement (#79)
                self._drag_scroll_to(event.pos[1])
                return
            self.ray.hover(event.pos)
            self.hovered_cell = self._cell_at(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._on_click(event)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self._dragging_scroll = False
        elif event.type == pygame.MOUSEWHEEL:
            if not self.show_help and self.history_rect.collidepoint(pygame.mouse.get_pos()):
                self._scroll_history(event.y)
        elif event.type == pygame.KEYDOWN:
            self._on_key(event)

    def _scroll_history(self, dy: int) -> None:
        content_h = len(self.game.clues) * _HISTORY_ROW_H + 8
        max_scroll = max(0.0, content_h - self.history_rect.height)
        if max_scroll <= 0:
            return
        # Molette vers le haut (dy > 0) -> remonter dans l'historique.
        self.history_scroll = min(max_scroll, max(0.0, self.history_scroll - dy * _HISTORY_ROW_H * 2))
        self.history_stick_bottom = self.history_scroll >= max_scroll - 1

    # --- Barre de défilement de l'historique (cliquable/glissable, #79) ------

    def _history_scrollbar(self):
        """Géométrie de la barre : (gouttière, pouce, hauteur du pouce, scroll max).

        Renvoie None si l'historique tient entièrement (pas de barre).
        """
        rect = self.history_rect
        content_h = len(self.game.clues) * _HISTORY_ROW_H + theme.s(8)
        max_scroll = max(0.0, content_h - rect.height)
        if max_scroll <= 0:
            return None
        thumb_h = max(theme.s(24), rect.height * rect.height / content_h)
        scroll = min(max(0.0, self.history_scroll), max_scroll)
        thumb_y = rect.y + (scroll / max_scroll) * (rect.height - thumb_h)
        track = pygame.Rect(rect.right - theme.s(9), rect.y, theme.s(9), rect.height)
        thumb = pygame.Rect(rect.right - theme.s(8), int(thumb_y), theme.s(7), int(thumb_h))
        return track, thumb, thumb_h, max_scroll

    def _start_scroll_drag(self, pos: tuple[int, int]) -> bool:
        """Début d'un glissement : sur le pouce (avec décalage) ou dans la gouttière (saut)."""
        sb = self._history_scrollbar()
        if sb is None:
            return False
        track, thumb, thumb_h, _ = sb
        if thumb.collidepoint(pos):
            self._dragging_scroll = True
            self._drag_grab_dy = pos[1] - thumb.y
            return True
        if track.collidepoint(pos):  # clic dans la gouttière : on centre le pouce puis on glisse
            self._dragging_scroll = True
            self._drag_grab_dy = thumb_h / 2
            self._drag_scroll_to(pos[1])
            return True
        return False

    def _drag_scroll_to(self, y: int) -> None:
        """Place le défilement selon la position verticale `y` du curseur (glissement)."""
        sb = self._history_scrollbar()
        if sb is None:
            return
        _, _, thumb_h, max_scroll = sb
        rect = self.history_rect
        travel = rect.height - thumb_h
        if travel <= 0:
            return
        thumb_top = min(rect.bottom - thumb_h, max(float(rect.y), y - self._drag_grab_dy))
        self.history_scroll = ((thumb_top - rect.y) / travel) * max_scroll
        self.history_stick_bottom = self.history_scroll >= max_scroll - 1

    def _on_click(self, event: pygame.event.Event) -> None:
        pos = event.pos
        if self.show_leave_prompt:  # popup « sauvegarder avant de quitter ? »
            if event.button == 1:
                layout = self._leave_prompt_layout(self.size)
                for (_fr, _en, _color, action), rect in zip(self._leave_buttons(), layout["rects"]):
                    if rect.collidepoint(pos):
                        action()
                        return
                if not layout["panel"].collidepoint(pos):
                    self.show_leave_prompt = False  # clic en dehors = annuler
            return
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
        if theme_toggle.hit(pos):  # bascule mode sombre / clair
            theme_toggle.toggle()
            return
        if lang_toggle.handle_click(pos, self.size[0]):  # drapeaux FR / UK
            return
        if self.help_rect.collidepoint(pos):
            self.show_help = True
            self.help_page = 0
            return
        if self._start_scroll_drag(pos):  # saisir/cliquer la barre de défilement (#79)
            return
        # Zone de saisie (désactivée en Coup Unique : aucune nouvelle question).
        if not self.one_shot and self.input_rect.collidepoint(pos):
            self.input_active = True
            return
        self.input_active = False
        if self.submit_rect.collidepoint(pos):
            self._submit()
            return
        if self.abandon_rect.collidepoint(pos):
            self.finished = ("giveup", self.game.request_score)
            return
        if self.progress_row.collidepoint(pos):  # case OU libellé « Progression »
            self.save_progress = not self.save_progress
            return
        if self.save_rect.collidepoint(pos):
            self._save()
            return
        if self.menu_rect.collidepoint(pos):
            self.show_leave_prompt = True
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
            # Double-clic sur une case vide, sans pièce en main : (dé)pose une
            # croix « pas de gemme ici » (#84). Sinon, pose/reprise habituelle.
            double = self._register_cell_click(cell)
            if double and self.selected is None and self.hypothesis.gem_at(cell) is None:
                self._toggle_cross(cell)
                return
            self._place_or_pick(cell)

    def _register_cell_click(self, cell: Position) -> bool:
        """Mémorise le clic et indique s'il complète un double-clic sur `cell`."""
        now = pygame.time.get_ticks()
        is_double = (self._last_click_cell == cell
                     and now - self._last_click_ms <= _DOUBLE_CLICK_MS)
        # On réinitialise après un double-clic pour qu'un 3e clic rapide ne
        # rebascule pas aussitôt la croix.
        self._last_click_cell = None if is_double else cell
        self._last_click_ms = now
        return is_double

    def _toggle_cross(self, cell: Position) -> None:
        """Ajoute ou retire la croix « pas de gemme » sur `cell`."""
        if cell in self.crosses:
            self.crosses.discard(cell)
        else:
            self.crosses.add(cell)

    def _on_key(self, event: pygame.event.Event) -> None:
        if self.show_leave_prompt:
            if event.key == pygame.K_ESCAPE:
                self.show_leave_prompt = False
            return
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
        elif event.key == pygame.K_c and self._has_mystery:
            self._cycle_mystery_color()
        elif event.key == pygame.K_ESCAPE:
            self.selected = None

    def _input_key(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_RETURN:
            self._ask()
        elif event.key == pygame.K_BACKSPACE:
            self.input_text = self.input_text[:-1]
        elif event.key == pygame.K_ESCAPE:
            self.input_active = False
        elif event.unicode.isalnum() and len(self.input_text) < 3:
            self.input_text += event.unicode.upper()

    # --- Actions -----------------------------------------------------------

    def _cycle_mystery_color(self) -> None:
        """Fait défiler la couleur devinée de la gemme mystère ([C])."""
        i = _MYSTERY_CYCLE.index(self.mystery_color)
        self.mystery_color = _MYSTERY_CYCLE[(i + 1) % len(_MYSTERY_CYCLE)]

    def _select_slot(self, index: int) -> None:
        piece = self.slots[index].piece
        if self.placed_counts.get(piece.name, 0) >= piece.quantity:
            return
        self.selected = piece
        self.orientation_index = 0

    def _place_or_pick(self, cell: Position) -> None:
        """Clic gauche : poser la pièce tenue, sinon reprendre celle de la case.

        Le retrait pur est réservé au clic droit (`_remove_at`). Cliquer une
        gemme déjà posée la « reprend » (retrait + sélection) pour la déplacer.
        """
        if self.selected is None:
            self._pick_up(cell)
            return
        color = self.mystery_color if self.selected.kind is GemKind.MYSTERY else None
        gem = self.selected.at(cell, self.orientation_index, color=color)
        # Blocage DUR uniquement sur bornes/chevauchement (pose impossible) ; une
        # gemme posée côte à côte d'une autre reste autorisée mais signalée en
        # rouge par l'aperçu (avertissement, voir `_draw_ghost`).
        if self.hypothesis.can_place(gem):
            self.hypothesis.place_gem(gem)
            self.crosses.difference_update(gem.absolute_cells())  # une gemme efface la croix (#84)
            name = self.selected.name
            self.placed_counts[name] = self.placed_counts.get(name, 0) + 1
            # On garde la pièce sélectionnée tant qu'il en reste à poser (trou de ver).
            if self.placed_counts[name] >= self.selected.quantity:
                self.selected = None

    def _pick_up(self, cell: Position | None) -> None:
        """Reprend la gemme posée en `cell` pour la redéplacer (clic gauche)."""
        if cell is None:
            return
        gem = self.hypothesis.gem_at(cell)
        if gem is None:
            return
        self.hypothesis.remove_gem(gem)
        self.placed_counts[gem.piece.name] = max(0, self.placed_counts.get(gem.piece.name, 0) - 1)
        self.selected = gem.piece
        self.orientation_index = gem.piece.variant_index(gem)
        if gem.kind is GemKind.MYSTERY and gem.color is not None:
            self.mystery_color = gem.color  # on reprend la couleur devinée

    def _remove_at(self, cell: Position | None) -> None:
        if cell is None:
            return
        gem = self.hypothesis.gem_at(cell)
        if gem is not None:
            self.hypothesis.remove_gem(gem)
            name = gem.piece.name
            self.placed_counts[name] = max(0, self.placed_counts.get(name, 0) - 1)

    def _ask(self) -> None:
        """Pose une vraie question : case (ex. A1) ou point de bord (tir)."""
        label = self.input_text.strip().upper()
        self.input_text = ""
        if not label:
            return
        if theme.looks_like_cell_label(label):
            self._ask_cell(label)
            return
        ep = self.ray.entry_by_label.get(label)
        if ep is None:
            self.message = i18n.t(f"Point « {label} » inconnu.", f"Unknown point « {label} ».")
            self.message_color = theme.LOSE_COLOR
            return
        self.game.play_shot(ep.entry, ep.direction)
        self.message = None

    def _ask_cell(self, label: str) -> None:
        """Pose la question « Qu'y a-t-il en <label> ? » sur la grille cachée."""
        cell = theme.parse_cell_label(label, self.grid.width, self.grid.height)
        if cell is None:
            self.message = i18n.t(f"Case « {label} » hors plateau.", f"Cell « {label} » off board.")
            self.message_color = theme.LOSE_COLOR
            return
        answer = self.game.query_cell(cell)
        self.message = i18n.t(f"Case {label} : ", f"Cell {label}: ") + _cell_answer_text(answer.content)
        self.message_color = theme.TEXT

    def _query_marker_rgb(self, content: CellContent) -> tuple[int, int, int]:
        """Couleur du marqueur d'une question de case dans l'historique."""
        if not content.occupied:
            return theme.SLOT_BG
        if content.color is not None:
            return theme.GEM_FILL[content.color]
        if content.kind in theme.GEM_FILL:
            return theme.GEM_FILL[content.kind]
        return theme.TEXT_DIM

    def _save(self, with_progress: bool | None = None) -> bool:
        """Sauvegarde la partie. `with_progress=None` suit la case « Progression ».

        Renvoie True si le fichier a bien été écrit (False si annulé/échec).
        """
        progress = self.save_progress if with_progress is None else with_progress
        path = dialogs.ask_save_path()
        if not path:
            return False
        data = serialization.to_dict(
            width=self.grid.width,
            height=self.grid.height,
            palette_pieces=self.palette_pieces,
            hidden_grid=self.grid,
            include_progress=progress,
            game=self.game,
            hypothesis_grid=self.hypothesis,
            timer_minutes=self.timer_minutes,
            max_proposals=self.game.max_proposals,
            one_shot=self.game.one_shot,
            given_shots=[(s.entry, s.direction) for s in self.game.given_shots],
            elapsed_seconds=self.elapsed,
            crosses=self.crosses,
        )
        try:
            dialogs.write_json(path, data)
        except OSError as exc:
            self.message = i18n.t("Échec de la sauvegarde : ", "Save failed: ") + str(exc)
            self.message_color = theme.LOSE_COLOR
            return False
        kind = i18n.t("avec progression", "with progress") if progress \
            else i18n.t("configuration seule", "configuration only")
        self.message = i18n.t(f"Partie sauvegardée ({kind}).", f"Game saved ({kind}).")
        self.message_color = theme.WIN_COLOR
        return True

    # --- Retour au menu (popup « sauvegarder avant de quitter ? ») ---------

    def _leave_save(self, with_progress: bool) -> None:
        """Sauvegarde puis retourne au menu ; reste en jeu si la sauvegarde est annulée."""
        self.show_leave_prompt = False
        if self._save(with_progress=with_progress):
            self.back_to_menu = True

    def _leave_no_save(self) -> None:
        self.show_leave_prompt = False
        self.back_to_menu = True

    def _leave_buttons(self) -> list[tuple[str, str, tuple[int, int, int], object]]:
        """(libellé FR, libellé EN, couleur, action) des boutons du popup de sortie."""
        return [
            ("Sauvegarder (avec progression)", "Save (with progress)", theme.BTN_SAVE,
             lambda: self._leave_save(True)),
            ("Sauvegarder (configuration seule)", "Save (configuration only)", theme.BTN_SAVE,
             lambda: self._leave_save(False)),
            ("Quitter sans sauvegarder", "Leave without saving", theme.BTN_RED,
             self._leave_no_save),
            ("Annuler", "Cancel", theme.SLOT_BG, lambda: setattr(self, "show_leave_prompt", False)),
        ]

    def _leave_prompt_layout(self, size: tuple[int, int]) -> dict:
        s = theme.s
        w, h = size
        pw = min(s(400), w - s(80))
        btn_h, gap, pad, title_h = s(42), s(10), s(24), s(54)
        rows = self._leave_buttons()
        ph = title_h + len(rows) * btn_h + (len(rows) - 1) * gap + pad
        px, py = (w - pw) // 2, (h - ph) // 2
        panel = pygame.Rect(px, py, pw, ph)
        rects, y = [], py + title_h
        for _ in rows:
            rects.append(pygame.Rect(px + pad, y, pw - 2 * pad, btn_h))
            y += btn_h + gap
        return {"panel": panel, "rects": rects}

    def _draw_leave_prompt(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        backdrop = pygame.Surface((w, h), pygame.SRCALPHA)
        backdrop.fill((6, 8, 14, 214))
        surface.blit(backdrop, (0, 0))
        layout = self._leave_prompt_layout((w, h))
        panel, rects = layout["panel"], layout["rects"]
        pygame.draw.rect(surface, theme.PANEL_BG, panel, border_radius=12)
        pygame.draw.rect(surface, theme.BOARD_BORDER, panel, width=2, border_radius=12)
        title = self.font.render(i18n.t("Quitter la partie ?", "Leave the game?"), True, theme.TEXT)
        surface.blit(title, title.get_rect(centerx=panel.centerx, y=panel.y + theme.s(18)))
        for (fr, en, color, _action), rect in zip(self._leave_buttons(), rects):
            pygame.draw.rect(surface, color, rect, border_radius=8)
            pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1, border_radius=8)
            text_color = theme.TEXT if color is theme.SLOT_BG else theme.BTN_TEXT
            label = self.font_small.render(i18n.t(fr, en), True, text_color)
            surface.blit(label, label.get_rect(center=rect.center))

    def _submit(self) -> None:
        won = self.game.submit_guess(list(self.hypothesis.gems))
        if won:
            self.finished = ("win", self.game.request_score)
            return
        if self.game.proposals_exhausted:  # plus d'essais : fin de partie (#45)
            self.finished = ("lost", self.game.request_score)
            return
        rem = self.game.remaining_proposals
        if rem is None:
            self.message = i18n.t("Proposition incorrecte, réessaie.", "Incorrect guess, try again.")
        else:
            self.message = i18n.t(f"Proposition incorrecte. Essais restants : {rem}.",
                                  f"Incorrect guess. Attempts left: {rem}.")
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
        if self.finished is not None:
            return
        self.elapsed += dt
        if self.time_limit and self.elapsed >= self.time_limit:
            self.elapsed = self.time_limit
            self.finished = ("timeout", self.game.request_score)

    def _remaining(self) -> float:
        """Secondes restantes avant la fin du minuteur (0 si désactivé/écoulé)."""
        if not self.time_limit:
            return 0.0
        return max(0.0, self.time_limit - self.elapsed)

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BACKGROUND)
        board_render.draw_board(surface, self.grid)
        self.ray.draw_beam(surface)  # rayon SOUS les gemmes (réflexion masquée par la pièce)
        board_render.draw_gems(surface, self.hypothesis)
        board_render.draw_crosses(surface, self.crosses)  # croix « pas de gemme » (#84)
        if self.reveal:
            self._draw_hidden_outline(surface)
        self._draw_ghost(surface)
        self._draw_hovered_coord(surface)
        self.ray.draw_entries(surface)
        self._draw_palette(surface)
        self._draw_panel(surface)
        theme_toggle.draw(surface)
        lang_toggle.draw(surface)
        if self.show_help:
            self._draw_help(surface)
        if self.show_leave_prompt:
            self._draw_leave_prompt(surface)

    def _draw_hidden_outline(self, surface: pygame.Surface) -> None:
        for gem in self.grid.gems:
            for pos, half in gem.absolute_cells().items():
                pygame.draw.polygon(surface, (250, 90, 90), theme.half_cell_polygon(pos, half), width=2)

    def _draw_ghost(self, surface: pygame.Surface) -> None:
        if self.selected is None or self.hovered_cell is None:
            return
        color = self.mystery_color if self.selected.kind is GemKind.MYSTERY else None
        gem = self.selected.at(self.hovered_cell, self.orientation_index, color=color)
        ok = placement_is_legal(self.hypothesis, gem)
        board_render.draw_ghost(surface, gem, ok, self.grid.is_inside)

    def _draw_hovered_coord(self, surface: pygame.Surface) -> None:
        """Badge « A1 » sur la case survolée (pour savoir quelle case interroger)."""
        if self.hovered_cell is None:
            return
        label = theme.cell_label(self.hovered_cell)
        img = self.font_small.render(label, True, theme.ON_ACCENT)
        x, y, _, _ = theme.cell_rect(self.hovered_cell)
        box = img.get_rect(topleft=(x + theme.s(3), y + theme.s(3))).inflate(theme.s(6), theme.s(4))
        pygame.draw.rect(surface, theme.SLOT_SELECTED, box, border_radius=3)
        surface.blit(img, img.get_rect(center=box.center))

    def _draw_clock(self, surface: pygame.Surface) -> None:
        """Horloge M:SS à droite du titre : compte à rebours si minuteur, sinon
        temps écoulé (compte croissant). Reprend le temps déjà passé au rechargement."""
        if self.time_limit:
            remaining = self._remaining()
            if remaining <= 20:
                color = theme.LOSE_COLOR
            elif remaining <= 60:
                color = (236, 170, 90)
            else:
                color = theme.TEXT
            text = _mmss(remaining)  # arrondi au-dessus : atteint 0:00 pile à la fin
        else:
            color = theme.TEXT_DIM
            text = _mmss(self.elapsed, ceil=False)  # temps écoulé (plancher)
        img = self.font_clock.render(text, True, color)
        surface.blit(img, img.get_rect(midright=(self.help_rect.left - theme.s(12), self.help_rect.centery)))

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
        surface.blit(self.font_big.render("Orapa Mine", True, theme.TEXT), (x, self.panel.top + s(12)))
        # Bouton d'aide « ? ».
        pygame.draw.circle(surface, theme.SLOT_BG, self.help_rect.center, s(14))
        pygame.draw.circle(surface, theme.BOARD_BORDER, self.help_rect.center, s(14), width=1)
        q = self.font.render("?", True, theme.TEXT)
        surface.blit(q, q.get_rect(center=self.help_rect.center))
        self._draw_clock(surface)
        test_hint = self.ray.last_test or i18n.t("Clique un point d'entrée pour tester.", "Click an entry point to test.")
        surface.blit(
            self.font_small.render(test_hint, True, theme.TEXT_DIM),
            (x, self.panel.top + s(54)),
        )
        # Boutons Proposer / Abandonner. Le libellé indique les essais restants
        # quand le nombre de propositions est limité (#45).
        pygame.draw.rect(surface, theme.BTN_GREEN, self.submit_rect, border_radius=6)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.submit_rect, width=1, border_radius=6)
        rem = self.game.remaining_proposals
        if rem is None:
            submit_text = i18n.t("Proposer la solution", "Submit solution")
        else:
            submit_text = i18n.t(f"Proposer ({rem} essai{'s' if rem != 1 else ''})",
                                 f"Submit ({rem} left)")
        btn = self.font_small.render(submit_text, True, theme.BTN_TEXT)
        surface.blit(btn, btn.get_rect(center=self.submit_rect.center))
        pygame.draw.rect(surface, theme.BTN_RED, self.abandon_rect, border_radius=6)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.abandon_rect, width=1, border_radius=6)
        ab = self.font_small.render(i18n.t("Abandonner", "Give up"), True, theme.BTN_TEXT)
        surface.blit(ab, ab.get_rect(center=self.abandon_rect.center))

        # Ligne sauvegarde : case « progression » + bouton Sauvegarder.
        pygame.draw.rect(surface, theme.INPUT_BG, self.progress_toggle_rect, border_radius=4)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.progress_toggle_rect, width=1, border_radius=4)
        if self.save_progress:
            pygame.draw.rect(surface, theme.SLOT_SELECTED, self.progress_toggle_rect.inflate(s(-8), s(-8)), border_radius=2)
        surface.blit(
            self.font_small.render(i18n.t("Progression", "Progress"), True, theme.TEXT),
            (self.progress_toggle_rect.right + s(8), self.progress_toggle_rect.y + s(2)),
        )
        pygame.draw.rect(surface, theme.SLOT_BG, self.save_rect, border_radius=6)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.save_rect, width=1, border_radius=6)
        sv = self.font_small.render(i18n.t("Sauvegarder", "Save"), True, theme.TEXT)
        surface.blit(sv, sv.get_rect(center=self.save_rect.center))

        # Bouton « Retour au menu ».
        pygame.draw.rect(surface, theme.BTN_BLUE, self.menu_rect, border_radius=6)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.menu_rect, width=1, border_radius=6)
        mb = self.font_small.render(i18n.t("Retour au menu", "Back to menu"), True, theme.BTN_TEXT)
        surface.blit(mb, mb.get_rect(center=self.menu_rect.center))

        hist_title = i18n.t("Indices", "Clues") if self.one_shot else i18n.t("Historique", "History")
        surface.blit(self.font.render(hist_title, True, theme.TEXT), (x, self.history_header_y))
        # À droite de l'en-tête : score en direct (requêtes) en mode normal ;
        # badge « Coup Unique » en mode Coup Unique (score = distance, à la fin).
        if self.one_shot:
            tag_img = self.font.render(i18n.t("Coup Unique", "One Shot"), True, theme.SLOT_SELECTED)
        else:
            tag_img = self.font.render(
                i18n.t(f"Score : {self.game.request_score}", f"Score: {self.game.request_score}"),
                True, theme.SLOT_SELECTED,
            )
        surface.blit(tag_img, tag_img.get_rect(topright=(self.panel.right - s(18), self.history_header_y)))
        self._draw_history(surface)

        if self.one_shot:
            # Pas de nouvelle question : on remplace la zone de saisie par un rappel.
            note = self.font_small.render(
                i18n.t("Déduis des indices, puis propose (1 essai).",
                       "Deduce from the clues, then submit (1 try)."),
                True, theme.TEXT_DIM)
            surface.blit(note, (x, self.input_rect.top - s(20)))
        else:
            # Zone de proposition (saisie d'un point d'entrée à interroger).
            label = self.font_small.render(
                i18n.t("Point de bord (5/C) ou case (A1) :", "Edge point (5/C) or cell (A1):"), True, theme.TEXT_DIM)
            surface.blit(label, (x, self.input_rect.top - s(20)))
            pygame.draw.rect(surface, theme.INPUT_BG, self.input_rect, border_radius=5)
            edge = theme.INPUT_ACTIVE if self.input_active else theme.BOARD_BORDER
            pygame.draw.rect(surface, edge, self.input_rect, width=2 if self.input_active else 1, border_radius=5)
            shown = self.input_text + ("|" if self.input_active else "")
            surface.blit(self.font.render(shown, True, theme.TEXT), (self.input_rect.x + s(8), self.input_rect.y + s(6)))

        if self.message:
            msg = self.font_small.render(self.message, True, self.message_color)
            surface.blit(msg, (x, self.input_rect.bottom + s(10)))

        hint = i18n.t(
            "clic=choisir/poser, double-clic=croix, clic sur une pièce=reprendre, [R] tourner, [C] couleur mystère, clic droit=retirer, [H] aide, [Maj+D] debug",
            "click=select/place, double-click=cross, click a piece=pick up, [R] rotate, [C] mystery color, right-click=remove, [H] help, [Shift+D] debug",
        )
        surface.blit(
            self.font_small.render(hint, True, theme.TEXT_DIM),
            (theme.PALETTE.x, self.size[1] - s(24)),
        )

    # --- Aide paginée ------------------------------------------------------

    _TITLE_H = theme.s(52)
    _FOOTER_H = theme.s(42)
    _MARGIN = theme.s(26)

    def _help_rows(self, content_width: int) -> list[tuple[int, "object"]]:
        """Construit la liste des lignes de l'aide (hauteur, fonction de dessin)."""
        rows: list[tuple[int, object]] = []

        def heading_draw(text: str):
            return lambda s, x, y, t=text: s.blit(self.font.render(t, True, theme.SLOT_SELECTED), (x, y))

        def line_draw(text: str):
            return lambda s, x, y, t=text: s.blit(self.font_small.render(t, True, theme.TEXT), (x, y))

        for head_fr, head_en, body_fr, body_en in _HELP:
            head = i18n.t(head_fr, head_en)
            if head_fr == "Couleurs":
                # La légende des couleurs forme un bloc insécable : une seule
                # « ligne » composite qui ne se coupe jamais entre deux pages
                # (mais partage une page avec ce qui précède si ça tient).
                block: list[tuple[int, object]] = [
                    (theme.s(28), heading_draw(head)),
                    (theme.s(22), line_draw(i18n.t(
                        "Le rayon se teinte au contact ; mélange peinture, le blanc éclaircit.",
                        "The beam is tinted on contact; paint-style mixing, white lightens."))),
                    (theme.s(22), line_draw(i18n.t(
                        "Aucune gemme touchée → rayon transparent.",
                        "No gem touched → transparent beam."))),
                ]
                col_w = content_width // 2  # deux colonnes de combinaisons
                for i in range(0, len(_COLOR_COMBOS), 2):
                    left = _COLOR_COMBOS[i]
                    right = _COLOR_COMBOS[i + 1] if i + 1 < len(_COLOR_COMBOS) else None
                    block.append((theme.s(26), self._combo_pair_drawer(left, right, col_w)))
                rows.append((sum(h for h, _ in block), _group_drawer(block)))
            else:
                rows.append((theme.s(28), heading_draw(head)))
                for wrapped in _wrap(i18n.t(body_fr, body_en), self.font_small, content_width):
                    rows.append((theme.s(22), line_draw(wrapped)))
            rows.append((theme.s(12), _spacer))  # espace entre sections
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
            s = theme.s
            cx = x
            inputs = [c for c in _COLOR_ORDER if c in combo]
            for i, gem_color in enumerate(inputs):
                if i > 0:
                    surface.blit(self.font_small.render("+", True, theme.TEXT_DIM), (cx, y + s(1)))
                    cx += s(13)
                _swatch(surface, cx, y, theme.GEM_FILL[gem_color])
                cx += s(20)
            surface.blit(self.font_small.render("=", True, theme.TEXT_DIM), (cx, y + s(1)))
            cx += s(18)
            name = i18n.color(mix_colors(combo))
            _swatch(surface, cx, y, theme.ray_rgb(mix_colors(combo)))
            cx += s(24)
            surface.blit(self.font_small.render(name, True, theme.TEXT), (cx, y + s(1)))

        return draw

    def _help_layout(self, size: tuple[int, int]) -> dict:
        s = theme.s
        w, h = size
        panel_w = min(s(680), w - s(80))
        max_panel_h = h - s(60)
        content_w = panel_w - 2 * self._MARGIN
        max_content_h = max_panel_h - self._TITLE_H - self._FOOTER_H

        rows = self._help_rows(content_w)
        pages = _paginate(rows, max_content_h)
        content_h = max((sum(rh for rh, _ in pg) for pg in pages), default=0)
        panel_h = self._TITLE_H + content_h + self._FOOTER_H
        px = (w - panel_w) // 2
        py = (h - panel_h) // 2
        panel = pygame.Rect(px, py, panel_w, panel_h)
        prev_rect = pygame.Rect(px + self._MARGIN, panel.bottom - s(36), s(40), s(28))
        next_rect = pygame.Rect(panel.right - self._MARGIN - s(40), panel.bottom - s(36), s(40), s(28))
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

        surface.blit(self.font_big.render(i18n.t("Comment jouer", "How to play"), True, theme.TEXT), (panel.x + self._MARGIN, panel.y + theme.s(16)))

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
        footer = i18n.t(
            f"Page {self.help_page + 1}/{len(pages)}   ·   ←/→ pages   ·   [H] fermer",
            f"Page {self.help_page + 1}/{len(pages)}   ·   ←/→ pages   ·   [H] close",
        )
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

        s = theme.s
        actions = self.game.clues
        if not actions:
            empty = self.font_small.render(i18n.t("Aucune question posée.", "No question asked yet."), True, theme.TEXT_DIM)
            surface.blit(empty, (rect.x + s(12), rect.y + s(10)))
            return

        content_h = len(actions) * _HISTORY_ROW_H + s(8)
        max_scroll = max(0.0, content_h - rect.height)
        if self.history_stick_bottom:
            self.history_scroll = max_scroll
        else:
            self.history_scroll = min(self.history_scroll, max_scroll)

        previous_clip = surface.get_clip()
        surface.set_clip(rect.inflate(s(-3), s(-3)))
        y0 = rect.y + s(6) - self.history_scroll
        for i, action in enumerate(actions):
            ry = y0 + i * _HISTORY_ROW_H
            if ry + _HISTORY_ROW_H >= rect.y and ry <= rect.bottom:
                self._draw_history_row(surface, rect.x + s(8), int(ry), action)
        surface.set_clip(previous_clip)

        # Barre de défilement cliquable/glissable (si le contenu déborde, #79).
        sb = self._history_scrollbar()
        if sb is not None:
            track, thumb, _, _ = sb
            pygame.draw.rect(surface, theme.SLOT_BG, track, border_radius=s(3))  # gouttière
            over = thumb.collidepoint(pygame.mouse.get_pos())
            if self._dragging_scroll:
                color = theme.SLOT_SELECTED
            elif over:
                color = theme.TEXT_DIM
            else:
                color = theme.BOARD_BORDER
            pygame.draw.rect(surface, color, thumb, border_radius=s(3))

    def _draw_history_row(
        self, surface: pygame.Surface, x: int, y: int, action: RayShot | CellQuery
    ) -> None:
        if isinstance(action, CellQuery):
            self._draw_query_row(surface, x, y, action)
        else:
            self._draw_shot_row(surface, x, y, action)

    def _draw_shot_row(self, surface: pygame.Surface, x: int, y: int, shot: RayShot) -> None:
        entry = theme.entry_label(shot.entry, shot.direction, self.grid.width, self.grid.height)
        if shot.result.absorbed:
            text, dot = f"{entry} → {i18n.color('absorbé')}", theme.RAY_ABSORBED
        else:
            text = f"{entry} → {self.ray.result_label(shot.result)}"
            dot = theme.ray_rgb(shot.result.color)
        pygame.draw.circle(surface, dot, (x + theme.s(6), y + theme.s(8)), theme.s(6))
        surface.blit(self.font_small.render(text, True, theme.TEXT), (x + theme.s(20), y))

    def _draw_query_row(self, surface: pygame.Surface, x: int, y: int, query: CellQuery) -> None:
        # Marqueur carré (vs cercle des tirs) pour distinguer d'un coup d'œil
        # une question de case d'un tir de rayon.
        text = f"{theme.cell_label(query.position)} → {_cell_answer_text(query.content)}"
        marker = pygame.Rect(x, y + theme.s(2), theme.s(12), theme.s(12))
        pygame.draw.rect(surface, self._query_marker_rgb(query.content), marker, border_radius=2)
        pygame.draw.rect(surface, theme.BOARD_BORDER, marker, width=1, border_radius=2)
        surface.blit(self.font_small.render(text, True, theme.TEXT), (x + theme.s(20), y))


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

# Chaque section : (titre FR, titre EN, corps FR, corps EN). Le titre FR sert
# aussi de clé interne (p. ex. le bloc insécable « Couleurs »).
_HELP: list[tuple[str, str, str, str]] = [
    (
        "But", "Goal",
        "Localise la position exacte de toutes les gemmes cachées de la mine.",
        "Find the exact position of every hidden gem in the mine.",
    ),
    (
        "Poser des hypothèses", "Place hypotheses",
        "Choisis une pièce dans la palette, puis clique sur le plateau pour la poser. "
        "Clique une pièce déjà posée pour la reprendre et la déplacer ; le clic droit la retire. "
        "Double-clique une case vide (sans pièce en main) pour y poser une croix « pas de "
        "gemme » ; double-clique encore pour l'enlever.",
        "Pick a piece from the palette, then click the board to place it. Click a placed "
        "piece to pick it up and move it; right-click removes it. Double-click an empty cell "
        "(with no piece held) to mark a “no gem” cross; double-click again to clear it.",
    ),
    (
        "Tester ton hypothèse", "Test your hypothesis",
        "Clique un point d'entrée sur le bord : un rayon rebondit sur TES pièces "
        "posées. Il part transparent et se teinte en touchant les gemmes.",
        "Click an entry point on the edge: a beam bounces off YOUR placed pieces. "
        "It starts transparent and gets tinted when it touches gems.",
    ),
    (
        "Interroger la mine", "Query the mine",
        "Saisis un point de bord (chiffre 1–18 ou lettre A–R) dans la zone de saisie "
        "puis Entrée : la vraie sortie et la couleur s'ajoutent à l'Historique.",
        "Enter an edge point (number 1–18 or letter A–R) in the input box then press "
        "Enter: the real exit and color are added to the History.",
    ),
    (
        "Interroger une case", "Query a cell",
        "Saisis une case « ligne-lettre + colonne-numéro » (ex. A1, C4) puis Entrée : "
        "la réponse (vide, couleur, ou nom d'une extension) s'ajoute à l'Historique.",
        "Enter a cell “row-letter + column-number” (e.g. A1, C4) then Enter: the "
        "answer (empty, a color, or an extension name) is added to the History.",
    ),
    (
        "Coup Unique", "One Shot",
        "Dans ce mode, des tirs te sont donnés d'avance (les Indices) et tu ne peux "
        "plus interroger la mine : déduis, place toutes les gemmes et propose une "
        "seule fois. Le score est la distance à la vérité (affichée à la fin).",
        "In this mode, beam tests are given up front (the Clues) and you can no "
        "longer query the mine: deduce, place every gem and submit once. The score "
        "is the distance to the truth (shown at the end).",
    ),
    (
        "Gemme mystère", "Mystery gem",
        "La gemme mystère a la taille du diamant mais une couleur cachée. "
        "Déduis-la (rayons, question de case) puis, en la posant, appuie sur [C] "
        "pour choisir la couleur que tu proposes. La vraie couleur est révélée à la fin.",
        "The mystery gem is diamond-sized but its color is hidden. Deduce it "
        "(beams, cell query) then, when placing it, press [C] to pick the color "
        "you guess. The true color is revealed at the end.",
    ),
    (
        "Déduire", "Deduce",
        "Rejoue les mêmes points sur tes hypothèses jusqu'à retrouver les vraies "
        "sorties et couleurs listées dans l'Historique.",
        "Replay the same points on your hypotheses until they match the real "
        "exits and colors listed in the History.",
    ),
    (
        "Gagner", "Win",
        "Quand tu es sûr de toi, clique « Proposer la solution ». Deux scores "
        "(plus bas = mieux) : le score de requêtes (tir = 1, question de case = 3, "
        "proposition ratée = 5) et, en fin de partie, la distance à la vérité. "
        "Le nombre de propositions peut être limité (bouton « Proposer (N essais) »).",
        "When you're confident, click “Submit solution”. Two scores (lower is "
        "better): the request score (beam = 1, cell query = 3, wrong guess = 5) "
        "and, at the end, the distance to the truth. The number of guesses can be "
        "limited (the “Submit (N left)” button).",
    ),
    (
        "Sauvegarder / charger", "Save / load",
        "« Sauvegarder » enregistre la partie ; coche « Progression » pour y "
        "inclure l'historique et tes pièces posées. Recharge-la depuis le menu "
        "de départ (« Charger… »).",
        "“Save” stores the game; tick “Progress” to also include the history and "
        "your placed pieces. Reload it from the start menu (“Load…”).",
    ),
    (
        "Couleurs", "Colors",
        "Le rayon mélange les couleurs comme de la peinture (rouge+jaune=orange, "
        "jaune+bleu=vert, rouge+bleu=violet…) ; le blanc éclaircit la teinte.",
        "The beam mixes colors like paint (red+yellow=orange, yellow+blue=green, "
        "red+blue=purple…); white lightens the shade.",
    ),
    (
        "Raccourcis", "Shortcuts",
        "[H] aide, [S] sauvegarder, [Maj+D] debug. [R] tourne/retourne la pièce ; [C] change la "
        "couleur de la gemme mystère ; clic sur une pièce posée = la reprendre ; clic droit = la retirer.",
        "[H] help, [S] save, [Shift+D] debug. [R] rotates/flips the piece; [C] changes the mystery "
        "gem color; click a placed piece to pick it up; right-click removes it.",
    ),
]


def _mmss(seconds: float, ceil: bool = True) -> str:
    """Formate une durée en M:SS. `ceil` arrondit au-dessus (compte à rebours :
    0:00 n'apparaît qu'à la toute fin) ; sinon au plancher (temps écoulé)."""
    total = max(0, int(seconds + 0.999) if ceil else int(seconds))
    return f"{total // 60}:{total % 60:02d}"


def _cell_answer_text(content: CellContent) -> str:
    """Réponse affichée à une question de case (vide / couleur / nom d'extension)."""
    if not content.occupied:
        return i18n.t("vide", "empty")
    if content.kind in _KIND_PIECE_NAME:  # extension : on annonce son nom
        return i18n.piece(_KIND_PIECE_NAME[content.kind])
    if content.color is not None:
        return i18n.color(content.color.value)
    return i18n.t("occupée", "occupied")


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


def _swatch(surface: pygame.Surface, x: int, y: int, rgb: tuple[int, int, int], size: int | None = None) -> None:
    """Dessine un petit carré de couleur (avec liseré) pour la légende des couleurs."""
    if size is None:
        size = theme.s(16)
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
