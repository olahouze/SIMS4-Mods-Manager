from typing import Optional
from PySide6.QtWidgets import QMessageBox, QWidget, QPushButton

from src.i18n import tr


class DialogHelper:
    """
    Standardized, dark-themed confirmation and alert dialog helpers.
    Applies unified styling, proper button focus, and multilingual support.
    """

    DARK_MESSAGEBOX_STYLE = """
        QMessageBox {
            background-color: #0f121d;
            color: #f8fafc;
            font-size: 13px;
        }
        QLabel {
            color: #cbd5e1;
            font-size: 12px;
        }
        QPushButton {
            background-color: #1e2438;
            color: #f1f5f9;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 6px 14px;
            font-weight: 600;
            font-size: 12px;
            min-width: 70px;
        }
        QPushButton:hover {
            background-color: #28314d;
            border-color: #6366f1;
        }
    """

    @classmethod
    def confirm(
        cls,
        parent: Optional[QWidget],
        title: str,
        message: str,
        confirm_text: Optional[str] = None,
        cancel_text: Optional[str] = None,
        is_destructive: bool = False,
    ) -> bool:
        """Displays a confirmation dialog and returns True if confirmed."""
        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Question if not is_destructive else QMessageBox.Icon.Warning)
        msg_box.setStyleSheet(cls.DARK_MESSAGEBOX_STYLE)

        confirm_btn = QPushButton(confirm_text or tr("dialogs.confirm"))
        if is_destructive:
            confirm_btn.setStyleSheet("""
                QPushButton {
                    background-color: #991b1b;
                    color: #ffffff;
                    border: 1px solid #dc2626;
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-weight: 700;
                }
                QPushButton:hover { background-color: #b91c1c; }
            """)
        else:
            confirm_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4f46e5;
                    color: #ffffff;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-weight: 700;
                }
                QPushButton:hover { background-color: #6366f1; }
            """)

        cancel_btn = QPushButton(cancel_text or tr("dialogs.cancel"))

        msg_box.addButton(cancel_btn, QMessageBox.ButtonRole.RejectRole)
        msg_box.addButton(confirm_btn, QMessageBox.ButtonRole.AcceptRole)
        msg_box.setDefaultButton(cancel_btn if is_destructive else confirm_btn)

        msg_box.exec()
        return msg_box.clickedButton() == confirm_btn

    @classmethod
    def error(cls, parent: Optional[QWidget], title: str, message: str) -> None:
        """Displays a standardized error dialog."""
        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setStyleSheet(cls.DARK_MESSAGEBOX_STYLE)
        ok_btn = msg_box.addButton(tr("dialogs.close"), QMessageBox.ButtonRole.AcceptRole)
        msg_box.setDefaultButton(ok_btn)
        msg_box.exec()

    @classmethod
    def info(cls, parent: Optional[QWidget], title: str, message: str) -> None:
        """Displays a standardized info dialog."""
        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setStyleSheet(cls.DARK_MESSAGEBOX_STYLE)
        ok_btn = msg_box.addButton(tr("dialogs.ok"), QMessageBox.ButtonRole.AcceptRole)
        msg_box.setDefaultButton(ok_btn)
        msg_box.exec()

    @classmethod
    def success(cls, parent: Optional[QWidget], title: str, message: str) -> None:
        """Displays a standardized success dialog."""
        cls.info(parent, title, message)
