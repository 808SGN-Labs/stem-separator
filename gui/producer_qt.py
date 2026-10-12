#!/usr/bin/env python3
"""StemLab producer interface — local Qt frontend for scripts/stem-separate."""

import os
import re
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QVBoxLayout, QWidget,
)

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "stem-separate"
# tqdm reports per-model steps, not overall job completion.
STEP_PROGRESS = re.compile(r"(\d{1,3})%\|[^\r\n]*?\|\s*(\d+)\s*/\s*(\d+)")
FOUR_STEM_PRESETS = {"balanced", "4stems", "maximum"}

PRESETS = [
    ("Balanced · Recommended", "balanced", "4 stems · Best practical CPU starting point"),
    ("Fast · Preview", "4stems", "4 stems · Faster, lower bass quality in pilot"),
    ("Maximum · Fine-tuned", "maximum", "4 stems · Slower, stronger bass in pilot"),
    ("Vocals · RoFormer", "vocals", "2 stems · Vocal extraction"),
    ("Six stems", "6stems", "6 stems · Includes piano and guitar"),
    ("Drum parts · Specialist", "drum-parts", "Use isolated drum stem as input"),
    ("De-reverb · Specialist", "deverb", "Use isolated vocal stem as input"),
]

STYLE = """
QWidget { color: #e6ecf0; font-size: 13px; font-family: 'Noto Sans', sans-serif; }
QMainWindow, QWidget#appRoot { background: #12171d; }
QLabel { background: transparent; }
QFrame#panel { background: #1a222b; border: 1px solid #2d3a46; border-radius: 12px; }
QLabel#brand { font-size: 26px; font-weight: 800; color: #f0f6f8; }
QLabel#muted { color: #91a5b4; }
QLabel#section { font-size: 15px; font-weight: 700; }
QLineEdit, QComboBox, QPlainTextEdit {
    background: #0d1319; color: #e8f0f4; border: 1px solid #364653;
    border-radius: 7px; padding: 9px; selection-background-color: #4c9b96;
}
QLineEdit:focus, QComboBox:focus { border: 1px solid #73d6c6; }
QComboBox QAbstractItemView { background: #1a222b; color: #e6ecf0; selection-background-color: #345a62; }
QPushButton { background: #283642; color: #ecf3f7; border: 1px solid #415260;
              border-radius: 7px; padding: 10px 15px; font-weight: 600; }
QPushButton:hover { background: #364958; }
QPushButton:disabled { color: #637581; background: #202a33; border-color: #2c3944; }
QPushButton#primary { background: #73d6c6; color: #102326; border-color: #73d6c6; font-weight: 800; }
QPushButton#primary:hover { background: #95e4d6; }
QPushButton#primary:disabled { background: #263b3d; color: #728987; border-color: #304a4b; }
QProgressBar { background: #0c1218; border: 1px solid #374753; border-radius: 5px;
               text-align: center; height: 9px; }
QProgressBar::chunk { background: #73d6c6; border-radius: 4px; }
"""


class DropEdit(QLineEdit):
    fileDropped = Signal(str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setPlaceholderText("Drop an audio file here or browse…")

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            self.fileDropped.emit(urls[0].toLocalFile())
            event.acceptProposedAction()


class Producer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("808SGN StemLab — Producer")
        self.resize(980, 740)
        self.setMinimumSize(760, 580)
        self.process = None
        self.cancel_requested = False
        self.output_user_set = False
        self.current_output = None
        self._progress_tail = ""
        self.build_ui()

    def build_ui(self):
        outer = QWidget()
        outer.setObjectName("appRoot")
        self.setCentralWidget(outer)
        root = QVBoxLayout(outer)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(17)

        header = QHBoxLayout()
        brand = QLabel("808SGN  /  STEMLAB")
        brand.setObjectName("brand")
        header.addWidget(brand)
        header.addStretch()
        tag = QLabel("LOCAL  ·  CPU  ·  OFFLINE PROCESSING")
        tag.setObjectName("muted")
        header.addWidget(tag)
        root.addLayout(header)

        sub = QLabel("Producer workspace  /  Separate audio into remix-ready stems")
        sub.setObjectName("muted")
        root.addWidget(sub)

        panel = QFrame()
        panel.setObjectName("panel")
        box = QVBoxLayout(panel)
        box.setContentsMargins(20, 20, 20, 20)
        box.setSpacing(12)
        box.addWidget(self.section("01   SOURCE AUDIO"))
        source_row = QHBoxLayout()
        self.input = DropEdit()
        self.input.fileDropped.connect(self.set_input)
        self.input.textChanged.connect(self.update_output)
        source_row.addWidget(self.input, 1)
        browse = QPushButton("Browse")
        browse.clicked.connect(self.browse_input)
        source_row.addWidget(browse)
        box.addLayout(source_row)
        hint = QLabel("WAV / FLAC recommended · MP3, M4A, OGG and AIFF accepted by backend")
        hint.setObjectName("muted")
        box.addWidget(hint)

        box.addSpacing(10)
        box.addWidget(self.section("02   SEPARATION MODE"))
        self.presets = QComboBox()
        for label, code, desc in PRESETS:
            self.presets.addItem(label, code)
        self.presets.currentIndexChanged.connect(self.update_preset)
        box.addWidget(self.presets)
        self.description = QLabel(PRESETS[0][2])
        self.description.setObjectName("muted")
        box.addWidget(self.description)

        box.addSpacing(10)
        box.addWidget(self.section("03   EXPORT DIRECTORY"))
        export_row = QHBoxLayout()
        self.output = QLineEdit()
        self.output.setPlaceholderText("Automatically set after choosing source")
        self.output.textEdited.connect(self.mark_output_custom)
        export_row.addWidget(self.output, 1)
        output_browse = QPushButton("Browse")
        output_browse.clicked.connect(self.browse_output)
        export_row.addWidget(output_browse)
        box.addLayout(export_row)
        root.addWidget(panel)

        action = QHBoxLayout()
        self.start_button = QPushButton("START SEPARATION  →")
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self.start)
        action.addWidget(self.start_button)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel)
        action.addWidget(self.cancel_button)
        open_button = QPushButton("Open output folder")
        open_button.clicked.connect(self.open_output)
        action.addWidget(open_button)
        action.addStretch()
        root.addLayout(action)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)  # Backend reports no reliable percentage.
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        progress_row = QHBoxLayout()
        progress_row.addWidget(self.progress, 1)
        self.stage_label = QLabel("IDLE")
        self.stage_label.setObjectName("muted")
        progress_row.addWidget(self.stage_label)
        root.addLayout(progress_row)

        log_header = QHBoxLayout()
        log_header.addWidget(self.section("PROCESS LOG"))
        log_header.addStretch()
        self.status = QLabel("READY")
        self.status.setObjectName("muted")
        log_header.addWidget(self.status)
        root.addLayout(log_header)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Your local processing output appears here.")
        root.addWidget(self.log, 1)

        footer = QLabel("StemLab research preview  ·  Pilot model rankings are source-dependent")
        footer.setObjectName("muted")
        root.addWidget(footer)

    @staticmethod
    def section(title):
        label = QLabel(title)
        label.setObjectName("section")
        return label

    def set_input(self, path):
        if Path(path).is_file():
            self.input.setText(path)
        else:
            QMessageBox.warning(self, "Invalid input", "Choose an existing audio file.")

    def browse_input(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose source audio", "",
            "Audio (*.wav *.flac *.mp3 *.m4a *.ogg *.aiff *.aif);;All files (*)"
        )
        if path:
            self.set_input(path)

    def browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if path:
            self.output_user_set = True
            self.output.setText(path)

    def mark_output_custom(self, _):
        self.output_user_set = True

    def update_output(self, _=None):
        if self.output_user_set:
            return
        value = self.input.text().strip()
        if value:
            source = Path(value).expanduser()
            self.output.setText(str(source.parent / (source.stem + "_stemlab") / self.presets.currentData()))
        else:
            self.output.clear()

    def update_preset(self, index):
        self.description.setText(PRESETS[index][2])
        self.update_output()

    def append_log(self, data):
        self.log.appendPlainText(data.rstrip("\n"))
        scrollbar = self.log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def start(self):
        source = Path(self.input.text().strip()).expanduser()
        if not source.is_file():
            QMessageBox.warning(self, "Input missing", "Select an existing source audio file.")
            return
        if not WRAPPER.is_file() or not os.access(WRAPPER, os.X_OK):
            QMessageBox.critical(self, "Backend unavailable", "Executable scripts/stem-separate was not found.")
            return
        output_text = self.output.text().strip()
        if not output_text:
            QMessageBox.warning(self, "Output missing", "Select an output directory.")
            return
        dest = Path(output_text).expanduser().resolve()
        try:
            if dest == source.resolve() or dest == source.parent.resolve():
                QMessageBox.warning(self, "Unsafe output", "Choose a separate output directory.")
                return
            if dest.exists() and any(dest.iterdir()):
                answer = QMessageBox.question(
                    self, "Non-empty output folder",
                    "This folder contains files. Continue? Existing files may be overwritten.",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if answer != QMessageBox.Yes:
                    return
            dest.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            QMessageBox.critical(self, "Output error", str(error))
            return

        self.cancel_requested = False
        self.current_output = dest
        self._progress_tail = ""
        self.stage_label.setText("STARTING")
        self.log.clear()
        self.append_log(f"Preset: {self.presets.currentData()}\nSource: {source}\nOutput: {dest}\n")
        self.process = QProcess(self)
        self.process.setProgram(str(WRAPPER))
        self.process.setArguments([self.presets.currentData(), str(source), str(dest)])
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.errorOccurred.connect(self.process_error)
        self.process.finished.connect(self.finished)
        self.set_running(True)
        self.status.setText("PROCESSING")
        self.process.start()

    def read_output(self):
        if self.process is not None:
            data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
            if data:
                self._progress_tail = (self._progress_tail + data)[-4096:]
                matches = list(STEP_PROGRESS.finditer(self._progress_tail))
                if matches:
                    _, current, total = map(int, matches[-1].groups())
                    if total > 0:
                        self.progress.setRange(0, total)
                        self.progress.setValue(min(current, total))
                        self.stage_label.setText(f"MODEL STEP {current}/{total}")
                self.append_log(data)

    def process_error(self, error):
        self.append_log(f"Process error: {self.process.errorString() if self.process else error}")
        if error == QProcess.FailedToStart and self.process is not None:
            self.set_running(False)
            self.status.setText("FAILED")
            self.stage_label.setText("START FAILED")
            self.process.deleteLater()
            self.process = None

    @staticmethod
    def probe_audio(path):
        command = [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,sample_rate,channels,bits_per_sample:format=duration",
            "-of", "json", str(path),
        ]
        import json
        result = subprocess.run(command, capture_output=True, text=True, timeout=12, check=True)
        payload = json.loads(result.stdout)
        stream = (payload.get("streams") or [{}])[0]
        return {
            "duration": float(payload["format"]["duration"]),
            "rate": int(stream["sample_rate"]),
            "channels": int(stream["channels"]),
            "codec": stream.get("codec_name", "unknown"),
        }

    def validate_output(self):
        """Check four-stem runs only; do not imply other presets were validated."""
        if self.presets.currentData() not in FOUR_STEM_PRESETS:
            self.append_log("Output check: manual inspection required for this preset.")
            return True
        source = Path(self.input.text().strip()).expanduser()
        output_dir = self.current_output
        model = {"balanced": "htdemucs", "4stems": "hdemucs_mmi", "maximum": "htdemucs_ft"}[self.presets.currentData()]
        expected = {}
        for stem in ("Bass", "Drums", "Other", "Vocals"):
            matches = [output_dir / f"{source.stem}_({stem})_{model}.wav"]
            matches = [path for path in matches if path.is_file()]
            if len(matches) != 1 or matches[0].stat().st_size == 0:
                self.append_log(f"Output check FAILED: expected one nonempty {stem} WAV; found {len(matches)}.")
                return False
            expected[stem] = matches[0]
        try:
            source_info = self.probe_audio(source)
            for stem, path in expected.items():
                info = self.probe_audio(path)
                if info["codec"] not in ("pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_f32le"):
                    raise ValueError(f"{stem}: unsupported WAV codec {info['codec']}")
                if info["channels"] != source_info["channels"]:
                    raise ValueError(f"{stem}: channel count differs from input")
                if abs(info["duration"] - source_info["duration"]) > 0.25:
                    raise ValueError(f"{stem}: duration differs by more than 0.25 seconds")
                self.append_log("Verified {}: {} Hz / {} ch / {} / {:.2f}s".format(stem, info["rate"], info["channels"], info["codec"], info["duration"]))
        except (OSError, subprocess.SubprocessError, KeyError, IndexError, ValueError) as exc:
            self.append_log(f"Output check FAILED: {exc}")
            return False
        self.append_log("Output check PASSED: four WAV stems exist, metadata and durations verified.")
        return True

    def finished(self, code, exit_status):
        if self.process is None:
            return
        self.read_output()
        if self.cancel_requested:
            self.status.setText("CANCELLED")
            self.append_log("Cancelled. Partial output may remain.")
        elif code == 0 and exit_status == QProcess.NormalExit:
            if self.validate_output():
                self.status.setText("COMPLETE")
                self.append_log("Separation finished successfully.")
            else:
                self.status.setText("CHECK OUTPUT")
                self.append_log("Processing exited successfully, but output verification failed.")
        else:
            self.status.setText("FAILED")
            self.append_log(f"Separation failed (exit code {code}).")
        self.set_running(False)
        self.stage_label.setText("VERIFIED" if self.status.text() == "COMPLETE" and self.presets.currentData() in FOUR_STEM_PRESETS else self.status.text())
        self.process.deleteLater()
        self.process = None

    def set_running(self, running):
        self.start_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.presets.setEnabled(not running)
        self.input.setEnabled(not running)
        self.output.setEnabled(not running)
        self.progress.setRange(0, 0 if running else 100)
        if not running:
            self.progress.setValue(0)

    def cancel(self):
        if self.process is None or self.process.state() == QProcess.NotRunning:
            return
        self.cancel_requested = True
        self.status.setText("CANCELLING")
        self.process.terminate()

    def open_output(self):
        output_text = self.output.text().strip()
        if self.current_output is None and not output_text:
            QMessageBox.information(self, "Output", "No output folder is selected yet.")
            return
        target = self.current_output or Path(output_text).expanduser()
        if not target.is_dir():
            QMessageBox.information(self, "Output", "No output folder exists yet.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def closeEvent(self, event):
        if self.process is not None and self.process.state() != QProcess.NotRunning:
            answer = QMessageBox.question(
                self, "Separation running", "Cancel the current job and close?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self.cancel()
            if not self.process.waitForFinished(3000):
                self.process.kill()
                self.process.waitForFinished(2000)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = Producer()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
