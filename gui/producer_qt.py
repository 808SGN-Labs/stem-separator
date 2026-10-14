#!/usr/bin/env python3
"""StemLab producer interface — local Qt frontend for scripts/stem-separate."""

import json
import math
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QProcess, QRunnable, QThreadPool, Qt, QUrl, Signal, QTimer, QMimeData, QSettings
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QDrag
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QListWidget, QSizePolicy, QScrollArea,
    QPushButton, QVBoxLayout, QWidget, QToolButton, QTreeWidget, QTreeWidgetItem, QHeaderView, QMenu,
)

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "stem-separate"
# tqdm reports per-model steps, not overall job completion.
STEP_PROGRESS = re.compile(r"(\d{1,3})%\|[^\r\n]*?\|\s*(\d+)\s*/\s*(\d+)")
FOUR_STEM_PRESETS = {"balanced", "4stems", "maximum"}
FOUR_STEM_MODELS = {"balanced": "htdemucs", "4stems": "hdemucs_mmi", "maximum": "htdemucs_ft"}
# The wrapper leaves audio-separator's --sample_rate at its 44.1 kHz default.
FOUR_STEM_OUTPUT_RATE = 44100
AUDIO_SUFFIXES = {".wav", ".flac", ".mp3", ".m4a", ".ogg", ".aiff", ".aif"}
OWNER_FILE = ".stemlab-source.json"
CHECK_TIMEOUT = 20


class CheckSignals(QObject):
    done = Signal(int, int, object)


class OutputCheck(QRunnable):
    def __init__(self, row_id, generation, cancelled, inspect, verify, source, preset, directory):
        super().__init__()
        self.row_id, self.generation, self.cancelled = row_id, generation, cancelled
        self.inspect, self.verify = inspect, verify
        self.source, self.preset, self.directory = source, preset, directory
        self.signals = CheckSignals()

    def run(self):
        state, paths, snapshot = 'BLOCKED', None, None
        try:
            if not self.cancelled.is_set():
                state = self.inspect(self.source, self.preset, self.directory)
                if state == 'EXISTING STEMS' and not self.cancelled.is_set():
                    before = file_snapshot(self.source, self.directory)
                    paths = self.verify(self.source, self.preset, self.directory,
                                        self.cancelled, time.monotonic() + CHECK_TIMEOUT)
                    snapshot = file_snapshot(self.source, self.directory)
                    state = 'VERIFIED EXISTING' if paths and before == snapshot else 'PARTIAL / UNKNOWN'
                elif state == 'PARTIAL / UNKNOWN' and self.preset not in FOUR_STEM_PRESETS | {'drum-parts'}:
                    state = 'UNVERIFIED'
                elif state == 'READY':
                    state = 'QUEUED'
        except (OSError, ValueError, RuntimeError):
            state, paths, snapshot = 'BLOCKED', None, None
        self.signals.done.emit(self.row_id, self.generation, (state, paths, snapshot))


def file_snapshot(source, directory):
    """Cheap identity check; never parse audio on the GUI thread."""
    def stat(path):
        try:
            info = path.lstat()
            return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        except OSError:
            return None
    try:
        entries = tuple(sorted((entry.name, stat(entry)) for entry in directory.iterdir()))
    except OSError:
        entries = None
    return stat(source), stat(directory), entries

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
QMainWindow, QWidget#appRoot, QScrollArea#workspaceScroll { background: #12171d; }
QLabel { background: transparent; }
QFrame#panel { background: #1a222b; border: 1px solid #2d3a46; border-radius: 12px; }
QToolButton { background: transparent; border: 0; color: #a9bcc7; font-weight: 700; padding: 6px 0; }
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
QTreeWidget { background: #10171d; border: 1px solid #33424d; border-radius: 8px; alternate-background-color: #172129; outline: 0; }
QTreeWidget::item { min-height: 36px; padding: 4px 8px; border-bottom: 1px solid #24303a; }
QTreeWidget::item:hover { background: #21323c; }
QTreeWidget::item:selected { background: #29464a; }
QTreeWidget::branch { background: transparent; }
QHeaderView::section { background: #1b2730; color: #a9bfca; border: 0; border-bottom: 1px solid #354651; padding: 10px 8px; font-weight: 700; letter-spacing: 1px; }
QComboBox#queueMode { background: #1c2a33; border: 1px solid #3b4d59; border-radius: 6px; padding: 5px 8px; }
QComboBox#queueMode:hover { border-color: #668b96; }
QPushButton#quiet { background: transparent; border: 1px solid #33424d; color: #acbbc5; }
QPushButton#quiet:hover { background: #253540; color: #e6ecf0; }
QLabel#queueHint { color: #879aa8; font-size: 12px; }
QLabel#footer { color: #718593; font-size: 11px; }
"""

# Neutral base CSS is rendered through named theme palettes; processing logic is unaffected.
THEMES = {
    'Saigon Mint': ('#12171d', '#1a222b', '#0d1319', '#73d6c6', '#29464a'),
    'Studio Graphite': ('#161a1e', '#252b31', '#10151a', '#b5c0c9', '#3b4953'),
    'Analog Orange': ('#1b1918', '#2c2724', '#13100f', '#e6a15a', '#57402e'),
    'Midnight Blue': ('#101722', '#202b3d', '#0b111c', '#82acf1', '#263f64'),
    'Berry & Mint': ('#1b1722', '#302637', '#110e17', '#c38dcc', '#49334f'),
    'Vintage Gold': ('#201d18', '#312b22', '#15120e', '#d9b778', '#564731'),
    'Lavender': ('#191724', '#292538', '#100f1b', '#ae9bf0', '#433a60'),
    'Avocado': ('#1b211a', '#2a3428', '#11170f', '#a6c179', '#40523a'),
}


def theme_stylesheet(name):
    """Substitute all base palette roles at once, avoiding cascading replacements."""
    background, panel, surface, accent, selected = THEMES.get(name, THEMES['Saigon Mint'])
    roles = {
        '#12171d': background, '#1a222b': panel, '#0d1319': surface,
        '#10171d': surface, '#73d6c6': accent, '#75cfc5': accent,
        '#29464a': selected, '#4c9b96': accent, '#95e4d6': accent,
        '#21323c': panel, '#172129': panel, '#1b2730': panel,
        '#202c36': panel, '#283642': panel, '#364958': selected,
        '#1c2a33': panel, '#253540': selected, '#0c1218': surface,
    }
    sheet = re.sub(r'#[0-9a-fA-F]{6}', lambda m: roles.get(m.group(0).lower(), m.group(0)), STYLE)
    return sheet + f"""
QDialog#appearanceDialog {{ background: {background}; color: #e6ecf0; }}
QDialog#appearanceDialog QLabel {{ color: #e6ecf0; }}
QDialog#appearanceDialog QLabel#appearanceHint {{ color: #91a5b4; font-size: 11px; }}
QDialog#appearanceDialog QPushButton {{ background: {panel}; color: #e6ecf0; border: 1px solid {selected}; padding: 7px 10px; }}
QDialog#appearanceDialog QPushButton:hover {{ background: {selected}; }}
QDialog#appearanceDialog QComboBox {{ background: {surface}; border: 1px solid {selected}; }}
QDialog#appearanceDialog QComboBox:focus {{ border-color: {accent}; }}
QDialog#appearanceDialog QComboBox QAbstractItemView {{ background: {panel}; selection-background-color: {selected}; }}
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


class QueueList(QTreeWidget):
    pathsDropped = Signal(list)

    def mousePressEvent(self, event):
        self._drag_origin = event.position().toPoint() if event.button() == Qt.LeftButton else None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._drag_origin is not None and event.buttons() & Qt.LeftButton
                and (event.position().toPoint() - self._drag_origin).manhattanLength()
                >= QApplication.startDragDistance()):
            origin = self._drag_origin
            self._drag_origin = None
            item = self.itemAt(origin)
            path = item.data(0, Qt.UserRole) if item else None
            if path:
                self.drag_stem(item)
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_origin = None
        super().mouseReleaseEvent(event)

    def drag_stem(self, item):
        path = item.data(0, Qt.UserRole) if item else None
        if not path:
            return
        if not self.can_export_item or not self.can_export_item(item):
            return
        if not Path(path).is_file():
            return
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(path))])
        drag = QDrag(self)
        drag.setMimeData(mime)
        return drag.exec(Qt.CopyAction)

    def startDrag(self, supported_actions):
        item = self.currentItem()
        if item:
            self.drag_stem(item)

    def __init__(self):
        super().__init__()
        self.can_export_item = None
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeWidget.DragDrop)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.CopyAction)
        self.setColumnCount(3)
        self.setHeaderLabels(["FILE", "MODE", "STATUS"])
        self.setAlternatingRowColors(True)
        self.setRootIsDecorated(True)
        self.setIndentation(22)
        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.header().setSectionResizeMode(1, QHeaderView.Fixed)
        self.header().resizeSection(1, 240)
        self.header().setSectionResizeMode(2, QHeaderView.Fixed)
        self.header().resizeSection(2, 170)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._drag_origin = None

    def dragEnterEvent(self, event):
        if any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.pathsDropped.emit(paths)
            event.acceptProposedAction()


class Producer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("808SGN StemLab — Producer")
        self.resize(1080, 720)
        self.setMinimumSize(760, 540)
        self.process = None
        self.cancel_requested = False
        self.output_user_set = False
        self.current_output = None
        self._progress_tail = ""
        self.batch_paths = []
        self.batch_presets = []
        self.batch_index = -1
        self.batch_active = False
        self.batch_preset = None
        self.batch_custom_output = None
        self._check_pool = QThreadPool(self)
        self._check_pool.setMaxThreadCount(2)
        self._next_row_id = 0
        self._row_ids = []
        self._generations = {}
        self._checks = {}
        self._verified = {}
        self._closing = False
        self.settings = QSettings('808SGN', 'StemLab')
        saved_theme = self.settings.value('appearance/theme', 'Saigon Mint')
        self.theme_name = saved_theme if saved_theme in THEMES else 'Saigon Mint'
        self.preview_audio = QAudioOutput(self)
        self.preview_audio.setVolume(0.7)
        self.preview_player = QMediaPlayer(self)
        self.preview_player.setAudioOutput(self.preview_audio)
        self.build_ui()

    def build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("workspaceScroll")
        # Accept drops on blank workspace surfaces, not only inside queue/input.
        scroll.viewport().setAcceptDrops(True)
        scroll.viewport().installEventFilter(self)
        outer = QWidget()
        outer.setAcceptDrops(True)
        outer.installEventFilter(self)
        outer.setObjectName("appRoot")
        scroll.setWidget(outer)
        self.setCentralWidget(scroll)
        root = QVBoxLayout(outer)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        header = QHBoxLayout()
        brand = QLabel("808SGN  /  STEMLAB")
        brand.setObjectName("brand")
        header.addWidget(brand)
        header.addStretch()
        self.appearance_button = QPushButton('Appearance')
        self.appearance_button.setObjectName('quiet')
        self.appearance_button.clicked.connect(self.open_appearance)
        header.addWidget(self.appearance_button)
        tag = QLabel("LOCAL  ·  CPU  ·  OFFLINE PROCESSING")
        tag.setObjectName("muted")
        header.addWidget(tag)
        root.addLayout(header)

        sub = QLabel("Producer workspace  /  Separate audio into remix-ready stems")
        sub.setObjectName("muted")
        root.addWidget(sub)

        # Internal run-state controls retained for backend/test compatibility.
        # The queue owns the visible import and per-file mode controls.
        self.input = DropEdit()
        self.input.setParent(self)
        self.input.hide()
        self.input.textChanged.connect(self.update_output)
        self.input_browse = QPushButton("Browse", self)
        self.input_browse.hide()
        self.presets = QComboBox(self)
        for label, code, desc in PRESETS:
            self.presets.addItem(label, code)
        self.presets.hide()
        self.description = QLabel(PRESETS[0][2], self)
        self.description.hide()
        self.presets.currentIndexChanged.connect(self.update_preset)
        self.output = QLineEdit(self)
        self.output.hide()
        self.output.textEdited.connect(self.mark_output_custom)
        self.output_browse = QPushButton("Browse", self)
        self.output_browse.hide()

        queue_panel = QFrame()
        queue_panel.setObjectName("panel")
        queue_box = QVBoxLayout(queue_panel)
        queue_box.setContentsMargins(18, 18, 18, 16)
        queue_box.setSpacing(12)
        root.addWidget(queue_panel, 1)

        queue_header = QHBoxLayout()
        queue_header.addWidget(self.section("PROCESSING QUEUE"))
        queue_header.addStretch()
        self.add_files_button = QPushButton("Add files")
        self.add_files_button.clicked.connect(self.add_batch_files)
        queue_header.addWidget(self.add_files_button)
        self.add_folder_button = QPushButton("Add folder")
        self.add_folder_button.clicked.connect(self.add_batch_folder)
        queue_header.addWidget(self.add_folder_button)
        self.clear_queue_button = QPushButton("Clear")
        self.clear_queue_button.setObjectName("quiet")
        self.clear_queue_button.clicked.connect(self.clear_batch)
        queue_header.addWidget(self.clear_queue_button)
        queue_box.addLayout(queue_header)
        drop_hint = QLabel("Drop audio files or folders into the queue · Set a mode per track")
        drop_hint.setObjectName("queueHint")
        queue_box.addWidget(drop_hint)
        self.queue_list = QueueList()
        self.queue_list.can_export_item = self.stem_export_allowed
        self.queue_list.pathsDropped.connect(self.add_paths)
        self.queue_list.itemExpanded.connect(self.on_queue_expanded)
        self.queue_list.itemDoubleClicked.connect(self.preview_stem_item)
        self.queue_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.queue_list.customContextMenuRequested.connect(self.stem_context_menu)
        self.queue_list.setToolTip("Drop audio files or folders here (top-level only)")
        self.queue_list.setMinimumHeight(280)
        queue_box.addWidget(self.queue_list, 1)
        start_row = QHBoxLayout()
        start_row.addStretch()
        self.batch_start_button = QPushButton("START PROCESSING  →")
        self.batch_start_button.setObjectName("primary")
        self.batch_start_button.clicked.connect(self.start_batch)
        start_row.addWidget(self.batch_start_button)
        queue_box.addLayout(start_row)

        action = QHBoxLayout()
        # Retained internally for run-state compatibility; one visible start action.
        self.start_button = QPushButton()
        self.start_button.setVisible(False)
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
        self.log_toggle = QToolButton()
        self.log_toggle.setText("▸  PROCESS DETAILS")
        self.log_toggle.setCheckable(True)
        self.log_toggle.setChecked(False)
        self.log_toggle.toggled.connect(self.toggle_log)
        log_header.addWidget(self.log_toggle)
        log_header.addStretch()
        self.copy_log_button = QPushButton("Copy details")
        self.copy_log_button.setToolTip("Copy all process details to clipboard")
        self.copy_log_button.clicked.connect(self.copy_process_details)
        self.copy_log_button.setVisible(False)
        log_header.addWidget(self.copy_log_button)
        self.status = QLabel("READY")
        self.status.setObjectName("muted")
        log_header.addWidget(self.status)
        root.addLayout(log_header)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Your local processing output appears here.")
        self.log.setMinimumHeight(140)
        root.addWidget(self.log)
        self.log.setVisible(False)

        footer = QLabel("StemLab research preview  ·  Pilot model rankings are source-dependent")
        footer.setObjectName("footer")
        root.addWidget(footer)

    def apply_theme(self, name):
        if name not in THEMES:
            return
        self.theme_name = name
        QApplication.instance().setStyleSheet(theme_stylesheet(name))
        self.settings.setValue('appearance/theme', name)
        # Queue item status brushes are not stylesheet-managed.
        for index in range(self.queue_list.topLevelItemCount()):
            item = self.queue_list.topLevelItem(index)
            state = item.data(2, Qt.UserRole)
            if state:
                self.set_batch_label(index, state)

    def open_appearance(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('StemLab · Appearance')
        dialog.setObjectName('appearanceDialog')
        dialog.setMinimumWidth(360)
        layout = QFormLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(12)
        combo = QComboBox(dialog)
        combo.addItems(THEMES)
        combo.setCurrentText(self.theme_name)
        previous = QPushButton('◀', dialog)
        following = QPushButton('▶', dialog)
        previous.setToolTip('Previous theme')
        following.setToolTip('Next theme')
        selector = QWidget(dialog)
        selector_row = QHBoxLayout(selector)
        selector_row.setContentsMargins(0, 0, 0, 0)
        selector_row.setSpacing(5)
        selector_row.addWidget(previous)
        selector_row.addWidget(combo, 1)
        selector_row.addWidget(following)
        previous.clicked.connect(lambda: combo.setCurrentIndex((combo.currentIndex() - 1) % combo.count()))
        following.clicked.connect(lambda: combo.setCurrentIndex((combo.currentIndex() + 1) % combo.count()))
        layout.addRow('Color theme', selector)
        note = QLabel('Applies instantly · Saved locally', dialog)
        note.setObjectName('appearanceHint')
        layout.addRow(note)
        actions = QDialogButtonBox(QDialogButtonBox.Close, parent=dialog)
        actions.rejected.connect(dialog.reject)
        layout.addRow(actions)
        combo.currentTextChanged.connect(self.apply_theme)
        dialog.exec()

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.DragEnter, QEvent.DragMove, QEvent.Drop):
            if self.batch_active or self.process is not None:
                event.ignore()
                return True
            paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
            if not paths:
                event.ignore()
                return True
            if event.type() == QEvent.Drop:
                self.add_paths(paths)
            event.acceptProposedAction()
            return True
        return super().eventFilter(obj, event)

    def copy_process_details(self):
        details = self.log.toPlainText()
        if details:
            QApplication.clipboard().setText(details)
            self.copy_log_button.setText("Copied")
            QTimer.singleShot(2000, lambda: self.copy_log_button.setText("Copy details"))

    def toggle_log(self, shown):
        self.copy_log_button.setVisible(shown)
        self.log.setVisible(shown)
        self.log_toggle.setText("▾  PROCESS DETAILS" if shown else "▸  PROCESS DETAILS")

    @staticmethod
    def section(title):
        label = QLabel(title)
        label.setObjectName("section")
        return label

    def set_input(self, path):
        if self.batch_active or self.process is not None:
            return
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
        if self.batch_active or self.process is not None:
            return
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
            self.output.setText(str(self.default_output_dir(source, self.presets.currentData())))
        else:
            self.output.clear()

    def update_preset(self, index):
        self.description.setText(PRESETS[index][2])
        self.update_output()

    def add_batch_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add audio files", "",
            "Audio (*.wav *.flac *.mp3 *.m4a *.ogg *.aiff *.aif);;All files (*)"
        )
        self.add_paths(paths)

    def add_batch_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Add folder to queue")
        if folder:
            self.add_paths([folder])

    def add_paths(self, inputs):
        if self.batch_active or self.process is not None:
            return
        candidates = []
        for value in inputs:
            path = Path(value).expanduser()
            if path.is_dir():
                try:
                    candidates.extend(sorted(
                        (entry for entry in path.iterdir()
                         if entry.is_file() and entry.suffix.lower() in AUDIO_SUFFIXES),
                        key=lambda entry: entry.name.casefold()
                    ))
                except OSError as error:
                    self.append_log(f"Cannot read folder: {error}")
            elif path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES:
                candidates.append(path)
        added = 0
        for path in candidates:
            resolved = path.resolve()
            if resolved not in self.batch_paths:
                self.batch_paths.append(resolved)
                self.batch_presets.append("balanced")
                self.add_queue_row(resolved)
                added += 1
        if not added:
            self.status.setText("NO NEW AUDIO FILES")

    def add_queue_row(self, source):
        self._next_row_id += 1
        row_id = self._next_row_id
        self._row_ids.append(row_id)
        self._generations[row_id] = 0
        item = QTreeWidgetItem([source.name, "", "Queued"])
        item.setToolTip(0, str(source) + "\nDrag filename to export original audio")
        item.setData(0, Qt.UserRole, str(source))
        item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
        item.setExpanded(False)
        self.queue_list.addTopLevelItem(item)
        mode = QComboBox()
        mode.setObjectName('queueMode')
        for label, code, _ in PRESETS:
            mode.addItem(label, code)
        index = len(self.batch_paths) - 1
        mode.setCurrentIndex(mode.findData(self.batch_presets[index]))
        mode.currentIndexChanged.connect(lambda _, row=index, combo=mode: self.set_job_preset(row, combo.currentData()))
        self.queue_list.setItemWidget(item, 1, mode)
        item.setSizeHint(0, mode.sizeHint())
        self.refresh_existing_status(index)

    def on_queue_expanded(self, item):
        index = self.queue_list.indexOfTopLevelItem(item)
        if index >= 0:
            self.refresh_stem_children(index)

    @staticmethod
    def stem_display_name(path):
        match = re.search(r"_\(([^)]+)\)_", path.name)
        return match.group(1).replace('_', ' ').title() if match else path.stem

    def preview_stem_item(self, item, column=0):
        if not self.stem_export_allowed(item):
            return
        path = item.data(0, Qt.UserRole)
        url = QUrl.fromLocalFile(path)
        if self.preview_player.source() == url and self.preview_player.playbackState() == QMediaPlayer.PlayingState:
            self.preview_player.stop()
            self.status.setText('PREVIEW STOPPED')
        else:
            self.preview_player.setSource(url)
            self.preview_player.play()
            self.status.setText('PREVIEW  ' + self.stem_display_name(Path(path)))

    def stem_context_menu(self, point):
        item = self.queue_list.itemAt(point)
        if not self.stem_export_allowed(item):
            return
        path = item.data(0, Qt.UserRole)
        menu = QMenu(self)
        menu.addAction('Play / Stop preview', lambda: self.preview_stem_item(item))
        menu.addAction('Copy file path', lambda: QApplication.clipboard().setText(path))
        menu.addAction('Open containing folder', lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent))))
        menu.exec(self.queue_list.viewport().mapToGlobal(point))

    def stem_output_dir(self, index):
        source = self.batch_paths[index]
        preset = self.batch_presets[index]
        if self.batch_custom_output and len(self.batch_paths) == 1:
            return Path(self.batch_custom_output).expanduser()
        return self.default_output_dir(source, preset)

    @staticmethod
    def default_output_dir(source, preset):
        root = source.parent / (source.stem + "_stemlab")
        # Keep existing lowercase .wav outputs at their original path. Other
        # filenames need their own directory so they cannot claim those stems.
        if source.suffix != ".wav":
            root /= source.name
        return root / preset

    @staticmethod
    def output_owner(source, preset):
        return {"source": str(source.resolve()), "preset": preset}

    def output_conflicts_with_source(self, index, directory, entries):
        source = self.batch_paths[index]
        marker = directory / OWNER_FILE
        if marker.exists() or marker.is_symlink():
            try:
                return json.loads(marker.read_text()) != self.output_owner(source, self.batch_presets[index])
            except (OSError, ValueError):
                return True
        # Legacy output has no reliable record of which source created it.
        return bool(entries)

    @staticmethod
    def expected_stem_paths(source, preset, directory):
        if preset in FOUR_STEM_PRESETS:
            model = FOUR_STEM_MODELS[preset]
            names = ('Bass', 'Drums', 'Other', 'Vocals')
        elif preset == 'drum-parts':
            model = 'MDX23C-DrumSep-aufr33-jarredou'
            names = ('kick', 'snare', 'toms', 'hh', 'ride', 'crash')
        else:
            return None
        return {name: directory / f'{source.stem}_({name})_{model}.wav' for name in names}

    def verified_stem_paths(self, source, preset, directory, cancelled=None, deadline=None):
        paths = self.expected_stem_paths(source, preset, directory)
        if paths is None:
            return None
        try:
            if not all(path.is_file() and not path.is_symlink() and path.stat().st_size > 0
                       for path in paths.values()):
                return None
            if cancelled is not None and cancelled.is_set():
                return None
            reference = (self.probe_audio(source, timeout=min(12, max(.01, deadline - time.monotonic())), cancelled=cancelled)
                         if deadline else self.probe_audio(source))
            if (reference['channels'] < 1 or reference['rate'] < 1
                    or not math.isfinite(reference['duration']) or reference['duration'] <= 0):
                return None
            for path in paths.values():
                if (cancelled is not None and cancelled.is_set()) or (deadline and time.monotonic() >= deadline):
                    return None
                info = (self.probe_audio(path, timeout=min(12, max(.01, deadline - time.monotonic())), cancelled=cancelled)
                        if deadline else self.probe_audio(path))
                if (info['codec'] not in ('pcm_s16le', 'pcm_s24le', 'pcm_s32le', 'pcm_f32le')
                        or info['channels'] != reference['channels']
                        or not math.isfinite(info['duration']) or info['duration'] <= 0
                        or abs(info['duration'] - reference['duration']) > 0.25
                        or info['rate'] != (FOUR_STEM_OUTPUT_RATE if preset in FOUR_STEM_PRESETS
                                            else reference['rate'])):
                    return None
            return paths
        except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError, IndexError):
            return None

    def stem_export_allowed(self, item):
        path = item.data(0, Qt.UserRole) if item else None
        if not path:
            return False
        parent = item.parent()
        if parent is None:
            index = self.queue_list.indexOfTopLevelItem(item)
            return index >= 0 and Path(path) == self.batch_paths[index] and Path(path).is_file()
        index = self.queue_list.indexOfTopLevelItem(parent)
        if index < 0 or parent.data(2, Qt.UserRole) not in ('VERIFIED', 'VERIFIED EXISTING'):
            return False
        verified = self._verified.get(self._row_ids[index])
        if verified is None:
            return False
        snapshot, paths = verified
        if file_snapshot(self.batch_paths[index], self.stem_output_dir(index)) != snapshot:
            self.refresh_existing_status(index)
            return False
        return Path(path) in paths.values()

    def refresh_stem_children(self, index):
        if not 0 <= index < len(self.batch_paths):
            return
        parent = self.queue_list.topLevelItem(index)
        expanded = parent.isExpanded()
        parent.takeChildren()
        directory = self.stem_output_dir(index)
        if parent.data(2, Qt.UserRole) == 'SOURCE CONFLICT':
            parent.setChildIndicatorPolicy(QTreeWidgetItem.DontShowIndicatorWhenChildless)
            return
        source = self.batch_paths[index]
        preset = self.batch_presets[index]
        expected = self.expected_stem_paths(source, preset, directory)
        try:
            if expected is not None:
                stems = [path for path in expected.values() if path.is_file()]
            else:
                stems = sorted((p for p in directory.iterdir()
                                if p.is_file() and p.suffix.lower() == ".wav"),
                               key=lambda p: p.name.casefold()) if directory.is_dir() else []
        except OSError:
            stems = []
        verified = self._verified.get(self._row_ids[index])
        ready = (parent.data(2, Qt.UserRole) in ('VERIFIED', 'VERIFIED EXISTING')
                 and verified is not None and file_snapshot(source, directory) == verified[0])
        for path in stems:
            child = QTreeWidgetItem([self.stem_display_name(path), "", "Ready" if ready else "Unverified"])
            child.setToolTip(0, str(path))
            child.setData(0, Qt.UserRole, str(path))
            parent.addChild(child)
        parent.setChildIndicatorPolicy(QTreeWidgetItem.DontShowIndicatorWhenChildless if stems
                                      else QTreeWidgetItem.ShowIndicator)
        if parent.isExpanded() != expanded:
            parent.setExpanded(expanded)

    def set_job_preset(self, index, preset):
        if not self.batch_active and 0 <= index < len(self.batch_presets):
            self.batch_presets[index] = preset
            self.refresh_existing_status(index)

    def clear_batch(self):
        if self.batch_active:
            return
        for check in self._checks.values():
            check[1].set()
        self._checks.clear()
        self._verified.clear()
        self._generations.clear()
        self._row_ids.clear()
        self.batch_paths.clear()
        self.batch_presets.clear()
        self.batch_custom_output = None
        self.queue_list.clear()

    def set_batch_label(self, index, state):
        item = self.queue_list.topLevelItem(index)
        label = 'Unverified' if state.upper() == 'COMPLETE — UNVERIFIED' else state.title()
        item.setText(2, label)
        item.setToolTip(2, ("Output source or preset cannot be confirmed. Inspect the existing folder before retrying."
                            if state == 'SOURCE CONFLICT' else label))
        item.setData(2, Qt.UserRole, state)
        key = state.upper()
        if key in ('VERIFIED', 'VERIFIED EXISTING', 'EXISTING STEMS'):
            color = '#83d2b5'
        elif key in ('PROCESSING',):
            color = '#75cfc5'
        elif key in ('FAILED', 'BLOCKED', 'MISSING SOURCE', 'SOURCE CONFLICT'):
            color = '#ee9b98'
        elif key in ('PARTIAL / UNKNOWN', 'UNVERIFIED', 'COMPLETE — UNVERIFIED'):
            color = '#e2bd83'
        else:
            color = '#9dafbc'
        if key in ('VERIFIED', 'VERIFIED EXISTING'):
            color = THEMES[self.theme_name][3]
        elif key == 'PROCESSING':
            color = QColor(THEMES[self.theme_name][3]).darker(120).name()
        item.setForeground(2, QBrush(QColor(color)))
        self.refresh_stem_children(index)

    def start_batch(self):
        if self.batch_active or self.process is not None:
            return
        if not self.batch_paths:
            value = self.input.text().strip()
            source = Path(value).expanduser()
            if not source.is_file():
                QMessageBox.warning(self, "No audio", "Add audio files or select a source.")
                return
            resolved = source.resolve()
            self.batch_paths.append(resolved)
            self.batch_presets.append(self.presets.currentData())
            self.add_queue_row(resolved)
        self.batch_custom_output = ((self.output.text().strip() if self.output_user_set
                                     else self.batch_custom_output) if len(self.batch_paths) == 1 else None)
        targets = {}
        for index in range(len(self.batch_paths)):
            target = self.stem_output_dir(index).resolve()
            if target in targets:
                first = targets[target]
                self.set_batch_label(first, 'SOURCE CONFLICT')
                self.set_batch_label(index, 'SOURCE CONFLICT')
                QMessageBox.warning(self, "Output conflict",
                                    f"{self.batch_paths[first].name} and {self.batch_paths[index].name} target {target}. "
                                    "Rename one source or process the files separately before retrying.")
                self.batch_custom_output = None
                return
            targets[target] = index
        self.log.clear()
        self.batch_active = True
        self.batch_index = -1
        self.cancel_requested = False
        self.batch_preset = self.presets.currentData()
        for index in range(len(self.batch_paths)):
            combo = self.queue_list.itemWidget(self.queue_list.topLevelItem(index), 1)
            if combo:
                combo.setEnabled(False)
        for index, row_id in enumerate(self._row_ids):
            previous = self._checks.pop(row_id, None)
            if previous:
                previous[1].set()
            self._generations[row_id] += 1
            self._verified.pop(row_id, None)
            self.set_batch_label(index, "QUEUED")
        self.batch_start_button.setEnabled(False)
        self.clear_queue_button.setEnabled(False)
        self.add_files_button.setEnabled(False)
        self.add_folder_button.setEnabled(False)
        self.presets.setEnabled(False)
        self.set_running(False)
        QTimer.singleShot(0, self.run_next_batch)

    def inspect_existing_output(self, index):
        """Classify an output directory without deleting or modifying files."""
        return self.inspect_output(self.batch_paths[index], self.batch_presets[index], self.stem_output_dir(index))

    @classmethod
    def inspect_output(cls, source, preset, directory):
        if not source.is_file():
            return 'MISSING SOURCE'
        try:
            if not directory.exists():
                return 'READY'
            if not directory.is_dir():
                return 'BLOCKED'
            entries = list(directory.iterdir())
            marker = directory / OWNER_FILE
            if marker.exists() or marker.is_symlink():
                try:
                    conflict = json.loads(marker.read_text()) != cls.output_owner(source, preset)
                except (OSError, ValueError):
                    conflict = True
            else:
                conflict = bool(entries)
            if conflict:
                return 'SOURCE CONFLICT'
            entries = [entry for entry in entries if entry.name != OWNER_FILE]
            if not entries:
                return 'READY'
            expected = cls.expected_stem_paths(source, preset, directory)
            if expected is not None and len(entries) == len(expected) and all(
                    p.is_file() and p.stat().st_size > 0 for p in expected.values()):
                return 'EXISTING STEMS'
            return 'PARTIAL / UNKNOWN'
        except OSError:
            return 'BLOCKED'

    def refresh_existing_status(self, index, purpose='import'):
        """Inspect existing results on import/preset change, without processing."""
        if self._closing:
            return 'UNVERIFIED'
        if not 0 <= index < len(self._row_ids):
            return 'UNVERIFIED'
        row_id = self._row_ids[index]
        previous = self._checks.pop(row_id, None)
        if previous:
            previous[1].set()
        self._generations[row_id] += 1
        generation = self._generations[row_id]
        self._verified.pop(row_id, None)
        self.set_batch_label(index, 'CHECKING')
        cancelled = threading.Event()
        check = OutputCheck(row_id, generation, cancelled, self.inspect_output,
                            self.verified_stem_paths, self.batch_paths[index],
                            self.batch_presets[index], self.stem_output_dir(index))
        check.signals.done.connect(self._check_finished)
        self._checks[row_id] = (check, cancelled, purpose)
        self._check_pool.start(check)
        return 'CHECKING'

    def _check_finished(self, row_id, generation, result):
        if self._closing:
            return
        if self._generations.get(row_id) != generation or row_id not in self._row_ids:
            return
        check = self._checks.pop(row_id, None)
        purpose = check[2] if check else 'import'
        index = self._row_ids.index(row_id)
        state, paths, snapshot = result
        if state == 'VERIFIED EXISTING' and paths and snapshot == file_snapshot(self.batch_paths[index], self.stem_output_dir(index)):
            self._verified[row_id] = (snapshot, paths)
        elif state == 'VERIFIED EXISTING':
            state = 'PARTIAL / UNKNOWN'
        if purpose == 'postprocess' and self.batch_active and index == self.batch_index:
            if self.cancel_requested:
                self.set_batch_label(index, 'CANCELLED')
                return
            if state == 'VERIFIED EXISTING':
                state = 'VERIFIED'
                self.append_log('Output check PASSED: expected WAV stems and audio metadata verified.')
            else:
                state = 'CHECK OUTPUT'
                self.append_log('Output check FAILED: expected WAV stems or compatible audio metadata missing.')
            self.status.setText(state)
            self.stage_label.setText(state)
            self.set_batch_label(index, state)
            QTimer.singleShot(0, self.run_next_batch)
        elif purpose == 'preflight' and self.batch_active and index == self.batch_index:
            if state == 'QUEUED':
                self._start_current_job()
            else:
                self.set_batch_label(index, state)
                source = self.batch_paths[index]
                target = self.stem_output_dir(index)
                advice = ' Inspect that folder and move it aside before retrying.' if state == 'SOURCE CONFLICT' else ''
                self.append_log(f'Skipped {source.name}: {state.lower()} at {target}; existing output was not changed.{advice}')
                QTimer.singleShot(0, self.run_next_batch)
        else:
            self.set_batch_label(index, state)

    def run_next_batch(self):
        if not self.batch_active:
            return
        self.batch_index += 1
        if self.batch_index >= len(self.batch_paths):
            self.batch_active = False
            self.batch_index = -1
            self.batch_start_button.setEnabled(True)
            self.clear_queue_button.setEnabled(True)
            self.add_files_button.setEnabled(True)
            self.add_folder_button.setEnabled(True)
            self.presets.setEnabled(True)
            self.input.setEnabled(True)
            self.output.setEnabled(True)
            self.start_button.setEnabled(True)
            self.set_running(False)
            self.status.setText("QUEUE FINISHED — CHECK ROW STATUS")
            self.unlock_queue_presets()
            return
        self.refresh_existing_status(self.batch_index, purpose='preflight')

    def _start_current_job(self):
        source = self.batch_paths[self.batch_index]
        preset = self.batch_presets[self.batch_index]
        target = self.stem_output_dir(self.batch_index)
        self.set_batch_label(self.batch_index, "PROCESSING")
        self.presets.setCurrentIndex(self.presets.findData(preset))
        self.input.setText(str(source))
        self.output_user_set = False
        self.output.setText(str(target))
        self.start()
        if self.process is None:
            self.set_batch_label(self.batch_index, "FAILED")
            QTimer.singleShot(0, self.run_next_batch)

    def unlock_queue_presets(self):
        for index in range(self.queue_list.topLevelItemCount()):
            combo = self.queue_list.itemWidget(self.queue_list.topLevelItem(index), 1)
            if combo:
                combo.setEnabled(True)

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
        owner = self.output_owner(source, self.presets.currentData())
        try:
            if dest == source.resolve() or dest == source.parent.resolve():
                QMessageBox.warning(self, "Unsafe output", "Choose a separate output directory.")
                return
            marker = dest / OWNER_FILE
            if dest.exists():
                if not dest.is_dir():
                    self.append_log("Output is not a directory; refusing to overwrite it.")
                    return
                entries = list(dest.iterdir())
                if entries and (len(entries) != 1 or entries[0] != marker
                                or json.loads(marker.read_text()) != owner):
                    self.append_log("Output is no longer empty or belongs to another source; choose a different folder.")
                    return
            dest.mkdir(parents=True, exist_ok=True)
            if not marker.exists():
                with marker.open('x') as stream:
                    json.dump(owner, stream)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Output error", str(error))
            return

        self.cancel_requested = False
        self.current_output = dest
        self._progress_tail = ""
        self.stage_label.setText("STARTING")
        if not self.batch_active:
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
            if self.batch_active:
                self.set_batch_label(self.batch_index, "FAILED")
                QTimer.singleShot(0, self.run_next_batch)

    @staticmethod
    def probe_audio(path, timeout=12, cancelled=None):
        command = [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,sample_rate,channels,bits_per_sample:format=duration",
            "-of", "json", str(path),
        ]
        import json
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic() + timeout
        try:
            while True:
                if cancelled is not None and cancelled.is_set():
                    raise subprocess.TimeoutExpired(command, timeout)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                try:
                    stdout, stderr = process.communicate(timeout=min(.1, remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
            if process.returncode:
                raise subprocess.CalledProcessError(process.returncode, command, stdout, stderr)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
        payload = json.loads(stdout)
        stream = (payload.get("streams") or [{}])[0]
        return {
            "duration": float(payload["format"]["duration"]),
            "rate": int(stream["sample_rate"]),
            "channels": int(stream["channels"]),
            "codec": stream.get("codec_name", "unknown"),
        }

    def finished(self, code, exit_status):
        if self.process is None:
            return
        self.read_output()
        if self.cancel_requested:
            self.status.setText("CANCELLED")
            self.append_log("Cancelled. Partial output may remain.")
        elif code == 0 and exit_status == QProcess.NormalExit:
            if self.presets.currentData() not in FOUR_STEM_PRESETS | {'drum-parts'}:
                self.status.setText("COMPLETE — UNVERIFIED")
                self.append_log("Separation exited successfully; inspect this preset's outputs manually.")
            else:
                self.status.setText("CHECKING")
        else:
            self.status.setText("FAILED")
            self.append_log(f"Separation failed (exit code {code}).")
        self.set_running(False)
        self.stage_label.setText("VERIFIED" if self.status.text() == "VERIFIED" and self.presets.currentData() in FOUR_STEM_PRESETS else self.status.text())
        self.process.deleteLater()
        self.process = None
        if self.batch_active:
            self.set_batch_label(self.batch_index, self.status.text())
            if self.status.text() == 'CHECKING':
                self.refresh_existing_status(self.batch_index, purpose='postprocess')
                return
            if self.cancel_requested:
                self.batch_active = False
                self.batch_index = -1
                self.batch_start_button.setEnabled(True)
                self.clear_queue_button.setEnabled(True)
                self.add_files_button.setEnabled(True)
                self.add_folder_button.setEnabled(True)
                self.presets.setEnabled(True)
                self.input.setEnabled(True)
                self.output.setEnabled(True)
                self.start_button.setEnabled(True)
                self.set_running(False)
                self.unlock_queue_presets()
            else:
                QTimer.singleShot(0, self.run_next_batch)

    def set_running(self, running):
        self.start_button.setEnabled(not running and not self.batch_active)
        self.cancel_button.setEnabled((running or self.batch_active) and not self.cancel_requested)
        self.input_browse.setEnabled(not running and not self.batch_active)
        self.output_browse.setEnabled(not running and not self.batch_active)
        self.batch_start_button.setEnabled(not running and not self.batch_active)
        self.clear_queue_button.setEnabled(not running and not self.batch_active)
        self.add_files_button.setEnabled(not running and not self.batch_active)
        self.add_folder_button.setEnabled(not running and not self.batch_active)
        self.presets.setEnabled(not running and not self.batch_active)
        self.input.setEnabled(not running and not self.batch_active)
        self.output.setEnabled(not running and not self.batch_active)
        self.progress.setRange(0, 0 if running else 100)
        if not running:
            self.progress.setValue(0)

    def cancel(self):
        if self.process is None:
            if self.batch_active:
                if 0 <= self.batch_index < len(self._row_ids):
                    row_id = self._row_ids[self.batch_index]
                    check = self._checks.pop(row_id, None)
                    if check:
                        check[1].set()
                    self._generations[row_id] += 1
                    self._verified.pop(row_id, None)
                    self.set_batch_label(self.batch_index, 'CANCELLED')
                self.batch_active = False
                self.batch_index = -1
                self.cancel_requested = True
                self.status.setText("CANCELLED")
                self.set_running(False)
                self.batch_start_button.setEnabled(True)
                self.clear_queue_button.setEnabled(True)
                self.add_files_button.setEnabled(True)
                self.add_folder_button.setEnabled(True)
                self.unlock_queue_presets()
            return
        self.cancel_requested = True
        self.cancel_button.setEnabled(False)
        self.status.setText("CANCELLING")
        process = self.process
        process.terminate()
        # Capture this process: a late timer must never kill a subsequent job.
        QTimer.singleShot(3000, lambda: self.kill_cancelled_process(process))

    def kill_cancelled_process(self, process):
        if self.process is process and process.state() != QProcess.NotRunning:
            process.kill()

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
        self._closing = True
        for check, cancelled, _ in self._checks.values():
            cancelled.set()
            check.signals.done.disconnect(self._check_finished)
        self._checks.clear()
        if self.process is not None and self.process.state() != QProcess.NotRunning:
            self.batch_active = False  # Never launch the next job while closing.
            process = self.process
            self.cancel()
            if not process.waitForFinished(3000):
                process.kill()
                process.waitForFinished(2000)
        self.batch_active = False
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = Producer()
    window.apply_theme(window.theme_name)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
