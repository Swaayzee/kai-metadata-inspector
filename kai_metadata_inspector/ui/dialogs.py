from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class MetadataEditorDialog(QDialog):
    FIELDS = [
        ("title", "Title"),
        ("description", "Description"),
        ("creator", "Creator / author"),
        ("rights", "Copyright / rights"),
        ("keywords", "Keywords (comma-separated)"),
        ("camera_make", "Camera make"),
        ("camera_model", "Camera model"),
        ("lens_make", "Lens make"),
        ("lens_model", "Lens model"),
        ("gps_latitude", "GPS latitude (signed decimal)"),
        ("gps_longitude", "GPS longitude (signed decimal)"),
        ("gps_altitude", "GPS altitude (metres)"),
        ("date_taken", "Date taken (YYYY:MM:DD HH:MM:SS)"),
    ]

    def __init__(self, initial: dict[str, str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit metadata — backup created before saving")
        self.resize(620, 620)
        layout = QVBoxLayout(self)
        note = QLabel("This changes the selected file. Kai creates a recovery copy first.")
        note.setObjectName("WarningLabel")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.inputs: dict[str, QLineEdit] = {}
        for key, label in self.FIELDS:
            edit = QLineEdit(initial.get(key, ""))
            self.inputs[key] = edit
            form.addRow(label, edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict[str, Any]:
        values: dict[str, Any] = {key: edit.text().strip() for key, edit in self.inputs.items()}
        values["keywords"] = [item.strip() for item in values["keywords"].split(",") if item.strip()]
        return values


class CleaningComparisonDialog(QDialog):
    def __init__(self, result: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.inspect_requested = False
        self.setWindowTitle("Cleaning comparison")
        self.resize(720, 560)
        layout = QVBoxLayout(self)

        heading = QLabel(
            f"BEFORE  {result['before_tag_count']} TAGS    →    "
            f"AFTER  {result['after_tag_count']} TAGS    //    "
            f"REMOVED  {result['removed_tag_count']}"
        )
        heading.setObjectName("ComparisonHeading")
        layout.addWidget(heading)

        safety = QLabel(
            "ORIGINAL VERIFIED UNCHANGED" if result.get("original_unchanged") else "WARNING: ORIGINAL HASH CHANGED"
        )
        safety.setObjectName("SuccessLabel" if result.get("original_unchanged") else "WarningLabel")
        layout.addWidget(safety)

        columns = QHBoxLayout()
        removed = QPlainTextEdit()
        removed.setReadOnly(True)
        removed.setPlainText("REMOVED TAGS\n\n" + ("\n".join(result.get("removed_keys", [])) or "None"))
        remaining = QPlainTextEdit()
        remaining.setReadOnly(True)
        remaining.setPlainText("REMAINING TAGS\n\n" + ("\n".join(result.get("remaining_keys", [])) or "None"))
        columns.addWidget(removed)
        columns.addWidget(remaining)
        layout.addLayout(columns, 1)

        path = QLabel(f"Cleaned copy: {result['output_path']}")
        path.setObjectName("PathLabel")
        path.setWordWrap(True)
        layout.addWidget(path)

        buttons = QHBoxLayout()
        inspect = QPushButton("INSPECT CLEANED COPY")
        inspect.setObjectName("PrimaryButton")
        inspect.clicked.connect(self._inspect)
        close = QPushButton("CLOSE")
        close.clicked.connect(self.accept)
        buttons.addStretch()
        buttons.addWidget(inspect)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def _inspect(self) -> None:
        self.inspect_requested = True
        self.accept()
