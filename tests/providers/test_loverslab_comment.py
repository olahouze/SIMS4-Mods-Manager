from unittest.mock import MagicMock, patch
from src.providers.loverslab.scraper import LoversLabProvider


def test_loverslab_check_user_already_commented_found():
    provider = LoversLabProvider()

    mock_html = """
    <html>
        <body>
            <div class="cFileComments">
                <article class="ipsComment" data-memberid="999888">
                    <a href="https://www.loverslab.com/profile/999888-myuser/">MyUser</a>
                    <time datetime="2026-09-12T14:32:00Z" title="12/09/2026 14:32">September 12</time>
                    <div data-role="commentContent" class="ipsType_richText">
                        <p>Hi @Author, in the Requirements section for this mod, the module WW Core Package was not found.</p>
                    </div>
                </article>
            </div>
        </body>
    </html>
    """

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = mock_html
    mock_session.get.return_value = mock_resp

    mock_acc = MagicMock()
    mock_acc.user_display_name = "MyUser"
    mock_acc.get_cookies_dict.return_value = {"ips4_member_id": "999888"}

    with patch("src.core.session_manager.SessionManager.get_saved_session", return_value=mock_acc), \
         patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=True), \
         patch("src.core.session_manager.SessionManager.get_http_session", return_value=mock_session):

        found, date_str = provider.check_user_already_commented(
            page_url="https://www.loverslab.com/files/file/3169-test/",
            required_keywords=["WW Core Package"],
        )

        assert found is True
        assert date_str is not None
        assert "12/09/2026" in date_str


def test_loverslab_check_user_already_commented_other_user():
    provider = LoversLabProvider()

    mock_html = """
    <html>
        <body>
            <div class="cFileComments">
                <article class="ipsComment" data-memberid="111222">
                    <a href="https://www.loverslab.com/profile/111222-otheruser/">OtherUser</a>
                    <time datetime="2026-09-12T14:32:00Z" title="12/09/2026 14:32">September 12</time>
                    <div data-role="commentContent" class="ipsType_richText">
                        <p>Hi @Author, requirements WW Core Package not found.</p>
                    </div>
                </article>
            </div>
        </body>
    </html>
    """

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = mock_html
    mock_session.get.return_value = mock_resp

    mock_acc = MagicMock()
    mock_acc.user_display_name = "MyUser"
    mock_acc.get_cookies_dict.return_value = {"ips4_member_id": "999888"}

    with patch("src.core.session_manager.SessionManager.get_saved_session", return_value=mock_acc), \
         patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=True), \
         patch("src.core.session_manager.SessionManager.get_http_session", return_value=mock_session):

        found, date_str = provider.check_user_already_commented(
            page_url="https://www.loverslab.com/files/file/3169-test/",
            required_keywords=["WW Core Package"],
        )

        assert found is False
        assert date_str is None


def test_loverslab_post_mod_comment_success():
    provider = LoversLabProvider()

    mock_page_html = """
    <html>
        <body>
            <form action="https://www.loverslab.com/files/file/3169-test/?do=addComment" method="post">
                <input type="hidden" name="csrfKey" value="a1b2c3d4e5f60718293a4b5c6d7e8f90">
            </form>
        </body>
    </html>
    """

    mock_session = MagicMock()
    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 200
    mock_get_resp.text = mock_page_html

    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.text = "<html><body><div>Comment added</div></body></html>"

    mock_session.get.return_value = mock_get_resp
    mock_session.post.return_value = mock_post_resp

    with patch("src.core.session_manager.SessionManager.is_member_authenticated", return_value=True), \
         patch("src.core.session_manager.SessionManager.get_http_session", return_value=mock_session):

        success, msg = provider.post_mod_comment(
            page_url="https://www.loverslab.com/files/file/3169-test/",
            message="Hi @Author, please check requirements.",
        )

        assert success is True
        assert "succès" in msg.lower()
        mock_session.post.assert_called_once()
        call_kwargs = mock_session.post.call_args[1]
        assert call_kwargs["data"]["csrfKey"] == "a1b2c3d4e5f60718293a4b5c6d7e8f90"
        assert "Hi @Author" in call_kwargs["data"]["comment_value"]
