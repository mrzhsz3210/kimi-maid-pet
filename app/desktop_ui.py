"""Application aliases, search preferences and local reminders."""
from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout)

from desktop_actions import SEARCH_ENGINES


class DesktopSettingsDialog(QDialog):
    def __init__(self, pet, actions):
        super().__init__(pet, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.actions = actions
        self.setWindowTitle('桌面动作设置')
        self.setMinimumWidth(580)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('语音说“打开记事本”时，只会打开下表中登记过的程序。'))
        self.apps = QTableWidget(0, 2)
        self.apps.setHorizontalHeaderLabels(['程序别名', '程序路径'])
        self.apps.horizontalHeader().setStretchLastSection(True)
        self.apps.setMinimumHeight(150)
        layout.addWidget(self.apps)
        for alias, path in actions.config['applications'].items():
            self.add_app(alias, path)
        row = QHBoxLayout()
        add = QPushButton('添加')
        add.clicked.connect(lambda: self.add_app())
        remove = QPushButton('删除选中')
        remove.clicked.connect(self.remove_app)
        browse = QPushButton('选择程序…')
        browse.clicked.connect(self.browse_app)
        for button in (add, remove, browse):
            row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)
        form = QFormLayout()
        self.engine = QComboBox()
        for key, (name, _) in SEARCH_ENGINES.items():
            self.engine.addItem(name, key)
        self.engine.setCurrentIndex(max(0, self.engine.findData(actions.config.get('searchEngine', 'bing'))))
        form.addRow('浏览器搜索使用', self.engine)
        layout.addLayout(form)
        layout.addWidget(QLabel('没药的提醒（桌宠运行时会到点提醒，重启后仍会保留）：'))
        self.reminders = QListWidget()
        layout.addWidget(self.reminders)
        reminder_form = QHBoxLayout()
        self.reminder_text = QLineEdit()
        self.reminder_text.setPlaceholderText('提醒内容，例如：喝水')
        self.reminder_value = QSpinBox()
        self.reminder_value.setRange(1, 999)
        self.reminder_value.setValue(10)
        self.reminder_unit = QComboBox()
        self.reminder_unit.addItems(['分钟', '小时', '天'])
        add_reminder = QPushButton('添加提醒')
        add_reminder.clicked.connect(self.add_reminder)
        reminder_form.addWidget(self.reminder_text, 1)
        reminder_form.addWidget(self.reminder_value)
        reminder_form.addWidget(self.reminder_unit)
        reminder_form.addWidget(add_reminder)
        layout.addLayout(reminder_form)
        remove_reminder = QPushButton('取消选中的提醒')
        remove_reminder.clicked.connect(self.cancel_reminder)
        layout.addWidget(remove_reminder)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.refresh_reminders()

    def add_app(self, alias='', path=''):
        row = self.apps.rowCount()
        self.apps.insertRow(row)
        self.apps.setItem(row, 0, QTableWidgetItem(alias))
        self.apps.setItem(row, 1, QTableWidgetItem(path))

    def remove_app(self):
        row = self.apps.currentRow()
        if row >= 0:
            self.apps.removeRow(row)

    def browse_app(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择程序', '', 'Windows 程序 (*.exe *.lnk);;所有文件 (*)')
        if not path:
            return
        row = self.apps.currentRow()
        if row < 0:
            self.add_app('', path)
            row = self.apps.rowCount() - 1
        else:
            self.apps.item(row, 1).setText(path)

    def refresh_reminders(self):
        self.reminders.clear()
        for item in self.actions.reminders.sorted_items():
            when = datetime.fromtimestamp(item['target']).strftime('%Y-%m-%d %H:%M:%S')
            entry = QListWidgetItem(when + ' · ' + item['text'])
            entry.setData(Qt.ItemDataRole.UserRole, item['id'])
            self.reminders.addItem(entry)

    def add_reminder(self):
        try:
            factor = {'分钟': 60, '小时': 3600, '天': 86400}[self.reminder_unit.currentText()]
            self.actions.reminders.add(self.reminder_value.value() * factor, self.reminder_text.text())
            self.reminder_text.clear()
            self.refresh_reminders()
        except Exception as error:
            QMessageBox.warning(self, '提醒未添加', str(error))

    def cancel_reminder(self):
        item = self.reminders.currentItem()
        if item:
            self.actions.reminders.cancel(item.data(Qt.ItemDataRole.UserRole))
            self.refresh_reminders()

    def accept(self):
        applications = {}
        for row in range(self.apps.rowCount()):
            alias = self.apps.item(row, 0).text() if self.apps.item(row, 0) else ''
            path = self.apps.item(row, 1).text() if self.apps.item(row, 1) else ''
            alias = alias.strip()
            if alias in applications:
                QMessageBox.warning(self, '程序别名重复', '请删除或修改重复的别名：' + alias)
                return
            applications[alias] = path.strip()
        try:
            self.actions.save_config(applications, self.engine.currentData())
        except Exception as error:
            QMessageBox.warning(self, '桌面动作设置未保存', str(error))
            return
        super().accept()
