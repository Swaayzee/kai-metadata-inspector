from __future__ import annotations

APP_STYLESHEET = """
QMainWindow, QWidget { background: #09090c; color: #d7d7df; }
QMenuBar, QMenu { background: #111116; color: #ddd; }
QLabel#TitleLabel { color: #d929ff; font-size: 18px; font-weight: 700; letter-spacing: 1px; }
QLabel#RiskLabel { color: #8cf7ff; border: 1px solid #31565c; padding: 6px 10px; font-weight: 700; }
QLabel#PathLabel { color: #88889a; padding: 3px 0; }
QLabel#CountLabel { color: #8cf7ff; padding: 0 8px; }
QLabel#WarningLabel { color: #ffb86b; border-left: 3px solid #ff9b42; padding: 8px; }
QLabel#SuccessLabel { color: #69f0ae; border-left: 3px solid #69f0ae; padding: 8px; }
QLabel#ComparisonHeading { color: #8cf7ff; font-size: 14px; font-weight: 700; padding: 8px 0; }
QPushButton { background: #17171e; border: 1px solid #343444; padding: 8px 12px; color: #e6e6ed; }
QPushButton:hover { border-color: #d929ff; color: white; }
QPushButton:disabled { color: #555563; border-color: #22222a; }
QPushButton#PrimaryButton { background: #351044; border-color: #d929ff; color: white; }
QLineEdit, QPlainTextEdit, QListWidget, QTableWidget {
    background: #101015; border: 1px solid #292934; color: #dad9e3; selection-background-color: #512064;
}
QLineEdit { padding: 8px; }
QHeaderView::section { background: #181820; color: #8cf7ff; border: 0; border-bottom: 1px solid #343444; padding: 7px; }
QTableWidget { gridline-color: #202029; alternate-background-color: #0c0c11; }
QProgressBar { background: #101015; border: 1px solid #292934; color: #d7d7df; text-align: center; min-height: 18px; }
QProgressBar::chunk { background: #6f1d8c; }
QStatusBar { background: #111116; color: #88889a; }
QSplitter::handle { background: #22222b; width: 1px; }
"""
