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
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #2d334d;
    min-height: 25px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #4f46e5;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
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
