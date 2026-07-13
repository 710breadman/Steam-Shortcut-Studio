from __future__ import annotations

from dataclasses import dataclass
from tkinter import StringVar

import customtkinter as ctk

from steam_shortcut_studio.selection import SelectionState


PALETTES = {
    "Ocean Blue": {
        "accent": "#1677ff",
        "accent_hover": "#2f8cff",
        "selected": "#0f315f",
        "border": "#1d4f8f",
    },
    "Orion Purple": {
        "accent": "#7c3aed",
        "accent_hover": "#8b5cf6",
        "selected": "#35205c",
        "border": "#6640a5",
    },
    "Forest Green": {
        "accent": "#12a66a",
        "accent_hover": "#22bd7b",
        "selected": "#163f35",
        "border": "#26745c",
    },
    "Solar Amber": {
        "accent": "#d97706",
        "accent_hover": "#f59e0b",
        "selected": "#4a3218",
        "border": "#8a5b1f",
    },
    "Rose": {
        "accent": "#db2777",
        "accent_hover": "#ec4899",
        "selected": "#51223e",
        "border": "#8e3765",
    },
}

COLORS = {
    "window": "#07111f",
    "sidebar": "#081625",
    "panel": "#0b1b2c",
    "panel_alt": "#0d2135",
    "panel_soft": "#10263b",
    "line": "#1c3147",
    "text": "#f1f5f9",
    "muted": "#8fa3b8",
    "success": "#34c878",
    "warning": "#f5b942",
    "danger": "#ef5350",
}


@dataclass(frozen=True, slots=True)
class MockGame:
    game_id: str
    title: str
    source: str
    platform: str
    last_played: str
    size: str
    status: str


GAMES = [
    MockGame("gow", "God of War", "Steam", "Steam", "May 9, 2024", "70.4 GB", "Protected"),
    MockGame("cp2077", "Cyberpunk 2077", "Steam", "Steam", "May 7, 2024", "78.1 GB", "Ready"),
    MockGame("elden", "Elden Ring", "Steam", "Steam", "May 5, 2024", "60.1 GB", "Protected"),
    MockGame("rdr2", "Red Dead Redemption 2", "Rockstar", "Windows", "Apr 28, 2024", "119 GB", "Review"),
    MockGame("fh5", "Forza Horizon 5", "Xbox App", "Windows", "Apr 27, 2024", "103 GB", "Review"),
    MockGame("hades", "Hades", "Steam", "Steam", "Apr 25, 2024", "15.1 GB", "Ready"),
    MockGame("bg3", "Baldur's Gate 3", "Steam", "Steam", "Apr 20, 2024", "122 GB", "Protected"),
    MockGame("spider", "Marvel's Spider-Man Remastered", "Steam", "Steam", "Apr 18, 2024", "66.8 GB", "Ready"),
    MockGame("hzd", "Horizon Zero Dawn Complete Edition", "Epic", "Windows", "Apr 12, 2024", "74.5 GB", "Review"),
    MockGame("witcher", "The Witcher 3: Wild Hunt", "GOG", "Windows", "Apr 10, 2024", "50.3 GB", "Ready"),
    MockGame("control", "Control Ultimate Edition", "Epic", "Windows", "Apr 4, 2024", "42.7 GB", "Review"),
    MockGame("persona", "Persona 5 Royal", "Steam", "Steam", "Mar 30, 2024", "41.8 GB", "Protected"),
]


def initial_selection_state(games: list[MockGame]) -> SelectionState:
    selection = SelectionState()
    if games:
        selection.replace((games[0].game_id,))
        selection.set_active(games[0].game_id)
    return selection


class ModernShell(ctk.CTk):
    def __init__(self) -> None:
        super().__init__(fg_color=COLORS["window"])
        self.title("Steam Shortcut Studio — Modern UI Prototype")
        self.geometry("1440x900")
        self.minsize(1100, 700)

        self.palette_name = "Ocean Blue"
        self.palette = PALETTES[self.palette_name]
        self.selection = initial_selection_state(GAMES)
        self.row_frames: dict[str, ctk.CTkFrame] = {}
        self.row_checks: dict[str, ctk.CTkCheckBox] = {}
        self.status_text = StringVar(value="Read-only prototype — no Steam files can be changed")

        self.grid_columnconfigure(0, minsize=210)
        self.grid_columnconfigure(1, weight=5, minsize=480)
        self.grid_columnconfigure(2, weight=6, minsize=470)
        self.grid_rowconfigure(1, weight=1)

        self._build_sidebar()
        self._build_topbar()
        self._build_library()
        self._build_inspector()
        self._build_footer()
        self._refresh_selection_ui()

    @property
    def selected_ids(self) -> set[str]:
        return self.selection.selected_ids

    @selected_ids.setter
    def selected_ids(self, item_ids: set[str]) -> None:
        self.selection.replace(item_ids)

    @property
    def active_id(self) -> str:
        return self.selection.active_id or ""

    @active_id.setter
    def active_id(self, item_id: str) -> None:
        self.selection.set_active(item_id or None)

    def _font(self, size: int, weight: str = "normal") -> ctk.CTkFont:
        return ctk.CTkFont(family="Segoe UI", size=size, weight=weight)

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, fg_color=COLORS["sidebar"], corner_radius=0)
        sidebar.grid(row=0, column=0, rowspan=3, sticky="nsew")
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(12, weight=1)

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, padx=18, pady=(22, 24), sticky="ew")
        ctk.CTkLabel(
            brand,
            text="◉",
            text_color=self.palette["accent"],
            font=self._font(34, "bold"),
        ).pack(side="left", padx=(0, 10))
        title = ctk.CTkFrame(brand, fg_color="transparent")
        title.pack(side="left", fill="x")
        ctk.CTkLabel(title, text="STEAM", anchor="w", font=self._font(15, "bold")).pack(fill="x")
        ctk.CTkLabel(title, text="SHORTCUT STUDIO", anchor="w", font=self._font(12, "bold")).pack(fill="x")
        ctk.CTkLabel(title, text="prototype", anchor="w", text_color=COLORS["muted"], font=self._font(10)).pack(fill="x")

        navigation = [
            ("▦", "Library"),
            ("↗", "Shortcuts"),
            ("▧", "Artwork"),
            ("≡", "Metadata"),
            ("⌕", "Import / Scan"),
            ("◈", "Backups"),
            ("⚙", "Settings"),
        ]
        for index, (icon, label) in enumerate(navigation, start=1):
            selected = label == "Library"
            button = ctk.CTkButton(
                sidebar,
                text=f"{icon}   {label}",
                anchor="w",
                height=44,
                corner_radius=9,
                fg_color=self.palette["selected"] if selected else "transparent",
                hover_color=COLORS["panel_soft"],
                border_width=1 if selected else 0,
                border_color=self.palette["border"],
                text_color=COLORS["text"] if selected else "#b7c5d4",
                font=self._font(13, "bold" if selected else "normal"),
                command=lambda value=label: self._set_status(f"Prototype navigation: {value}"),
            )
            button.grid(row=index, column=0, padx=12, pady=3, sticky="ew")

        appearance = ctk.CTkFrame(sidebar, fg_color=COLORS["panel"], corner_radius=12)
        appearance.grid(row=13, column=0, padx=12, pady=(8, 10), sticky="ew")
        ctk.CTkLabel(
            appearance,
            text="APPEARANCE",
            anchor="w",
            text_color=COLORS["muted"],
            font=self._font(10, "bold"),
        ).pack(fill="x", padx=12, pady=(10, 6))
        chips = ctk.CTkFrame(appearance, fg_color="transparent")
        chips.pack(fill="x", padx=10, pady=(0, 10))
        for name, palette in PALETTES.items():
            ctk.CTkButton(
                chips,
                text="",
                width=24,
                height=24,
                corner_radius=12,
                fg_color=palette["accent"],
                hover_color=palette["accent_hover"],
                border_width=2 if name == self.palette_name else 0,
                border_color="#dceeff",
                command=lambda value=name: self._change_palette(value),
            ).pack(side="left", padx=4)

        library_card = ctk.CTkFrame(sidebar, fg_color=COLORS["panel"], corner_radius=12)
        library_card.grid(row=14, column=0, padx=12, pady=(0, 18), sticky="ew")
        ctk.CTkLabel(library_card, text="▱  Steam Library", anchor="w", font=self._font(12, "bold")).pack(fill="x", padx=12, pady=(12, 2))
        ctk.CTkLabel(library_card, text="D:\\SteamLibrary", anchor="w", text_color=COLORS["muted"], font=self._font(10)).pack(fill="x", padx=12)
        ctk.CTkProgressBar(library_card, height=7, progress_color=self.palette["accent"]).pack(fill="x", padx=12, pady=(12, 4))
        library_card.winfo_children()[-1].set(0.76)
        ctk.CTkLabel(library_card, text="1.42 TB of 1.86 TB", anchor="w", text_color=COLORS["muted"], font=self._font(10)).pack(fill="x", padx=12, pady=(0, 12))

    def _build_topbar(self) -> None:
        topbar = ctk.CTkFrame(self, fg_color=COLORS["panel"], corner_radius=12)
        topbar.grid(row=0, column=1, columnspan=2, padx=(12, 14), pady=(12, 8), sticky="ew")
        topbar.grid_columnconfigure(5, weight=1)

        actions = [
            ("⌕", "Scan", "Folders & libraries"),
            ("↻", "Refresh Metadata", "Update info"),
            ("✦", "Auto-Art", "Find matches"),
            ("◫", "Preview", "Review changes"),
        ]
        for column, (icon, title, subtitle) in enumerate(actions):
            button = ctk.CTkButton(
                topbar,
                text=f"{icon}  {title}\n    {subtitle}",
                anchor="w",
                width=160 if column else 135,
                height=52,
                corner_radius=9,
                fg_color="transparent",
                hover_color=COLORS["panel_soft"],
                text_color=COLORS["text"],
                font=self._font(12, "bold"),
                command=lambda value=title: self._set_status(f"Prototype action: {value}"),
            )
            button.grid(row=0, column=column, padx=(6 if column else 10, 2), pady=8)

        ctk.CTkLabel(
            topbar,
            text="READ ONLY",
            text_color=COLORS["warning"],
            font=self._font(10, "bold"),
        ).grid(row=0, column=5, padx=10, sticky="e")
        self.apply_button = ctk.CTkButton(
            topbar,
            text="Apply Changes  ▾\nSafety gate locked",
            width=190,
            height=52,
            corner_radius=9,
            fg_color="#23415f",
            hover_color="#294a6b",
            text_color="#91a8bc",
            state="disabled",
            font=self._font(12, "bold"),
        )
        self.apply_button.grid(row=0, column=6, padx=(4, 10), pady=8)

    def _build_library(self) -> None:
        container = ctk.CTkFrame(self, fg_color=COLORS["panel"], corner_radius=12)
        container.grid(row=1, column=1, padx=(12, 6), pady=(0, 8), sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(3, weight=1)

        controls = ctk.CTkFrame(container, fg_color="transparent")
        controls.grid(row=0, column=0, padx=12, pady=(12, 8), sticky="ew")
        controls.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(
            controls,
            placeholder_text="Search games...",
            height=38,
            corner_radius=8,
            border_color=COLORS["line"],
            fg_color=COLORS["window"],
        ).grid(row=0, column=0, padx=(0, 8), sticky="ew")
        ctk.CTkOptionMenu(
            controls,
            values=["All Games (842)", "Steam", "Non-Steam", "Needs Review", "Missing Artwork"],
            width=150,
            height=38,
            fg_color=COLORS["panel_soft"],
            button_color=COLORS["panel_soft"],
            button_hover_color=self.palette["selected"],
            command=lambda value: self._set_status(f"Filter: {value}"),
        ).grid(row=0, column=1)

        header = ctk.CTkFrame(container, fg_color=COLORS["window"], corner_radius=7, height=34)
        header.grid(row=1, column=0, padx=12, sticky="ew")
        for column, (text, weight) in enumerate(
            [("", 0), ("TITLE", 4), ("SOURCE", 2), ("PLATFORM", 2), ("LAST PLAYED", 2), ("SIZE", 1)]
        ):
            header.grid_columnconfigure(column, weight=weight, minsize=34 if column == 0 else 60)
            ctk.CTkLabel(
                header,
                text=text,
                anchor="w",
                text_color=COLORS["muted"],
                font=self._font(10, "bold"),
            ).grid(row=0, column=column, padx=6, pady=8, sticky="ew")

        self.game_list = ctk.CTkScrollableFrame(container, fg_color="transparent", corner_radius=0)
        self.game_list.grid(row=3, column=0, padx=8, pady=6, sticky="nsew")
        self.game_list.grid_columnconfigure(0, weight=1)
        for game in GAMES:
            self._add_game_row(game)

        self.bulk_bar = ctk.CTkFrame(container, fg_color=COLORS["panel_soft"], corner_radius=9)
        self.bulk_bar.grid(row=4, column=0, padx=12, pady=(4, 12), sticky="ew")
        self.bulk_bar.grid_columnconfigure(1, weight=1)
        self.selection_label = ctk.CTkLabel(self.bulk_bar, text="", font=self._font(11, "bold"))
        self.selection_label.grid(row=0, column=0, padx=12, pady=9)
        actions = ["Scan Selected", "Find Art", "Refresh Metadata", "Preview"]
        for index, action in enumerate(actions, start=2):
            ctk.CTkButton(
                self.bulk_bar,
                text=action,
                width=105 if action != "Refresh Metadata" else 130,
                height=31,
                corner_radius=7,
                fg_color=self.palette["accent"] if action == "Find Art" else COLORS["panel"],
                hover_color=self.palette["accent_hover"] if action == "Find Art" else COLORS["line"],
                command=lambda value=action: self._bulk_action(value),
            ).grid(row=0, column=index, padx=3, pady=7)

    def _add_game_row(self, game: MockGame) -> None:
        row = ctk.CTkFrame(
            self.game_list,
            fg_color=self.palette["selected"] if game.game_id == self.active_id else COLORS["panel_alt"],
            corner_radius=8,
            border_width=1,
            border_color=self.palette["border"] if game.game_id == self.active_id else COLORS["line"],
        )
        row.grid(sticky="ew", padx=2, pady=3)
        row.grid_columnconfigure(1, weight=4, minsize=190)
        row.grid_columnconfigure(2, weight=2, minsize=80)
        row.grid_columnconfigure(3, weight=2, minsize=70)
        row.grid_columnconfigure(4, weight=2, minsize=90)
        row.grid_columnconfigure(5, weight=1, minsize=60)

        checkbox = ctk.CTkCheckBox(
            row,
            text="",
            width=24,
            checkbox_width=18,
            checkbox_height=18,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            command=lambda item=game.game_id: self._toggle_selected(item),
        )
        checkbox.grid(row=0, column=0, padx=(8, 2), pady=10)
        if game.game_id in self.selected_ids:
            checkbox.select()

        title = ctk.CTkLabel(row, text=game.title, anchor="w", font=self._font(11, "bold"))
        title.grid(row=0, column=1, padx=6, pady=10, sticky="ew")
        title.bind("<Button-1>", lambda _event, item=game.game_id: self._activate(item))

        for column, value in enumerate(
            [game.source, game.platform, game.last_played, game.size], start=2
        ):
            label = ctk.CTkLabel(
                row,
                text=value,
                anchor="w",
                text_color="#b8c6d5",
                font=self._font(10),
            )
            label.grid(row=0, column=column, padx=6, pady=10, sticky="ew")
            label.bind("<Button-1>", lambda _event, item=game.game_id: self._activate(item))

        self.row_frames[game.game_id] = row
        self.row_checks[game.game_id] = checkbox

    def _build_inspector(self) -> None:
        inspector = ctk.CTkFrame(self, fg_color=COLORS["panel"], corner_radius=12)
        inspector.grid(row=1, column=2, padx=(6, 14), pady=(0, 8), sticky="nsew")
        inspector.grid_columnconfigure(0, weight=1)
        inspector.grid_rowconfigure(2, weight=1)

        heading = ctk.CTkFrame(inspector, fg_color="transparent")
        heading.grid(row=0, column=0, padx=14, pady=(14, 8), sticky="ew")
        heading.grid_columnconfigure(1, weight=1)
        avatar = ctk.CTkFrame(heading, width=52, height=52, fg_color="#3a2930", corner_radius=9)
        avatar.grid(row=0, column=0, rowspan=2, padx=(0, 12))
        avatar.grid_propagate(False)
        ctk.CTkLabel(avatar, text="GOW", font=self._font(12, "bold")).place(relx=0.5, rely=0.5, anchor="center")
        self.inspector_title = ctk.CTkLabel(heading, text="God of War", anchor="w", font=self._font(20, "bold"))
        self.inspector_title.grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(
            heading,
            text="Steam App ID: 1593500   •   Installed   •   Last played May 9, 2024",
            anchor="w",
            text_color=COLORS["muted"],
            font=self._font(10),
        ).grid(row=1, column=1, sticky="ew")

        tabs = ctk.CTkSegmentedButton(
            inspector,
            values=["Artwork", "Details", "Metadata", "Links", "Local Files"],
            selected_color=self.palette["accent"],
            selected_hover_color=self.palette["accent_hover"],
            unselected_color=COLORS["panel_alt"],
            unselected_hover_color=COLORS["panel_soft"],
            command=lambda value: self._set_status(f"Inspector tab: {value}"),
        )
        tabs.set("Artwork")
        tabs.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="ew")

        body = ctk.CTkScrollableFrame(inspector, fg_color="transparent")
        body.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")
        body.grid_columnconfigure((0, 1), weight=1)

        self._art_card(body, 0, 0, "Portrait", "600 × 900", "GOD\nOF\nWAR", 156)
        self._art_card(body, 0, 1, "Wide Capsule", "616 × 353", "GOD OF WAR", 156)
        self._art_card(body, 1, 0, "Hero", "1920 × 620", "GOD OF WAR — HERO", 125)
        self._art_card(body, 1, 1, "Logo", "512 × 256", "GOD OF WAR", 125)
        self._art_card(body, 2, 0, "Icon", "256 × 256", "Ω", 120)

        source = ctk.CTkFrame(body, fg_color=COLORS["panel_alt"], corner_radius=10, border_width=1, border_color=COLORS["line"])
        source.grid(row=2, column=1, padx=5, pady=5, sticky="nsew")
        ctk.CTkLabel(source, text="AUTO-ART SOURCE", anchor="w", text_color=COLORS["muted"], font=self._font(10, "bold")).pack(fill="x", padx=12, pady=(12, 6))
        ctk.CTkOptionMenu(
            source,
            values=["SteamGridDB", "Official Steam", "Local Files", "Wikimedia", "RAWG"],
            fg_color=COLORS["panel_soft"],
            button_color=COLORS["panel_soft"],
            button_hover_color=self.palette["selected"],
        ).pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(source, text="Match confidence                              92%", anchor="w", text_color=COLORS["success"], font=self._font(10, "bold")).pack(fill="x", padx=12, pady=(12, 5))
        progress = ctk.CTkProgressBar(source, height=7, progress_color=COLORS["success"])
        progress.pack(fill="x", padx=12, pady=(0, 12))
        progress.set(0.92)

        safety = ctk.CTkFrame(body, fg_color=COLORS["panel_alt"], corner_radius=10, border_width=1, border_color=COLORS["line"])
        safety.grid(row=3, column=0, columnspan=2, padx=5, pady=(10, 5), sticky="ew")
        safety.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkLabel(safety, text="SAFETY & BACKUP", anchor="w", text_color="#68aefc", font=self._font(11, "bold")).grid(row=0, column=0, columnspan=3, padx=12, pady=(12, 4), sticky="ew")
        self._safety_card(safety, 0, "▣", "Backup Ready", "Grouped restore point")
        self._safety_card(safety, 1, "✓", "Write Verification", "Read-back required")
        self._safety_card(safety, 2, "↶", "Rollback Available", "Automatic on failure")
        ctk.CTkLabel(
            safety,
            text="Prototype mode: apply is intentionally disabled until production transaction integration is complete.",
            anchor="w",
            text_color=COLORS["muted"],
            font=self._font(10),
        ).grid(row=2, column=0, columnspan=3, padx=12, pady=(4, 12), sticky="ew")

    def _art_card(
        self,
        parent: ctk.CTkScrollableFrame,
        row: int,
        column: int,
        title: str,
        dimensions: str,
        preview: str,
        height: int,
    ) -> None:
        card = ctk.CTkFrame(parent, fg_color=COLORS["panel_alt"], corner_radius=10, border_width=1, border_color=COLORS["line"])
        card.grid(row=row, column=column, padx=5, pady=5, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=f"{title}   {dimensions}   ✓", anchor="w", text_color="#c8d8e8", font=self._font(10, "bold")).grid(row=0, column=0, padx=10, pady=(10, 6), sticky="ew")
        preview_box = ctk.CTkFrame(card, height=height, fg_color="#172f4b", corner_radius=8)
        preview_box.grid(row=1, column=0, padx=10, sticky="ew")
        preview_box.grid_propagate(False)
        ctk.CTkLabel(preview_box, text=preview, text_color="#dceeff", font=self._font(16, "bold")).place(relx=0.5, rely=0.5, anchor="center")
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.grid(row=2, column=0, padx=8, pady=8, sticky="ew")
        for index, label in enumerate(["Auto Match", "Review", "Replace", "Clear"]):
            ctk.CTkButton(
                buttons,
                text=label,
                height=28,
                width=72,
                corner_radius=6,
                fg_color=self.palette["accent"] if label == "Auto Match" else "transparent",
                hover_color=self.palette["accent_hover"] if label == "Auto Match" else COLORS["panel_soft"],
                border_width=0 if label == "Auto Match" else 1,
                border_color=COLORS["line"],
                text_color=COLORS["danger"] if label == "Clear" else COLORS["text"],
                font=self._font(9, "bold"),
                command=lambda value=f"{title}: {label}": self._set_status(f"Prototype action: {value}"),
            ).pack(side="left", expand=True, fill="x", padx=2)

    def _safety_card(self, parent: ctk.CTkFrame, column: int, icon: str, title: str, detail: str) -> None:
        card = ctk.CTkFrame(parent, fg_color=COLORS["panel_soft"], corner_radius=8)
        card.grid(row=1, column=column, padx=6, pady=6, sticky="ew")
        ctk.CTkLabel(card, text=f"{icon}  {title}", anchor="w", text_color=COLORS["success"], font=self._font(10, "bold")).pack(fill="x", padx=10, pady=(9, 2))
        ctk.CTkLabel(card, text=detail, anchor="w", text_color=COLORS["muted"], font=self._font(9)).pack(fill="x", padx=10, pady=(0, 9))

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color=COLORS["sidebar"], corner_radius=0, height=30)
        footer.grid(row=2, column=1, columnspan=2, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(footer, textvariable=self.status_text, anchor="w", text_color=COLORS["muted"], font=self._font(10)).grid(row=0, column=0, padx=14, pady=6, sticky="ew")
        ctk.CTkLabel(footer, text="●  Steam connection: mock", text_color=COLORS["success"], font=self._font(10)).grid(row=0, column=1, padx=14)

    def _toggle_selected(self, game_id: str) -> None:
        self.selection.toggle(game_id)
        self._refresh_selection_ui()

    def _activate(self, game_id: str) -> None:
        self.selection.set_active(game_id)
        game = next(item for item in GAMES if item.game_id == game_id)
        self.inspector_title.configure(text=game.title)
        self._refresh_selection_ui()
        self._set_status(f"Inspector opened: {game.title}")

    def _refresh_selection_ui(self) -> None:
        for game_id, row in self.row_frames.items():
            active = game_id == self.active_id
            row.configure(
                fg_color=self.palette["selected"] if active else COLORS["panel_alt"],
                border_color=self.palette["border"] if active else COLORS["line"],
            )
            check = self.row_checks[game_id]
            check.configure(fg_color=self.palette["accent"], hover_color=self.palette["accent_hover"])
            if game_id in self.selected_ids:
                check.select()
            else:
                check.deselect()

        count = len(self.selected_ids)
        self.selection_label.configure(text=f"{count} selected")
        if count:
            self.bulk_bar.grid()
        else:
            self.bulk_bar.grid_remove()

    def _bulk_action(self, action: str) -> None:
        count = len(self.selected_ids)
        self._set_status(f"Prototype: {action} would process {count} selected game{'s' if count != 1 else ''}")

    def _change_palette(self, name: str) -> None:
        self.palette_name = name
        self.palette = PALETTES[name]
        self.apply_button.configure(border_color=self.palette["border"])
        self._refresh_selection_ui()
        self._set_status(f"Accent preview changed to {name}; restart prototype for full palette refresh")

    def _set_status(self, message: str) -> None:
        self.status_text.set(message)


def main() -> None:
    ctk.set_appearance_mode("dark")
    app = ModernShell()
    app.mainloop()


if __name__ == "__main__":
    main()
