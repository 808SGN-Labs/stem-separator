import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
spec = importlib.util.spec_from_file_location('producer', Path(__file__).resolve().parents[1] / 'gui/producer_qt.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
app = m.QApplication.instance() or m.QApplication([])

class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.w = m.Producer()
        self.backend = self.root / 'backend'
        self.backend.write_text('#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\np=Path(sys.argv[3]); p.mkdir(parents=True,exist_ok=True)\n(p/"called").write_text(sys.argv[1])\n')
        self.backend.chmod(0o755)
        self.wrapper = patch.object(m, 'WRAPPER', self.backend)
        self.wrapper.start()
    def tearDown(self):
        self.w.close()
        self.w.deleteLater()
        app.processEvents()
        self.wrapper.stop()
        self.tmp.cleanup()
    def audio(self, name):
        p=self.root/name; p.write_bytes(b'fixture'); return p
    def wait_done(self, timeout=6):
        deadline=time.monotonic()+timeout
        while self.w.batch_active and time.monotonic()<deadline:
            app.processEvents(); time.sleep(.005)
        self.assertFalse(self.w.batch_active)
    def test_expandable_stems_show_real_wavs_only(self):
        source = self.audio('song.wav')
        self.w.add_paths([str(source)])
        target = self.root / 'song_stemlab' / 'balanced'
        target.mkdir(parents=True)
        (target / 'Vocals.wav').write_bytes(b'content')
        (target / 'empty.wav').touch()
        (target / 'notes.txt').write_text('not a stem')
        self.w.refresh_stem_children(0)
        parent = self.w.queue_list.topLevelItem(0)
        self.assertEqual(parent.childCount(), 1)
        self.assertEqual(parent.child(0).text(0), 'Vocals')
        self.assertEqual(parent.child(0).data(0, m.Qt.UserRole), str(target / 'Vocals.wav'))

    def test_recovery_classifies_existing_outputs_without_overwrite(self):
        source = self.audio('recovery.wav')
        self.w.add_paths([str(source)])
        target = self.root / 'recovery_stemlab' / 'balanced'
        self.assertEqual(self.w.inspect_existing_output(0), 'READY')
        target.mkdir(parents=True)
        self.assertEqual(self.w.inspect_existing_output(0), 'READY')
        paths = [target / f'recovery_({stem})_htdemucs.wav' for stem in ('Bass', 'Drums', 'Other', 'Vocals')]
        for p in paths[:3]:
            p.write_bytes(b'fixture')
        self.assertEqual(self.w.inspect_existing_output(0), 'PARTIAL / UNKNOWN')
        paths[3].write_bytes(b'fixture')
        self.assertEqual(self.w.inspect_existing_output(0), 'EXISTING STEMS')
        paths[0].write_bytes(b'')
        self.assertEqual(self.w.inspect_existing_output(0), 'PARTIAL / UNKNOWN')
        paths[0].write_bytes(b'preserve')
        self.w.start_batch()
        self.wait_done()
        self.assertEqual(paths[0].read_bytes(), b'preserve')
        self.assertEqual(self.w.queue_list.topLevelItem(0).text(2), 'Existing Stems')
        self.assertFalse((target / 'called').exists())

    def test_reimport_verifies_existing_wavs_without_processing(self):
        import wave
        source = self.root / 'existing.wav'
        def wav(path, frames=44100):
            with wave.open(str(path), 'wb') as f:
                f.setnchannels(2); f.setsampwidth(2); f.setframerate(44100)
                f.writeframes(b'\0' * frames * 4)
        wav(source)
        directory = self.root / 'existing_stemlab' / 'balanced'
        directory.mkdir(parents=True)
        stems = [directory / f'existing_({name})_htdemucs.wav' for name in ('Bass','Drums','Other','Vocals')]
        for path in stems: wav(path)
        self.w.add_paths([str(source)])
        self.assertEqual(self.w.queue_list.topLevelItem(0).text(2), 'Verified Existing')
        self.assertFalse((directory / 'called').exists())
        wav(stems[0], frames=100)
        self.assertEqual(self.w.refresh_existing_status(0), 'PARTIAL / UNKNOWN')
        self.assertEqual(self.w.queue_list.topLevelItem(0).text(2), 'Partial / Unknown')
        self.assertFalse((directory / 'called').exists())

    def test_source_row_exposes_drag_path(self):
        source = self.audio('source.wav')
        self.w.add_paths([str(source)])
        parent = self.w.queue_list.topLevelItem(0)
        self.assertEqual(parent.data(0, m.Qt.UserRole), str(source.resolve()))
        self.assertTrue(source.is_file())

    def test_stem_labels_preserve_original_files(self):
        p = Path('3_(kick)_MDX23C-DrumSep-aufr33-jarredou.wav')
        self.assertEqual(self.w.stem_display_name(p), 'Kick')
        self.assertEqual(self.w.stem_display_name(Path('17_(Vocals)_htdemucs.wav')), 'Vocals')

    def test_drum_parts_validation(self):
        import wave
        source = self.root / 'drums.wav'
        def wav(path):
            with wave.open(str(path), 'wb') as f:
                f.setnchannels(2); f.setsampwidth(2); f.setframerate(44100)
                f.writeframes(b'\0' * 44100 * 4)
        wav(source)
        target = self.root / 'stems'; target.mkdir()
        for stem in ('kick', 'snare', 'toms', 'hh', 'ride', 'crash'):
            wav(target / f'drums_({stem})_MDX23C-DrumSep-aufr33-jarredou.wav')
        self.w.set_input(str(source))
        self.w.presets.setCurrentIndex(self.w.presets.findData('drum-parts'))
        self.w.current_output = target
        self.assertTrue(self.w.validate_output())
        kick = target / 'drums_(kick)_MDX23C-DrumSep-aufr33-jarredou.wav'
        kick.unlink()
        self.assertFalse(self.w.validate_output())
        wav(kick)
        original = self.w.probe_audio
        with patch.object(self.w, 'probe_audio') as probe:
            def wrong_rate(path):
                info = original(path)
                if Path(path) == kick:
                    info['rate'] = 48000
                return info
            probe.side_effect = wrong_rate
            self.assertFalse(self.w.validate_output())
        with patch.object(self.w, 'probe_audio') as probe:
            def wrong_codec(path):
                info = original(path)
                if Path(path) == kick:
                    info['codec'] = 'mp3'
                return info
            probe.side_effect = wrong_codec
            self.assertFalse(self.w.validate_output())

    def test_copy_button_follows_details_visibility(self):
        self.assertFalse(self.w.copy_log_button.isVisible())
        self.w.log_toggle.setChecked(True)
        self.assertFalse(self.w.copy_log_button.isHidden())
        self.w.log_toggle.setChecked(False)
        self.assertTrue(self.w.copy_log_button.isHidden())

    def test_copy_process_details(self):
        self.w.log.setPlainText('Process completed\nOutput verified')
        self.w.copy_process_details()
        self.assertEqual(app.clipboard().text(), 'Process completed\nOutput verified')
        self.assertEqual(self.w.copy_log_button.text(), 'Copied')

    def test_appearance_themes_live_and_persist(self):
        self.assertEqual(len(m.THEMES), 8)
        source = self.audio('theme.wav')
        self.w.add_paths([str(source)])
        previous = self.w.settings.value('appearance/theme', 'Saigon Mint')
        try:
            self.w.apply_theme('Saigon Mint')
            self.w.set_batch_label(0, 'PROCESSING')
            before = self.w.queue_list.topLevelItem(0).foreground(2).color().name()
            self.w.apply_theme('Analog Orange')
            self.assertEqual(self.w.theme_name, 'Analog Orange')
            self.assertEqual(self.w.settings.value('appearance/theme'), 'Analog Orange')
            self.assertIn(m.THEMES['Analog Orange'][3], app.styleSheet())
            after = self.w.queue_list.topLevelItem(0).foreground(2).color().name()
            self.assertNotEqual(before, after)
            self.w.apply_theme('Not A Theme')
            self.assertEqual(self.w.theme_name, 'Analog Orange')
        finally:
            self.w.apply_theme(previous if previous in m.THEMES else 'Saigon Mint')
            self.w.settings.setValue('appearance/theme', previous)

    def test_queue_polish_status_colors_and_controls(self):
        source = self.audio('polish.wav')
        self.w.add_paths([str(source)])
        row = self.w.queue_list.topLevelItem(0)
        mode = self.w.queue_list.itemWidget(row, 1)
        self.assertEqual(mode.objectName(), 'queueMode')
        self.assertEqual(self.w.clear_queue_button.objectName(), 'quiet')
        self.w.set_batch_label(0, 'VERIFIED')
        verified = row.foreground(2).color().name()
        self.w.set_batch_label(0, 'FAILED')
        failed = row.foreground(2).color().name()
        self.w.set_batch_label(0, 'PROCESSING')
        processing = row.foreground(2).color().name()
        self.assertEqual(len({verified, failed, processing}), 3)
        self.assertEqual(row.text(2), 'Processing')

    def test_queue_is_primary_workspace(self):
        self.assertTrue(self.w.input.isHidden())
        self.assertTrue(self.w.presets.isHidden())
        self.assertTrue(self.w.output.isHidden())
        self.assertFalse(self.w.queue_list.isHidden())
        self.assertFalse(self.w.batch_start_button.isHidden())

    def test_workspace_drop_adds_audio_to_queue(self):
        from PySide6.QtCore import QPointF, QMimeData, Qt, QUrl
        from PySide6.QtGui import QDropEvent
        audio = self.audio('dropped.wav')
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(audio))])
        event = QDropEvent(QPointF(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        viewport = self.w.centralWidget().viewport()
        self.assertTrue(self.w.eventFilter(viewport, event))
        self.assertEqual(self.w.batch_paths, [audio.resolve()])
        self.assertEqual(self.w.queue_list.topLevelItemCount(), 1)

    def test_two_modes_and_locked_controls(self):
        a,b=self.audio('a.wav'),self.audio('b.wav')
        self.w.add_paths([str(a),str(b)])
        combo=self.w.queue_list.itemWidget(self.w.queue_list.topLevelItem(1),1)
        combo.setCurrentIndex(combo.findData('vocals'))
        with patch.object(self.w,'validate_output',side_effect=[True,None]):
            self.w.start_batch()
            self.assertFalse(self.w.input_browse.isEnabled())
            self.assertFalse(self.w.output_browse.isEnabled())
            self.w.set_input(str(b))
            self.wait_done()
        self.assertEqual((self.root/'a_stemlab/balanced/called').read_text(),'balanced')
        self.assertEqual((self.root/'b_stemlab/vocals/called').read_text(),'vocals')
        self.assertEqual(self.w.queue_list.topLevelItem(0).text(2),'Verified')
        self.assertEqual(self.w.queue_list.topLevelItem(1).text(2),'Unverified')
        self.assertIn('a.wav',self.w.log.toPlainText())
        self.assertIn('b.wav',self.w.log.toPlainText())
    def test_folder_duplicate_and_skip(self):
        a=self.audio('a.WAV'); self.audio('ignore.txt')
        (self.root/'nested').mkdir(); (self.root/'nested/x.wav').touch()
        (self.root/'alias.wav').symlink_to(a)
        self.w.add_paths([str(self.root),str(a)])
        self.assertEqual(self.w.batch_paths,[a.resolve()])
        target=self.root/'a_stemlab/balanced';target.parent.mkdir();target.write_text('preserve')
        self.w.start_batch();self.wait_done()
        self.assertEqual(target.read_text(),'preserve')
        self.assertEqual(self.w.queue_list.topLevelItem(0).text(2),'Blocked')
    def test_legacy_mode_display(self):
        self.w.set_input(str(self.audio('a.wav')))
        self.w.presets.setCurrentIndex(self.w.presets.findData('maximum'))
        self.w.start_batch()
        combo=self.w.queue_list.itemWidget(self.w.queue_list.topLevelItem(0),1)
        self.assertEqual(combo.currentData(),'maximum')
        self.w.cancel();app.processEvents()
        self.assertIsNone(self.w.process)
    def test_failure_continues(self):
        self.backend.write_text('#!/bin/sh\nexit 7\n')
        self.w.add_paths([str(self.audio('a.wav')),str(self.audio('b.wav'))])
        self.w.start_batch();self.wait_done()
        self.assertEqual([self.w.queue_list.topLevelItem(i).text(2) for i in range(2)],['Failed','Failed'])
    def test_cancel_between_jobs_restores_queue_controls(self):
        self.w.add_paths([str(self.audio('a.wav')), str(self.audio('b.wav'))])
        self.w.start_batch()
        self.assertTrue(self.w.batch_active)
        self.assertFalse(self.w.batch_start_button.isEnabled())
        self.w.cancel()  # No QProcess has started yet; next job is queued by QTimer.
        app.processEvents()
        self.assertFalse(self.w.batch_active)
        self.assertEqual(self.w.status.text(), 'CANCELLED')
        self.assertTrue(self.w.batch_start_button.isEnabled())
        self.assertTrue(self.w.clear_queue_button.isEnabled())
        self.assertTrue(self.w.add_files_button.isEnabled())
        self.assertTrue(self.w.add_folder_button.isEnabled())
        self.assertTrue(self.w.queue_list.itemWidget(self.w.queue_list.topLevelItem(0), 1).isEnabled())
        self.assertFalse((self.root / 'a_stemlab').exists())

    def test_cancel_kills_stubborn_process(self):
        self.backend.write_text('#!/usr/bin/env python3\nimport signal,time\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\nprint("ready",flush=True)\ntime.sleep(30)\n')
        self.w.add_paths([str(self.audio('a.wav')),str(self.audio('b.wav'))])
        self.w.start_batch()
        end=time.monotonic()+3
        while 'ready' not in self.w.log.toPlainText() and time.monotonic()<end:
            app.processEvents();time.sleep(.005)
        self.assertIn('ready',self.w.log.toPlainText())
        self.w.cancel();self.wait_done()
        self.assertEqual(self.w.queue_list.topLevelItem(0).text(2),'Cancelled')
        self.assertFalse((self.root/'b_stemlab').exists())
    def test_validation_rejects_missing_output(self):
        self.w.set_input(str(self.audio('a.wav')))
        self.w.current_output=self.root
        self.assertFalse(self.w.validate_output())
    def test_real_wav_validation(self):
        import wave
        def wav(path, frames=44100):
            with wave.open(str(path), 'wb') as out:
                out.setnchannels(2); out.setsampwidth(2); out.setframerate(44100)
                out.writeframes(b'\0' * frames * 4)
        source=self.root/'valid.wav'; wav(source)
        self.w.set_input(str(source)); self.w.current_output=self.root
        for stem in ('Bass','Drums','Other','Vocals'):
            wav(self.root/f'valid_({stem})_htdemucs.wav')
        self.assertTrue(self.w.validate_output())
        wav(self.root/'valid_(Bass)_htdemucs.wav', frames=100)
        self.assertFalse(self.w.validate_output())

    def test_close_running(self):
        self.backend.write_text('#!/bin/sh\nexec sleep 30\n')
        self.w.add_paths([str(self.audio('a.wav')),str(self.audio('b.wav'))]);self.w.start_batch()
        while self.w.process is None: app.processEvents()
        with patch.object(m.QMessageBox,'question',return_value=m.QMessageBox.Yes):
            self.w.close()
        self.assertIsNone(self.w.process)
        self.assertFalse(self.w.batch_active)

if __name__=='__main__': unittest.main()
