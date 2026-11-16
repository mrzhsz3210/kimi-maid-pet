import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from desktop_actions import DesktopActions, ReminderService, SETTINGS_PAGES

app = QApplication.instance() or QApplication([])


class FakePet(QObject):
    def __init__(self):
        super().__init__()
        self.pet_name = '没药'
        self.voice = Mock()
        self.messages = []
        self.play_click_sound = Mock()
        self.hidden = False

    def say(self, text, ms=4000):
        self.messages.append(text)

    def set_manual_hidden(self, value):
        self.hidden = value


class DesktopActionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.pet = FakePet()
        self.actions = DesktopActions(self.pet, root / 'actions.json', root / 'reminders.json')

    def tearDown(self):
        self.actions.shutdown()
        self.temp.cleanup()

    def test_only_registered_applications_are_launched(self):
        with patch('desktop_actions.subprocess.Popen') as launch:
            result = self.actions.match('没药，打开记事本')
            self.assertTrue(result[0])
            launch.assert_called_once_with(['notepad.exe'], shell=False)
        with patch('desktop_actions.subprocess.Popen') as launch:
            result = self.actions.match('打开一个陌生程序')
            self.assertFalse(result[0])
            launch.assert_not_called()

    def test_browser_search_uses_configured_engine(self):
        with patch('desktop_actions.webbrowser.open', return_value=True) as opened:
            result = self.actions.match('用浏览器搜索北京天气')
            self.assertTrue(result[0])
            url = opened.call_args.args[0]
            self.assertTrue(url.startswith('https://www.bing.com/search?q='))
            self.assertIn('%E5%8C%97%E4%BA%AC', url)

    def test_url_protocol_and_credentials_are_validated(self):
        with patch('desktop_actions.webbrowser.open', return_value=True) as opened:
            self.assertTrue(self.actions.match('打开 https://example.com')[0])
            opened.assert_called_once()
        for url in ('file:///C:/Windows/System32/cmd.exe', 'https://user:pass@example.com'):
            with patch('desktop_actions.webbrowser.open') as opened:
                self.assertFalse(self.actions.open_url(url)[0])
                opened.assert_not_called()

    def test_settings_pages_are_allow_listed(self):
        with patch('desktop_actions.os.startfile') as opened:
            result = self.actions.match('打开飞行模式')
            self.assertTrue(result[0])
            opened.assert_called_once_with(SETTINGS_PAGES['飞行模式'])

    def test_volume_scalar_and_mute(self):
        endpoint = Mock()
        endpoint.GetMasterVolumeLevelScalar.return_value = 0.4
        with patch.object(self.actions, 'endpoint_volume', return_value=endpoint):
            self.assertEqual(self.actions.get_volume(), 40)
            self.assertTrue(self.actions.set_volume(35)[0])
            endpoint.SetMasterVolumeLevelScalar.assert_called_once_with(0.35, None)
            self.assertTrue(self.actions.mute_volume(True)[0])
            endpoint.SetMute.assert_called_once_with(True, None)

    def test_relative_reminder_is_persisted(self):
        result = self.actions.match('1分钟后提醒我喝水')
        self.assertTrue(result[0])
        items = self.actions.reminders.sorted_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['text'], '喝水')
        service = ReminderService(self.pet, self.actions.reminders.path)
        self.assertEqual(len(service.sorted_items()), 1)
        self.assertEqual(service.sorted_items()[0]['text'], '喝水')
        service.shutdown()

    def test_reminder_fires_and_is_removed(self):
        self.actions.reminders.add(1, '活动一下')
        QTest.qWait(1250)
        self.assertTrue(any('活动一下' in message for message in self.pet.messages))
        self.assertEqual(self.actions.reminders.sorted_items(), [])

    def test_local_action_skips_chat_and_keeps_followup(self):
        with patch('desktop_actions.subprocess.Popen'):
            self.assertTrue(self.actions.try_handle('打开记事本'))
        self.pet.voice.begin_followup.assert_called_once()
        self.assertTrue(any('记事本' in message for message in self.pet.messages))
        self.assertFalse(self.actions.try_handle('今天天气怎么样'))


if __name__ == '__main__':
    unittest.main()
