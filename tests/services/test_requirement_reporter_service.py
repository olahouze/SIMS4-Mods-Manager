from unittest.mock import MagicMock, patch
from src.services.requirement_reporter_service import RequirementReporterService


def test_format_author_mention():
    assert RequirementReporterService.format_author_mention("TurboDriver") == "@TurboDriver"
    assert RequirementReporterService.format_author_mention("@TurboDriver") == "@TurboDriver"
    assert RequirementReporterService.format_author_mention("") == "@Author"
    assert RequirementReporterService.format_author_mention("   ") == "@Author"


def test_build_english_message():
    msg = RequirementReporterService.build_english_message(
        mod_title="Custom Wicked Animations",
        author="KikiSims",
        missing_modules=["WW Core Package", "Nisa Kinky Pack"],
    )
    assert "Hi @KikiSims," in msg
    assert 'In the Requirements section for "Custom Wicked Animations"' in msg
    assert "- WW Core Package" in msg
    assert "- Nisa Kinky Pack" in msg
    assert "Could you please check or clarify the exact name or link" in msg
    assert "Thank you!" in msg


def test_build_english_message_with_unnecessary_and_mixed():
    # Only unnecessary items
    msg_unnecessary = RequirementReporterService.build_english_message(
        mod_title="Conversation Mod",
        author="ModMaker",
        unnecessary_modules=["No third-party library is required", "Script mods enabled"],
    )
    assert "Hi @ModMaker," in msg_unnecessary
    assert "do not appear to be mods or required files" in msg_unnecessary
    assert "- No third-party library is required" in msg_unnecessary
    assert "- Script mods enabled" in msg_unnecessary

    # Mixed missing and unnecessary
    msg_mixed = RequirementReporterService.build_english_message(
        mod_title="Complex Mod",
        author="SimAuthor",
        missing_modules=["Real Missing Library"],
        unnecessary_modules=["Conversation lock is a script only mod"],
    )
    assert "1) The following required module(s) could not be identified" in msg_mixed
    assert "- Real Missing Library" in msg_mixed
    assert "2) Additionally, the following item(s) listed under Requirements do not appear to be mods" in msg_mixed
    assert "- Conversation lock is a script only mod" in msg_mixed


def test_check_report_status_not_authenticated():
    with patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=False):
        res = RequirementReporterService.check_report_status(
            source="loverslab",
            page_url="https://www.loverslab.com/files/file/123-test/",
            mod_title="Test Mod",
            author="ModAuthor",
            missing_modules=["MissingLib"],
        )
        assert res["can_report"] is False
        assert res["already_reported"] is False
        assert res["is_authenticated"] is False
        assert "non connecté" in res["reason"]


def test_check_report_status_already_commented():
    mock_provider = MagicMock()
    mock_provider.check_user_already_commented.return_value = (True, "12/09/2026 à 14:32")

    with patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=True), \
         patch("src.providers.ProviderRegistry.get_provider", return_value=mock_provider):
        res = RequirementReporterService.check_report_status(
            source="loverslab",
            page_url="https://www.loverslab.com/files/file/123-test/",
            mod_title="Test Mod",
            author="ModAuthor",
            missing_modules=["MissingLib"],
        )
        assert res["can_report"] is False
        assert res["already_reported"] is True
        assert res["reported_at"] == "12/09/2026 à 14:32"
        assert res["is_authenticated"] is True
        mock_provider.check_user_already_commented.assert_called_once()


def test_check_report_status_can_report():
    mock_provider = MagicMock()
    mock_provider.check_user_already_commented.return_value = (False, None)

    with patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=True), \
         patch("src.providers.ProviderRegistry.get_provider", return_value=mock_provider):
        res = RequirementReporterService.check_report_status(
            source="loverslab",
            page_url="https://www.loverslab.com/files/file/123-test/",
            mod_title="Test Mod",
            author="ModAuthor",
            missing_modules=["MissingLib"],
        )
        assert res["can_report"] is True
        assert res["already_reported"] is False
        assert res["reported_at"] is None
        assert res["is_authenticated"] is True


def test_submit_report_blocks_when_already_reported():
    mock_provider = MagicMock()
    mock_provider.check_user_already_commented.return_value = (True, "12/09/2026 à 14:32")

    with patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=True), \
         patch("src.providers.ProviderRegistry.get_provider", return_value=mock_provider):
        res = RequirementReporterService.submit_report(
            source="loverslab",
            page_url="https://www.loverslab.com/files/file/123-test/",
            mod_title="Test Mod",
            author="ModAuthor",
            missing_modules=["MissingLib"],
        )
        assert res["success"] is False
        assert res["already_reported"] is True
        assert "déjà été interpelé" in res["message"]
        mock_provider.post_mod_comment.assert_not_called()


def test_submit_report_success():
    mock_provider = MagicMock()
    mock_provider.check_user_already_commented.return_value = (False, None)
    mock_provider.post_mod_comment.return_value = (True, "Message publié avec succès sur le forum LoversLab.")

    with patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=True), \
         patch("src.providers.ProviderRegistry.get_provider", return_value=mock_provider):
        res = RequirementReporterService.submit_report(
            source="loverslab",
            page_url="https://www.loverslab.com/files/file/123-test/",
            mod_title="Test Mod",
            author="ModAuthor",
            missing_modules=["MissingLib"],
        )
        assert res["success"] is True
        assert res["already_reported"] is True
        assert res["reported_at"] == "à l'instant"
        mock_provider.post_mod_comment.assert_called_once()
