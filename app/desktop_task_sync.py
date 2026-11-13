"""Observe local Kimi Code sessions through hook events written by hook_relay.

No model requests are made here; the pet only tails the local event log that
Kimi's own hooks append to. Event payloads contain no reasoning or command
output, only public session metadata (title, tool names, status).
"""
import json
import time
from pathlib import Path
from PySide6.QtCore import QObject, QTimer

ACTIVE_EVENTS = ('TurnStarted', 'PostToolUse', 'PermissionRequest')


class DesktopTaskSync(QObject):
    def __init__(self, pet, log_path=None, clock=time.monotonic):
        super().__init__(pet)
        self.pet = pet
        self.clock = clock
        if log_path is None:
            from platform_support import user_data
            log_path = user_data() / 'sync-events.jsonl'
        self.log_path = Path(log_path)
        self.offset = 0
        self.known = {}
        self.running = set()
        self.born = clock()
        self.bootstrap = True
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.poll)

    def start(self):
        # Skip events from before the pet started; only fresh work is reported.
        try:
            self.offset = self.log_path.stat().st_size
        except OSError:
            self.offset = 0
        self.timer.start()

    def stop(self):
        self.timer.stop()

    def details(self, key):
        # Hook events carry no conversation content; point the主人 at Kimi.
        self.pet.say('主人，细节请到 Kimi 里查看哦。', 6000)

    def _progress(self, key, title, text, repeat=False):
        record = self.known.get(key)
        if record is None:
            return False
        signature = (str(title).strip(), str(text).strip())
        seen = record.setdefault('seen', set())
        if signature in seen:
            if not repeat:
                return False
            if self.clock() - record.get('repeat_times', {}).get(str(signature), 0) < 300:
                return False
        seen.add(signature)
        record.setdefault('repeat_times', {})[str(signature)] = self.clock()
        self.pet.task_progress(title, text, lambda k=key: self.details(k))
        return True

    def poll(self):
        try:
            self._poll()
        except (OSError, ValueError, RuntimeError):
            # Qt callbacks must not leak an exception into the event loop.
            pass

    def _poll(self):
        if not self.pet.settings.value('syncKimiTasks', True, type=bool):
            return
        try:
            size = self.log_path.stat().st_size
        except OSError:
            return
        if size < self.offset:
            self.offset = 0
        if size == self.offset:
            self._check_silent()
            return
        with self.log_path.open('r', encoding='utf-8', errors='replace') as handle:
            handle.seek(self.offset)
            chunk = handle.read()
            self.offset = handle.tell()
        for line in chunk.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            self.handle_event(event)
        self._check_silent()

    def _check_silent(self):
        now = self.clock()
        for key in list(self.running):
            record = self.known.get(key)
            if not record:
                continue
            if now - record.get('last_notice', 0) >= 300:
                self._progress(key, '主人，我还在留意进展…',
                               '已经有一会儿没有新动静了；任务还没有报告完成，你可以到 Kimi 看看是否需要处理。', repeat=True)
                record['last_notice'] = now

    def handle_event(self, event):
        name = event.get('hook_event_name')
        # Hook payloads do not all carry turn_id, so track tasks per session.
        key = str(event.get('session_id') or 'unknown')
        title = str(event.get('session_title') or '未命名任务')[:45]
        now = self.clock()
        if name == 'TurnStarted':
            record = self.known.setdefault(key, {'started_notice': now, 'last_notice': now, 'seen': set()})
            record['last_notice'] = now
            was_running = bool(self.running)
            self.running.add(key)
            if not was_running and not (self.pet.chat and self.pet.chat.running_turn):
                self.pet.task_started()
            prompt = str(event.get('prompt') or '').strip().replace('\n', ' ')[:80]
            self._progress(key, '主人，我收到啦！',
                           '这就认真帮你处理 Kimi 里的任务。' + ('\n' + prompt if prompt else ''))
        elif name == 'PostToolUse':
            tool = str(event.get('tool_name') or '工具')
            record = self.known.get(key)
            if record:
                record['last_notice'] = now
            if key in self.running:
                self._progress(key, '主人，我忙到这一步啦…', '正在使用工具：' + tool)
        elif name == 'PermissionRequest':
            self._progress(key, '主人，有个情况要告诉你。',
                           'Kimi 里有一步需要你确认权限或补充信息，请到 Kimi 查看。', repeat=True)
        elif name == 'PostToolUseFailure':
            tool = str(event.get('tool_name') or '工具')
            self._progress(key, '主人，有个情况要告诉你。',
                           '工具「' + tool + '」这一步没有成功。任务是否完成会另外通知你。', repeat=True)
        elif name == 'Stop':
            if key in self.running:
                self.running.discard(key)
                if not self.running and not (self.pet.chat and self.pet.chat.running_turn):
                    self.pet.task_finished()
                self.pet.task_completed('Kimi 已报告本轮任务完成，细节请到 Kimi 查看。', lambda: self.details(key))
        elif name == 'StopFailure':
            if key in self.running:
                self.running.discard(key)
                if not self.running and not (self.pet.chat and self.pet.chat.running_turn):
                    self.pet.task_finished()
            self._progress(key, '主人，任务还没有完成。',
                           '这次处理遇到了异常，请到 Kimi 查看并处理。', repeat=True)
        elif name == 'Interrupt':
            if key in self.running:
                self.running.discard(key)
                if not self.running and not (self.pet.chat and self.pet.chat.running_turn):
                    self.pet.task_finished()
                self._progress(key, '主人，任务已中断。', '你在 Kimi 里停下了这一步。')
        elif name == 'SessionEnd':
            self.running.discard(key)
            self.known.pop(key, None)
