import sys

from PySide6.QtWidgets import QApplication

from kai_metadata_inspector.config import APP_VERSION
from kai_metadata_inspector.core.runtime import runtime_diagnostics
from kai_metadata_inspector.ui.main_window import MainWindow


def main():
    if "--version" in sys.argv:
        print(APP_VERSION)
        return
    if "--diagnostics" in sys.argv:
        diagnostics = runtime_diagnostics()
        print(f"Kai Metadata Inspector {APP_VERSION}")
        for key, value in diagnostics.items():
            print(f"{key}: {value}")
        raise SystemExit(0 if diagnostics["status"] == "ok" else 1)
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
