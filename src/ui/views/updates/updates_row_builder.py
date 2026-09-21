"""
Row cells builder for UpdatesView table.
"""

from typing import Callable, Tuple
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
)
from PySide6.QtCore import Qt

from src.i18n import tr
from src.ui.components.status_badge import StatusBadge


class UpdatesRowBuilder:
    """Static factory creating styled table cell widgets for mod update rows."""

    @staticmethod
    def create_checkbox_cell(is_checked: bool, on_toggle: Callable[[], None]) -> Tuple[QWidget, QCheckBox]:
        """Exécute l'opération create checkbox cell.

        Args:
            is_checked: Paramètre is_checked.
            on_toggle: Paramètre on_toggle.

        Returns:
            Résultat de l'opération create_checkbox_cell.
        """
        cb_widget = QWidget()
        cb_layout = QHBoxLayout(cb_widget)
        cb_layout.setContentsMargins(0, 0, 0, 0)
        cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cb = QCheckBox()
        cb.setStyleSheet("""
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #475569;
                background-color: #1e2238;
            }
            QCheckBox::indicator:hover { border-color: #818cf8; }
            QCheckBox::indicator:checked { background-color: #6366f1; border-color: #818cf8; }
        """)
        cb.setChecked(is_checked)
        cb.toggled.connect(lambda _: on_toggle())
        cb_layout.addWidget(cb)
        return cb_widget, cb

    @staticmethod
    def create_title_cell(title: str, source: str, folder_name: str) -> QWidget:
        """Exécute l'opération create title cell.

        Args:
            title: Paramètre title.
            source: Paramètre source.
            folder_name: Paramètre folder_name.

        Returns:
            Résultat de l'opération create_title_cell.
        """
        title_widget = QWidget()
        t_layout = QVBoxLayout(title_widget)
        t_layout.setContentsMargins(12, 10, 12, 10)
        t_layout.setSpacing(4)
        t_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        title_label.setToolTip(title)
        t_layout.addWidget(title_label)

        sub_layout = QHBoxLayout()
        sub_layout.setContentsMargins(0, 0, 0, 0)
        sub_layout.setSpacing(8)

        src_badge = StatusBadge(source.capitalize(), badge_type=source)
        sub_layout.addWidget(src_badge)

        if folder_name:
            folder_label = QLabel(f"📁 {folder_name}")
            folder_label.setStyleSheet("font-size: 11px; color: #64748b;")
            sub_layout.addWidget(folder_label)

        sub_layout.addStretch()
        t_layout.addLayout(sub_layout)
        return title_widget

    @staticmethod
    def create_version_pill(version_str: str) -> QWidget:
        """Exécute l'opération create version pill.

        Args:
            version_str: Paramètre version_str.

        Returns:
            Résultat de l'opération create_version_pill.
        """
        cur_widget = QWidget()
        c_layout = QHBoxLayout(cur_widget)
        c_layout.setContentsMargins(8, 0, 8, 0)
        c_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cur_lbl = QLabel(version_str or "Inconnue")
        cur_lbl.setStyleSheet("""
            background-color: #1a1d2e;
            color: #cbd5e1;
            border: 1px solid #2e344d;
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 12px;
            font-weight: 600;
        """)
        c_layout.addWidget(cur_lbl)
        return cur_widget

    @staticmethod
    def create_new_version_pill(new_version_str: str, has_update: bool) -> QWidget:
        """Exécute l'opération create new version pill.

        Args:
            new_version_str: Paramètre new_version_str.
            has_update: Paramètre has_update.

        Returns:
            Résultat de l'opération create_new_version_pill.
        """
        new_widget = QWidget()
        n_layout = QHBoxLayout(new_widget)
        n_layout.setContentsMargins(8, 0, 8, 0)
        n_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        new_ver = new_version_str or "-"
        new_lbl = QLabel(f"▲ {new_ver}" if has_update else new_ver)
        if has_update:
            new_lbl.setStyleSheet("""
                background-color: #064e3b;
                color: #34d399;
                border: 1px solid #059669;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 700;
            """)
        else:
            new_lbl.setStyleSheet("""
                background-color: #1a1d2e;
                color: #64748b;
                border: 1px solid #2e344d;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
            """)
        n_layout.addWidget(new_lbl)
        return new_widget

    @staticmethod
    def create_status_cell(has_update: bool, has_link: bool) -> QWidget:
        """Exécute l'opération create status cell.

        Args:
            has_update: Paramètre has_update.
            has_link: Paramètre has_link.

        Returns:
            Résultat de l'opération create_status_cell.
        """
        stat_widget = QWidget()
        s_layout = QHBoxLayout(stat_widget)
        s_layout.setContentsMargins(8, 0, 8, 0)
        s_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if has_update:
            badge = StatusBadge(tr("updates.badge_update_avail"), badge_type="warning")
        elif has_link:
            badge = StatusBadge(tr("updates.badge_up_to_date"), badge_type="active")
        else:
            badge = StatusBadge(tr("updates.badge_manual"), badge_type="neutral")

        s_layout.addWidget(badge)
        return stat_widget

    @staticmethod
    def create_action_cell(has_update: bool, on_update: Callable[[], None]) -> QWidget:
        """Exécute l'opération create action cell.

        Args:
            has_update: Paramètre has_update.
            on_update: Paramètre on_update.

        Returns:
            Résultat de l'opération create_action_cell.
        """
        action_widget = QWidget()
        act_layout = QHBoxLayout(action_widget)
        act_layout.setContentsMargins(8, 0, 8, 0)
        act_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if has_update:
            update_btn = QPushButton(tr("updates.btn_update"))
            update_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4f46e5;
                    color: #ffffff;
                    font-weight: 700;
                    font-size: 12px;
                    border-radius: 6px;
                    padding: 7px 16px;
                    border: none;
                    min-height: 20px;
                }
                QPushButton:hover { background-color: #6366f1; }
            """)
            update_btn.clicked.connect(on_update)
            act_layout.addWidget(update_btn)
        else:
            up_to_date_btn = QPushButton(tr("updates.btn_up_to_date"))
            up_to_date_btn.setEnabled(False)
            up_to_date_btn.setStyleSheet("""
                QPushButton {
                    background-color: #181b29;
                    color: #475569;
                    font-weight: 600;
                    font-size: 12px;
                    border-radius: 6px;
                    padding: 7px 14px;
                    border: 1px solid #232738;
                    min-height: 20px;
                }
            """)
            act_layout.addWidget(up_to_date_btn)

        return action_widget
