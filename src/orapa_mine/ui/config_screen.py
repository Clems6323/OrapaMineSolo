"""Écran de configuration de partie : difficulté, extensions, taille de grille.

Produit une `Difficulty` (via `self.result`) que l'app lit pour lancer la
partie. Aucune règle de jeu ici.
"""

from __future__ import annotations

import pygame

from orapa_mine.ai.generator import (
    DISALLOWED_EXTENSIONS_BY_SIZE,
    MAX_EXTENSIONS_BY_SIZE,
    Difficulty,
)
from orapa_mine.model import gems_catalog as cat
from orapa_mine.model import serialization
from orapa_mine.model.serialization import LoadedGame
from orapa_mine.ui import dialogs, i18n, lang_toggle, theme, theme_toggle
from orapa_mine.ui.timer_field import TimerField

SIZE = (760, 798)  # taille logique ; mise à l'échelle DPI dans __init__


class ConfigScreen:
    """Menu de configuration cliquable (rectangles + cases à cocher)."""

    # Attributs des extensions, dans l'ordre d'affichage (sert à compter et à
    # rogner les extensions au-delà du maximum autorisé — #75).
    _EXT_ATTRS = ("diamant", "corps_noir", "wormhole", "filter", "rainbow")

    def __init__(self) -> None:
        self.size = (theme.s(SIZE[0]), theme.s(SIZE[1]))
        self.diamant = False
        self.corps_noir = False
        self.wormhole = False
        self.filter = False
        self.rainbow = False
        self.sizes = [("Petit", 8, 6), ("Standard", 10, 8), ("Grand", 12, 10)]
        self.size_index = 1
        self.timer = TimerField()  # minuteur optionnel (0 = désactivé)
        self.result: Difficulty | None = None
        self.loaded: LoadedGame | None = None
        self.creator: Difficulty | None = None  # lancer le mode créateur
        self.error: str | None = None

        self.font_big = theme.font(40, bold=True)
        self.font = theme.font(20)
        self.font_small = theme.font(16)

        s = theme.s
        self.diamant_rect = pygame.Rect(s(170), s(228), s(26), s(26))
        self.corps_rect = pygame.Rect(s(170), s(266), s(26), s(26))
        self.wormhole_rect = pygame.Rect(s(170), s(304), s(26), s(26))
        self.filter_rect = pygame.Rect(s(170), s(342), s(26), s(26))
        self.rainbow_rect = pygame.Rect(s(170), s(380), s(26), s(26))
        # Zone cliquable de chaque ligne (case + libellé) : on peut cocher en
        # cliquant la case OU le texte (#35). Largeur ajustée au texte réel pour
        # ne pas offrir une zone de clic démesurée (#65).
        self._build_ext_rows()
        bw, gap = s(180), s(20)
        total = 3 * bw + 2 * gap
        start_x = (self.size[0] - total) // 2
        self.size_rects = [
            pygame.Rect(start_x + i * (bw + gap), s(462), bw, s(60)) for i in range(3)
        ]
        # Minuteur (stepper − valeur + éditable), centré sous le total de gemmes.
        self.timer.set_rects(
            pygame.Rect(s(271), s(620), s(44), s(40)),
            pygame.Rect(s(325), s(620), s(110), s(40)),
            pygame.Rect(s(445), s(620), s(44), s(40)),
        )

        bw2, gap2 = s(224), s(16)
        total2 = 3 * bw2 + 2 * gap2
        bx = (self.size[0] - total2) // 2
        self.start_rect = pygame.Rect(bx, s(692), bw2, s(58))
        self.creator_rect = pygame.Rect(bx + bw2 + gap2, s(692), bw2, s(58))
        self.load_rect = pygame.Rect(bx + 2 * (bw2 + gap2), s(692), bw2, s(58))

    # --- Événements --------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            self.timer.handle_key(event)
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        p = event.pos
        if theme_toggle.hit(p):  # bascule mode sombre / clair
            theme_toggle.toggle()
            return
        if lang_toggle.handle_click(p, self.size[0]):  # drapeaux FR / UK
            self._build_ext_rows()  # le texte change de langue → recalc des zones (#65)
            return
        if self.timer.handle_click(p):  # − / + / case du minuteur
            return
        if self.diamant_row.collidepoint(p):
            self._toggle_ext("diamant")
        elif self.corps_row.collidepoint(p):
            self._toggle_ext("corps_noir")
        elif self.wormhole_row.collidepoint(p):
            self._toggle_ext("wormhole")
        elif self.filter_row.collidepoint(p):
            self._toggle_ext("filter")
        elif self.rainbow_row.collidepoint(p):
            self._toggle_ext("rainbow")
        elif self.start_rect.collidepoint(p):
            self._begin()
        elif self.creator_rect.collidepoint(p):
            self.creator = self._difficulty()
        elif self.load_rect.collidepoint(p):
            self._load()
        else:
            for i, rect in enumerate(self.size_rects):
                if rect.collidepoint(p):
                    self.size_index = i
                    self._enforce_ext_rules()  # une grille plus petite restreint les extensions (#75)

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
        """(Dé)coche une extension ; refuse si interdite ou si le plafond est atteint."""
        if not getattr(self, attr) and self._ext_disabled(attr):
            return
        setattr(self, attr, not getattr(self, attr))

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

    def _load(self) -> None:
        path = dialogs.ask_open_path()
        if not path:
            return
        try:
            self.loaded = serialization.from_dict(dialogs.read_json(path))
        except (OSError, ValueError, KeyError) as exc:
            self.error = i18n.t("Chargement impossible : ", "Could not load: ") + str(exc)

    def _difficulty(self) -> Difficulty:
        """Construit la difficulté à partir des cases/boutons sélectionnés."""
        pieces = [cat.RED, cat.YELLOW, cat.BLUE, cat.WHITE_BIG, cat.WHITE_SMALL]
        if self.diamant:
            pieces.append(cat.DIAMOND)
        if self.filter:
            pieces.append(cat.FILTER)
        if self.corps_noir:
            pieces.append(cat.BLACK_BODY)
        if self.wormhole:
            pieces.append(cat.WORMHOLE)
        if self.rainbow:
            pieces.append(cat.RAINBOW)
        name, width, height = self.sizes[self.size_index]
        return Difficulty(
            pieces=pieces, width=width, height=height, name=name.lower(),
            timer_minutes=self.timer.minutes,
        )

    def _begin(self) -> None:
        self.result = self._difficulty()

    def update(self, dt: float) -> None:  # noqa: D401 - rien à animer
        pass

    # --- Rendu -------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        s = theme.s
        surface.fill(theme.BACKGROUND)
        theme_toggle.draw(surface)
        cx = self.size[0] // 2
        title = self.font_big.render("ORAPA MINE", True, theme.TEXT)
        surface.blit(title, title.get_rect(centerx=cx, y=s(56)))
        sub = self.font.render(i18n.t("Configuration de la partie", "Game setup"), True, theme.TEXT_DIM)
        surface.blit(sub, sub.get_rect(centerx=cx, y=s(108)))

        # Sélecteur de langue : drapeaux France / Royaume-Uni (haut droite).
        lang_toggle.draw(surface)

        base = self.font_small.render(
            i18n.t("Base : 1 rouge, 1 jaune, 1 bleu, 2 blanches (5 gemmes)",
                   "Base: 1 red, 1 yellow, 1 blue, 2 white (5 gems)"), True, theme.TEXT_DIM
        )
        surface.blit(base, (s(100), s(158)))

        ext_header = i18n.t("Extensions", "Extensions") + f"  ({self._ext_count()}/{self._max_ext()})"
        surface.blit(self.font.render(ext_header, True, theme.TEXT), (s(100), s(196)))
        d_txt, c_txt, w_txt, f_txt, r_txt = self._ext_label_texts()
        # Cases grisées : extension interdite pour la taille, ou plafond atteint (#75).
        self._checkbox(surface, self.diamant_rect, self.diamant, d_txt, disabled=self._ext_disabled("diamant"))
        self._checkbox(surface, self.corps_rect, self.corps_noir, c_txt, disabled=self._ext_disabled("corps_noir"))
        self._checkbox(surface, self.wormhole_rect, self.wormhole, w_txt, disabled=self._ext_disabled("wormhole"))
        self._checkbox(surface, self.filter_rect, self.filter, f_txt, disabled=self._ext_disabled("filter"))
        self._checkbox(surface, self.rainbow_rect, self.rainbow, r_txt, disabled=self._ext_disabled("rainbow"))

        surface.blit(self.font.render(i18n.t("Taille de la grille", "Grid size"), True, theme.TEXT), (s(100), s(422)))
        for i, rect in enumerate(self.size_rects):
            selected = i == self.size_index
            bg = theme.SLOT_SELECTED if selected else theme.SLOT_BG
            pygame.draw.rect(surface, bg, rect, border_radius=8)
            pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1, border_radius=8)
            name, w, h = self.sizes[i]
            fg = theme.ON_ACCENT if selected else theme.TEXT
            n = self.font.render(i18n.size_name(name), True, fg)
            d = self.font_small.render(f"{w} × {h}", True, fg if selected else theme.TEXT_DIM)
            surface.blit(n, n.get_rect(centerx=rect.centerx, y=rect.y + s(10)))
            surface.blit(d, d.get_rect(centerx=rect.centerx, y=rect.y + s(34)))

        total = (5 + (1 if self.diamant else 0) + (1 if self.filter else 0)
                 + (1 if self.corps_noir else 0) + (2 if self.wormhole else 0)
                 + (1 if self.rainbow else 0))
        count = self.font_small.render(
            i18n.t(f"Total : {total} gemmes à trouver", f"Total: {total} gems to find"), True, theme.TEXT_DIM)
        surface.blit(count, count.get_rect(centerx=cx, y=s(564)))

        # Minuteur (optionnel) : label + stepper − valeur + (éditable au clavier).
        timer_label = self.font.render(i18n.t("Minuteur", "Timer"), True, theme.TEXT)
        surface.blit(timer_label, timer_label.get_rect(centerx=cx, y=s(590)))
        self.timer.draw(surface, self.font, i18n.t("Désactivé", "Off"))

        self._button(surface, self.start_rect, theme.BTN_GREEN, i18n.t("Commencer", "Start"), theme.BTN_TEXT)
        self._button(surface, self.creator_rect, theme.BTN_BLUE, i18n.t("Mode créateur", "Creator mode"), theme.BTN_TEXT)
        self._button(surface, self.load_rect, theme.SLOT_BG, i18n.t("Charger…", "Load…"))

        if self.error:
            err = self.font_small.render(self.error, True, theme.LOSE_COLOR)
            surface.blit(err, err.get_rect(centerx=cx, y=s(762)))

    def _button(self, surface: pygame.Surface, rect: pygame.Rect, bg, text: str, text_color=None) -> None:
        pygame.draw.rect(surface, bg, rect, border_radius=10)
        pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1, border_radius=10)
        label = self.font.render(text, True, text_color or theme.TEXT)
        surface.blit(label, label.get_rect(center=rect.center))

    def _ext_label_texts(self) -> list[str]:
        """Libellés des extensions (source unique pour le rendu et les zones cliquables)."""
        return [
            i18n.t("Diamant (dévie sans teinter)", "Diamond (deviates without tinting)"),
            i18n.t("Corps noir (absorbe le rayon)", "Black body (absorbs the beam)"),
            i18n.t("Trou de ver ×2 (téléporte le rayon)", "Wormhole ×2 (teleports the beam)"),
            i18n.t("Filtre (remet le rayon transparent)", "Filter (resets the beam to transparent)"),
            i18n.t("Arc-en-ciel (carré 4 couleurs)", "Rainbow (4-color square)"),
        ]

    def _build_ext_rows(self) -> None:
        """Zones cliquables des extensions, ajustées à la largeur du texte (#65)."""
        s = theme.s
        gap, pad = s(14), s(12)  # écart case→texte (cf. _checkbox) + marge droite
        boxes = [
            self.diamant_rect, self.corps_rect, self.wormhole_rect,
            self.filter_rect, self.rainbow_rect,
        ]
        rows = [
            pygame.Rect(cb.x, cb.y, cb.width + gap + self.font.size(text)[0] + pad, cb.height)
            for cb, text in zip(boxes, self._ext_label_texts())
        ]
        (self.diamant_row, self.corps_row, self.wormhole_row,
         self.filter_row, self.rainbow_row) = rows

    def _checkbox(self, surface: pygame.Surface, rect: pygame.Rect, on: bool, text: str, disabled: bool = False) -> None:
        pygame.draw.rect(surface, theme.INPUT_BG, rect, border_radius=4)
        pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1, border_radius=4)
        if on:
            inner = rect.inflate(theme.s(-8), theme.s(-8))
            pygame.draw.rect(surface, theme.SLOT_SELECTED, inner, border_radius=3)
        label = self.font.render(text, True, theme.TEXT_DIM if disabled else theme.TEXT)
        surface.blit(label, (rect.right + theme.s(14), rect.y + theme.s(2)))
