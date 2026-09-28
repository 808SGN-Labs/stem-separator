#!/usr/bin/env python3

import array
import json
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget


class WaveformWidget(QWidget):
    seekRequested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.peaks = []
        self.position_ms = 0
        self.duration_ms = 0

        self.setMinimumHeight(150)
        self.setCursor(Qt.PointingHandCursor)

    def load_wav(self, path):
        """
        Build a lightweight waveform preview from any audio format FFmpeg can
        decode. Audio is converted only for display to mono 16-bit PCM at
        8 kHz; the original file used for playback is never modified.
        """
        path = Path(path)

        self.peaks = []
        self.position_ms = 0
        self.duration_ms = 0

        if not path.is_file():
            raise FileNotFoundError(path)

        probe = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        probe_data = json.loads(probe.stdout)
        duration_seconds = float(
            probe_data.get("format", {}).get("duration", 0.0)
        )
        self.duration_ms = int(duration_seconds * 1000)

        # Decode a display-only mono preview. 8 kHz is plenty for waveform
        # shape while keeping CPU/memory usage low.
        decoded = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "error",
                "-i", str(path),
                "-map", "0:a:0",
                "-ac", "1",
                "-ar", "8000",
                "-f", "s16le",
                "-",
            ],
            check=True,
            capture_output=True,
        )

        samples = array.array("h")
        samples.frombytes(decoded.stdout)

        if not samples:
            self.update()
            return

        # Keep enough horizontal detail for a desktop QC window.
        target_bins = 1400
        samples_per_bin = max(
            1,
            len(samples) // target_bins
        )

        for start in range(
            0,
            len(samples),
            samples_per_bin,
        ):
            chunk = samples[
                start:start + samples_per_bin
            ]

            if not chunk:
                continue

            self.peaks.append(
                (
                    min(chunk) / 32768.0,
                    max(chunk) / 32768.0,
                )
            )

        self.update()

    def set_position(self, position_ms):
        self.position_ms = position_ms
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.Antialiasing,
            False
        )

        rect = self.rect()
        center = rect.height() / 2

        # Background
        painter.fillRect(
            rect,
            self.palette().base()
        )

        if self.peaks:
            waveform_pen = QPen(
                self.palette().highlight().color()
            )
            waveform_pen.setWidth(1)
            painter.setPen(waveform_pen)

            width = max(1, rect.width())
            count = len(self.peaks)

            for x in range(width):
                index = int(
                    x * count / width
                )

                index = min(index, count - 1)

                low, high = self.peaks[index]

                y1 = center - high * center * 0.92
                y2 = center - low * center * 0.92

                painter.drawLine(
                    x,
                    int(y1),
                    x,
                    int(y2),
                )

        # Centre line
        centre_pen = QPen(
            self.palette().mid().color()
        )
        painter.setPen(centre_pen)
        painter.drawLine(
            0,
            int(center),
            rect.width(),
            int(center),
        )

        # Playhead
        if self.duration_ms > 0:
            ratio = min(
                1.0,
                max(
                    0.0,
                    self.position_ms
                    / self.duration_ms,
                ),
            )

            x = int(
                ratio * rect.width()
            )

            playhead_pen = QPen(
                self.palette().text().color()
            )
            playhead_pen.setWidth(2)

            painter.setPen(playhead_pen)
            painter.drawLine(
                x,
                0,
                x,
                rect.height(),
            )

    def mousePressEvent(self, event):
        self.request_seek(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.request_seek(event)

    def request_seek(self, event):
        if self.duration_ms <= 0:
            return

        ratio = event.position().x() / max(
            1,
            self.width()
        )

        ratio = min(
            1.0,
            max(0.0, ratio),
        )

        self.seekRequested.emit(
            int(ratio * self.duration_ms)
        )
