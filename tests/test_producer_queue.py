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
        (target / 'drums_(kick)_MDX23C-DrumSep-aufr33-jarredou.wav').unlink()
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
        self.assertEqual(self.w.queue_list.topLevelItem(0).text(2),'Skipped')
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
