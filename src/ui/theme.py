"""
Dark modern styling system for SIMS4-Mods-Manager with rich aesthetics.
"""

DARK_THEME_QSS = """
/* Global Application Styles */
QWidget {
    background-color: #0f111a;
    color: #e2e8f0;
    font-family: 'Segoe UI', 'SF Pro Display', -apple-system, Roboto, sans-serif;
    font-size: 13px;
    selection-background-color: #6366f1;
    selection-color: #ffffff;
}

QToolTip {
    background-color: #1e2238;
    color: #f8fafc;
    border: 1px solid #6366f1;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
    font-family: 'Segoe UI', 'SF Pro Display', sans-serif;
}

/* Main Window & Central Widget */
QMainWindow {
    background-color: #0f111a;
}

/* Sidebar Navigation */
QFrame#Sidebar {
    background-color: #161824;
    border-right: 1px solid #232738;
}

QLabel#AppTitle {
    font-size: 18px;
    font-weight: 700;
    color: #f8fafc;
    padding: 10px 0;
}

QLabel#AppSubtitle {
    font-size: 11px;
    color: #818cf8;
    font-weight: 600;
    letter-spacing: 1px;
}

QPushButton.NavButton {
    background-color: transparent;
    color: #94a3b8;
    border: none;
    border-radius: 8px;
    padding: 12px 16px;
    text-align: left;
    font-size: 13px;
    font-weight: 500;
}

QPushButton.NavButton:hover {
    background-color: #202436;
    color: #f1f5f9;
}

QPushButton.NavButton:checked, QPushButton.NavButton[active="true"] {
    background-color: #4f46e5;
    color: #ffffff;
    font-weight: 600;
}

/* Content Area */
QFrame#ContentArea {
    background-color: #0f111a;
}

/* Cards */
QFrame.ModCard {
    background-color: #181b2a;
    border: 1px solid #252a3d;
    border-radius: 12px;
}

QFrame.ModCard:hover {
    border: 1px solid #6366f1;
    background-color: #1e2235;
}

/* Settings Sections & Surfaces */
QFrame.SettingsSection, QFrame#SettingsSection {
    background-color: #161824;
    border: 1px solid #282e44;
    border-radius: 12px;
}

QLabel.CardTitle {
    font-size: 14px;
    font-weight: 600;
    color: #f8fafc;
}

QLabel.CardAuthor {
    font-size: 12px;
    color: #94a3b8;
}

QLabel.CardDate {
    font-size: 11px;
    color: #64748b;
}

/* Buttons */
QPushButton.PrimaryBtn {
    background-color: #6366f1;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton.PrimaryBtn:hover {
    background-color: #4f46e5;
}

QPushButton.PrimaryBtn:pressed {
    background-color: #4338ca;
}

QPushButton.SecondaryBtn {
    background-color: #202436;
    color: #cbd5e1;
    border: 1px solid #2e354d;
    border-radius: 6px;
    padding: 8px 14px;
    font-weight: 500;
}

QPushButton.SecondaryBtn:hover {
    background-color: #2a3048;
    color: #f8fafc;
    border-color: #475569;
}

QPushButton.SuccessBtn {
    background-color: #10b981;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton.SuccessBtn:hover {
    background-color: #059669;
}

QPushButton.DangerBtn {
    background-color: #ef4444;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 500;
}

QPushButton.DangerBtn:hover {
    background-color: #dc2626;
}

QPushButton.WarningBtn {
    background-color: #f59e0b;
    color: #0f172a;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 700;
}

QPushButton.WarningBtn:hover {
    background-color: #d97706;
    color: #ffffff;
}

/* Inputs & Search */
QLineEdit {
    background-color: #181b2a;
    border: 1px solid #282e44;
    border-radius: 8px;
    padding: 8px 14px;
    color: #f8fafc;
    font-size: 13px;
}

QLineEdit:focus {
    border: 1px solid #6366f1;
    background-color: #1c2033;
}

QComboBox {
    background-color: #181b2a;
    border: 1px solid #282e44;
    border-radius: 8px;
    padding: 8px 12px;
    color: #f8fafc;
    font-size: 13px;
    min-width: 140px;
}

QComboBox:hover {
    border-color: #4f46e5;
}

QComboBox::drop-down {
    border: none;
    padding-right: 10px;
}

QComboBox QAbstractItemView {
    background-color: #181b2a;
    border: 1px solid #282e44;
    selection-background-color: #4f46e5;
    color: #f8fafc;
    padding: 4px;
}

/* Scrollbars */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #2d334d;
    min-height: 25px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: #6366f1;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: transparent;
    height: 6px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #2d334d;
    min-width: 25px;
    border-radius: 3px;
}

QScrollBar::handle:horizontal:hover {
    background: #6366f1;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Progress Bar */
QProgressBar {
    background-color: #181b2a;
    border: 1px solid #282e44;
    border-radius: 6px;
    text-align: center;
    color: #ffffff;
    font-weight: 600;
    height: 18px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #a855f7);
    border-radius: 5px;
}

/* Table View */
QTableWidget {
    background-color: #161824;
    border: 1px solid #232738;
    border-radius: 8px;
    gridline-color: #232738;
    color: #f1f5f9;
}

QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #1f2334;
}

QTableWidget::item:selected {
    background-color: #282e48;
}

QHeaderView::section {
    background-color: #1c2033;
    color: #94a3b8;
    padding: 10px;
    font-weight: 600;
    border: none;
    border-bottom: 2px solid #282e44;
}
"""


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
        palette = cls.BADGE_PALETTES.get(variant, cls.BADGE_PALETTES["neutral"])
        return f"""
            color: {palette['fg']};
            background-color: {palette['bg']};
            border: 1px solid {palette['border']};
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
    def subtle_toggle_button_style(cls, is_active: bool = False, active_color: str = "#93c5fd", border_color: str = "#2563eb") -> str:
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

