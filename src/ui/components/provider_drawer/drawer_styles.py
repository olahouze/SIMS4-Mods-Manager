"""
DrawerStyles: Centralized stylesheets and status-based style generators
for ProviderDrawer components.
"""


class DrawerStyles:
    @staticmethod
    def status_pill(state: str) -> str:
        if state == "ERROR":
            return """
                background-color: #450a0a; color: #fca5a5;
                border: 1px solid #dc2626; border-radius: 4px;
                padding: 2px 6px; font-size: 10px; font-weight: 700;
            """
        if state == "PAUSED":
            return """
                background-color: #451a03; color: #fde68a;
                border: 1px solid #d97706; border-radius: 4px;
                padding: 2px 6px; font-size: 10px; font-weight: 700;
            """
        if state == "RUNNING":
            return """
                background-color: #1e1b4b; color: #93c5fd;
                border: 1px solid #3b82f6; border-radius: 4px;
                padding: 2px 6px; font-size: 10px; font-weight: 700;
            """
        if state == "STOPPED":
            return """
                background-color: #262626; color: #d4d4d8;
                border: 1px solid #52525b; border-radius: 4px;
                padding: 2px 6px; font-size: 10px; font-weight: 700;
            """
        return """
            background-color: #064e3b; color: #a7f3d0;
            border: 1px solid #059669; border-radius: 4px;
            padding: 2px 6px; font-size: 10px; font-weight: 700;
        """

    @staticmethod
    def toggle_button(state: str) -> str:
        if state == "ERROR":
            bg, border = "#450a0a", "#dc2626"
        elif state == "PAUSED":
            bg, border = "#451a03", "#d97706"
        elif state == "RUNNING":
            bg, border = "#1e1b4b", "#3b82f6"
        else:
            bg, border = "#111827", "#1f2937"

        return f"""
            QPushButton {{
                background-color: {bg};
                color: #f8fafc;
                border: 1px solid {border};
                border-radius: 6px;
                font-weight: 700;
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: #1f293d; }}
        """

    @staticmethod
    def site_tab_pill(state: str) -> str:
        if state == "ERROR":
            return """
                background-color: #450a0a; color: #fca5a5;
                border: 1px solid #dc2626; border-radius: 6px;
                padding: 4px 6px; font-size: 11px; font-weight: 700;
            """
        if state == "PAUSED":
            return """
                background-color: #451a03; color: #fde68a;
                border: 1px solid #d97706; border-radius: 6px;
                padding: 4px 6px; font-size: 11px; font-weight: 700;
            """
        if state == "RUNNING":
            return """
                background-color: #1e1b4b; color: #93c5fd;
                border: 1px solid #3b82f6; border-radius: 6px;
                padding: 4px 6px; font-size: 11px; font-weight: 700;
            """
        return """
            background-color: #064e3b; color: #a7f3d0;
            border: 1px solid #059669; border-radius: 6px;
            padding: 4px 6px; font-size: 11px; font-weight: 700;
        """

    @staticmethod
    def resync_button(loading: bool = False, is_paused: bool = False) -> str:
        if is_paused:
            return """
                QPushButton {
                    background-color: #451a03; color: #fde68a;
                    border: 1px solid #d97706; border-radius: 6px;
                    font-size: 12px; font-weight: 700;
                }
            """
        if loading:
            return """
                QPushButton {
                    background-color: #1e293b; color: #64748b;
                    border: 1px solid #334155; border-radius: 6px;
                    font-size: 12px; font-weight: 700;
                }
            """
        return """
            QPushButton {
                background-color: #1d4ed8; color: #ffffff;
                border: 1px solid #3b82f6; border-radius: 6px;
                font-size: 12px; font-weight: 700;
            }
            QPushButton:hover { background-color: #2563eb; }
        """

    @staticmethod
    def pause_button(is_paused: bool = False, disabled: bool = False) -> str:
        if disabled:
            return """
                QPushButton {
                    background-color: #1e2538; color: #475569;
                    border: 1px solid #334155; border-radius: 6px;
                    font-size: 11px; font-weight: 600;
                }
            """
        if is_paused:
            return """
                QPushButton {
                    background-color: #1e3a8a; color: #93c5fd;
                    border: 1px solid #3b82f6; border-radius: 6px;
                    font-size: 11px; font-weight: 700;
                }
                QPushButton:hover { background-color: #2563eb; color: #ffffff; }
            """
        return """
            QPushButton {
                background-color: #78350f; color: #fde68a;
                border: 1px solid #d97706; border-radius: 6px;
                font-size: 11px; font-weight: 700;
            }
            QPushButton:hover { background-color: #92400e; color: #ffffff; }
        """

    @staticmethod
    def stop_button(disabled: bool = False) -> str:
        if disabled:
            return """
                QPushButton {
                    background-color: #1e2538; color: #475569;
                    border: 1px solid #334155; border-radius: 6px;
                    font-size: 11px; font-weight: 600;
                }
            """
        return """
            QPushButton {
                background-color: #7f1d1d; color: #fecaca;
                border: 1px solid #dc2626; border-radius: 6px;
                font-size: 11px; font-weight: 700;
            }
            QPushButton:hover { background-color: #991b1b; color: #ffffff; }
        """
