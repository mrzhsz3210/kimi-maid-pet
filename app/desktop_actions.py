"""Deterministic, allow-listed desktop actions for voice commands."""
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid
import webbrowser
from urllib.parse import quote_plus, urlsplit

from PySide6.QtCore import QObject, QTimer

from platform_support import user_data

SEARCH_ENGINES = {
    'bing': ('必应', 'https://www.bing.com/search?q='),
    'baidu': ('百度', 'https://www.baidu.com/s?wd='),
    'google': ('Google', 'https://www.google.com/search?q='),
}
DEFAULT_CONFIG = {
    'applications': {'记事本': 'notepad.exe', '计算器': 'calc.exe', '资源管理器': 'explorer.exe'},
    'searchEngine': 'bing',
}
SETTINGS_PAGES = {
    '飞行模式': 'ms-settings:network-airplanemode',
    '免打扰': 'ms-settings:notificationssettings',
    '通知设置': 'ms-settings:notificationssettings',
    '闹钟': 'ms-clock:',
    '音量设置': 'ms-settings:apps-volume',
    '显示设置': 'ms-settings:display',
    '夜间模式': 'ms-settings:nightlight',
    '蓝牙设置': 'ms-settings:bluetooth',
}


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


class ReminderService(QObject):
    def __init__(self, pet, path=None):
        super().__init__(pet)
        self.pet = pet
        self.path = Path(path) if path else user_data() / 'reminders.json'
        self.items = []
        self.timers = {}
        if self.path.is_file():
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, list):
                raise ValueError('提醒文件格式不正确')
            self.items = [item for item in data if isinstance(item, dict) and item.get('id') and item.get('text') and item.get('target')]
        for item in self.items:
            self.schedule(item)

    def sorted_items(self):
        return sorted(self.items, key=lambda item: item['target'])

    def add(self, seconds, text):
        seconds = float(seconds)
        if not 1 <= seconds <= 7 * 86400:
            raise ValueError('提醒时间需要在 1 秒到 7 天之间')
        text = text.strip()
        if not text:
            raise ValueError('提醒内容不能为空')
        item = {'id': uuid.uuid4().hex, 'text': text[:200], 'target': time.time() + seconds}
        self.items.append(item)
        atomic_json(self.path, self.sorted_items())
        self.schedule(item)
        return item

    def schedule(self, item):
        timer = QTimer(self)
        timer.setSingleShot(True)
        reminder_id = item['id']
        timer.timeout.connect(lambda checked=False, value=reminder_id: self.trigger(value))
        self.timers[reminder_id] = timer
        delay = max(0, round((item['target'] - time.time()) * 1000))
        timer.start(min(delay, 2_147_000_000))

    def cancel(self, reminder_id):
        timer = self.timers.pop(reminder_id, None)
        if timer:
            timer.stop()
            timer.deleteLater()
        before = len(self.items)
        self.items = [item for item in self.items if item['id'] != reminder_id]
        if len(self.items) != before:
            atomic_json(self.path, self.sorted_items())

    def trigger(self, reminder_id):
        timer = self.timers.pop(reminder_id, None)
        if timer:
            timer.deleteLater()
        item = next((entry for entry in self.items if entry['id'] == reminder_id), None)
        if not item:
            return
        self.items = [entry for entry in self.items if entry['id'] != reminder_id]
        atomic_json(self.path, self.sorted_items())
        self.pet.set_manual_hidden(False)
        self.pet.play_click_sound()
        self.pet.say(self.pet.pet_name + ' · 提醒\n' + item['text'], 0)

    def shutdown(self):
        for timer in self.timers.values():
            timer.stop()
        self.timers.clear()


class DesktopActions(QObject):
    def __init__(self, pet, config_path=None, reminders_path=None):
        super().__init__(pet)
        self.pet = pet
        self.config_path = Path(config_path) if config_path else user_data() / 'desktop-actions.json'
        self.config = self.load_config()
        self.reminders = ReminderService(pet, reminders_path)

    def load_config(self):
        if not self.config_path.is_file():
            return json.loads(json.dumps(DEFAULT_CONFIG))
        value = json.loads(self.config_path.read_text(encoding='utf-8'))
        applications = value.get('applications')
        if not isinstance(applications, dict) or not all(isinstance(key, str) and isinstance(path, str) for key, path in applications.items()):
            raise ValueError('程序别名配置格式不正确')
        return {'applications': dict(applications), 'searchEngine': value.get('searchEngine') if value.get('searchEngine') in SEARCH_ENGINES else 'bing'}

    def save_config(self, applications, search_engine):
        if search_engine not in SEARCH_ENGINES:
            raise ValueError('未知搜索引擎')
        cleaned = {}
        for alias, path in applications.items():
            alias, path = alias.strip(), path.strip()
            if not alias or not path:
                raise ValueError('程序别名和路径不能为空')
            if alias in cleaned:
                raise ValueError('程序别名重复：' + alias)
            cleaned[alias] = path
        self.config = {'applications': cleaned, 'searchEngine': search_engine}
        atomic_json(self.config_path, self.config)

    def open_application(self, alias):
        applications = self.config['applications']
        match = next((name for name in applications if name.casefold() == alias.strip().casefold()), None)
        if not match:
            return False, f'我还没有学会打开“{alias}”。请在桌面动作设置里添加程序别名和路径。'
        try:
            subprocess.Popen([applications[match]], shell=False)
            return True, '已经打开' + match + '啦，主人。'
        except OSError as error:
            return False, '打开' + match + '失败：' + str(error)

    def open_url(self, url):
        parsed = urlsplit(url.strip())
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            return False, '这个网页地址不安全或格式不正确。'
        if len(url) > 2048:
            return False, '网页地址太长了。'
        if webbrowser.open(url, new=2):
            return True, '已经在浏览器里打开网页啦。'
        return False, '没有成功唤起默认浏览器。'

    def search_web(self, query):
        query = query.strip()
        if not query:
            return False, '想让我搜索什么呢？'
        engine = self.config.get('searchEngine', 'bing')
        name, prefix = SEARCH_ENGINES[engine]
        url = prefix + quote_plus(query[:500])
        if webbrowser.open(url, new=2):
            return True, f'已经在浏览器里用{name}搜索“{query}”啦。'
        return False, '没有成功唤起默认浏览器。'

    def open_settings(self, name):
        if os.name != 'nt':
            return False, '系统设置页动作目前只支持 Windows。'
        try:
            os.startfile(SETTINGS_PAGES[name])
            return True, '已经打开' + name + '设置页；具体开关请主人在页面上确认。'
        except OSError as error:
            return False, '打开设置页失败：' + str(error)

    def endpoint_volume(self):
        if os.name != 'nt':
            raise RuntimeError('音量控制目前只支持 Windows')
        from pycaw.pycaw import AudioUtilities
        return AudioUtilities.GetSpeakers().EndpointVolume

    def get_volume(self):
        return round(self.endpoint_volume().GetMasterVolumeLevelScalar() * 100)

    def set_volume(self, level):
        level = max(0, min(100, int(level)))
        self.endpoint_volume().SetMasterVolumeLevelScalar(level / 100, None)
        return True, f'已经把音量调到 {level}% 啦，主人。'

    def change_volume(self, difference):
        level = max(0, min(100, self.get_volume() + difference))
        return self.set_volume(level)

    def mute_volume(self, muted):
        self.endpoint_volume().SetMute(bool(muted), None)
        return True, '已经静音啦。' if muted else '已经取消静音啦。'

    def match(self, text):
        text = text.strip()
        if not text:
            return None
        try:
            reminder = re.search(r'(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>秒|分钟|小时|天)后(?:提醒我|叫我)(?P<text>.+)', text)
            if reminder:
                value = float(reminder.group('value'))
                factor = {'秒': 1, '分钟': 60, '小时': 3600, '天': 86400}[reminder.group('unit')]
                self.reminders.add(value * factor, reminder.group('text'))
                return True, f'记住啦，{reminder.group("value")}{reminder.group("unit")}后提醒你{reminder.group("text")}。'
            if re.search(r'半小时后(?:提醒我|叫我)', text):
                content = re.split(r'半小时后(?:提醒我|叫我)', text, maxsplit=1)[1]
                self.reminders.add(1800, content)
                return True, '记住啦，半小时后提醒你' + content + '。'
            for name in SETTINGS_PAGES:
                if name in text:
                    return self.open_settings(name)
            url = re.search(r'https?://[^\s，。！？]+', text)
            if url:
                return self.open_url(url.group(0))
            search = re.search(r'(?:用浏览器)?(?:搜索|搜一下|百度一下|百度搜索)(?:一下)?\s*([^，。！？]+)', text)
            if search:
                return self.search_web(search.group(1))
            if '取消静音' in text:
                return self.mute_volume(False)
            if '静音' in text:
                return self.mute_volume(True)
            level = re.search(r'音量.*?(?:调到|调成|设为|设置为|改成)\s*(?:百分之)?\s*(\d{1,3})', text)
            if level:
                return self.set_volume(int(level.group(1)))
            if re.search(r'音量.*(?:大一点|高一点|大一些|高一些)', text):
                return self.change_volume(10)
            if re.search(r'音量.*(?:小一点|低一点|小一些|低一些)', text):
                return self.change_volume(-10)
            if '音量' in text and re.search(r'多少|多大|现在', text):
                return True, f'现在的音量是 {self.get_volume()}%。'
            if '浏览器' in text and re.search(r'打开|启动', text):
                if webbrowser.open('about:blank', new=2):
                    return True, '已经打开默认浏览器啦。'
                return False, '没有成功唤起默认浏览器。'
            opened = re.search(r'(?:打开|启动|运行)(?:一下)?\s*([^，。！？]+)', text)
            if opened:
                alias = opened.group(1).strip()
                alias = re.sub(r'(?:这个|那个)?(?:程序|软件|应用)$', '', alias).strip()
                return self.open_application(alias)
        except Exception as error:
            return False, '这个动作没有完成：' + str(error)
        return None

    def try_handle(self, text):
        result = self.match(text)
        if result is None:
            return False
        success, message = result
        self.pet.say((self.pet.pet_name + '：' if success else '唔，') + message, 6000)
        if self.pet.voice:
            self.pet.voice.begin_followup()
        return True

    def shutdown(self):
        self.reminders.shutdown()
