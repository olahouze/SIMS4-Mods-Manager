"""
Dark modern styling system for SIMS4-Mods-Manager with rich aesthetics.
"""

from src.ui.styles.global_qss import DARK_THEME_QSS

__all__ = ["DARK_THEME_QSS", "Theme"]


class Theme:
    """Design tokens and reusable stylesheet generators to maintain DRY styling across all Qt components."""

    # Color tokens
    BG_DARK = "#0f111a"
    BG_CARD = "#141b2c"
    BG_CARD_ALT = "#121829"
    BORDER_DEFAULT = "#232f48"
    BORDER_MUTED = "#334155"
    BORDER_PRIMARY = "#2563eb"
    PRIMARY = "#4f46e5"
    PRIMARY_HOVER = "#6366f1"

    BADGE_PALETTES = {
        "success": {"bg": "#064e3b", "fg": "#a7f3d0", "border": "#059669"},
        "danger": {"bg": "#450a0a", "fg": "#fca5a5", "border": "#dc2626"},
        "warning": {"bg": "#451a03", "fg": "#fde68a", "border": "#d97706"},
        "info": {"bg": "#1e3a8a", "fg": "#93c5fd", "border": "#2563eb"},
        "purple": {"bg": "#3b0764", "fg": "#e9d5ff", "border": "#7e22ce"},
        "neutral": {"bg": "#1e293b", "fg": "#94a3b8", "border": "#475569"},
    }

    @classmethod
    def badge_style(cls, variant: str = "neutral", font_size: int = 10, padding: str = "1px 6px") -> str:
        """Exécute l'opération badge style.

        Args:
            variant: Paramètre variant.
            font_size: Paramètre font_size.
            padding: Paramètre padding.

        Returns:
            Résultat de l'opération badge_style.
        """
        palette = cls.BADGE_PALETTES.get(variant, cls.BADGE_PALETTES["neutral"])
        return f"""
            color: {palette["fg"]};
            background-color: {palette["bg"]};
            border: 1px solid {palette["border"]};
            border-radius: 4px;
            padding: {padding};
            font-size: {font_size}px;
            font-weight: 600;
        """

    @classmethod
    def card_frame_style(
        cls,
        interactive: bool = False,
        dashed: bool = False,
        bg: str | None = None,
        border: str | None = None,
        radius: int = 6,
        padding: str = "4px 8px",
    ) -> str:
        """Exécute l'opération card frame style.

        Args:
            interactive: Paramètre interactive.
            dashed: Paramètre dashed.
            bg: Paramètre bg.
            border: Paramètre border.
            radius: Paramètre radius.
            padding: Paramètre padding.

        Returns:
            Résultat de l'opération card_frame_style.
        """
        b_type = "dashed" if dashed else "solid"
        bg_col = bg or cls.BG_CARD
        b_col = border or cls.BORDER_DEFAULT
        hover_block = f"QFrame:hover {{ border-color: {cls.PRIMARY_HOVER}; }}" if interactive else ""
        return f"""
            QFrame {{
                background-color: {bg_col};
                border: 1px {b_type} {b_col};
                border-radius: {radius}px;
                padding: {padding};
            }}
            {hover_block}
        """

    @classmethod
    def action_button_style(
        cls,
        variant: str = "primary",
        font_size: int = 11,
        radius: int = 6,
        padding: str = "4px 10px",
    ) -> str:
        """Exécute l'opération action button style.

        Args:
            variant: Paramètre variant.
            font_size: Paramètre font_size.
            radius: Paramètre radius.
            padding: Paramètre padding.

        Returns:
            Résultat de l'opération action_button_style.
        """
        if variant == "primary":
            return f"""
                QPushButton {{
                    background-color: {cls.PRIMARY};
                    color: #ffffff;
                    border: none;
                    border-radius: {radius}px;
                    padding: {padding};
                    font-size: {font_size}px;
                    font-weight: 600;
                }}
                QPushButton:hover {{ background-color: {cls.PRIMARY_HOVER}; }}
            """
        elif variant == "warning":
            return f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #b45309);
                    color: #ffffff;
                    border: 1px solid #f59e0b;
                    border-radius: {radius}px;
                    padding: {padding};
                    font-size: {font_size}px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b45309, stop:1 #92400e);
                }}
            """
        elif variant == "danger":
            return f"""
                QPushButton {{
                    background-color: #dc2626;
                    color: #ffffff;
                    border: none;
                    border-radius: {radius}px;
                    padding: {padding};
                    font-size: {font_size}px;
                    font-weight: 600;
                }}
                QPushButton:hover {{ background-color: #ef4444; }}
            """
        # Default subtle / neutral
        return f"""
            QPushButton {{
                background-color: #1e253b;
                color: #cbd5e1;
                border: 1px solid #475569;
                border-radius: {radius}px;
                padding: {padding};
                font-size: {font_size}px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #334155;
                color: #ffffff;
            }}
        """

    @classmethod
    def subtle_toggle_button_style(
        cls, is_active: bool = False, active_color: str = "#93c5fd", border_color: str = "#2563eb"
    ) -> str:
        """Exécute l'opération subtle toggle button style.

        Args:
            is_active: Paramètre is_active.
            active_color: Paramètre active_color.
            border_color: Paramètre border_color.

        Returns:
            Résultat de l'opération subtle_toggle_button_style.
        """
        if is_active:
            return f"""
                QPushButton {{
                    background-color: #1e253b;
                    color: {active_color};
                    border: 1px solid {border_color};
                    border-radius: 4px;
                    padding: 2px 6px;
                    font-size: 10px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: #1d4ed8;
                    color: #ffffff;
                }}
            """
        return """
            QPushButton {
                background-color: #1e253b;
                color: #cbd5e1;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
        """

    @classmethod
    def table_style(cls) -> str:
        """Returns standard styling for QTableWidget."""
        return """
            QTableWidget {
                background-color: #11131e;
                alternate-background-color: #151827;
                border: 1px solid #232738;
                border-radius: 10px;
                outline: none;
            }
            QTableWidget::item {
                border-bottom: 1px solid #1e2235;
            }
            QTableWidget::item:selected {
                background-color: #1e2338;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #0c0e18;
                color: #94a3b8;
                font-weight: 700;
                font-size: 11px;
                border: none;
                border-bottom: 2px solid #232738;
                padding: 10px 8px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            QScrollBar:vertical {
                background-color: #0c0e18;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #232738;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #3b4260;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """

    @classmethod
    def input_style(cls) -> str:
        """Returns standard styling for QLineEdit input fields."""
        return """
            QLineEdit {
                background-color: #0f111a;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                min-height: 22px;
            }
            QLineEdit:focus {
                border-color: #6366f1;
            }
        """

    @classmethod
    def secondary_button_style(cls) -> str:
        """Returns standard secondary action button styling."""
        return """
            QPushButton {
                background-color: #202436;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 13px;
                font-weight: 600;
                min-height: 22px;
            }
            QPushButton:hover {
                background-color: #2d334d;
                border-color: #6366f1;
            }
            QPushButton:pressed {
                background-color: #191c2b;
            }
        """
