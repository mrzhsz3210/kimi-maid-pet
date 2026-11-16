"""Voice preferences and explicit, user-initiated local model downloads."""
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QVBoxLayout)

from voice_input import DEFAULT_WAKE_WORDS, parse_wake_words
from voice_models import install_models, missing_models, model_root


class ModelDownloadWorker(QThread):
    progress = Signal(str)
    ready = Signal()
    failed = Signal(str)

    def run(self):
        try:
            install_models(progress=self.progress.emit)
            self.ready.emit()
        except Exception as error:
            self.failed.emit(str(error))


class VoiceSettingsDialog(QDialog):
    def __init__(self, pet):
        super().__init__(pet, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.pet = pet
        self.setWindowTitle('语音对话设置')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        form = QFormLayout()
        self.name = QLineEdit(pet.settings.value('petName', '没药'))
        self.name.setMaxLength(20)
        form.addRow('她的昵称', self.name)
        self.wake_words = QLineEdit(pet.settings.value('wakeWords', DEFAULT_WAKE_WORDS))
        self.wake_words.setToolTip('多个唤醒词用逗号分隔。没药固定读作 mò yào；Kimi 使用英文发音。')
        form.addRow('唤醒词', self.wake_words)
        self.silence = QDoubleSpinBox()
        self.silence.setRange(0.6, 3.0)
        self.silence.setSingleStep(0.1)
        self.silence.setSuffix(' 秒')
        self.silence.setValue(pet.settings.value('voiceSilence', 1.2, type=float))
        form.addRow('说完后的静音', self.silence)
        self.followup = QCheckBox('回答后允许连续对话，不用重复叫昵称')
        self.followup.setChecked(pet.settings.value('voiceFollowup', True, type=bool))
        form.addRow('', self.followup)
        self.followup_seconds = QSpinBox()
        self.followup_seconds.setRange(5, 120)
        self.followup_seconds.setSuffix(' 秒')
        self.followup_seconds.setValue(pet.settings.value('voiceFollowupSeconds', 20, type=int))
        self.followup_seconds.setEnabled(self.followup.isChecked())
        self.followup.toggled.connect(self.followup_seconds.setEnabled)
        form.addRow('连续对话等待', self.followup_seconds)
        self.enabled = QCheckBox('启用本地语音唤醒')
        self.enabled.setChecked(pet.settings.value('voiceEnabled', False, type=bool))
        form.addRow('', self.enabled)
        layout.addLayout(form)
        privacy = QLabel('唤醒和语音识别均在本机进行，不保存原始录音；识别出的文字会发送给 Kimi。\n语音聊天可自动搜索和读取公开网页，但不会批准文件修改、命令执行或其他工具。')
        privacy.setWordWrap(True)
        layout.addWidget(privacy)
        self.model_status = QLabel()
        self.model_status.setWordWrap(True)
        layout.addWidget(self.model_status)
        row = QHBoxLayout()
        self.download = QPushButton('下载 / 修复本地模型')
        self.download.clicked.connect(self.download_models)
        row.addWidget(self.download)
        row.addStretch(1)
        layout.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.refresh_models()
        self.setMinimumWidth(480)

    def refresh_models(self):
        missing = missing_models()
        if missing:
            self.model_status.setText(f'模型尚未就绪，缺少 {len(missing)} 个文件。\n位置：{model_root()}')
        else:
            self.model_status.setText('本地唤醒、静音检测和中文识别模型已就绪。')

    def download_models(self):
        if hasattr(self, 'downloader') and self.downloader.isRunning():
            return
        self.download.setEnabled(False)
        self.model_status.setText('正在从 sherpa-onnx 官方发布页和作者模型仓库下载模型…')
        self.downloader = ModelDownloadWorker(self)
        self.downloader.progress.connect(self.model_status.setText)
        self.downloader.ready.connect(self.download_finished)
        self.downloader.failed.connect(self.download_failed)
        self.downloader.start()

    def download_finished(self):
        self.download.setEnabled(True)
        self.refresh_models()

    def download_failed(self, error):
        self.download.setEnabled(True)
        self.model_status.setText('模型下载失败：' + error)

    def accept(self):
        name = self.name.text().strip()
        if not name:
            QMessageBox.warning(self, '昵称不能为空', '给她留一个昵称吧。')
            return
        try:
            words = '，'.join(parse_wake_words(self.wake_words.text()))
            self.pet.apply_voice_settings(name, words, self.silence.value(), self.enabled.isChecked(),
                self.followup.isChecked(), self.followup_seconds.value())
        except Exception as error:
            QMessageBox.warning(self, '语音设置未保存', str(error))
            return
        super().accept()
