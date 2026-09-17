"""
DependencySectionBuilder: Factory functions to render dependency sections
(DLCs, unfound requirements, comments/notes, already installed, missing).
Used across DependenciesDialog and detail views for uniform UI and DRY code.
"""
from typing import List, Callable
from PySide6.QtWidgets import (
    QVBoxLayout,
    QLabel,
    QPushButton,
)

from src.i18n import tr
from src.ui.components.dependency_card import DependencyCardWidget


def build_dlcs_section(layout: QVBoxLayout, dlcs: List[dict]) -> None:
    """Renders the official game DLCs section."""
    if not dlcs:
        return

    dlc_header = QLabel(tr("dependencies.dlc_header", count=len(dlcs)))
    dlc_header.setStyleSheet("font-size: 13px; font-weight: 700; color: #a78bfa;")
    layout.addWidget(dlc_header)

    dlc_notice = QLabel(tr("dependencies.dlc_notice"))
    dlc_notice.setStyleSheet("font-size: 11px; color: #c4b5fd; margin-bottom: 2px;")
    dlc_notice.setWordWrap(True)
    layout.addWidget(dlc_notice)

    for dlc in dlcs:
        dlc_title = dlc.get("title") or dlc.get("dlc_name") or "DLC Sims 4"
        is_inst = dlc.get("is_installed", False)
        badge_t = tr("dependencies.dlc_detected") if is_inst else tr("dependencies.dlc_check")
        card = DependencyCardWidget(
            dlc_title,
            badge_t,
            badge_variant="success" if is_inst else "warning",
            prefix="🎮",
        )
        layout.addWidget(card)


def build_unfound_section(
    layout: QVBoxLayout,
    unfound: List[dict],
    toggle_callback: Callable[[dict, bool], None],
) -> None:
    """Renders the unfound dependencies section with mark-as-comment actions."""
    if not unfound:
        return

    unf_header = QLabel(tr("dependencies.unfound_header", count=len(unfound)))
    unf_header.setStyleSheet("font-size: 13px; font-weight: 800; color: #f87171;")
    layout.addWidget(unf_header)

    for dep in unfound:
        dep_title = dep.get("title") or f"Mod #{dep.get('remote_id')}"
        btn_comment = QPushButton(tr("dependencies.btn_mark_comment"))
        btn_comment.clicked.connect(lambda _, d=dep: toggle_callback(d, True))
        card = DependencyCardWidget(
            dep_title,
            tr("dependencies.badge_unfound"),
            badge_variant="danger",
            prefix="⚠️",
            action_btn=btn_comment,
        )
        layout.addWidget(card)


def build_comments_section(
    layout: QVBoxLayout,
    comments: List[dict],
    toggle_callback: Callable[[dict, bool], None],
) -> None:
    """Renders the comments/notes section with mark-as-mod actions."""
    if not comments:
        return

    com_header = QLabel(tr("dependencies.comments_header", count=len(comments)))
    com_header.setStyleSheet("font-size: 13px; font-weight: 700; color: #38bdf8; margin-top: 4px;")
    layout.addWidget(com_header)

    for dep in comments:
        dep_title = dep.get("title") or f"Mod #{dep.get('remote_id')}"
        btn_uncomment = QPushButton(tr("dependencies.btn_mark_mod"))
        btn_uncomment.clicked.connect(lambda _, d=dep: toggle_callback(d, False))
        card = DependencyCardWidget(
            dep_title,
            tr("dependencies.badge_comment"),
            badge_variant="info",
            prefix="💬",
            action_btn=btn_uncomment,
        )
        layout.addWidget(card)


def build_installed_section(layout: QVBoxLayout, installed: List[dict]) -> None:
    """Renders the already installed dependencies section."""
    if not installed:
        return

    ok_header = QLabel(tr("dependencies.already_header", count=len(installed)))
    ok_header.setStyleSheet("font-size: 13px; font-weight: 700; color: #34d399; margin-top: 6px;")
    layout.addWidget(ok_header)

    for dep in installed:
        dep_title = dep.get("title") or f"Mod #{dep.get('remote_id')}"
        card = DependencyCardWidget(
            dep_title,
            tr("dependencies.badge_installed"),
            badge_variant="success",
            prefix="✓",
        )
        layout.addWidget(card)


def build_missing_section(layout: QVBoxLayout, missing: List[dict]) -> None:
    """Renders the missing dependencies section ready to be installed."""
    if not missing:
        return

    miss_header = QLabel(tr("dependencies.missing_header", count=len(missing)))
    miss_header.setStyleSheet("font-size: 13px; font-weight: 700; color: #60a5fa; margin-top: 6px;")
    layout.addWidget(miss_header)

    for dep in missing:
        dep_title = dep.get("title") or f"Mod #{dep.get('remote_id')}"
        card = DependencyCardWidget(
            dep_title,
            tr("dependencies.badge_to_install"),
            badge_variant="info",
            prefix="⬇",
        )
        layout.addWidget(card)
