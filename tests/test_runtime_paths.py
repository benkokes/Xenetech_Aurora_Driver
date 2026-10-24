import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from aurora_jobserver import runtime_paths,startup


class RuntimePathTests(unittest.TestCase):
    def test_source_paths_preserve_current_state_and_shared_guard(self):
        with patch.object(sys,'frozen',False,create=True):
            self.assertEqual(runtime_paths.default_state(),runtime_paths.project_root()/'runtime/desktop-jobserver')
            self.assertEqual(runtime_paths.default_locks(),runtime_paths.project_root()/'runtime/device-locks')

    def test_frozen_resources_and_writable_user_records_are_separate(self):
        with patch.object(sys,'frozen',True,create=True),patch.object(sys,'_MEIPASS',r'C:\Program Files\Aurora\_internal',create=True),patch.dict(os.environ,{'LOCALAPPDATA':r'C:\Users\Example\AppData\Local'}):
            self.assertEqual(runtime_paths.intake_path(),Path(r'C:\Program Files\Aurora\_internal/native/Aurora.XpsIntake.exe'))
            self.assertEqual(runtime_paths.default_state(),Path(r'C:\Users\Example\AppData\Local\AuroraJobServer\state'))
            self.assertNotIn('Program Files',str(runtime_paths.default_locks()))
            with patch.object(sys,'executable',r'C:\Program Files\Aurora\AuroraJobServer.exe'):
                self.assertEqual(startup.command(runtime_paths.default_state()),subprocess.list2cmdline([
                    str(Path(sys.executable).resolve()),'--state',str(runtime_paths.default_state().resolve())]))

    def test_frozen_rejects_relative_state_root(self):
        with patch.object(sys,'frozen',True,create=True),patch.dict(os.environ,{'LOCALAPPDATA':'relative'}):
            with self.assertRaises(ValueError):runtime_paths.default_state()
