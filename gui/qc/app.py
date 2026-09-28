#!/usr/bin/env python3

import json
import sys
from pathlib import Path

from PySide6.QtCore import QFile, QTimer, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)
from PySide6.QtGui import QKeySequence, QShortcut

from waveform import WaveformWidget
from reconstruct import build_reconstruction

ROOT = Path(__file__).resolve().parents[2]
UI_FILE = Path(__file__).with_name("qc_window.ui")
RESULTS_DIR = ROOT / "data" / "results"
LISTENING_DIR = ROOT / "data" / "listening"
DEFAULT_BLIND_PACK = LISTENING_DIR / "control-01-vocals-blind-02"


class QCApp:
    def __init__(self):
        self.window = self.load_ui()

        self.waveform = WaveformWidget(self.window.waveformPlaceholder)
        placeholder_layout = self.window.waveformPlaceholder.layout()
        if placeholder_layout is None:
            placeholder_layout = QVBoxLayout(self.window.waveformPlaceholder)
            placeholder_layout.setContentsMargins(0, 0, 0, 0)
        placeholder_layout.addWidget(self.waveform)

        self.players = [QMediaPlayer(), QMediaPlayer()]
        self.audios = [QAudioOutput(), QAudioOutput()]

        for player, audio in zip(self.players, self.audios):
            audio.setVolume(0.0)
            player.setAudioOutput(audio)

        self.active_index = 0
        self.player = self.players[self.active_index]
        self.audio = self.audios[self.active_index]
        self.audio.setVolume(0.8)

        self.crossfade_timer = QTimer(self.window)
        self.crossfade_timer.setInterval(10)
        self.crossfade_timer.timeout.connect(self._crossfade_step)
        self.crossfade_duration_ms = 100
        self.crossfade_elapsed_ms = 0
        self.crossfade_from_index = None
        self.crossfade_to_index = None

        self.run_dir = None
        self.result = None
        self.sources = {}
        self.current_source = "mix"

        self.mode = "run"
        self.blind_pack_dir = DEFAULT_BLIND_PACK
        self.blind_sources = {}
        self.blind_scores = {}
        self.blind_mapping = {}
        self.current_candidate = None
        self.blind_revealed = False

        self.qc = {
            "schema_version": 1,
            "run_id": None,
            "overall": None,
            "stems": {},
        }

        self.setup_groups()
        self.connect_ui()
        self.setup_blind_pack_selector()
        self.populate_run_selector()
        self.load_blind_pack()
        self.set_mode("run")
        self.setup_shortcuts()

    def load_ui(self):
        loader = QUiLoader()
        ui = QFile(str(UI_FILE))

        if not ui.open(QFile.ReadOnly):
            raise RuntimeError(f"Cannot open UI: {UI_FILE}")

        window = loader.load(ui)
        ui.close()

        if window is None:
            raise RuntimeError(loader.errorString())

        return window

    def setup_groups(self):
        self.source_group = QButtonGroup(self.window)
        self.source_group.setExclusive(True)

        for button in [
            self.window.mixButton,
            self.window.reconButton,
            self.window.bassButton,
            self.window.drumsButton,
            self.window.otherButton,
            self.window.vocalsButton,
        ]:
            self.source_group.addButton(button)

        self.mode_group = QButtonGroup(self.window)
        self.mode_group.setExclusive(True)
        self.mode_group.addButton(self.window.runQcModeButton)
        self.mode_group.addButton(self.window.blindModeButton)

        self.blind_candidate_group = QButtonGroup(self.window)
        self.blind_candidate_group.setExclusive(True)
        for button in [
            self.window.candidateAButton,
            self.window.candidateBButton,
            self.window.candidateCButton,
            self.window.candidateDButton,
            self.window.candidateEButton,
        ]:
            self.blind_candidate_group.addButton(button)

        self.usability_group = QButtonGroup(self.window)
        self.usability_group.setExclusive(True)

        for button in [
            self.window.goodRadio,
            self.window.acceptableRadio,
            self.window.poorRadio,
        ]:
            self.usability_group.addButton(button)

        self.overall_group = QButtonGroup(self.window)
        self.overall_group.setExclusive(True)

        for button in [
            self.window.usableRadio,
            self.window.marginalRadio,
            self.window.unusableRadio,
        ]:
            self.overall_group.addButton(button)

    def connect_ui(self):
        self.window.mixButton.clicked.connect(
            lambda: self.switch_source("mix")
        )
        self.window.reconButton.clicked.connect(
            lambda: self.switch_source("recon")
        )
        self.window.bassButton.clicked.connect(
            lambda: self.switch_source("bass")
        )
        self.window.drumsButton.clicked.connect(
            lambda: self.switch_source("drums")
        )
        self.window.otherButton.clicked.connect(
            lambda: self.switch_source("other")
        )
        self.window.vocalsButton.clicked.connect(
            lambda: self.switch_source("vocals")
        )

        self.window.playButton.clicked.connect(self.toggle_play)

        for player in self.players:
            player.positionChanged.connect(
                lambda position, p=player:
                self.position_changed_from(p, position)
            )
            player.durationChanged.connect(
                lambda duration, p=player:
                self.duration_changed_from(p, duration)
            )
            player.playbackStateChanged.connect(
                lambda state, p=player:
                self.playback_state_changed_from(p, state)
            )
            player.mediaStatusChanged.connect(
                lambda status, p=player:
                self.media_status_changed_from(p, status)
            )

        self.window.positionSlider.sliderMoved.connect(
            self.seek_active_player
        )
        self.waveform.seekRequested.connect(
            self.seek_active_player
        )

        self.window.saveButton.clicked.connect(self.save_current)
        self.window.saveNextButton.clicked.connect(self.save_next)

        self.window.runQcModeButton.clicked.connect(
            lambda: self.set_mode("run")
        )
        self.window.blindModeButton.clicked.connect(
            lambda: self.set_mode("blind")
        )

        for label, button in {
            "A": self.window.candidateAButton,
            "B": self.window.candidateBButton,
            "C": self.window.candidateCButton,
            "D": self.window.candidateDButton,
            "E": self.window.candidateEButton,
        }.items():
            button.clicked.connect(
                lambda checked=False, candidate=label:
                self.switch_candidate(candidate)
            )

        self.window.revealButton.clicked.connect(self.reveal_models)

        self.window.runComboBox.currentIndexChanged.connect(
            self.run_selection_changed
        )


    def discover_blind_packs(self):
        if not LISTENING_DIR.is_dir():
            return []

        packs = []

        for directory in LISTENING_DIR.iterdir():
            if not directory.is_dir():
                continue

            wavs = [
                directory / f"{label}.wav"
                for label in "ABCDE"
            ]

            score_file = directory / "scores.json"
            mapping_file = directory / "mapping.secret.json"

            # Only show directories that look like real Blind Vocal packs.
            if (
                all(path.is_file() for path in wavs)
                and score_file.is_file()
                and mapping_file.is_file()
            ):
                packs.append(directory)

        packs.sort(
            key=lambda path: path.name
        )

        return packs


    def setup_blind_pack_selector(self):
        self.window.blindModeButton.setText("BLIND VOCAL")

        self.blindPackLabel = QLabel(
            "Blind Pack",
            self.window.blindSourceGroup,
        )

        self.blindPackComboBox = QComboBox(
            self.window.blindSourceGroup
        )

        self.blindPackComboBox.setMinimumWidth(280)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 8)
        row.addWidget(self.blindPackLabel)
        row.addWidget(self.blindPackComboBox, 1)

        group_layout = self.window.blindSourceGroup.layout()

        if group_layout is None:
            group_layout = QVBoxLayout(
                self.window.blindSourceGroup
            )

        # Put selector above A/B/C/D/E.
        group_layout.insertLayout(0, row)

        packs = self.discover_blind_packs()

        self.blindPackComboBox.blockSignals(True)
        self.blindPackComboBox.clear()

        selected_index = -1

        for index, pack in enumerate(packs):
            self.blindPackComboBox.addItem(
                pack.name,
                str(pack),
            )

            if pack == self.blind_pack_dir:
                selected_index = index

        if packs:
            if selected_index < 0:
                # Prefer newest control numerically/name-wise when the
                # previous default pack does not exist.
                selected_index = len(packs) - 1
                self.blind_pack_dir = packs[selected_index]

            self.blindPackComboBox.setCurrentIndex(
                selected_index
            )
        else:
            self.blindPackComboBox.addItem(
                "No blind packs found",
                None,
            )
            self.blindPackComboBox.setEnabled(False)

        self.blindPackComboBox.blockSignals(False)

        self.blindPackComboBox.currentIndexChanged.connect(
            self.blind_pack_changed
        )


    def blind_pack_changed(self, index):
        if index < 0:
            return

        value = self.blindPackComboBox.itemData(index)

        if not value:
            return

        new_pack = Path(value)

        if new_pack == self.blind_pack_dir:
            return

        # Save the currently displayed candidate into the OLD pack
        # before changing directories.
        if (
            self.mode == "blind"
            and self.current_candidate is not None
        ):
            self.store_blind_score()
            self.write_blind_scores()

        # Stop playback and clear waveform before swapping pack.
        self.reset_media_for_run_change()

        self.blind_pack_dir = new_pack
        self.current_candidate = None
        self.blind_revealed = False

        self.load_blind_pack()

        if self.blind_sources:
            first = sorted(self.blind_sources)[0]
            self.switch_candidate(first)

        self.window.statusbar.showMessage(
            f"Loaded Blind Vocal pack: {new_pack.name}",
            5000,
        )


    def set_mode(self, mode):
        if mode not in ("run", "blind"):
            return

        if self.mode == "blind" and mode != "blind":
            self.store_blind_score()
            self.write_blind_scores()
        elif self.mode == "run" and mode != "run":
            self.store_current_qc()

        self.mode = mode
        is_run = mode == "run"

        self.window.runQcModeButton.setChecked(is_run)
        self.window.blindModeButton.setChecked(not is_run)

        for widget in [
            self.window.runLabel,
            self.window.runComboBox,
            self.window.sourceGroup,
            self.window.qcGroup,
            self.window.overallLabel,
            self.window.usableRadio,
            self.window.marginalRadio,
            self.window.unusableRadio,
        ]:
            widget.setVisible(is_run)

        self.window.blindSourceGroup.setVisible(not is_run)
        self.window.blindQcGroup.setVisible(not is_run)
        self.window.revealButton.setVisible(not is_run)

        if is_run:
            self.window.saveButton.setText("SAVE")
            self.window.saveNextButton.setText("SAVE + NEXT")

            if self.result is not None:
                experiment = self.result.get(
                    "experiment",
                    self.result.get("run_id", "run"),
                )
                model_name = self.result.get("model", {}).get(
                    "name",
                    "unknown",
                )
                self.window.experimentLabel.setText(
                    f"{experiment} / {model_name}"
                )
                self.switch_source(self.current_source)
        else:
            self.window.saveButton.setText("SAVE SCORE")
            self.window.saveNextButton.setText("SAVE + NEXT")
            self.window.experimentLabel.setText(
                f"BLIND VOCAL / {self.blind_pack_dir.name}"
            )

            if not self.blind_sources:
                self.window.currentStemLabel.setText("NO BLIND PACK")
                self.window.statusbar.showMessage(
                    f"Blind pack not found: {self.blind_pack_dir}",
                    7000,
                )
                return

            candidate = self.current_candidate or sorted(self.blind_sources)[0]
            self.switch_candidate(candidate)

    def load_blind_pack(self):
        self.blind_sources = {}
        self.blind_scores = {}
        self.blind_mapping = {}
        self.blind_revealed = False

        if not self.blind_pack_dir.is_dir():
            return

        for label in "ABCDE":
            path = self.blind_pack_dir / f"{label}.wav"
            if path.is_file():
                self.blind_sources[label] = path

        score_file = self.blind_pack_dir / "scores.json"
        if score_file.is_file():
            try:
                payload = json.loads(score_file.read_text(encoding="utf-8"))
                self.blind_scores = payload.get("scores", {})
            except Exception:
                self.blind_scores = {}

        for label in self.blind_sources:
            self.blind_scores.setdefault(
                label,
                {
                    "vocal_isolation": None,
                    "vocal_integrity": None,
                    "artifact_control": None,
                    "low_level_detail": None,
                    "remix_usability": None,
                    "notes": "",
                },
            )

        mapping_file = self.blind_pack_dir / "mapping.secret.json"
        if mapping_file.is_file():
            try:
                self.blind_mapping = json.loads(
                    mapping_file.read_text(encoding="utf-8")
                )
            except Exception:
                self.blind_mapping = {}

        self.update_blind_status()

    def store_blind_score(self):
        if not self.current_candidate:
            return

        row = self.blind_scores.setdefault(self.current_candidate, {})

        values = {
            "vocal_isolation": self.window.isolationSpin.value(),
            "vocal_integrity": self.window.integritySpin.value(),
            "artifact_control": self.window.artifactSpin.value(),
            "low_level_detail": self.window.detailSpin.value(),
            "remix_usability": self.window.remixSpin.value(),
        }

        for key, value in values.items():
            row[key] = value if value > 0 else None

        row["notes"] = self.window.blindNotesEdit.toPlainText().strip()

    def restore_blind_score(self):
        row = self.blind_scores.get(self.current_candidate, {})

        mapping = {
            "vocal_isolation": self.window.isolationSpin,
            "vocal_integrity": self.window.integritySpin,
            "artifact_control": self.window.artifactSpin,
            "low_level_detail": self.window.detailSpin,
            "remix_usability": self.window.remixSpin,
        }

        for key, spin in mapping.items():
            value = row.get(key)
            spin.setValue(int(value) if value is not None else 0)

        self.window.blindNotesEdit.setPlainText(row.get("notes", ""))

    def write_blind_scores(self):
        if not self.blind_pack_dir.is_dir():
            return

        score_file = self.blind_pack_dir / "scores.json"
        payload = {}

        if score_file.is_file():
            try:
                payload = json.loads(score_file.read_text(encoding="utf-8"))
            except Exception:
                payload = {}

        payload.setdefault(
            "instructions",
            {
                "scale": "1-5; higher is better",
                "do_not_open_mapping_until_finished": True,
            },
        )
        payload["scores"] = self.blind_scores

        score_file.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )

        self.update_blind_status()

    def blind_complete(self):
        required = (
            "vocal_isolation",
            "vocal_integrity",
            "artifact_control",
            "low_level_detail",
            "remix_usability",
        )

        if not self.blind_sources:
            return False

        for label in self.blind_sources:
            row = self.blind_scores.get(label, {})
            if any(row.get(key) not in (1, 2, 3, 4, 5) for key in required):
                return False

        return True

    def update_blind_status(self):
        total = len(self.blind_sources)
        completed = 0

        required = (
            "vocal_isolation",
            "vocal_integrity",
            "artifact_control",
            "low_level_detail",
            "remix_usability",
        )

        for label in self.blind_sources:
            row = self.blind_scores.get(label, {})
            if all(row.get(key) in (1, 2, 3, 4, 5) for key in required):
                completed += 1

        pack_name = self.blind_pack_dir.name

        self.window.blindStatusLabel.setText(
            f"{pack_name}  •  Scored {completed}/{total}  •  Models hidden"
            if not self.blind_revealed
            else
            f"{pack_name}  •  Scored {completed}/{total}  •  Models revealed"
        )
        self.window.revealButton.setEnabled(self.blind_complete())

    def switch_candidate(self, candidate):
        if candidate not in self.blind_sources:
            return

        if self.current_candidate is not None:
            self.store_blind_score()

        old_position = self.player.position()
        was_playing = (
            self.player.playbackState()
            == QMediaPlayer.PlayingState
        )

        self.current_candidate = candidate

        button_map = {
            "A": self.window.candidateAButton,
            "B": self.window.candidateBButton,
            "C": self.window.candidateCButton,
            "D": self.window.candidateDButton,
            "E": self.window.candidateEButton,
        }
        button_map[candidate].setChecked(True)

        label = f"CANDIDATE {candidate}"
        if self.blind_revealed:
            model = self.blind_mapping.get(candidate, {}).get("model")
            if model:
                label += f" / {model}"
        self.window.currentStemLabel.setText(label)

        try:
            self.waveform.load_wav(self.blind_sources[candidate])
        except Exception as exc:
            self.window.statusbar.showMessage(
                f"Waveform unavailable: {exc}"
            )

        self.start_source_transition(
            self.blind_sources[candidate],
            old_position,
            was_playing,
        )
        self.restore_blind_score()
        self.update_blind_status()

    def save_current(self):
        if self.mode == "blind":
            self.store_blind_score()
            self.write_blind_scores()
            self.window.statusbar.showMessage(
                f"Saved blind score for {self.current_candidate}",
                4000,
            )
        else:
            self.save_qc()

    def save_next(self):
        if self.mode != "blind":
            self.save_qc()
            return

        self.store_blind_score()
        self.write_blind_scores()

        labels = sorted(self.blind_sources)
        if self.current_candidate not in labels:
            return

        index = labels.index(self.current_candidate)
        if index + 1 < len(labels):
            self.switch_candidate(labels[index + 1])
        else:
            self.window.statusbar.showMessage(
                "Last candidate reached. Reveal is enabled once all scores are complete.",
                6000,
            )

    def reveal_models(self):
        self.store_blind_score()
        self.write_blind_scores()

        if not self.blind_complete():
            QMessageBox.information(
                self.window,
                "StemLab Blind Compare",
                "Score all five criteria for every candidate before reveal.",
            )
            return

        if not self.blind_mapping:
            QMessageBox.warning(
                self.window,
                "StemLab Blind Compare",
                "mapping.secret.json is missing or invalid.",
            )
            return

        self.blind_revealed = True
        self.update_blind_status()

        lines = []
        for label in sorted(self.blind_sources):
            entry = self.blind_mapping.get(label, {})
            model = entry.get("model", "unknown")
            preset = entry.get("preset", "-")
            runtime = entry.get("runtime_seconds")
            runtime_text = f"{runtime:.2f}s" if isinstance(runtime, (int, float)) else "-"
            lines.append(f"{label}  {model}  [{preset}]  {runtime_text}")

            button = {
                "A": self.window.candidateAButton,
                "B": self.window.candidateBButton,
                "C": self.window.candidateCButton,
                "D": self.window.candidateDButton,
                "E": self.window.candidateEButton,
            }[label]
            button.setToolTip(model)

        if self.current_candidate:
            self.switch_candidate(self.current_candidate)

        QMessageBox.information(
            self.window,
            "StemLab Blind Compare — Reveal",
            "\n".join(lines),
        )

    def discover_runs(self):
        runs_by_key = {}

        for result_file in RESULTS_DIR.glob("*/result.json"):
            try:
                result = json.loads(
                    result_file.read_text(encoding="utf-8")
                )
            except Exception:
                continue

            model = result.get("model", {})
            experiment = result.get(
                "experiment",
                result.get("run_id", result_file.parent.name),
            )

            model_name = model.get(
                "name",
                result.get("configuration", {}).get(
                    "preset",
                    "unknown",
                ),
            )

            run = {
                "result_file": result_file,
                "experiment": experiment,
                "model_name": model_name,
                "run_id": result.get(
                    "run_id",
                    result_file.parent.name,
                ),
                "mtime": result_file.stat().st_mtime,
            }

            # One dropdown entry per experiment + model.
            # Keep only the newest result if duplicate runs exist.
            key = (experiment, model_name)

            previous = runs_by_key.get(key)

            if (
                previous is None
                or run["mtime"] > previous["mtime"]
            ):
                runs_by_key[key] = run

        runs = list(runs_by_key.values())

        runs.sort(
            key=lambda item: item["mtime"],
            reverse=True,
        )

        return runs

    def populate_run_selector(self):
        self.runs = self.discover_runs()

        self.window.runComboBox.blockSignals(True)
        self.window.runComboBox.clear()

        for run in self.runs:
            label = (
                f"{run['experiment']} / "
                f"{run['model_name']}"
            )
            self.window.runComboBox.addItem(
                label,
                str(run["result_file"]),
            )

        if not self.runs:
            self.window.runComboBox.blockSignals(False)
            QMessageBox.critical(
                self.window,
                "StemLab QC",
                "No benchmark result.json found.",
            )
            return

        # Select while signals are still blocked, then load exactly once.
        self.window.runComboBox.setCurrentIndex(0)
        self.window.runComboBox.blockSignals(False)
        self.load_run(self.runs[0]["result_file"])

    def run_selection_changed(self, index):
        if index < 0:
            return

        result_file = self.window.runComboBox.itemData(index)
        if not result_file:
            return

        self.load_run(Path(result_file))

    def reset_media_for_run_change(self):
        self.crossfade_timer.stop()
        self.crossfade_from_index = None
        self.crossfade_to_index = None
        self.crossfade_elapsed_ms = 0

        for player, audio in zip(self.players, self.audios):
            player.stop()
            player.setSource(QUrl())
            audio.setVolume(0.0)

        self.active_index = 0
        self.player = self.players[0]
        self.audio = self.audios[0]
        self.audio.setVolume(0.8)

        self.waveform.peaks = []
        self.waveform.position_ms = 0
        self.waveform.duration_ms = 0
        self.waveform.update()

        self.window.positionSlider.setValue(0)
        self.window.currentTimeLabel.setText("00:00")
        self.window.durationLabel.setText("00:00")

    def load_run(self, result_file):
        self.reset_media_for_run_change()
        self.run_dir = result_file.parent
        self.result = json.loads(
            result_file.read_text(encoding="utf-8")
        )

        self.qc = {
            "schema_version": 1,
            "run_id": self.result["run_id"],
            "overall": None,
            "stems": {},
        }
        self.current_source = "mix"

        input_path = ROOT / self.result["input"]["path"]

        self.sources = {
            "mix": input_path,
        }

        output_stems = {}

        for output in self.result["outputs"]:
            path = ROOT / output["path"]
            name = path.name.lower()

            for stem in (
                "bass",
                "drums",
                "other",
                "vocals",
                "guitar",
                "piano",
            ):
                if f"({stem})" in name:
                    output_stems[stem] = path

                    # Only the four primary stems have dedicated QC buttons.
                    if stem in ("bass", "drums", "other", "vocals"):
                        self.sources[stem] = path

        # RECON must include every stem produced by the model.
        if output_stems:
            recon_path = self.run_dir / "recon-f32.wav"

            # Rebuild if missing. Existing recon files from the earlier
            # four-stem-only implementation are removed for 6-stem runs.
            expected_count = len(output_stems)
            if recon_path.exists() and expected_count > 4:
                recon_path.unlink()

            if not recon_path.exists():
                build_reconstruction(
                    output_stems,
                    recon_path,
                )

            self.sources["recon"] = recon_path
            self.window.reconButton.setEnabled(True)
        else:
            self.window.reconButton.setEnabled(False)

        experiment = self.result.get(
            "experiment",
            self.result["run_id"],
        )

        model = self.result.get("model", {})
        model_name = model.get(
            "name",
            self.result.get("configuration", {}).get(
                "preset",
                "unknown",
            ),
        )

        if self.mode == "run":
            self.window.experimentLabel.setText(
                f"{experiment} / {model_name}"
            )

        existing_qc = self.run_dir / "qc.json"

        if existing_qc.exists():
            self.qc = json.loads(
                existing_qc.read_text(encoding="utf-8")
            )

        if self.mode == "run":
            self.switch_source("mix")

        self.window.statusbar.showMessage(
            f"Loaded {self.result['run_id']}"
        )

    def store_current_qc(self):
        if self.current_source in ("mix", "recon"):
            return

        usability = None

        if self.window.goodRadio.isChecked():
            usability = "good"
        elif self.window.acceptableRadio.isChecked():
            usability = "acceptable"
        elif self.window.poorRadio.isChecked():
            usability = "poor"

        issues = []

        issue_map = {
            "leakage": self.window.leakageCheck,
            "artifacts": self.window.artifactsCheck,
            "missing_source": self.window.missingCheck,
            "transients": self.window.transientsCheck,
            "low_end": self.window.lowEndCheck,
            "other": self.window.otherIssueCheck,
        }

        for name, checkbox in issue_map.items():
            if checkbox.isChecked():
                issues.append(name)

        self.qc["stems"][self.current_source] = {
            "usability": usability,
            "issues": issues,
            "note": self.window.notesEdit.toPlainText().strip(),
        }

    def restore_current_qc(self):
        self.usability_group.setExclusive(False)

        for button in self.usability_group.buttons():
            button.setChecked(False)

        self.usability_group.setExclusive(True)

        for checkbox in [
            self.window.leakageCheck,
            self.window.artifactsCheck,
            self.window.missingCheck,
            self.window.transientsCheck,
            self.window.lowEndCheck,
            self.window.otherIssueCheck,
        ]:
            checkbox.setChecked(False)

        self.window.notesEdit.clear()

        if self.current_source in ("mix", "recon"):
            return

        data = self.qc["stems"].get(self.current_source, {})

        usability = data.get("usability")

        if usability == "good":
            self.window.goodRadio.setChecked(True)
        elif usability == "acceptable":
            self.window.acceptableRadio.setChecked(True)
        elif usability == "poor":
            self.window.poorRadio.setChecked(True)

        issues = set(data.get("issues", []))

        issue_map = {
            "leakage": self.window.leakageCheck,
            "artifacts": self.window.artifactsCheck,
            "missing_source": self.window.missingCheck,
            "transients": self.window.transientsCheck,
            "low_end": self.window.lowEndCheck,
            "other": self.window.otherIssueCheck,
        }

        for name, checkbox in issue_map.items():
            checkbox.setChecked(name in issues)

        self.window.notesEdit.setPlainText(
            data.get("note", "")
        )

    def switch_source(self, source):
        if source not in self.sources:
            self.window.statusbar.showMessage(
                f"{source.upper()} not available"
            )
            return

        self.store_current_qc()

        old_position = self.player.position()
        was_playing = (
            self.player.playbackState()
            == QMediaPlayer.PlayingState
        )

        self.current_source = source

        button_map = {
            "mix": self.window.mixButton,
            "recon": self.window.reconButton,
            "bass": self.window.bassButton,
            "drums": self.window.drumsButton,
            "other": self.window.otherButton,
            "vocals": self.window.vocalsButton,
        }

        button_map[source].setChecked(True)

        display_name = {
            "mix": "SOURCE",
            "recon": "RECON",
            "bass": "BASS",
            "drums": "DRUMS",
            "other": "OTHER",
            "vocals": "VOCALS",
        }[source]

        self.window.currentStemLabel.setText(display_name)

        try:
            self.waveform.load_wav(self.sources[source])
        except Exception as exc:
            self.window.statusbar.showMessage(f"Waveform unavailable: {exc}")

        self.start_source_transition(
            self.sources[source],
            old_position,
            was_playing,
        )

        self.restore_current_qc()

    def start_source_transition(self, path, position, was_playing):
        if self.crossfade_timer.isActive():
            self.crossfade_timer.stop()
            self._finish_crossfade()

        # No crossfade is needed while paused/stopped. Reuse the active player
        # directly; this avoids QtMultimedia getting stuck while preparing a
        # second paused decoder.
        if not was_playing:
            for index, player in enumerate(self.players):
                if index != self.active_index:
                    player.stop()
                    player.setSource(QUrl())
                    self.audios[index].setVolume(0.0)

            self.player.stop()
            self.player.setSource(QUrl.fromLocalFile(str(path)))
            self.audio.setVolume(0.8)

            QTimer.singleShot(
                40,
                lambda: self._finish_paused_source_switch(position),
            )
            return

        old_index = self.active_index
        new_index = 1 - old_index

        old_player = self.players[old_index]
        old_audio = self.audios[old_index]
        new_player = self.players[new_index]
        new_audio = self.audios[new_index]

        new_audio.setVolume(0.0)
        new_player.stop()
        new_player.setSource(
            QUrl.fromLocalFile(str(path))
        )

        def begin():
            new_player.setPosition(position)
            new_player.play()

            self.crossfade_from_index = old_index
            self.crossfade_to_index = new_index
            self.crossfade_elapsed_ms = 0
            self.crossfade_timer.start()

        QTimer.singleShot(60, begin)

    def _finish_paused_source_switch(self, position):
        self.player.setPosition(position)
        self._sync_ui_from_active_player()

    def _crossfade_step(self):
        if (
            self.crossfade_from_index is None
            or self.crossfade_to_index is None
        ):
            self.crossfade_timer.stop()
            return

        self.crossfade_elapsed_ms += self.crossfade_timer.interval()
        ratio = min(
            1.0,
            self.crossfade_elapsed_ms
            / self.crossfade_duration_ms,
        )

        old_audio = self.audios[self.crossfade_from_index]
        new_audio = self.audios[self.crossfade_to_index]

        old_audio.setVolume(0.8 * (1.0 - ratio))
        new_audio.setVolume(0.8 * ratio)

        if ratio >= 1.0:
            self.crossfade_timer.stop()
            self._finish_crossfade()

    def _finish_crossfade(self):
        if (
            self.crossfade_from_index is None
            or self.crossfade_to_index is None
        ):
            return

        old_index = self.crossfade_from_index
        new_index = self.crossfade_to_index

        self.players[old_index].stop()
        self.audios[old_index].setVolume(0.0)
        self.audios[new_index].setVolume(0.8)

        self.active_index = new_index
        self.player = self.players[new_index]
        self.audio = self.audios[new_index]

        self.crossfade_from_index = None
        self.crossfade_to_index = None

        self._sync_ui_from_active_player()

    def _sync_ui_from_active_player(self):
        self.position_changed(self.player.position())
        self.duration_changed(self.player.duration())
        self.playback_state_changed(
            self.player.playbackState()
        )

    def seek_active_player(self, position):
        self.player.setPosition(position)

    def toggle_play(self):
        if (
            self.player.playbackState()
            == QMediaPlayer.PlayingState
        ):
            for player in self.players:
                if (
                    player.playbackState()
                    == QMediaPlayer.PlayingState
                ):
                    player.pause()
        else:
            self.player.play()

    def playback_state_changed_from(self, player, state):
        if player is not self.player:
            return

        if state == QMediaPlayer.PlayingState:
            self.window.playButton.setText("❚❚  PAUSE")
        else:
            self.window.playButton.setText("▶  PLAY")

    def media_status_changed_from(self, player, status):
        if player is not self.player:
            return

        if (
            status == QMediaPlayer.EndOfMedia
            and self.window.loopCheckBox.isChecked()
        ):
            self.player.setPosition(0)
            self.player.play()

    def position_changed_from(self, player, position):
        if player is not self.player:
            return

        self.waveform.set_position(position)

        if not self.window.positionSlider.isSliderDown():
            self.window.positionSlider.setValue(position)

        self.window.currentTimeLabel.setText(
            self.format_time(position)
        )

    def duration_changed_from(self, player, duration):
        if player is not self.player:
            return

        self.window.positionSlider.setMaximum(duration)
        self.window.durationLabel.setText(
            self.format_time(duration)
        )

    # Compatibility helpers used internally after swapping active players.
    def playback_state_changed(self, state):
        self.playback_state_changed_from(self.player, state)

    def media_status_changed(self, status):
        self.media_status_changed_from(self.player, status)

    def position_changed(self, position):
        self.position_changed_from(self.player, position)

    def duration_changed(self, duration):
        self.duration_changed_from(self.player, duration)

    @staticmethod
    def format_time(ms):
        seconds = max(0, ms // 1000)
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def save_qc(self):
        self.store_current_qc()

        if self.window.usableRadio.isChecked():
            self.qc["overall"] = "usable"
        elif self.window.marginalRadio.isChecked():
            self.qc["overall"] = "marginal"
        elif self.window.unusableRadio.isChecked():
            self.qc["overall"] = "unusable"

        output = self.run_dir / "qc.json"

        output.write_text(
            json.dumps(self.qc, indent=2) + "\n",
            encoding="utf-8",
        )

        self.window.statusbar.showMessage(
            f"Saved {output.relative_to(ROOT)}",
            5000,
        )
    def setup_shortcuts(self):
        mappings = {
            "1": lambda: self.switch_source("mix"),
            "2": lambda: self.switch_source("recon"),
            "3": lambda: self.switch_source("bass"),
            "4": lambda: self.switch_source("drums"),
            "5": lambda: self.switch_source("other"),
            "6": lambda: self.switch_source("vocals"),
            "Space": self.toggle_play,
            "G": lambda: self.window.goodRadio.setChecked(True),
            "A": lambda: self.window.acceptableRadio.setChecked(True),
            "P": lambda: self.window.poorRadio.setChecked(True),
            "Ctrl+S": self.save_current,
        }

        self.shortcuts = []

        for key, callback in mappings.items():
            shortcut = QShortcut(
                QKeySequence(key),
                self.window,
            )
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)

def main():
    app = QApplication(sys.argv)

    qc = QCApp()
    qc.window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
