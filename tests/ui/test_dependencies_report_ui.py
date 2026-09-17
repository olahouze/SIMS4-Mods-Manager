from unittest.mock import MagicMock, patch
from src.ui.components.report_preview_dialog import ReportPreviewDialog
from src.ui.components.dependencies_dialog import DependenciesDialog, CheckReportStatusWorker


def test_report_preview_dialog_initialization(qapp):
    dlg = ReportPreviewDialog(
        mod_title="Amazing Mod",
        author="KikiSims",
        missing_modules=["Module X", "Module Y"],
        source="loverslab",
        page_url="https://loverslab.com/test",
        initial_message="Hi @KikiSims, missing Module X, Module Y.",
    )
    assert dlg.author == "KikiSims"
    assert len(dlg.missing_modules) == 2
    assert "Hi @KikiSims" in dlg.text_edit.toPlainText()
    assert dlg.send_btn.isEnabled()


def test_check_report_status_worker(qapp):
    mock_client = MagicMock()
    mock_client.check_missing_report.return_value = {
        "can_report": False,
        "already_reported": True,
        "reported_at": "12/09/2026 à 14:32",
    }
    with patch("src.ui.components.dependencies_dialog.get_api_client", return_value=mock_client):
        worker = CheckReportStatusWorker({"author": "AuthorSims"})
        results = []
        worker.status_ready.connect(results.append)
        worker.run()
        assert len(results) == 1
        assert results[0]["already_reported"] is True


def test_dependencies_dialog_report_button_lifecycle(qapp):
    unfound_items = [
        {"title": "Missing Library A", "remote_id": "991"},
        {"title": "Missing Extension B", "remote_id": "992"},
    ]
    mod_data = {
        "id": 42,
        "source": "loverslab",
        "remote_id": "1234",
        "title": "Complex Parent Mod",
        "author": "AuthorSims",
        "page_url": "https://loverslab.com/files/file/1234-complex/",
    }

    with patch.object(DependenciesDialog, "_start_live_status_check"):
        dlg = DependenciesDialog(
            mod_title="Complex Parent Mod",
            already_installed=[],
            missing=[],
            unfound=unfound_items,
            is_partial=True,
            mod_data=mod_data,
        )

        assert hasattr(dlg, "btn_report_author")

        # Simulate receiving status: already reported
        dlg._on_status_ready({
            "can_report": False,
            "already_reported": True,
            "reported_at": "12/09/2026 à 14:32",
            "formatted_message": "Hi @AuthorSims...",
            "author": "@AuthorSims",
            "is_authenticated": True,
        })
        assert dlg.btn_report_author.isEnabled() is False
        assert "12/09/2026" in dlg.btn_report_author.text()

        # Simulate receiving status: NOT yet reported
        dlg._on_status_ready({
            "can_report": True,
            "already_reported": False,
            "reported_at": None,
            "formatted_message": "Hi @AuthorSims...",
            "author": "@AuthorSims",
            "is_authenticated": True,
        })
        assert dlg.btn_report_author.isEnabled() is True
        assert "Interpeler" in dlg.btn_report_author.text() or "Notify" in dlg.btn_report_author.text()

        # Simulate successful submission callback
        dlg._on_report_sent_success("à l'instant")
        assert dlg.btn_report_author.isEnabled() is False
        assert "interpelé" in dlg.btn_report_author.text().lower() or "notified" in dlg.btn_report_author.text().lower()


def test_report_preview_dialog_checkboxes_toggle(qapp):
    dlg = ReportPreviewDialog(
        mod_title="Amazing Mod",
        author="KikiSims",
        missing_modules=["Module A", "Module B"],
        source="loverslab",
    )
    # Both checkboxes exist and are checked by default
    assert len(dlg.module_checkboxes) == 2
    assert all(cb.isChecked() for cb in dlg.module_checkboxes)
    assert "Module A" in dlg.text_edit.toPlainText()
    assert "Module B" in dlg.text_edit.toPlainText()
    assert dlg.send_btn.isEnabled()

    # Uncheck Module A
    dlg.module_checkboxes[0].setChecked(False)
    assert "Module A" not in dlg.text_edit.toPlainText()
    assert "Module B" in dlg.text_edit.toPlainText()
    assert dlg.send_btn.isEnabled()
    assert dlg._get_selected_modules() == ["Module B"]

    # Uncheck Module B -> both unchecked -> send button disabled
    dlg.module_checkboxes[1].setChecked(False)
    assert dlg._get_selected_modules() == []
    assert dlg.send_btn.isEnabled() is False

    # Re-check Module A -> send button re-enabled
    dlg.module_checkboxes[0].setChecked(True)
    assert dlg.send_btn.isEnabled() is True
    assert "Module A" in dlg.text_edit.toPlainText()
    assert dlg._get_selected_modules() == ["Module A"]


def test_report_preview_dialog_radio_choices(qapp):
    dlg = ReportPreviewDialog(
        mod_title="Custom Animation Pack",
        author="AnimatorSim",
        missing_modules=["Missing Lib X", "Some Unnecessary Text"],
        source="loverslab",
    )
    assert len(dlg.module_items) == 2

    # Initially both are checked and default to rb_missing
    assert dlg.module_items[0]["rb_missing"].isChecked()
    assert dlg.module_items[1]["rb_missing"].isChecked()

    # Switch second item to rb_unnecessary
    dlg.module_items[1]["rb_unnecessary"].setChecked(True)

    text = dlg.text_edit.toPlainText()
    assert "1) The following required module(s) could not be identified" in text
    assert "- Missing Lib X" in text
    assert "2) Additionally, the following item(s) listed under Requirements do not appear to be mods" in text
    assert "- Some Unnecessary Text" in text

    missing, unnecessary = dlg._get_categorized_modules()
    assert missing == ["Missing Lib X"]
    assert unnecessary == ["Some Unnecessary Text"]


def test_mod_detail_view_report_author_lifecycle(qapp):
    from src.ui.views.mod_detail_view import ModDetailView

    view = ModDetailView()
    view.mod_data = {
        "id": 100,
        "title": "Custom Trait Mod",
        "author": "CreatorSims",
        "source": "loverslab",
        "page_url": "https://loverslab.com/files/file/100-custom-trait/",
        "remote_id": "100",
    }

    # When mod has unfound dependencies, btn_report_author must be visible
    mod_details = {
        "requirements_status": "PENDING_VERIFICATION",
        "requirements_text": "MissingCoreLibrary",
        "dependencies": [
            {
                "remote_id": "999",
                "title": "MissingCoreLibrary",
                "status": "NOT_DETECTED_FINISHED",
                "is_installed": False,
            }
        ],
    }

    with patch.object(view, "_trigger_check_report_status"):
        view._render_requirements(mod_details)
        assert not view.btn_report_author.isHidden()
        assert view.btn_report_author.isEnabled() is False
        assert "MissingCoreLibrary" in view._unfound_dep_names

        # Status ready: already reported
        view._on_report_status_ready({
            "can_report": False,
            "already_reported": True,
            "reported_at": "10/09/2026 à 10:00",
            "formatted_message": "Hi @CreatorSims...",
            "author": "@CreatorSims",
            "is_authenticated": True,
        })
        assert view.btn_report_author.isEnabled() is False
        assert "10/09/2026" in view.btn_report_author.text()

        # Status ready: can report
        view._on_report_status_ready({
            "can_report": True,
            "already_reported": False,
            "reported_at": None,
            "formatted_message": "Hi @CreatorSims...",
            "author": "@CreatorSims",
            "is_authenticated": True,
        })
        assert view.btn_report_author.isEnabled() is True
        assert "Interpeler" in view.btn_report_author.text() or "Notify" in view.btn_report_author.text()

        # Report sent successfully callback
        view._on_report_sent_success("à l'instant")
        assert view.btn_report_author.isEnabled() is False
        assert "interpelé" in view.btn_report_author.text().lower() or "notified" in view.btn_report_author.text().lower()


def test_mod_detail_view_categorized_dependencies_rendering(qapp):
    from src.ui.views.mod_detail_view import ModDetailView
    from PySide6.QtWidgets import QLabel

    view = ModDetailView()
    view.mod_data = {
        "id": 200,
        "title": "Mega Overhaul Mod",
        "author": "AwesomeAuthor",
        "source": "loverslab",
        "page_url": "https://loverslab.com/files/file/200-mega-overhaul/",
        "remote_id": "200",
    }

    categorized_data = {
        "requirements_status": "PENDING_VERIFICATION",
        "requirements_text": "Requires City Living, XML Injector, WickedWhims, and UnknownFramework",
        "dependencies": [
            {
                "remote_id": "EP03",
                "title": "The Sims 4 : City Living",
                "is_game_dlc": True,
                "is_installed": True,
                "status": "GAME_DLC",
            },
            {
                "remote_id": "501",
                "title": "XML Injector",
                "is_game_dlc": False,
                "is_installed": False,
                "status": "DETECTED_NOT_INSTALLED",
            },
            {
                "remote_id": "3169",
                "title": "WickedWhims",
                "is_game_dlc": False,
                "is_installed": True,
                "status": "INSTALLED",
            },
            {
                "remote_id": "",
                "title": "UnknownFramework",
                "is_game_dlc": False,
                "is_installed": False,
                "status": "NOT_DETECTED_FINISHED",
            },
        ],
    }

    with patch.object(view, "_trigger_check_report_status"):
        view._render_requirements(categorized_data)

        # 1. Section and body must be visible (not hidden)
        assert not view.req_frame.isHidden()
        assert not view.req_body.isHidden()

        # 2. Extract texts from all labels in deps_layout
        all_texts = []
        for i in range(view.deps_layout.count()):
            w = view.deps_layout.itemAt(i).widget()
            if w:
                for lbl in w.findChildren(QLabel):
                    all_texts.append(lbl.text())
                if isinstance(w, QLabel):
                    all_texts.append(w.text())

        full_content = " ".join(all_texts)

        # Check headers
        assert "Packs DLC" in full_content
        assert "Dépendances trouvées à installer" in full_content
        assert "Dépendances déjà installées" in full_content
        assert "Dépendances introuvables" in full_content

        # Check badges and items
        assert "City Living" in full_content
        assert "Détecté dans le jeu" in full_content
        assert "XML Injector" in full_content
        assert "Sera installé automatiquement" in full_content
        assert "WickedWhims" in full_content
        assert "Déjà installé" in full_content
        assert "UnknownFramework" in full_content
        assert "Introuvable" in full_content

        # Check report button is displayed for UnknownFramework
        assert not view.btn_report_author.isHidden()
        assert "UnknownFramework" in view._unfound_dep_names


def test_interpellate_button_preserved_when_all_deps_are_comments(qapp):
    """Verifies that btn_report_author remains visible even when 100% of dependencies are classified as comments."""
    from src.ui.views.mod_detail_view import ModDetailView

    view = ModDetailView()
    data = {
        "id": 101,
        "title": "Mod With Comments Only",
        "author": "CreatorSims",
        "source": "loverslab",
        "remote_id": "9988",
        "requirements_overrides": {
            "Note About Installation": "COMMENT",
            "Please Read Description": "COMMENT",
        },
        "dependencies": [
            {
                "remote_id": "",
                "title": "Note About Installation",
                "is_game_dlc": False,
                "is_installed": False,
                "status": "NOT_DETECTED_FINISHED",
            },
            {
                "remote_id": "",
                "title": "Please Read Description",
                "is_game_dlc": False,
                "is_installed": False,
                "status": "NOT_DETECTED_FINISHED",
            },
        ],
    }

    with patch.object(view, "_trigger_check_report_status") as mock_check:
        view.mod_data = data
        view._render_requirements(data)

        # The report author button must remain visible!
        assert not view.btn_report_author.isHidden()
        assert len(view._unfound_dep_names) == 0
        assert len(view._comment_deps) == 2
        mock_check.assert_called_once()


def test_report_preview_dialog_scroll_and_bidirectional_sync(qapp):
    """Verifies ReportPreviewDialog contains a QScrollArea and emits override_changed when toggling choices."""
    from PySide6.QtWidgets import QScrollArea
    from src.ui.components.report_preview_dialog import ReportPreviewDialog

    dlg = ReportPreviewDialog(
        mod_title="Custom Animation Pack",
        author="AnimAuthor",
        missing_modules=[],
        unnecessary_modules=["Note 1", "Note 2"],
        requirements_overrides={"Note 1": "COMMENT", "Note 2": "COMMENT"},
        source="loverslab",
    )

    # 1. Must contain a QScrollArea for module choices
    scroll_areas = dlg.findChildren(QScrollArea)
    assert len(scroll_areas) >= 1

    # 2. Message generated must specifically target comments (not missing files)
    message_text = dlg.text_edit.toPlainText()
    assert "Note 1" in message_text
    assert "comments" in message_text.lower() or "text notes" in message_text.lower()
    assert "could not be identified" not in message_text

    # 3. Bidirectional override change signal
    received_overrides = []
    dlg.override_changed.connect(lambda name, o_type: received_overrides.append((name, o_type)))

    # Toggle Note 1 to "MOD" (missing module)
    note1_item = next(item for item in dlg.module_items if item["name"] == "Note 1")
    note1_item["rb_missing"].setChecked(True)

    assert ("Note 1", "MOD") in received_overrides
    assert dlg.requirements_overrides["Note 1"] == "MOD"
    # The message should now contain the missing modules section
    new_message = dlg.text_edit.toPlainText()
    assert "could not be identified" in new_message.lower()


