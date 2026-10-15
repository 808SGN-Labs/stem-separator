#!/usr/bin/env python3
"""Offline installer contract tests: no real uv, network, or user data touched."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install.sh"


class InstallPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.bin = base / "bin"
        self.bin.mkdir()
        self.xdg = base / "xdg data"
        self.log = base / "uv-args.txt"
        self.env = dict(os.environ, XDG_DATA_HOME=str(self.xdg),
                        PATH=f"{self.bin}:{os.environ.get('PATH', '')}",
                        STEMLAB_TEST_UV_LOG=str(self.log), CC='cc', CXX='c++', MAKE='make')
        self.env.pop("STEMLAB_TEST_FAIL_PIP", None)
        self.stub("ffmpeg", "#!/bin/sh\nexit 0\n")
        self.stub("ffprobe", "#!/bin/sh\nexit 0\n")
        self.stub("cc", '#!/bin/sh\n[ "${STEMLAB_TEST_FAIL_CC:-}" != 1 ]\n')
        self.stub("c++", '#!/bin/sh\n[ "${STEMLAB_TEST_FAIL_CXX:-}" != 1 ]\n')
        self.stub("make", '#!/bin/sh\nexit 0\n')
        self.stub("uv", '#!/bin/sh\n'
                        '[ -z "${UV_VENV_CLEAR:-}" ] && [ -z "${UV_VENV_FORCE:-}" ] || exit 91\n'
                        'printf "%s\\n" "$*" >> "$STEMLAB_TEST_UV_LOG"\n'
                        'if [ "$1" = venv ]; then\n'
                        '  for target do :; done\n'
                        '  mkdir -p "$target/bin"\n'
                        '  printf "home = fixture\\n" > "$target/pyvenv.cfg"\n'
                        '  cat > "$target/bin/python" <<\'PYTHON\'\n'
                        '#!/bin/sh\n'
                        'case "$*" in\n'
                        '  *Python.h*) [ "${STEMLAB_TEST_MISSING_HEADER:-}" != 1 ] ;;\n'
                        '  *libxcb-cursor.so.0*) [ "${STEMLAB_TEST_MISSING_XCB:-}" != 1 ] ;;\n'
                        '  *) exit 0 ;;\n'
                        'esac\n'
                        'PYTHON\n'
                        '  chmod +x "$target/bin/python"\n'
                        'fi\n'
                        '[ "$1" = pip ] && [ "${STEMLAB_TEST_FAIL_PIP:-}" = 1 ] && exit 53\n'
                        'exit 0\n')

    def stub(self, name, content):
        path = self.bin / name
        path.write_text(content)
        path.chmod(0o755)

    def test_installer_targets_isolated_venv_and_installs_gui(self):
        result = subprocess.run(["bash", str(INSTALLER)], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = self.log.read_text().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], f"venv --no-python-downloads --python 3.12 {self.xdg}/808sgn-stem-lab/.venv")
        self.assertIn("audio-separator[cpu]==0.47.0", lines[1])
        self.assertIn("audioread==3.0.1", lines[1])
        self.assertIn("PySide6==6.11.2", lines[1])
        self.assertIn(str(self.xdg / "808sgn-stem-lab/.venv/bin/python"), lines[1])
        self.assertEqual((self.xdg / "808sgn-stem-lab/.venv/.stemlab-managed").read_text(),
                         "808sgn-stem-lab-venv-v1\n")
        app = self.xdg / "808sgn-stem-lab/app"
        for name in ("gui/producer_qt.py", "scripts/stem-separate",
                     "scripts/stemlab-gui", "scripts/install-desktop.sh", "LICENSE-CODE"):
            self.assertEqual((app / name).read_bytes(), (ROOT / name).read_bytes())
        self.assertTrue((app / "scripts/stemlab-gui").stat().st_mode & 0o111)

    def test_fresh_checkout_installs_relocatable_launcher(self):
        checkout = Path(self.tmp.name) / "fresh checkout"
        for name in ("gui/producer_qt.py", "scripts/install.sh", "scripts/stem-separate",
                     "scripts/stemlab-gui", "scripts/install-desktop.sh", "LICENSE-CODE"):
            dest = checkout / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, dest)
        result = subprocess.run(["bash", str(checkout / "scripts/install.sh")], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        app = self.xdg / "808sgn-stem-lab/app"
        desktop = subprocess.run(["bash", str(checkout / "scripts/install-desktop.sh")],
                                 env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(desktop.returncode, 0, desktop.stderr)
        entry = self.xdg / "applications/808sgn-stemlab.desktop"
        self.assertIn(str(app / "scripts/stemlab-gui"), entry.read_text())
        checkout.rename(Path(self.tmp.name) / "moved checkout")
        python = self.xdg / "808sgn-stem-lab/.venv/bin/python"
        python.parent.mkdir(parents=True, exist_ok=True)
        python.write_text('#!/bin/sh\n[ "$1" = "-c" ] && exit 0\nprintf "%s\\n%s\\n" "$1" "$STEM_LAB_VENV" > "$STEMLAB_TEST_GUI_LOG"\n')
        python.chmod(0o755)
        gui_log = Path(self.tmp.name) / "gui-script.txt"
        env = dict(self.env, STEMLAB_TEST_GUI_LOG=str(gui_log))
        env.pop("XDG_DATA_HOME")  # The installed launcher must find its own venv.
        env.pop("STEM_LAB_VENV", None)
        launch = subprocess.run(["bash", str(app / "scripts/stemlab-gui")], env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(launch.returncode, 0, launch.stderr)
        self.assertEqual(gui_log.read_text().splitlines(),
                         [str(app / "gui/producer_qt.py"), str(app / "../.venv")])
        backend = python.parent / "audio-separator"
        backend.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$STEMLAB_TEST_BACKEND_LOG"\n')
        backend.chmod(0o755)
        input_file = Path(self.tmp.name) / "input.wav"
        input_file.write_bytes(b"offline fixture")
        backend_log = Path(self.tmp.name) / "backend-args.txt"
        wrapper_env = dict(self.env, STEM_LAB_VENV=str(app / "../.venv"),
                           STEM_LAB_MODELS=str(Path(self.tmp.name) / "models"),
                           STEMLAB_TEST_BACKEND_LOG=str(backend_log))
        wrapper = subprocess.run(["bash", str(app / "scripts/stem-separate"),
                                  "balanced", str(input_file), str(Path(self.tmp.name) / "output")],
                                 env=wrapper_env, capture_output=True, text=True, timeout=10)
        self.assertEqual(wrapper.returncode, 0, wrapper.stderr)
        self.assertIn("htdemucs.yaml", backend_log.read_text())
        remove = subprocess.run(["bash", str(app / "scripts/install-desktop.sh"), "--remove"],
                                env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(remove.returncode, 0, remove.stderr)
        self.assertFalse(entry.exists())

    def test_refuses_unowned_app_directory(self):
        app = self.xdg / "808sgn-stem-lab/app"
        app.mkdir(parents=True)
        personal = app / "personal.txt"
        personal.write_text("keep")
        result = subprocess.run(["bash", str(INSTALLER)], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unowned", result.stderr)
        self.assertEqual(personal.read_text(), "keep")
        self.assertFalse(self.log.exists())

    def test_refuses_foreign_marker(self):
        app = self.xdg / "808sgn-stem-lab/app"
        app.mkdir(parents=True)
        (app / ".stemlab-managed").write_text("another application\n")
        result = subprocess.run(["bash", str(INSTALLER)], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unowned", result.stderr)
        self.assertFalse(self.log.exists())

    def test_unmarked_existing_venv_is_rejected_before_uv(self):
        venv = self.xdg / "808sgn-stem-lab/.venv"
        (venv / "bin").mkdir(parents=True)
        (venv / "pyvenv.cfg").write_text("home = unrelated\n")
        (venv / "bin/python").write_text("keep")
        sentinel = venv / "personal.txt"
        sentinel.write_text("keep")
        env = dict(self.env, UV_VENV_CLEAR="1", UV_VENV_FORCE="1")
        result = subprocess.run(["bash", str(INSTALLER)], env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unowned or invalid Python environment", result.stderr)
        self.assertEqual(sentinel.read_text(), "keep")
        self.assertFalse(self.log.exists())

    def test_replaced_or_symlinked_venv_is_not_claimed(self):
        first = subprocess.run(["bash", str(INSTALLER)], env=self.env,
                               capture_output=True, text=True, timeout=10)
        self.assertEqual(first.returncode, 0, first.stderr)
        venv = self.xdg / "808sgn-stem-lab/.venv"
        (venv / ".stemlab-managed").write_text("another environment\n")
        before = self.log.read_text()
        result = subprocess.run(["bash", str(INSTALLER)], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.log.read_text(), before)
        self.assertEqual((venv / ".stemlab-managed").read_text(), "another environment\n")

        foreign = Path(self.tmp.name) / "foreign venv"
        foreign.mkdir()
        (foreign / "personal.txt").write_text("keep")
        venv.rename(Path(self.tmp.name) / "original venv")
        venv.symlink_to(foreign, target_is_directory=True)
        result = subprocess.run(["bash", str(INSTALLER)], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.log.read_text(), before)
        self.assertEqual((foreign / "personal.txt").read_text(), "keep")

    def test_owned_rerun_preserves_venv_with_hostile_uv_environment(self):
        first = subprocess.run(["bash", str(INSTALLER)], env=self.env,
                               capture_output=True, text=True, timeout=10)
        self.assertEqual(first.returncode, 0, first.stderr)
        venv = self.xdg / "808sgn-stem-lab/.venv"
        sentinel = venv / "personal.txt"
        sentinel.write_text("keep")
        env = dict(self.env, UV_VENV_CLEAR="1", UV_VENV_FORCE="1")
        second = subprocess.run(["bash", str(INSTALLER)], env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(sentinel.read_text(), "keep")
        self.assertEqual([line.split()[0] for line in self.log.read_text().splitlines()],
                         ["venv", "pip", "pip"])

    def test_fresh_install_ignores_hostile_uv_environment(self):
        env = dict(self.env, UV_VENV_CLEAR="1", UV_VENV_FORCE="1")
        result = subprocess.run(["bash", str(INSTALLER)], env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.log.read_text().splitlines()), 2)

    def test_failed_dependency_step_can_resume_without_recreating_venv(self):
        failing_env = dict(self.env, STEMLAB_TEST_FAIL_PIP="1")
        first = subprocess.run(["bash", str(INSTALLER)], env=failing_env,
                               capture_output=True, text=True, timeout=10)
        self.assertNotEqual(first.returncode, 0)
        venv = self.xdg / "808sgn-stem-lab/.venv"
        self.assertEqual((venv / ".stemlab-managed").read_text(),
                         "808sgn-stem-lab-venv-v1\n")
        sentinel = venv / "personal.txt"
        sentinel.write_text("keep")
        second = subprocess.run(["bash", str(INSTALLER)], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(sentinel.read_text(), "keep")
        self.assertEqual([line.split()[0] for line in self.log.read_text().splitlines()],
                         ["venv", "pip", "pip"])

    def test_missing_native_build_tool_fails_before_creating_app(self):
        env = dict(self.env, MAKE='stemlab-missing-make')
        result = subprocess.run(["bash", str(INSTALLER)], env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Native build tool missing', result.stderr)
        self.assertIn('build-essential', result.stderr)
        self.assertFalse(self.log.exists())
        self.assertFalse(self.xdg.exists())

    def test_nonworking_c_compiler_fails_before_creating_app(self):
        env = dict(self.env, STEMLAB_TEST_FAIL_CC='1')
        result = subprocess.run(["bash", str(INSTALLER)], env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('C/C++ compiler check failed', result.stderr)
        self.assertFalse(self.log.exists())
        self.assertFalse(self.xdg.exists())

    def test_nonworking_cpp_compiler_fails_before_creating_app(self):
        env = dict(self.env, STEMLAB_TEST_FAIL_CXX='1')
        result = subprocess.run(["bash", str(INSTALLER)], env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('C/C++ compiler check failed', result.stderr)
        self.assertFalse(self.log.exists())
        self.assertFalse(self.xdg.exists())

    def test_missing_python_headers_stops_before_dependency_install(self):
        env = dict(self.env, STEMLAB_TEST_MISSING_HEADER='1')
        result = subprocess.run(["bash", str(INSTALLER)], env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Python.h is missing', result.stderr)
        self.assertIn('python3.12-dev', result.stderr)
        self.assertEqual([line.split()[0] for line in self.log.read_text().splitlines()], ['venv'])
        self.assertFalse((self.xdg / '808sgn-stem-lab/app').exists())

    def test_missing_qt_xcb_library_stops_before_dependency_install(self):
        env = dict(self.env, STEMLAB_TEST_MISSING_XCB='1')
        result = subprocess.run(["bash", str(INSTALLER)], env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('libxcb-cursor.so.0', result.stderr)
        self.assertIn('libxcb-cursor0', result.stderr)
        self.assertEqual([line.split()[0] for line in self.log.read_text().splitlines()], ['venv'])
        self.assertFalse((self.xdg / '808sgn-stem-lab/app').exists())

    def test_failed_header_check_preserves_existing_owned_venv(self):
        first = subprocess.run(["bash", str(INSTALLER)], env=self.env,
                               capture_output=True, text=True, timeout=10)
        self.assertEqual(first.returncode, 0, first.stderr)
        venv = self.xdg / '808sgn-stem-lab/.venv'
        sentinel = venv / 'personal.txt'
        sentinel.write_text('keep')
        env = dict(self.env, STEMLAB_TEST_MISSING_HEADER='1')
        second = subprocess.run(["bash", str(INSTALLER)], env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual(sentinel.read_text(), 'keep')
        self.assertEqual([line.split()[0] for line in self.log.read_text().splitlines()],
                         ['venv', 'pip'])

    def test_missing_ffmpeg_is_reported_without_install(self):
        # Restrict PATH to stubs while still exposing bash itself via absolute path.
        self.bin.joinpath("ffmpeg").unlink()
        self.env["PATH"] = str(self.bin)
        result = subprocess.run(["/bin/bash", str(INSTALLER)], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FFmpeg is required", result.stderr)
        self.assertFalse(self.log.exists())

    def test_missing_ffprobe_is_reported_without_install(self):
        self.bin.joinpath("ffprobe").unlink()
        self.env["PATH"] = str(self.bin)
        result = subprocess.run(["/bin/bash", str(INSTALLER)], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ffprobe is required", result.stderr)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
