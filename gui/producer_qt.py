#!/usr/bin/env python3
"""StemLab producer interface — local Qt frontend for scripts/stem-separate."""

import os
import re
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QProcess, Qt, QUrl, Signal, QTimer, QMimeData
from PySide6.QtGui import QDesktopServices, QDrag
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QListWidget, QSizePolicy, QScrollArea,
    QPushButton, QVBoxLayout, QWidget, QToolButton, QTreeWidget, QTreeWidgetItem, QHeaderView, QMenu,
)

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "stem-separate"
# tqdm reports per-model steps, not overall job completion.
STEP_PROGRESS = re.compile(r"(\d{1,3})%\|[^\r\n]*?\|\s*(\d+)\s*/\s*(\d+)")
FOUR_STEM_PRESETS = {"balanced", "4stems", "maximum"}
AUDIO_SUFFIXES = {".wav", ".flac", ".mp3", ".m4a", ".ogg", ".aiff", ".aif"}

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
QTreeWidget { background: #0d1319; border: 1px solid #364653; border-radius: 7px; alternate-background-color: #131c24; }
QTreeWidget::item { min-height: 30px; padding: 2px 5px; }
QTreeWidget::item:selected { background: #29464a; }
QHeaderView::section { background: #202c36; color: #a9bfca; border: 0; border-bottom: 1px solid #354651; padding: 8px; font-weight: 700; }
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
            if path and Path(path).is_file():
                self.drag_stem(path)
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_origin = None
        super().mouseReleaseEvent(event)

    def drag_stem(self, path):
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(path))])
        drag = QDrag(self)
        drag.setMimeData(mime)
        return drag.exec(Qt.CopyAction)

    def startDrag(self, supported_actions):
        item = self.currentItem()
        path = item.data(0, Qt.UserRole) if item else None
        if path and Path(path).is_file():
            self.drag_stem(path)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeWidget.DragDrop)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.CopyAction)
        self.setColumnCount(3)
        self.setHeaderLabels(["FILE", "MODE", "STATUS"])
        self.setAlternatingRowColors(True)
        self.setRootIsDecorated(True)
        self.setIndentation(18)
        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.header().setSectionResizeMode(1, QHeaderView.Fixed)
        self.header().resizeSection(1, 260)
        self.header().setSectionResizeMode(2, QHeaderView.Fixed)
        self.header().resizeSection(2, 150)
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
        queue_box.setContentsMargins(16, 16, 16, 16)
        queue_box.setSpacing(10)
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
        self.clear_queue_button.clicked.connect(self.clear_batch)
        queue_header.addWidget(self.clear_queue_button)
        queue_box.addLayout(queue_header)
        drop_hint = QLabel("Drop audio files or folders into the queue · Set a mode per track")
        drop_hint.setObjectName("muted")
        queue_box.addWidget(drop_hint)
        self.queue_list = QueueList()
        self.queue_list.pathsDropped.connect(self.add_paths)
        self.queue_list.itemExpanded.connect(self.on_queue_expanded)
        self.queue_list.itemDoubleClicked.connect(self.preview_stem_item)
        self.queue_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.queue_list.customContextMenuRequested.connect(self.stem_context_menu)
        self.queue_list.setToolTip("Drop audio files or folders here (top-level only)")
        self.queue_list.setMinimumHeight(255)
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
        footer.setObjectName("muted")
        root.addWidget(footer)

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
            self.output.setText(str(source.parent / (source.stem + "_stemlab") / self.presets.currentData()))
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
        item = QTreeWidgetItem([source.name, "", "Queued"])
        item.setToolTip(0, str(source) + "\nDrag filename to export original audio")
        item.setData(0, Qt.UserRole, str(source))
        item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
        item.setExpanded(False)
        self.queue_list.addTopLevelItem(item)
        mode = QComboBox()
        for label, code, _ in PRESETS:
            mode.addItem(label, code)
        index = len(self.batch_paths) - 1
        mode.setCurrentIndex(mode.findData(self.batch_presets[index]))
        mode.currentIndexChanged.connect(lambda _, row=index, combo=mode: self.set_job_preset(row, combo.currentData()))
        self.queue_list.setItemWidget(item, 1, mode)
        item.setSizeHint(0, mode.sizeHint())
        self.refresh_stem_children(index)

    def on_queue_expanded(self, item):
        index = self.queue_list.indexOfTopLevelItem(item)
        if index >= 0:
            self.refresh_stem_children(index)

    @staticmethod
    def stem_display_name(path):
        match = re.search(r"_\(([^)]+)\)_", path.name)
        return match.group(1).replace('_', ' ').title() if match else path.stem

    def preview_stem_item(self, item, column=0):
        path = item.data(0, Qt.UserRole)
        if not path or not Path(path).is_file():
            return
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
        path = item.data(0, Qt.UserRole) if item else None
        if not path or not Path(path).is_file():
            return
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
        return source.parent / (source.stem + "_stemlab") / preset

    def refresh_stem_children(self, index):
        if not 0 <= index < len(self.batch_paths):
            return
        parent = self.queue_list.topLevelItem(index)
        expanded = parent.isExpanded()
        parent.takeChildren()
        directory = self.stem_output_dir(index)
        try:
            stems = sorted((p for p in directory.iterdir()
                            if p.is_file() and p.suffix.lower() == ".wav" and p.stat().st_size > 0),
                           key=lambda p: p.name.casefold()) if directory.is_dir() else []
        except OSError:
            stems = []
        for path in stems:
            child = QTreeWidgetItem([self.stem_display_name(path), "", "Ready"])
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
            self.refresh_stem_children(index)

    def clear_batch(self):
        if self.batch_active:
            return
        self.batch_paths.clear()
        self.batch_presets.clear()
        self.queue_list.clear()

    def set_batch_label(self, index, state):
        item = self.queue_list.topLevelItem(index)
        item.setText(2, 'Unverified' if state.upper() == 'COMPLETE — UNVERIFIED' else state.title())
        item.setToolTip(2, state.title())
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
        self.log.clear()
        self.batch_active = True
        self.batch_index = -1
        self.cancel_requested = False
        self.batch_preset = self.presets.currentData()
        for index in range(len(self.batch_paths)):
            combo = self.queue_list.itemWidget(self.queue_list.topLevelItem(index), 1)
            if combo:
                combo.setEnabled(False)
        self.batch_custom_output = (self.output.text().strip() if len(self.batch_paths) == 1 and self.output_user_set else None)
        for index in range(len(self.batch_paths)):
            self.set_batch_label(index, "QUEUED")
        self.batch_start_button.setEnabled(False)
        self.clear_queue_button.setEnabled(False)
        self.add_files_button.setEnabled(False)
        self.add_folder_button.setEnabled(False)
        self.presets.setEnabled(False)
        self.set_running(False)
        QTimer.singleShot(0, self.run_next_batch)

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
        source = self.batch_paths[self.batch_index]
        preset = self.batch_presets[self.batch_index]
        target = self.stem_output_dir(self.batch_index)
        try:
            skip = not source.is_file() or (
                target.exists() and (not target.is_dir() or any(target.iterdir()))
            )
        except OSError as error:
            self.set_batch_label(self.batch_index, "FAILED")
            self.append_log(f"Cannot inspect output for {source.name}: {error}")
            QTimer.singleShot(0, self.run_next_batch)
            return
        if skip:
            self.set_batch_label(self.batch_index, "SKIPPED")
            self.append_log(f"Skipped {source.name}: missing source or output path is not an empty directory.")
            QTimer.singleShot(0, self.run_next_batch)
            return
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
        try:
            if dest == source.resolve() or dest == source.parent.resolve():
                QMessageBox.warning(self, "Unsafe output", "Choose a separate output directory.")
                return
            if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
                if self.batch_active:
                    self.append_log("Output is no longer empty; refusing to overwrite it.")
                    return
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
        if self.presets.currentData() == 'drum-parts':
            source = Path(self.input.text().strip()).expanduser()
            expected = ('kick', 'snare', 'toms', 'hh', 'ride', 'crash')
            paths = [self.current_output / f'{source.stem}_({stem})_MDX23C-DrumSep-aufr33-jarredou.wav' for stem in expected]
            try:
                if not all(p.is_file() and p.stat().st_size > 0 for p in paths):
                    self.append_log('Drum output check FAILED: missing or empty drum stem.')
                    return False
                reference = self.probe_audio(source)
                for path in paths:
                    info = self.probe_audio(path)
                    if info['channels'] != reference['channels'] or abs(info['duration'] - reference['duration']) > 0.25:
                        raise ValueError(f'{path.name}: channels or duration differ from input')
                self.append_log('Drum output check PASSED: six nonempty WAV stems and metadata verified.')
                return True
            except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError) as exc:
                self.append_log(f'Drum output check FAILED: {exc}')
                return False
        if self.presets.currentData() not in FOUR_STEM_PRESETS:
            self.append_log("Output check: manual inspection required for this preset.")
            return None
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
            validation = self.validate_output()
            if validation is True:
                self.status.setText("VERIFIED")
                self.append_log("Separation finished successfully; output verified.")
            elif validation is None:
                self.status.setText("COMPLETE — UNVERIFIED")
                self.append_log("Separation exited successfully; inspect this preset's outputs manually.")
            else:
                self.status.setText("CHECK OUTPUT")
                self.append_log("Processing exited successfully, but output verification failed.")
        else:
            self.status.setText("FAILED")
            self.append_log(f"Separation failed (exit code {code}).")
        self.set_running(False)
        self.stage_label.setText("VERIFIED" if self.status.text() == "VERIFIED" and self.presets.currentData() in FOUR_STEM_PRESETS else self.status.text())
        self.process.deleteLater()
        self.process = None
        if self.batch_active:
            self.set_batch_label(self.batch_index, self.status.text())
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
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
