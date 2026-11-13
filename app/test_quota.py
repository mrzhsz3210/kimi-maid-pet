import unittest
from unittest.mock import patch
import quota


class Tests(unittest.TestCase):
    def test_windows_from_cli_status(self):
        windows = quota.quota_windows({'version': '2.5.2', 'loggedIn': True})
        self.assertEqual(len(windows), 1)
        self.assertIn('Kimi Code CLI', windows[0]['name'])
        self.assertIsNone(windows[0]['remaining'])
        self.assertIsNone(windows[0]['resetsAt'])

    def test_missing_cli_raises(self):
        with patch('quota.shutil.which', return_value=None), \
             patch('quota.Path.is_file', return_value=False):
            with self.assertRaises(RuntimeError):
                quota.find_kimi()

    def test_env_override_wins(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as folder:
            fake = quota.Path(folder) / 'kimi.exe'
            fake.write_text('x')
            with patch.dict(os.environ, {'MAID_KIMI': str(fake)}):
                self.assertEqual(quota.find_kimi(), str(fake))


if __name__ == '__main__':
    unittest.main()
