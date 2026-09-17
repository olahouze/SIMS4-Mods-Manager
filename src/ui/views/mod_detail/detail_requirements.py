"""
DetailRequirementsWidget: Collapsible requirements, DLCs, and dependencies section
with integrated author interpellation for ModDetailView.
"""
import re
from typing import Dict, List, Any, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
)

from src.ui.components.dependency_card import DependencyCardWidget
from src.ui.components.author_interpellate_widget import AuthorInterpellateWidget
from src.ui.theme import Theme
from src.utils.game_dlc_matcher import GameDlcMatcher, SIMS4_PREFIX_REGEX


class DetailRequirementsWidget(QWidget):
    toggle_comment_requested = Signal(dict, bool)  # dep, to_comment
    override_changed = Signal(str, str)  # module_name, "COMMENT" | "MOD"
    report_sent = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_collapsed = False
        self._unfound_dep_names: List[str] = []
        self._comment_deps: List[dict] = []
        self._mod_data: Dict[str, Any] = {}
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 4, 0, 8)
        main_layout.setSpacing(6)

        self.req_frame = QFrame()
        self.req_frame.setStyleSheet(Theme.card_frame_style(bg="#101424", border="#232d45", padding="10px 14px"))
        self.rf_layout = QVBoxLayout(self.req_frame)
        self.rf_layout.setContentsMargins(10, 8, 10, 8)
        self.rf_layout.setSpacing(6)

        # Header row with collapse button
        hdr_row = QHBoxLayout()
        self.req_title = QLabel("🔗 Dépendances & Prérequis (Requirements) :")
        self.req_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        hdr_row.addWidget(self.req_title, stretch=1)

        self.req_collapse_btn = QPushButton("▲ Réduire")
        self.btn_collapse = self.req_collapse_btn
        self.req_collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.req_collapse_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 5px;
                padding: 3px 8px;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #f1f5f9;
            }
        """)
        self.req_collapse_btn.clicked.connect(self._toggle_collapse)
        hdr_row.addWidget(self.req_collapse_btn)
        self.rf_layout.addLayout(hdr_row)

        # Retractable body container
        self.req_body = QWidget()
        self.deps_container = self.req_body
        self.req_body_layout = QVBoxLayout(self.req_body)
        self.req_body_layout.setContentsMargins(0, 0, 0, 0)
        self.req_body_layout.setSpacing(8)

        self.req_desc = QLabel()
        self.req_desc.setWordWrap(True)
        self.req_desc.setStyleSheet("font-size: 12px; color: #cbd5e1;")
        self.req_body_layout.addWidget(self.req_desc)

        self.deps_inner_container = QWidget()
        self.deps_layout = QVBoxLayout(self.deps_inner_container)
        self.deps_layout.setContentsMargins(0, 0, 0, 0)
        self.deps_layout.setSpacing(6)
        self.req_body_layout.addWidget(self.deps_inner_container)

        # Author Interpellation Button Widget
        self.interpellate_widget = AuthorInterpellateWidget(self)
        self.interpellate_widget.override_changed.connect(self.override_changed.emit)
        self.interpellate_widget.report_sent.connect(self.report_sent.emit)
        self.req_body_layout.addWidget(self.interpellate_widget)

        self.rf_layout.addWidget(self.req_body)
        main_layout.addWidget(self.req_frame)
        self.req_frame.setVisible(False)

    @property
    def btn_report_author(self) -> QPushButton:
        return self.interpellate_widget.btn_report

    def _toggle_collapse(self):
        self._is_collapsed = not self._is_collapsed
        self.req_body.setVisible(not self._is_collapsed)
        self.req_collapse_btn.setText("▼ Développer" if self._is_collapsed else "▲ Réduire")

    def set_loading(self):
        self._is_collapsed = False
        self.req_frame.setVisible(True)
        self.req_collapse_btn.setVisible(True)
        self.req_collapse_btn.setText("▲ Réduire")
        self.req_body.setVisible(True)
        self.req_frame.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 10px 14px;
            }
        """)
        self.req_title.setText("🔄 Analyse des dépendances et prérequis...")
        self.req_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #94a3b8;")
        self.req_desc.setText(
            "Analyse en cours des prérequis du mod et vérification des dépendances sur LoversLab...\n"
            "Veuillez patienter pendant l'inspection des données."
        )
        self.req_desc.setStyleSheet("font-size: 11px; color: #64748b;")
        while self.deps_layout.count():
            it = self.deps_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.interpellate_widget.setVisible(False)

    def render_requirements(self, data: dict) -> Dict[str, Any]:
        """Displays requirements status, dependencies list categorized by type, and forum interpellation."""
        self._mod_data = data
        req_text = data.get("requirements_text")
        req_status = data.get("requirements_status", "NONE")
        raw_deps = data.get("dependencies", [])

        while self.deps_layout.count():
            it = self.deps_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        self.req_body.setVisible(True)
        self.req_collapse_btn.setText("▲ Réduire")

        overrides = dict(data.get("requirements_overrides", {}) or {})

        game_dlcs = []
        already_installed = []
        to_install = []
        unfound = []
        comments = []

        for d in raw_deps:
            t = (d.get("title") or "").strip()
            clean_t = re.sub(r"^[\s•\*\-\–\—\d\.\)\:\[\]\(\)\{\}\"\'\`]+", "", t).strip()
            clean_t = re.sub(
                r"(?i)^(?:requirements?|pr[ée]requis|prerequisites?|needs?|required(?:\s*(?:mods?|packs?|dlcs?))?|requires?|dlcs?|packs?)\s*[:\-–—\s]\s*",
                "",
                clean_t,
            ).strip().strip("'\"`[](){}")

            if GameDlcMatcher.is_base_game_only(clean_t):
                d["is_game_dlc"] = True
                d["status"] = "GAME_DLC"
                d["is_installed"] = True
                d["dlc_name"] = "Jeu de base"
                if not d.get("title") or d.get("title").lower() in ["sims 4", "the sims 4"]:
                    d["title"] = "The Sims 4 (Jeu de base)"
                game_dlcs.append(d)
                continue

            starts_with_sims4 = bool(SIMS4_PREFIX_REGEX.match(clean_t))
            is_dlc_matched, _, _ = GameDlcMatcher.match_dlc(clean_t)
            is_dlc = d.get("is_game_dlc", False) or d.get("status") == "GAME_DLC" or starts_with_sims4 or is_dlc_matched
            is_inst = d.get("is_installed", False) or d.get("status") == "INSTALLED"
            st = d.get("status", "DETECTED_NOT_INSTALLED")

            if is_dlc:
                game_dlcs.append(d)
            elif is_inst:
                already_installed.append(d)
            elif st == "DETECTED_NOT_INSTALLED":
                to_install.append(d)
            elif d.get("is_comment") or st == "COMMENT_NOISE" or overrides.get(t) == "COMMENT":
                d["is_comment"] = True
                comments.append(d)
            else:
                unfound.append(d)

        if (req_status in ["PENDING_VERIFICATION", "PARTIAL"] or (req_text and not raw_deps)) and not unfound and not comments and req_text and req_text.strip():
            clean_req_text = re.sub(r"^[\s•\*\-\–\—\d\.\)\:\[\]\(\)\{\}\"\'\`]+", "", req_text).strip()
            clean_req_text = re.sub(
                r"(?i)^(?:requirements?|pr[ée]requis|prerequisites?|needs?|required(?:\s*(?:mods?|packs?|dlcs?))?|requires?|dlcs?|packs?)\s*[:\-–—\s]\s*",
                "",
                clean_req_text,
            ).strip().strip("'\"`[](){}")
            is_bg = GameDlcMatcher.is_base_game_only(clean_req_text)
            is_dlc_text = bool(SIMS4_PREFIX_REGEX.match(clean_req_text)) or GameDlcMatcher.match_dlc(clean_req_text)[0]
            if not is_bg and not is_dlc_text:
                synth_entry = {
                    "title": req_text.strip(),
                    "status": "NOT_DETECTED_FINISHED",
                    "is_installed": False,
                    "is_game_dlc": False,
                }
                if overrides.get(req_text.strip()) == "COMMENT":
                    synth_entry["is_comment"] = True
                    comments.append(synth_entry)
                else:
                    unfound.append(synth_entry)

        self._comment_deps = comments
        has_deps = bool(game_dlcs or already_installed or to_install or unfound or comments)

        if has_deps:
            self.req_frame.setVisible(True)
            self.req_collapse_btn.setVisible(True)

            if unfound:
                self.req_frame.setStyleSheet("""
                    QFrame {
                        background-color: #1e1308;
                        border: 1px solid #d97706;
                        border-radius: 8px;
                        padding: 10px 14px;
                    }
                """)
                total_cnt = len(raw_deps) or len(unfound)
                self.req_title.setText(f"⚠️ Dépendances requises ({total_cnt}) - Composants manquants")
                self.req_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #fde68a;")
                self.req_desc.setText(
                    "Ce mod nécessite des composants dont certains ne sont pas trouvés sur LoversLab. "
                    "Vous pouvez marquer les faux positifs comme commentaires pour débloquer l'installation complète."
                )
                self.req_desc.setStyleSheet("font-size: 11px; color: #fcd34d; margin-top: 2px;")
            else:
                self.req_frame.setStyleSheet("""
                    QFrame {
                        background-color: #0b1524;
                        border: 1px solid #2563eb;
                        border-radius: 8px;
                        padding: 10px 14px;
                    }
                """)
                self.req_title.setText(f"🔗 Dépendances et DLCs identifiés ({len(raw_deps)}) :")
                self.req_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #93c5fd;")
                self.req_desc.setText(
                    "Ce mod s'appuie sur les composants suivants. Les mods manquants seront automatiquement téléchargés, "
                    "et les éventuels packs DLC officiels sont à vérifier dans votre jeu :"
                )
                self.req_desc.setStyleSheet("font-size: 11px; color: #94a3b8; margin-top: 2px;")

            def _add_section_header(title: str, color: str):
                lbl = QLabel(title)
                lbl.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {color}; margin-top: 4px; margin-bottom: 2px;")
                self.deps_layout.addWidget(lbl)

            if game_dlcs:
                _add_section_header(f"🎮 Packs DLC Officiels Sims 4 ({len(game_dlcs)}) :", "#c084fc")
                for d in game_dlcs:
                    t = d.get("title") or d.get("dlc_name") or "DLC Sims 4"
                    is_detected = d.get("is_installed", False)
                    badge_t = "✅ Détecté dans le jeu" if is_detected else "🎮 DLC Jeu (À vérifier)"
                    card = DependencyCardWidget(t, badge_t, badge_variant="success" if is_detected else "purple", prefix="🎮")
                    self.deps_layout.addWidget(card)

            if to_install:
                _add_section_header(f"📥 Dépendances trouvées à installer ({len(to_install)}) :", "#60a5fa")
                for d in to_install:
                    t = d.get("title") or f"Mod #{d.get('remote_id')}"
                    card = DependencyCardWidget(t, "📥 Sera installé automatiquement", badge_variant="info", prefix="•")
                    self.deps_layout.addWidget(card)

            if already_installed:
                _add_section_header(f"✅ Dépendances déjà installées ({len(already_installed)}) :", "#4ade80")
                for d in already_installed:
                    t = d.get("title") or f"Mod #{d.get('remote_id')}"
                    card = DependencyCardWidget(t, "✅ Déjà installé", badge_variant="success", prefix="✓")
                    self.deps_layout.addWidget(card)

            self._unfound_dep_names = []
            if unfound:
                _add_section_header(f"⚠️ Dépendances introuvables ({len(unfound)}) :", "#f87171")
                for d in unfound:
                    t = d.get("title") or f"Mod #{d.get('remote_id')}"
                    self._unfound_dep_names.append(t)
                    btn_comm = QPushButton("💬 Marquer comme commentaire")
                    btn_comm.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn_comm.setStyleSheet(Theme.subtle_toggle_button_style(is_active=False))
                    btn_comm.clicked.connect(lambda _, item=d: self.toggle_comment_requested.emit(item, True))
                    card = DependencyCardWidget(t, "⚠️ Introuvable sur LoversLab", badge_variant="danger", prefix="⚠️", action_btn=btn_comm)
                    self.deps_layout.addWidget(card)

            if comments:
                _add_section_header(f"💬 Notes & Commentaires identifiés ({len(comments)}) :", "#94a3b8")
                comm_note = QLabel("Ces éléments ont été marqués comme simples commentaires textuels et ne bloqueront pas l'installation :")
                comm_note.setStyleSheet("font-size: 11px; color: #64748b; margin-bottom: 2px;")
                comm_note.setWordWrap(True)
                self.deps_layout.addWidget(comm_note)
                for d in comments:
                    t = d.get("title") or f"Mod #{d.get('remote_id')}"
                    btn_mod = QPushButton("📦 Marquer comme vrai mod requis")
                    btn_mod.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn_mod.setStyleSheet(Theme.subtle_toggle_button_style(is_active=True))
                    btn_mod.clicked.connect(lambda _, item=d: self.toggle_comment_requested.emit(item, False))
                    card = DependencyCardWidget(t, "💬 Commentaire / Note", badge_variant="neutral", prefix="💬", action_btn=btn_mod)
                    self.deps_layout.addWidget(card)

            if unfound or comments:
                self.interpellate_widget.setVisible(True)
                self.interpellate_widget.btn_report.setEnabled(False)
            else:
                self.interpellate_widget.setVisible(False)

        else:
            self.interpellate_widget.setVisible(False)
            self._unfound_dep_names = []
            if req_text and req_text.strip():
                self.req_frame.setVisible(True)
                self.req_collapse_btn.setVisible(True)
                self.req_collapse_btn.setText("▲ Réduire")
                self.req_body.setVisible(True)
                self.req_frame.setStyleSheet("""
                    QFrame {
                        background-color: #101424;
                        border: 1px solid #232d45;
                        border-radius: 8px;
                        padding: 10px 14px;
                    }
                """)
                self.req_title.setText("ℹ️ Notes de prérequis :")
                self.req_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #cbd5e1;")
                self.req_desc.setText(req_text)
            else:
                self.req_frame.setVisible(False)

        return {
            "has_deps": has_deps,
            "unfound": unfound,
            "to_install": to_install,
            "already_installed": already_installed,
            "comments": comments,
        }

    def _trigger_check_report_status(self, data: dict, comment_names: Optional[List[str]] = None):
        if comment_names is None:
            comment_names = [(c.get("title") or f"Mod #{c.get('remote_id')}") for c in self._comment_deps if (c.get("title") or c.get("remote_id"))]
        self.interpellate_widget.check_status(data, self._unfound_dep_names, comment_names)

    def _on_report_status_ready(self, res: dict):
        self.interpellate_widget._on_status_ready(res)

    def _on_report_sent_success(self, reported_at: str):
        self.interpellate_widget._on_report_sent_success(reported_at)
