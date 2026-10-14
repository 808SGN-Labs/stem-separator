#!/usr/bin/env python3
"""Isolated regression tests for the source-checkout desktop installer."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-desktop.sh"


class DesktopInstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.xdg = Path(self.tmp.name) / "data"
        self.entry = self.xdg / "applications" / "808sgn-stemlab.desktop"
        self.env = dict(os.environ, XDG_DATA_HOME=str(self.xdg))

    def run_installer(self, *args, success=True):
        result = subprocess.run(
            ["bash", str(INSTALLER), *args], env=self.env,
            capture_output=True, text=True, timeout=10, check=False,
        )
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return result

    def test_install_is_idempotent_and_remove_is_safe(self):
        self.run_installer()
        entry = self.entry.read_text()
        self.assertIn("[Desktop Entry]", entry)
        self.assertIn("Terminal=false", entry)
        self.assertIn("Name=808SGN StemLab", entry)
        self.assertIn(str(ROOT / "scripts" / "stemlab-gui"), entry)
        self.run_installer()
        self.assertEqual(entry, self.entry.read_text())
        self.run_installer("--remove")
        self.assertFalse(self.entry.exists())
        self.run_installer("--remove")

    def test_refuses_foreign_entry_and_symlink(self):
        self.entry.parent.mkdir(parents=True)
        self.entry.write_text("[Desktop Entry]\nName=Foreign Application\n")
        self.run_installer(success=False)
        self.assertIn("Foreign Application", self.entry.read_text())
        self.run_installer("--remove")
        self.assertTrue(self.entry.exists())
        self.entry.unlink()
        target = Path(self.tmp.name) / "other.desktop"
        target.write_text("[Desktop Entry]\nName=Other\n")
        self.entry.symlink_to(target)
        self.run_installer(success=False)
        self.run_installer("--remove", success=False)
        self.assertEqual(target.read_text(), "[Desktop Entry]\nName=Other\n")


if __name__ == "__main__":
    unittest.main()
