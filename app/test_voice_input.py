import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from PySide6.QtCore import QObject, QSettings
from PySide6.QtWidgets import QApplication
from voice_input import (DEFAULT_WAKE_WORDS, VoiceController, VoiceWorker, is_cancel_phrase,
    keyword_pronunciation, parse_wake_words, write_keywords)
from voice_models import missing_models, model_paths


class VoiceInputTests(unittest.TestCase):
    def test_default_wake_words_include_chinese_and_english_aliases(self):
        self.assertEqual(parse_wake_words(DEFAULT_WAKE_WORDS), ['没药', 'Kimi', 'Kimi娘'])
        self.assertEqual(parse_wake_words('没药，Kimi，没药'), ['没药', 'Kimi'])

    def test_wake_word_validation(self):
        for value in ('', 'hello world', 'bad@word', 'bad:word'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_wake_words(value)

    def test_polyphonic_name_has_explicit_fourth_tone(self):
        self.assertEqual(keyword_pronunciation('没药', None), 'm ò y ào')
        self.assertEqual(keyword_pronunciation('Kimi', None), 'K IH1 M IY0')
        self.assertEqual(keyword_pronunciation('Kimi娘', None), 'K IH1 M IY0 n iáng')

    def test_keywords_file_preserves_display_names_and_pronunciation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'keywords.txt'
            write_keywords(path, DEFAULT_WAKE_WORDS, Path(folder) / 'unused.phone')
            lines = path.read_text(encoding='utf-8').splitlines()
            self.assertEqual(lines[0], 'm ò y ào :1.0 #0.25 @没药')
            self.assertEqual(lines[1], 'K IH1 M IY0 :1.0 #0.25 @Kimi')
            self.assertEqual(lines[2], 'K IH1 M IY0 n iáng :1.0 #0.25 @Kimi娘')

    def test_other_chinese_names_are_convertible(self):
        pronunciation = keyword_pronunciation('小药', None)
        self.assertEqual(pronunciation, 'x iǎo y ào')

    def test_cancel_phrases_ignore_punctuation(self):
        self.assertTrue(is_cancel_phrase('没事了。'))
        self.assertTrue(is_cancel_phrase('退下吧！'))
        self.assertFalse(is_cancel_phrase('取消这个任务需要什么命令'))

    def test_model_check_is_external_and_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = model_paths(folder)
            self.assertEqual(len(missing_models(folder)), len(paths))
            for path in paths.values():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'model')
            self.assertEqual(missing_models(folder), [])


app = QApplication.instance() or QApplication([])


class FollowupTests(unittest.TestCase):
    def test_followup_request_replaces_pause_and_can_be_cancelled(self):
        worker = VoiceWorker(DEFAULT_WAKE_WORDS)
        worker.set_paused(True)
        self.assertTrue(worker.paused.is_set())
        worker.start_followup(20)
        self.assertFalse(worker.paused.is_set())
        self.assertTrue(worker.followup_request.is_set())
        worker.set_paused(True)
        self.assertFalse(worker.followup_request.is_set())

    def test_controller_uses_configured_followup_timeout(self):
        with tempfile.TemporaryDirectory() as folder:
            pet = QObject()
            pet.settings = QSettings(str(Path(folder) / 'voice.ini'), QSettings.Format.IniFormat)
            pet.settings.setValue('voiceFollowup', True)
            pet.settings.setValue('voiceFollowupSeconds', 25)
            controller = VoiceController(pet)
            controller.worker = Mock()
            controller.worker.isRunning.return_value = True
            controller.begin_followup()
            controller.worker.start_followup.assert_called_once_with(25)

    def test_disabled_followup_returns_to_wake_word_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            pet = QObject()
            pet.settings = QSettings(str(Path(folder) / 'voice.ini'), QSettings.Format.IniFormat)
            pet.settings.setValue('voiceFollowup', False)
            controller = VoiceController(pet)
            controller.worker = Mock()
            controller.worker.isRunning.return_value = True
            controller.begin_followup()
            controller.worker.start_followup.assert_not_called()
            controller.worker.set_paused.assert_called_with(False)


if __name__ == '__main__':
    unittest.main()
