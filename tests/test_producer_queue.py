import importlib.util
import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
import wave
from pathlib import Path, PureWindowsPath
from unittest.mock import MagicMock, patch
from shiboken6 import isValid
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
spec = importlib.util.spec_from_file_location('producer', Path(__file__).resolve().parents[1] / 'gui/producer_qt.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
app = m.QApplication.instance() or m.QApplication([])


class BackendCommandTests(unittest.TestCase):
    def test_linux_keeps_wrapper_and_positional_arguments(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            wrapper = root / 'scripts' / 'stem-separate'
            wrapper.parent.mkdir()
            wrapper.write_text('#!/bin/sh\nexit 0\n')
            wrapper.chmod(0o755)
            source = root / 'audio with spaces.wav'
            output = root / 'stems 夜'
            self.assertEqual(
                m.build_backend_command('balanced', source, output, platform='linux', app_root=root),
                (str(wrapper), ['balanced', str(source), str(output)]),
            )
            wrapper.chmod(0o644)
            with self.assertRaisesRegex(FileNotFoundError, 'scripts/stem-separate'):
                m.build_backend_command('balanced', source, output, platform='linux', app_root=root)

    def test_windows_uses_app_owned_executable_and_argument_list(self):
        root = PureWindowsPath(r'C:\Program Files\StemLab\app')
        source = PureWindowsPath(r'D:\Audio Projects\夜の曲.wav')
        output = PureWindowsPath(r'D:\Stems\Night Mix')
        expected_program = str(root.parent / '.venv' / 'Scripts' / 'audio-separator.exe')
        seen = []
        program, arguments = m.build_backend_command(
            'balanced', source, output, platform='win32', app_root=root,
            environ={'LOCALAPPDATA': r'C:\Users\Tester\AppData\Local'},
            executable_exists=lambda path: seen.append(path) or path == expected_program,
        )
        self.assertEqual(seen, [str(root / '.venv' / 'Scripts' / 'audio-separator.exe'),
                                expected_program])
        self.assertEqual(program, expected_program)
        self.assertEqual(arguments, [str(source), '--model_filename', 'htdemucs.yaml',
                                     '--model_file_dir', r'C:\Users\Tester\AppData\Local\808sgn-stem-lab\models',
                                     '--output_dir', str(output), '--output_format', 'WAV'])
        self.assertTrue(all(isinstance(arg, str) for arg in arguments))

    def test_windows_models_match_every_wrapper_preset_and_honor_overrides(self):
        expected = {'4stems': 'hdemucs_mmi.yaml', 'balanced': 'htdemucs.yaml',
                    'maximum': 'htdemucs_ft.yaml', 'vocals': 'vocals_mel_band_roformer.ckpt',
                    '6stems': 'htdemucs_6s.yaml',
                    'drum-parts': 'MDX23C-DrumSep-aufr33-jarredou.ckpt',
                    'deverb': 'deverb_bs_roformer_8_384dim_10depth.ckpt'}
        env = {'STEM_LAB_VENV': r'E:\Private App\venv',
               'STEM_LAB_MODELS': r'F:\Model Cache\音'}
        for preset, model in expected.items():
            with self.subTest(preset=preset):
                program, args = m.build_backend_command(
                    preset, r'C:\Input\source.wav', r'C:\Output Dir', platform='win32',
                    app_root=PureWindowsPath(r'C:\StemLab\app'), environ=env,
                    executable_exists=lambda _: True,
                )
                self.assertEqual(program, r'E:\Private App\venv\Scripts\audio-separator.exe')
                self.assertEqual(args[1:5], ['--model_filename', model,
                                              '--model_file_dir', env['STEM_LAB_MODELS']])
                self.assertEqual(args[-4:], ['--output_dir', r'C:\Output Dir', '--output_format', 'WAV'])

    def test_windows_prefers_checkout_venv(self):
        root = PureWindowsPath(r'C:\StemLab')
        program, _ = m.build_backend_command(
            'balanced', 'source.wav', 'output', platform='win32', app_root=root,
            environ={'LOCALAPPDATA': r'C:\Local'}, executable_exists=lambda _: True)
        self.assertEqual(program, str(root / '.venv' / 'Scripts' / 'audio-separator.exe'))

    def test_windows_explicit_venv_does_not_fall_back(self):
        seen = []
        with self.assertRaises(FileNotFoundError):
            m.build_backend_command(
                'balanced', 'source.wav', 'output', platform='win32',
                environ={'STEM_LAB_VENV': r'E:\Missing'},
                executable_exists=lambda path: seen.append(path) or False)
        self.assertTrue(seen)
        self.assertEqual(set(seen), {r'E:\Missing\Scripts\audio-separator.exe'})

    def test_windows_missing_executable_has_actionable_diagnostic(self):
        root = PureWindowsPath(r'C:\StemLab\app')
        with self.assertRaisesRegex(FileNotFoundError, 'Install the CPU dependencies'):
            m.build_backend_command('balanced', r'C:\Input.wav', r'C:\Output', platform='win32',
                                    app_root=root, environ={'LOCALAPPDATA': r'C:\Local'},
                                    executable_exists=lambda _: False)
        with self.assertRaisesRegex(ValueError, 'LOCALAPPDATA'):
            m.build_backend_command('balanced', r'C:\Input.wav', r'C:\Output', platform='win32',
                                    app_root=root, environ={}, executable_exists=lambda _: True)


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.audio_output_patch = patch.object(m, 'QAudioOutput', new_callable=MagicMock)
        self.media_player_patch = patch.object(m, 'QMediaPlayer', new_callable=MagicMock)
        self.audio_output_patch.start()
        self.media_player_patch.start()
        self.w = m.Producer()
        self.backend = self.root / 'backend'
        self.backend.write_text('#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\np=Path(sys.argv[3]); p.mkdir(parents=True,exist_ok=True)\n(p/"called").write_text(sys.argv[1])\nwith Path(__file__).with_name("backend_calls").open("a") as log: log.write("\\t".join(sys.argv[1:4]) + "\\n")\n')
        self.backend.chmod(0o755)
        self.wrapper = patch.object(m, 'WRAPPER', self.backend)
        self.wrapper.start()
    def tearDown(self):
        self.w.close()
        self.w.deleteLater()
        app.processEvents()
        self.wrapper.stop()
        self.media_player_patch.stop()
        self.audio_output_patch.stop()
        self.tmp.cleanup()
    def audio(self, name):
        p=self.root/name; p.write_bytes(b'fixture'); return p
    def wav(self, path, frames=44100, rate=44100, channels=2):
        with wave.open(str(path), 'wb') as out:
            out.setnchannels(channels); out.setsampwidth(2); out.setframerate(rate)
            out.writeframes(b'\0' * frames * channels * 2)
        return path
    def backend_calls(self):
        log = self.root / 'backend_calls'
        return [line.split('\t') for line in log.read_text().splitlines()] if log.exists() else []
    def mark_owned(self, directory, source, preset='balanced'):
        (directory / m.OWNER_FILE).write_text(json.dumps(self.w.output_owner(source, preset)))
    def wait_done(self, timeout=6):
        deadline=time.monotonic()+timeout
        while self.w.batch_active and time.monotonic()<deadline:
            app.processEvents(); time.sleep(.005)
        self.assertFalse(self.w.batch_active)
    def wait_checks(self, timeout=6):
        deadline = time.monotonic() + timeout
        while self.w._checks and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.005)
        app.processEvents()
        self.assertFalse(self.w._checks)
    def check_state(self, index):
        self.assertEqual(self.w.refresh_existing_status(index), 'CHECKING')
        self.wait_checks()
        return self.w.queue_list.topLevelItem(index).data(2, m.Qt.UserRole)
    def validate_output(self):
        return self.w.verified_stem_paths(Path(self.w.input.text().strip()),
                                          self.w.presets.currentData(), self.w.current_output) is not None
    def test_slow_ffprobe_does_not_block_qt_events(self):
        source = self.wav(self.root / 'slow.wav')
        directory = self.root / 'slow_stemlab' / 'balanced'
        directory.mkdir(parents=True)
        self.mark_owned(directory, source)
        for stem in ('Bass', 'Drums', 'Other', 'Vocals'):
            self.wav(directory / f'slow_({stem})_htdemucs.wav')
        probe = self.root / 'ffprobe'
        probe.write_text('#!/usr/bin/env python3\nimport time\nfrom pathlib import Path\n'
                         'with Path(__file__).with_name("probe_calls").open("a") as log: log.write("called\\n")\n'
                         'time.sleep(0.15)\n'
                         'print(\'{"streams":[{"codec_name":"pcm_s16le","sample_rate":"44100","channels":2}],"format":{"duration":"1.0"}}\')\n')
        probe.chmod(0o755)
        ticks = []
        widget_threads = []
        set_label = self.w.set_batch_label
        def checked_label(*args):
            widget_threads.append(threading.get_ident())
            return set_label(*args)
        with patch.object(self.w, 'set_batch_label', side_effect=checked_label), \
                patch.dict(os.environ, {'PATH': str(self.root) + os.pathsep + os.environ['PATH']}):
            m.QTimer.singleShot(20, lambda: ticks.append(time.monotonic()))
            started = time.monotonic()
            self.w.add_paths([str(source)])
            self.assertLess(time.monotonic() - started, 0.2)
            deadline = time.monotonic() + 2
            while not ticks and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(.005)
            self.assertTrue(ticks)
            self.assertEqual(self.w.queue_list.topLevelItem(0).text(2), 'Checking')
            self.wait_checks()
        self.assertEqual(self.w.queue_list.topLevelItem(0).text(2), 'Verified Existing')
        self.assertEqual((self.root / 'probe_calls').read_text().count('called'), 5)
        self.assertEqual(set(widget_threads), {threading.main_thread().ident})

    def test_stale_check_cannot_verify_changed_preset_or_reimport(self):
        source = self.wav(self.root / 'stale.wav')
        directory = self.root / 'stale_stemlab' / 'balanced'
        directory.mkdir(parents=True)
        self.mark_owned(directory, source)
        for stem in ('Bass', 'Drums', 'Other', 'Vocals'):
            self.wav(directory / f'stale_({stem})_htdemucs.wav')
        entered, release = threading.Event(), threading.Event()
        original = self.w.probe_audio
        def delayed(path, **kwargs):
            entered.set()
            release.wait(4)
            return original(path, **kwargs)
        with patch.object(self.w, 'probe_audio', side_effect=delayed):
            self.w.add_paths([str(source)])
            deadline = time.monotonic() + 2
            while not entered.is_set() and time.monotonic() < deadline:
                app.processEvents(); time.sleep(.005)
            self.assertTrue(entered.is_set())
            combo = self.w.queue_list.itemWidget(self.w.queue_list.topLevelItem(0), 1)
            combo.setCurrentIndex(combo.findData('vocals'))
            self.wait_checks()
            self.assertEqual(self.w.queue_list.topLevelItem(0).text(2), 'Queued')
            self.assertFalse(self.w._verified)
            self.w.clear_batch()
            self.w.add_paths([str(source)])
            combo = self.w.queue_list.itemWidget(self.w.queue_list.topLevelItem(0), 1)
            combo.setCurrentIndex(combo.findData('vocals'))
            release.set()
            self.wait_checks()
        self.assertNotEqual(self.w.queue_list.topLevelItem(0).text(2), 'Verified Existing')
        self.assertFalse(self.w._verified)

    def test_missing_verified_stem_schedules_recheck_without_probe_on_drag(self):
        source = self.wav(self.root / 'removed.wav')
        directory = self.root / 'removed_stemlab' / 'balanced'
        directory.mkdir(parents=True)
        self.mark_owned(directory, source)
        stems = [self.wav(directory / f'removed_({stem})_htdemucs.wav')
                 for stem in ('Bass', 'Drums', 'Other', 'Vocals')]
        self.w.add_paths([str(source)])
        self.wait_checks()
        child = self.w.queue_list.topLevelItem(0).child(0)
        stems[0].unlink()
        with patch.object(self.w, 'probe_audio', side_effect=AssertionError('GUI reprobed')), \
                patch.object(m, 'QDrag') as drag:
            self.w.queue_list.drag_stem(child)
            drag.assert_not_called()
        self.assertEqual(self.w.queue_list.topLevelItem(0).text(2), 'Checking')
        self.wait_checks()
        self.assertEqual(self.w.queue_list.topLevelItem(0).text(2), 'Partial / Unknown')

    def test_multiple_checks_are_bounded_and_cancelled_on_clear(self):
        sources = [self.wav(self.root / f'many{i}.wav') for i in range(4)]
        for source in sources:
            directory = self.w.default_output_dir(source, 'balanced')
            directory.mkdir(parents=True)
            self.mark_owned(directory, source)
            for stem in ('Bass', 'Drums', 'Other', 'Vocals'):
                self.wav(directory / f'{source.stem}_({stem})_htdemucs.wav')
        entered = threading.Event()
        release = threading.Event()
        def delayed(path, **kwargs):
            entered.set()
            release.wait(2)
            return m.Producer.probe_audio(path, **kwargs)
        with patch.object(self.w, 'probe_audio', side_effect=delayed):
            self.w.add_paths([str(source) for source in sources])
            self.assertEqual(self.w._check_pool.maxThreadCount(), 2)
            self.assertEqual(self.w.queue_list.topLevelItemCount(), 4)
            self.assertTrue(entered.wait(2))
            self.w.clear_batch()
            release.set()
            deadline = time.monotonic() + 3
            while self.w._check_pool.activeThreadCount() and time.monotonic() < deadline:
                app.processEvents(); time.sleep(.005)
            app.processEvents()
        self.assertEqual(self.w.queue_list.topLevelItemCount(), 0)
        self.assertFalse(self.w._verified)

    def test_ffprobe_timeout_and_cancellation_stop_subprocess(self):
        probe = self.root / 'ffprobe'
        probe.write_text('#!/usr/bin/env python3\nimport time\ntime.sleep(5)\n')
        probe.chmod(0o755)
        source = self.audio('probe.wav')
        with patch.dict(os.environ, {'PATH': str(self.root) + os.pathsep + os.environ['PATH']}):
            started = time.monotonic()
            with self.assertRaises(subprocess.TimeoutExpired):
                self.w.probe_audio(source, timeout=.15)
            self.assertLess(time.monotonic() - started, 1)
            cancelled = threading.Event()
            failures = []
            def run():
                try:
                    self.w.probe_audio(source, cancelled=cancelled)
                except subprocess.TimeoutExpired as error:
                    failures.append(error)
            worker = threading.Thread(target=run)
            worker.start()
            time.sleep(.1)
            cancelled.set()
            worker.join(1)
            self.assertFalse(worker.is_alive())
            self.assertEqual(len(failures), 1)

    def test_close_during_validation_disconnects_result_before_widget_destruction(self):
        source = self.wav(self.root / 'closing.wav')
        directory = self.root / 'closing_stemlab' / 'balanced'
        directory.mkdir(parents=True)
        self.mark_owned(directory, source)
        for stem in ('Bass', 'Drums', 'Other', 'Vocals'):
            self.wav(directory / f'closing_({stem})_htdemucs.wav')
        callbacks = []
        class ClosingProducer(m.Producer):
            def _check_finished(self, *args):
                callbacks.append('result')
                super()._check_finished(*args)
        other = ClosingProducer()
        entered, release = threading.Event(), threading.Event()
        original = other.probe_audio
        def delayed(path, **kwargs):
            entered.set()
            release.wait(3)
            return original(path, **kwargs)
        try:
            with patch.object(other, 'probe_audio', side_effect=delayed):
                other.add_paths([str(source)])
                deadline = time.monotonic() + 2
                while not entered.is_set() and time.monotonic() < deadline:
                    app.processEvents(); time.sleep(.005)
                self.assertTrue(entered.is_set())
                self.assertEqual(other.queue_list.topLevelItem(0).text(2), 'Checking')
                other.close()
                self.assertTrue(other._closing)
                self.assertFalse(other._checks)
                other.deleteLater()
                release.set()
                app.sendPostedEvents(None, m.QEvent.DeferredDelete)
                app.processEvents()
                self.assertFalse(isValid(other))
                self.assertEqual(callbacks, [])
        finally:
            release.set()
            if isValid(other):
                other.close()
                other.deleteLater()
                app.sendPostedEvents(None, m.QEvent.DeferredDelete)

    def test_close_discards_already_queued_worker_result(self):
        source = self.audio('queued-close.wav')
        callbacks = []
        class ClosingProducer(m.Producer):
            def _check_finished(self, *args):
                callbacks.append('result')
                super()._check_finished(*args)
        other = ClosingProducer()
        entered = threading.Event()
        def inspect(*args):
            entered.set()
            return 'READY'
        try:
            with patch.object(other, 'inspect_output', side_effect=inspect):
                other.add_paths([str(source)])
                self.assertTrue(entered.wait(2))
                deadline = time.monotonic() + 2
                while other._check_pool.activeThreadCount() and time.monotonic() < deadline:
                    time.sleep(.005)
                self.assertEqual(other._check_pool.activeThreadCount(), 0)
                self.assertEqual(other.queue_list.topLevelItem(0).text(2), 'Checking')
                other.close()
                other.deleteLater()
                app.sendPostedEvents(None, m.QEvent.DeferredDelete)
                app.processEvents()
                self.assertFalse(isValid(other))
                self.assertEqual(callbacks, [])
        finally:
            if isValid(other):
                other.close()
                other.deleteLater()
                app.sendPostedEvents(None, m.QEvent.DeferredDelete)

    def test_successful_job_verifies_then_drags_generated_stem(self):
        source = self.wav(self.root / 'generated.wav')
        self.backend.write_text('''#!/usr/bin/env python3
import sys, wave
from pathlib import Path
source, directory = Path(sys.argv[2]), Path(sys.argv[3])
with Path(__file__).with_name("backend_calls").open("a") as log:
    log.write("\\t".join(sys.argv[1:4]) + "\\n")
for name in ("Bass", "Drums", "Other", "Vocals"):
    with wave.open(str(directory / f"{source.stem}_({name})_htdemucs.wav"), "wb") as out:
        out.setnchannels(2); out.setsampwidth(2); out.setframerate(44100)
        out.writeframes(b"\\0" * 44100 * 4)
''')
        self.w.add_paths([str(source)])
        self.w.start_batch()
        self.wait_done()
        self.assertEqual(len(self.backend_calls()), 1)
        parent = self.w.queue_list.topLevelItem(0)
        self.assertEqual(parent.text(2), 'Verified')
        self.assertEqual([parent.child(i).text(2) for i in range(4)], ['Ready'] * 4)
        with patch.object(m, 'QDrag') as drag:
            self.w.queue_list.drag_stem(parent.child(0))
        drag.assert_called_once()
        self.assertEqual(Path(drag.return_value.setMimeData.call_args.args[0].urls()[0].toLocalFile()).name,
                         'generated_(Bass)_htdemucs.wav')
    def test_unrelated_wavs_are_not_listed_as_supported_stems(self):
        source = self.wav(self.root / 'song.wav')
        self.w.add_paths([str(source)])
        target = self.root / 'song_stemlab' / 'balanced'
        target.mkdir(parents=True)
        self.mark_owned(target, source)
        (target / 'Vocals.wav').write_bytes(b'content')
        (target / 'empty.wav').touch()
        (target / 'notes.txt').write_text('not a stem')
        self.w.refresh_stem_children(0)
        parent = self.w.queue_list.topLevelItem(0)
        self.assertEqual(parent.childCount(), 0)

    def test_partial_and_invalid_stems_are_not_ready_or_exportable(self):
        source = self.wav(self.root / 'unsafe.wav')
        self.w.add_paths([str(source)])
        target = self.w.stem_output_dir(0)
        target.mkdir(parents=True)
        self.mark_owned(target, source)
        (target / 'junk.wav').write_bytes(b'not audio')
        (target / 'unsafe_(Bass)_htdemucs.wav').write_bytes(b'malformed WAV')
        (target / 'unsafe_(Drums)_htdemucs.wav').touch()
        self.w.refresh_existing_status(0)
        self.wait_checks()
        parent = self.w.queue_list.topLevelItem(0)
        self.assertEqual(parent.text(2), 'Partial / Unknown')
        self.assertEqual({parent.child(i).text(0) for i in range(parent.childCount())},
                         {'Bass', 'Drums'})
        self.assertTrue(all(parent.child(i).text(2) == 'Unverified'
                            for i in range(parent.childCount())))
        child = parent.child(0)
        with patch.object(self.w.preview_player, 'setSource') as preview, \
                patch.object(m, 'QMenu') as menu, patch.object(m, 'QDrag') as drag, \
                patch.object(self.w.queue_list, 'itemAt', return_value=child):
            self.w.preview_stem_item(child)
            self.w.stem_context_menu(self.w.queue_list.visualItemRect(child).center())
            self.w.queue_list.setCurrentItem(child)
            self.w.queue_list.startDrag(m.Qt.CopyAction)
        preview.assert_not_called()
        menu.assert_not_called()
        drag.assert_not_called()

    def test_recovery_classifies_existing_outputs_without_overwrite(self):
        source = self.audio('recovery.wav')
        self.w.add_paths([str(source)])
        target = self.root / 'recovery_stemlab' / 'balanced'
        self.assertEqual(self.w.inspect_existing_output(0), 'READY')
        target.mkdir(parents=True)
        self.assertEqual(self.w.inspect_existing_output(0), 'READY')
        self.mark_owned(target, source)
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
        self.assertEqual(self.w.queue_list.topLevelItem(0).text(2), 'Partial / Unknown')
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
        self.mark_owned(directory, source)
        stems = [directory / f'existing_({name})_htdemucs.wav' for name in ('Bass','Drums','Other','Vocals')]
        for path in stems: wav(path)
        self.w.add_paths([str(source)])
        self.wait_checks()
        self.assertEqual(self.w.queue_list.topLevelItem(0).text(2), 'Verified Existing')
        parent = self.w.queue_list.topLevelItem(0)
        self.assertEqual([parent.child(i).text(2) for i in range(parent.childCount())], ['Ready'] * 4)
        child = parent.child(0)
        with patch.object(self.w.preview_player, 'setSource') as preview, \
                patch.object(m, 'QMenu') as menu, patch.object(m, 'QDrag') as drag, \
                patch.object(self.w.queue_list, 'itemAt', return_value=child):
            self.w.preview_stem_item(child)
            self.w.stem_context_menu(self.w.queue_list.visualItemRect(child).center())
            self.w.queue_list.setCurrentItem(child)
            self.w.queue_list.startDrag(m.Qt.CopyAction)
        preview.assert_called_once()
        menu.return_value.exec.assert_called_once()
        drag.assert_called_once()
        self.assertEqual(drag.return_value.setMimeData.call_args.args[0].urls()[0].toLocalFile(),
                         str(stems[0]))
        self.assertFalse((directory / 'called').exists())
        wav(stems[0], frames=100)
        self.assertEqual(self.check_state(0), 'PARTIAL / UNKNOWN')
        self.assertEqual(self.w.queue_list.topLevelItem(0).text(2), 'Partial / Unknown')
        self.assertTrue(all(parent.child(i).text(2) == 'Unverified' for i in range(parent.childCount())))
        self.assertFalse((directory / 'called').exists())

    def test_changed_or_malformed_wav_loses_readiness_before_export(self):
        source = self.wav(self.root / 'changed.wav')
        directory = self.root / 'changed_stemlab' / 'balanced'
        directory.mkdir(parents=True)
        self.mark_owned(directory, source)
        stems = [self.wav(directory / f'changed_({name})_htdemucs.wav')
                 for name in ('Bass', 'Drums', 'Other', 'Vocals')]
        self.w.add_paths([str(source)])
        self.wait_checks()
        parent = self.w.queue_list.topLevelItem(0)
        self.assertEqual(parent.text(2), 'Verified Existing')
        for payload in (b'not a WAV', b'RIFF\0\0\0\0WAVE', b''):
            stems[0].write_bytes(payload)
            child = parent.child(0)
            with patch.object(self.w.preview_player, 'setSource') as preview, \
                    patch.object(m, 'QDrag') as drag:
                self.w.preview_stem_item(child)
                self.w.queue_list.setCurrentItem(child)
                self.w.queue_list.startDrag(m.Qt.CopyAction)
            preview.assert_not_called()
            drag.assert_not_called()
            self.w.refresh_stem_children(0)
            self.assertTrue(all(parent.child(i).text(2) == 'Unverified'
                                for i in range(parent.childCount())))
            self.wav(stems[0])
            self.w.refresh_stem_children(0)

    def test_preset_change_and_unvalidated_preset_never_mark_ready(self):
        source = self.wav(self.root / 'modes.wav')
        self.w.add_paths([str(source)])
        combo = self.w.queue_list.itemWidget(self.w.queue_list.topLevelItem(0), 1)
        combo.setCurrentIndex(combo.findData('vocals'))
        directory = self.w.stem_output_dir(0)
        directory.mkdir(parents=True)
        self.mark_owned(directory, source, 'vocals')
        self.wav(directory / 'modes_(Vocals)_model.wav')
        self.w.set_batch_label(0, 'COMPLETE — UNVERIFIED')
        parent = self.w.queue_list.topLevelItem(0)
        self.assertEqual(parent.childCount(), 1)
        self.assertEqual(parent.child(0).text(2), 'Unverified')
        self.assertEqual(self.check_state(0), 'UNVERIFIED')
        self.assertEqual(parent.text(2), 'Unverified')
        with patch.object(m, 'QDrag') as drag:
            self.w.queue_list.setCurrentItem(parent.child(0))
            self.w.queue_list.startDrag(m.Qt.CopyAction)
        drag.assert_not_called()
        old_child = parent.child(0)
        combo.setCurrentIndex(combo.findData('balanced'))
        self.assertEqual(parent.childCount(), 0)
        with patch.object(self.w.preview_player, 'setSource') as preview, patch.object(m, 'QDrag') as drag:
            self.w.preview_stem_item(old_child)
            self.w.queue_list.drag_stem(old_child)
        preview.assert_not_called()
        drag.assert_not_called()

    def test_multifile_queue_expansion_and_mixed_statuses(self):
        import wave
        def wav(path):
            with wave.open(str(path), 'wb') as out:
                out.setnchannels(2)
                out.setsampwidth(2)
                out.setframerate(44100)
                out.writeframes(b'\0' * 44100 * 4)
        ready = self.audio('queued.wav')
        verified = self.root / 'verified.wav'
        wav(verified)
        incomplete = self.audio('partial.wav')
        target = self.root / 'verified_stemlab' / 'balanced'
        target.mkdir(parents=True)
        self.mark_owned(target, verified)
        for stem in ('Bass', 'Drums', 'Other', 'Vocals'):
            wav(target / f'verified_({stem})_htdemucs.wav')
        partial_dir = self.root / 'partial_stemlab' / 'balanced'
        partial_dir.mkdir(parents=True)
        self.mark_owned(partial_dir, incomplete)
        (partial_dir / 'partial_(Bass)_htdemucs.wav').write_bytes(b'fixture')
        self.w.add_paths([str(ready), str(verified), str(incomplete)])
        self.wait_checks()
        tree = self.w.queue_list
        self.assertEqual(tree.topLevelItemCount(), 3)
        self.assertEqual([tree.topLevelItem(i).text(2) for i in range(3)],
                         ['Queued', 'Verified Existing', 'Partial / Unknown'])
        parent = tree.topLevelItem(1)
        parent.setExpanded(True)
        app.processEvents()
        self.assertTrue(parent.isExpanded())
        self.assertEqual(parent.childCount(), 4)
        self.assertEqual({parent.child(i).text(0) for i in range(4)},
                         {'Bass', 'Drums', 'Other', 'Vocals'})
        self.assertTrue(all(Path(parent.child(i).data(0, m.Qt.UserRole)).is_file()
                            for i in range(4)))
        self.assertEqual(tree.topLevelItem(0).childCount(), 0)
        self.assertEqual(tree.topLevelItem(2).childCount(), 1)
        self.assertEqual(tree.topLevelItem(1).text(2), 'Verified Existing')

    def test_source_row_exposes_drag_path(self):
        source = self.audio('source.wav')
        self.w.add_paths([str(source)])
        parent = self.w.queue_list.topLevelItem(0)
        self.assertEqual(parent.data(0, m.Qt.UserRole), str(source.resolve()))
        self.assertTrue(source.is_file())
        with patch.object(m, 'QDrag') as drag:
            self.w.queue_list.setCurrentItem(parent)
            self.w.queue_list.startDrag(m.Qt.CopyAction)
        drag.assert_called_once()
        self.assertEqual(drag.return_value.setMimeData.call_args.args[0].urls()[0].toLocalFile(),
                         str(source))

    def test_drum_parts_reimport_requires_all_six_valid_stems(self):
        source = self.wav(self.root / 'drums.wav')
        self.w.add_paths([str(source)])
        combo = self.w.queue_list.itemWidget(self.w.queue_list.topLevelItem(0), 1)
        combo.setCurrentIndex(combo.findData('drum-parts'))
        target = self.w.stem_output_dir(0)
        target.mkdir(parents=True)
        self.mark_owned(target, source, 'drum-parts')
        paths = [self.wav(target / f'drums_({name})_MDX23C-DrumSep-aufr33-jarredou.wav')
                 for name in ('kick', 'snare', 'toms', 'hh', 'ride', 'crash')]
        self.assertEqual(self.check_state(0), 'VERIFIED EXISTING')
        parent = self.w.queue_list.topLevelItem(0)
        self.assertEqual([parent.child(i).text(2) for i in range(6)], ['Ready'] * 6)
        paths[0].write_bytes(b'broken')
        self.assertEqual(self.check_state(0), 'PARTIAL / UNKNOWN')
        self.assertTrue(all(parent.child(i).text(2) == 'Unverified' for i in range(6)))

    def test_four_stem_rate_matches_backend_output_not_source(self):
        source = self.wav(self.root / 'rate.wav', frames=48000, rate=48000)
        self.w.add_paths([str(source)])
        combo = self.w.queue_list.itemWidget(self.w.queue_list.topLevelItem(0), 1)
        self.w.set_input(str(source))
        for preset, model in m.FOUR_STEM_MODELS.items():
            with self.subTest(preset=preset):
                combo.setCurrentIndex(combo.findData(preset))
                self.w.presets.setCurrentIndex(self.w.presets.findData(preset))
                target = self.w.stem_output_dir(0)
                target.mkdir(parents=True)
                self.mark_owned(target, source, preset)
                paths = [self.wav(target / f'rate_({name})_{model}.wav')
                         for name in ('Bass', 'Drums', 'Other', 'Vocals')]
                self.assertEqual(self.check_state(0), 'VERIFIED EXISTING')
                self.w.current_output = target
                self.assertTrue(self.validate_output())
                self.wav(paths[0], frames=48000, rate=48000)
                self.assertEqual(self.check_state(0), 'PARTIAL / UNKNOWN')
                self.assertFalse(self.validate_output())
                self.assertTrue(all(self.w.queue_list.topLevelItem(0).child(i).text(2) == 'Unverified'
                                    for i in range(4)))

    def test_mono_source_verifies_stereo_four_stems(self):
        source = self.wav(self.root / 'mono.wav', channels=1)
        self.w.add_paths([str(source)])
        for preset in m.FOUR_STEM_PRESETS:
            with self.subTest(preset=preset):
                self.w.set_job_preset(0, preset)
                target = self.w.stem_output_dir(0)
                target.mkdir(parents=True)
                self.mark_owned(target, source, preset)
                paths = self.w.expected_stem_paths(source, preset, target)
                for path in paths.values():
                    self.wav(path)
                self.assertEqual(self.check_state(0), 'VERIFIED EXISTING')
                for channels in (1, 3):
                    self.wav(paths['Bass'], channels=channels)
                    self.assertEqual(self.check_state(0), 'PARTIAL / UNKNOWN')

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
        self.assertTrue(self.validate_output())
        kick = target / 'drums_(kick)_MDX23C-DrumSep-aufr33-jarredou.wav'
        kick.unlink()
        self.assertFalse(self.validate_output())
        wav(kick)
        original = self.w.probe_audio
        with patch.object(self.w, 'probe_audio') as probe:
            def wrong_rate(path):
                info = original(path)
                if Path(path) == kick:
                    info['rate'] = 48000
                return info
            probe.side_effect = wrong_rate
            self.assertFalse(self.validate_output())
        with patch.object(self.w, 'probe_audio') as probe:
            def wrong_codec(path):
                info = original(path)
                if Path(path) == kick:
                    info['codec'] = 'mp3'
                return info
            probe.side_effect = wrong_codec
            self.assertFalse(self.validate_output())

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
            self.assertIn('QDialog#appearanceDialog', app.styleSheet())
            self.assertIn('QDialog#appearanceDialog QComboBox', app.styleSheet())
            after = self.w.queue_list.topLevelItem(0).foreground(2).color().name()
            self.assertNotEqual(before, after)
            self.w.apply_theme('Not A Theme')
            self.assertEqual(self.w.theme_name, 'Analog Orange')
        finally:
            self.w.apply_theme(previous if previous in m.THEMES else 'Saigon Mint')
            self.w.settings.setValue('appearance/theme', previous)

    def test_queue_chevrons_are_visible_in_both_states_for_all_themes(self):
        source = self.wav(self.root / 'chevrons.wav')
        directory = self.w.default_output_dir(source, 'balanced')
        directory.mkdir(parents=True)
        self.mark_owned(directory, source)
        for stem in ('Bass', 'Drums', 'Other', 'Vocals'):
            self.wav(directory / f'chevrons_({stem})_htdemucs.wav')
        self.w.add_paths([str(source), str(self.audio('no-stems.wav'))])
        self.wait_checks()
        self.w.show()
        tree = self.w.queue_list
        parent = tree.topLevelItem(0)
        empty = tree.topLevelItem(1)
        self.assertEqual(tree.indentation(), 22)
        self.assertEqual(parent.childCount(), 4)
        self.assertEqual(parent.childIndicatorPolicy(), m.QTreeWidgetItem.DontShowIndicatorWhenChildless)
        self.assertEqual(empty.childIndicatorPolicy(), m.QTreeWidgetItem.DontShowIndicatorWhenChildless)
        old_style = app.styleSheet()
        try:
            for theme in m.THEMES:
                with self.subTest(theme=theme):
                    app.setStyleSheet(m.theme_stylesheet(theme))
                    masks = []
                    for expanded in (False, True):
                        parent.setExpanded(expanded)
                        app.processEvents()
                        image = tree.viewport().grab().toImage()
                        center_y = tree.visualItemRect(parent).center().y()
                        mask = {(x, y - center_y) for y in range(center_y - 8, center_y + 9)
                                for x in range(3, tree.indentation())
                                if max(image.pixelColor(x, y).red(), image.pixelColor(x, y).green(),
                                       image.pixelColor(x, y).blue()) > 180}
                        self.assertGreater(len(mask), 8)
                        masks.append(mask)
                    self.assertNotEqual(masks[0], masks[1])
                    self.assertEqual([parent.child(i).text(2) for i in range(4)], ['Ready'] * 4)
            parent.setExpanded(False)
            app.processEvents()
            image = tree.viewport().grab().toImage()
            center_y = tree.visualItemRect(empty).center().y()
            bright = sum(max(image.pixelColor(x, y).red(), image.pixelColor(x, y).green(),
                             image.pixelColor(x, y).blue()) > 180
                         for y in range(center_y - 8, center_y + 9)
                         for x in range(3, tree.indentation()))
            self.assertLess(bright, 5)  # No chevron when there are no stem files.
            tree.setCurrentItem(parent)
            parent.setExpanded(False)
            parent.setExpanded(True)
            self.assertIs(tree.currentItem(), parent)
        finally:
            app.setStyleSheet(old_style)

    def test_source_rows_are_distinct_and_stems_compact_in_all_themes(self):
        source = self.wav(self.root / 'hierarchy.wav')
        directory = self.w.default_output_dir(source, 'balanced')
        directory.mkdir(parents=True)
        self.mark_owned(directory, source)
        for stem in ('Bass', 'Drums', 'Other', 'Vocals'):
            self.wav(directory / f'hierarchy_({stem})_htdemucs.wav')
        self.w.add_paths([str(source)])
        self.wait_checks()
        self.w.show()
        tree = self.w.queue_list
        parent = tree.topLevelItem(0)
        parent.setExpanded(True)
        old_style, old_theme = app.styleSheet(), self.w.theme_name
        try:
            with patch.object(self.w.settings, 'setValue'):
                for theme in m.THEMES:
                    with self.subTest(theme=theme):
                        self.w.apply_theme(theme)
                        app.processEvents()
                        child = parent.child(0)
                        self.assertGreater(parent.font(0).weight(), child.font(0).weight())
                        self.assertLess(tree.visualItemRect(child).height(),
                                        tree.visualItemRect(parent).height())
                        self.assertEqual(parent.childCount(), 4)
                        image = tree.viewport().grab().toImage()
                        source_color = image.pixelColor(400, tree.visualItemRect(parent).center().y())
                        child_color = image.pixelColor(400, tree.visualItemRect(child).center().y())
                        self.assertNotEqual(source_color.name(), child_color.name())
                        self.assertEqual(image.pixelColor(0, tree.visualItemRect(parent).center().y()).name(),
                                         m.THEMES[theme][3])
                        self.assertEqual(tree.progress_color.name(), m.THEMES[theme][3])
                        self.w.set_batch_label(0, 'PROCESSING')
                        app.processEvents()
                        image = tree.viewport().grab().toImage()
                        file_rect = tree.visualRect(tree.model().index(0, 0))
                        self.assertEqual(image.pixelColor(file_rect.left() + 10, file_rect.bottom() - 1).name(),
                                         m.THEMES[theme][3])
                        self.w.set_batch_label(0, 'VERIFIED EXISTING')
                        self.assertFalse(tree.progress_timer.isActive())
        finally:
            self.w.theme_name = old_theme
            app.setStyleSheet(old_style)

    def test_source_progress_is_indeterminate_and_event_loop_stays_responsive(self):
        self.backend.write_text(self.backend.read_text() +
                                '\nprint("50%|###| 2/4", flush=True)\nimport time\ntime.sleep(0.45)\n')
        source = self.audio('progress.wav')
        self.w.add_paths([str(source)])
        self.wait_checks()
        parent = self.w.queue_list.topLevelItem(0)
        tree = self.w.queue_list
        self.assertEqual(parent.childCount(), 0)
        self.assertEqual(parent.childIndicatorPolicy(), m.QTreeWidgetItem.DontShowIndicatorWhenChildless)
        self.assertFalse(tree.progress_timer.isActive())
        self.w.start_batch()
        deadline = time.monotonic() + 2
        while (self.w.stage_label.text() != 'MODEL STEP 2/4'
               and time.monotonic() < deadline):
            app.processEvents(); time.sleep(.005)
        self.assertEqual(self.w.stage_label.text(), 'MODEL STEP 2/4')
        self.assertEqual((self.w.progress.value(), self.w.progress.maximum()), (2, 4))
        self.assertEqual(parent.data(2, m.Qt.UserRole), 'PROCESSING')
        self.assertTrue(tree.progress_timer.isActive())
        ticks = []
        m.QTimer.singleShot(20, lambda: ticks.append(tree._progress_offset))
        deadline = time.monotonic() + 1
        while not ticks and time.monotonic() < deadline:
            app.processEvents(); time.sleep(.005)
        self.assertTrue(ticks)
        self.assertGreaterEqual(ticks[0], 80)
        self.wait_done()
        self.assertFalse(tree.progress_timer.isActive())
        self.assertEqual(parent.childCount(), 0)

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
        self.w.start_batch()
        self.assertFalse(self.w.input_browse.isEnabled())
        self.assertFalse(self.w.output_browse.isEnabled())
        self.w.set_input(str(b))
        self.wait_done()
        self.assertEqual((self.root/'a_stemlab/balanced/called').read_text(),'balanced')
        self.assertEqual((self.root/'b_stemlab/vocals/called').read_text(),'vocals')
        self.assertEqual(self.w.queue_list.topLevelItem(0).text(2),'Check Output')
        self.assertEqual(self.w.queue_list.topLevelItem(1).text(2),'Unverified')
        self.assertIn('a.wav',self.w.log.toPlainText())
        self.assertIn('b.wav',self.w.log.toPlainText())

    def test_same_basename_files_run_to_distinct_destinations(self):
        wav = self.root / 'song.wav'
        mp3 = self.root / 'song.mp3'
        with wave.open(str(wav), 'wb') as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(44100)
            out.writeframes(b'\0\0' * 44100)
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        'sine=frequency=440:duration=1', str(mp3)], check=True)
        self.assertNotEqual(self.w.probe_audio(wav)['codec'], self.w.probe_audio(mp3)['codec'])
        self.w.add_paths([str(wav), str(mp3)])
        self.assertNotEqual(self.w.stem_output_dir(0), self.w.stem_output_dir(1))
        self.w.start_batch()
        self.wait_done()
        self.assertEqual((self.w.stem_output_dir(0) / 'called').read_text(), 'balanced')
        self.assertEqual((self.w.stem_output_dir(1) / 'called').read_text(), 'balanced')
        self.assertEqual([call[1] for call in self.backend_calls()], [str(wav), str(mp3)])

    def test_uppercase_wav_has_its_own_destination(self):
        paths = [self.audio(name) for name in
                 ('song.wav', 'song.mp3', 'song.WAV', 'song.MP3', 'SONG.wav', 'SONG.mp3')]
        self.w.add_paths([str(path) for path in paths])
        self.assertEqual(len({self.w.stem_output_dir(i).resolve() for i in range(len(paths))}), len(paths))
        self.w.start_batch()
        self.wait_done()
        self.assertEqual([call[1] for call in self.backend_calls()], [str(path) for path in paths])

    def test_manual_start_refuses_existing_audio(self):
        source = self.audio('manual.wav')
        destination = self.root / 'manual-output'
        destination.mkdir()
        existing = destination / 'Vocals.wav'
        existing.write_bytes(b'preserve')
        self.w.set_input(str(source))
        self.w.output.setText(str(destination))
        self.w.start()
        self.assertIsNone(self.w.process)
        self.assertEqual(existing.read_bytes(), b'preserve')

    def test_custom_output_reimport_and_preset_require_matching_owner(self):
        first = self.audio('first.wav')
        second = self.audio('second.wav')
        destination = self.root / 'shared-output'
        self.w.add_paths([str(first)])
        self.w.output_user_set = True
        self.w.output.setText(str(destination))
        self.w.start_batch()
        self.wait_done()
        self.assertEqual(len(self.backend_calls()), 1)
        self.assertEqual((destination / m.OWNER_FILE).is_file(), True)
        self.assertEqual(self.w.inspect_existing_output(0), 'PARTIAL / UNKNOWN')
        self.w.start_batch()
        self.wait_done()
        self.assertEqual(len(self.backend_calls()), 1)
        combo = self.w.queue_list.itemWidget(self.w.queue_list.topLevelItem(0), 1)
        combo.setCurrentIndex(combo.findData('vocals'))
        self.assertEqual(self.w.inspect_existing_output(0), 'SOURCE CONFLICT')
        self.w.clear_batch()
        self.w.add_paths([str(second)])
        self.w.output_user_set = True
        self.w.output.setText(str(destination))
        self.w.start_batch()
        self.wait_done()
        self.assertEqual(self.w.queue_list.topLevelItem(0).text(2), 'Source Conflict')
        self.assertIn('move it aside before retrying', self.w.log.toPlainText())
        self.assertEqual(len(self.backend_calls()), 1)
        self.assertEqual((destination / 'called').read_text(), 'balanced')

    def test_unmarked_legacy_stems_are_preserved_without_claiming_source(self):
        source = self.audio('song.wav')
        old_source = self.audio('song.mp3')
        directory = self.root / 'song_stemlab' / 'balanced'
        directory.mkdir(parents=True)
        stems = [directory / f'song_({stem})_htdemucs.wav'
                 for stem in ('Bass', 'Drums', 'Other', 'Vocals')]
        for stem in stems:
            stem.write_bytes(b'old mp3 result')
        self.w.add_paths([str(source), str(old_source)])
        self.wait_checks()
        self.assertEqual(self.w.inspect_existing_output(0), 'SOURCE CONFLICT')
        self.assertEqual(self.w.queue_list.topLevelItem(0).childCount(), 0)
        self.assertEqual(self.w.inspect_existing_output(1), 'READY')
        self.w.start_batch()
        self.wait_done()
        self.assertEqual([call[1] for call in self.backend_calls()], [str(old_source)])
        self.assertTrue(all(stem.read_bytes() == b'old mp3 result' for stem in stems))

    def test_owned_empty_output_is_ready_then_partial_when_files_appear(self):
        source = self.audio('song.wav')
        self.w.add_paths([str(source)])
        directory = self.w.stem_output_dir(0)
        directory.mkdir(parents=True)
        self.mark_owned(directory, source)
        self.assertEqual(self.w.inspect_existing_output(0), 'READY')
        (directory / 'incomplete.wav').write_bytes(b'partial')
        self.assertEqual(self.w.inspect_existing_output(0), 'PARTIAL / UNKNOWN')

    def test_duplicate_destination_preflight_blocks_queue(self):
        first = self.audio('first.wav')
        second = self.audio('second.wav')
        self.w.add_paths([str(first), str(second)])
        shared = self.root / 'shared'
        with patch.object(self.w, 'stem_output_dir', return_value=shared), \
                patch.object(m.QMessageBox, 'warning') as warning:
            self.w.start_batch()
        self.assertFalse(self.w.batch_active)
        self.assertEqual(len(self.backend_calls()), 0)
        self.assertFalse(shared.exists())
        self.assertEqual(warning.call_count, 1)
        self.assertIn('Rename one source', warning.call_args.args[2])

    def test_multiple_queue_entries_ignore_single_custom_output(self):
        first = self.audio('first.wav')
        second = self.audio('second.wav')
        destination = self.root / 'custom'
        self.w.add_paths([str(first), str(second)])
        self.w.output_user_set = True
        self.w.output.setText(str(destination))
        self.w.start_batch()
        self.wait_done()
        self.assertEqual(len(self.backend_calls()), 2)
        self.assertFalse(destination.exists())
        self.assertEqual({Path(call[2]) for call in self.backend_calls()},
                         {self.w.default_output_dir(first, 'balanced'),
                          self.w.default_output_dir(second, 'balanced')})

    def test_folder_import_preserves_source_identity(self):
        self.audio('song.wav')
        self.audio('song.mp3')
        self.w.add_paths([str(self.root)])
        self.assertEqual({path.name for path in self.w.batch_paths}, {'song.wav', 'song.mp3'})
        self.assertEqual(len({self.w.stem_output_dir(i) for i in range(2)}), 2)
        self.w.start_batch()
        self.wait_done()
        self.assertTrue(all((self.w.stem_output_dir(i) / 'called').is_file() for i in range(2)))
        self.assertEqual(len(self.backend_calls()), 2)

    def test_reimport_and_preset_change_use_matching_source_output(self):
        wav = self.audio('song.wav')
        mp3 = self.audio('song.mp3')
        self.w.add_paths([str(wav), str(mp3)])
        wav_index = self.w.batch_paths.index(wav.resolve())
        mp3_index = self.w.batch_paths.index(mp3.resolve())
        wav_dir = self.w.stem_output_dir(wav_index)
        wav_dir.mkdir(parents=True)
        (wav_dir / 'original.wav').write_bytes(b'preserve')
        self.assertEqual(self.w.inspect_existing_output(wav_index), 'SOURCE CONFLICT')
        self.assertEqual(self.w.inspect_existing_output(mp3_index), 'READY')
        mp3_combo = self.w.queue_list.itemWidget(self.w.queue_list.topLevelItem(mp3_index), 1)
        mp3_combo.setCurrentIndex(mp3_combo.findData('vocals'))
        self.assertEqual(self.w.inspect_existing_output(mp3_index), 'READY')
        self.assertNotEqual(self.w.stem_output_dir(wav_index), self.w.stem_output_dir(mp3_index))
        self.w.start_batch()
        self.wait_done()
        self.assertEqual((wav_dir / 'original.wav').read_bytes(), b'preserve')
        self.assertFalse((wav_dir / 'called').exists())
        self.assertEqual((self.w.stem_output_dir(mp3_index) / 'called').read_text(), 'vocals')
        self.assertEqual([call[1] for call in self.backend_calls()], [str(mp3)])
        self.w.clear_batch()
        self.w.add_paths([str(mp3), str(wav), str(mp3)])
        self.assertEqual(len(self.w.batch_paths), 2)
        self.assertEqual(self.w.inspect_existing_output(0), 'READY')
        self.assertEqual(self.w.inspect_existing_output(1), 'SOURCE CONFLICT')
        self.w.queue_list.itemWidget(self.w.queue_list.topLevelItem(0), 1).setCurrentIndex(
            self.w.queue_list.itemWidget(self.w.queue_list.topLevelItem(0), 1).findData('vocals'))
        self.assertEqual(self.w.inspect_existing_output(0), 'PARTIAL / UNKNOWN')

    def test_folder_duplicate_and_skip(self):
        a=self.audio('a.WAV'); self.audio('ignore.txt')
        (self.root/'nested').mkdir(); (self.root/'nested/x.wav').touch()
        (self.root/'alias.wav').symlink_to(a)
        self.w.add_paths([str(self.root),str(a)])
        self.assertEqual(self.w.batch_paths,[a.resolve()])
        target=self.w.stem_output_dir(0);target.parent.mkdir(parents=True);target.write_text('preserve')
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
        self.backend.write_text('#!/usr/bin/env python3\nimport sys,wave\nfrom pathlib import Path\np=Path(sys.argv[3]);p.mkdir(parents=True,exist_ok=True)\nwith wave.open(str(p/(Path(sys.argv[2]).stem+"_(Bass)_htdemucs.wav")),"wb") as out:\n out.setnchannels(2);out.setsampwidth(2);out.setframerate(44100);out.writeframes(b"\\0"*44100*4)\nsys.exit(7)\n')
        self.w.add_paths([str(self.audio('a.wav')),str(self.audio('b.wav'))])
        self.w.start_batch();self.wait_done()
        self.assertFalse(self.w.queue_list.progress_timer.isActive())
        self.assertEqual([self.w.queue_list.topLevelItem(i).text(2) for i in range(2)],['Failed','Failed'])
        for i in range(2):
            parent = self.w.queue_list.topLevelItem(i)
            self.assertEqual(parent.childCount(), 1)
            self.assertEqual(parent.child(0).text(2), 'Unverified')
            with patch.object(m, 'QDrag') as drag:
                self.w.queue_list.setCurrentItem(parent.child(0))
                self.w.queue_list.startDrag(m.Qt.CopyAction)
            drag.assert_not_called()

    def test_failed_partial_job_preserved_while_next_job_verifies_and_rerun_skips(self):
        failed = self.wav(self.root / 'failed.wav')
        following = self.wav(self.root / 'following.wav')
        self.backend.write_text('''#!/usr/bin/env python3
import sys, wave
from pathlib import Path
source, directory = Path(sys.argv[2]), Path(sys.argv[3])
with Path(__file__).with_name("backend_calls").open("a") as log:
    log.write("\\t".join(sys.argv[1:4]) + "\\n")
if source.name == "failed.wav":
    (directory / "failed_(Bass)_htdemucs.wav").write_bytes(b"partial fixture")
    sys.exit(7)
for name in ("Bass", "Drums", "Other", "Vocals"):
    with wave.open(str(directory / f"{source.stem}_({name})_htdemucs.wav"), "wb") as out:
        out.setnchannels(2); out.setsampwidth(2); out.setframerate(44100)
        out.writeframes(b"\\0" * 44100 * 4)
''')
        self.w.add_paths([str(failed), str(following)])
        self.w.start_batch()
        self.wait_done()
        self.assertEqual([item.text(2) for item in
                          (self.w.queue_list.topLevelItem(0), self.w.queue_list.topLevelItem(1))],
                         ['Failed', 'Verified'])
        partial = self.w.stem_output_dir(0) / 'failed_(Bass)_htdemucs.wav'
        self.assertEqual(partial.read_bytes(), b'partial fixture')
        self.assertEqual(len(self.backend_calls()), 2)

        self.w.start_batch()
        self.wait_done()
        self.assertEqual(len(self.backend_calls()), 2)
        self.assertEqual(partial.read_bytes(), b'partial fixture')
        self.assertEqual(self.w.queue_list.topLevelItem(0).text(2), 'Partial / Unknown')
        self.assertEqual(self.w.queue_list.topLevelItem(1).text(2), 'Verified Existing')
        self.assertIn('existing output was not changed', self.w.log.toPlainText())

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
        self.backend.write_text('#!/usr/bin/env python3\nimport signal,time,sys,wave\nfrom pathlib import Path\np=Path(sys.argv[3]);p.mkdir(parents=True,exist_ok=True)\nwith wave.open(str(p/"a_(Bass)_htdemucs.wav"),"wb") as out:\n out.setnchannels(2);out.setsampwidth(2);out.setframerate(44100);out.writeframes(b"\\0"*44100*4)\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\nprint("ready",flush=True)\ntime.sleep(30)\n')
        self.w.add_paths([str(self.audio('a.wav')),str(self.audio('b.wav'))])
        self.w.start_batch()
        end=time.monotonic()+3
        while 'ready' not in self.w.log.toPlainText() and time.monotonic()<end:
            app.processEvents();time.sleep(.005)
        self.assertIn('ready',self.w.log.toPlainText())
        self.assertTrue(self.w.queue_list.progress_timer.isActive())
        self.w.cancel();self.wait_done()
        self.assertFalse(self.w.queue_list.progress_timer.isActive())
        self.assertEqual(self.w.queue_list.topLevelItem(0).text(2),'Cancelled')
        self.assertEqual(self.w.queue_list.topLevelItem(0).childCount(), 1)
        self.assertEqual(self.w.queue_list.topLevelItem(0).child(0).text(2), 'Unverified')
        with patch.object(m, 'QDrag') as drag:
            self.w.queue_list.setCurrentItem(self.w.queue_list.topLevelItem(0).child(0))
            self.w.queue_list.startDrag(m.Qt.CopyAction)
        drag.assert_not_called()
        self.assertFalse((self.root/'b_stemlab').exists())
    def test_validation_rejects_missing_output(self):
        self.w.set_input(str(self.audio('a.wav')))
        self.w.current_output=self.root
        self.assertFalse(self.validate_output())
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
        self.assertTrue(self.validate_output())
        wav(self.root/'valid_(Bass)_htdemucs.wav', frames=100)
        self.assertFalse(self.validate_output())

    def test_close_running(self):
        self.backend.write_text('#!/bin/sh\nexec sleep 30\n')
        self.w.add_paths([str(self.audio('a.wav')),str(self.audio('b.wav'))]);self.w.start_batch()
        while self.w.process is None: app.processEvents()
        with patch.object(m.QMessageBox,'question',return_value=m.QMessageBox.Yes):
            self.w.close()
        self.assertIsNone(self.w.process)
        self.assertFalse(self.w.batch_active)

if __name__=='__main__': unittest.main()
