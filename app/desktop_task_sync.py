"""Observe local Kimi Code sessions (CLI and desktop) via their state files.

Read-only watcher over ~/.kimi-code/sessions/*/*/state.json. Only public
metadata is read: session title, last prompt, turn status, timestamps.
Never reads conversation content, never sends model requests.
"""
import json
import re
import time
from pathlib import Path
from PySide6.QtCore import QObject, QTimer

TERMINAL_OK = 'completed'
MIN_TASK_MS = 8000       # 不足 8 秒的轮次当作快问快答，不报开始也不庆祝
CELEBRATION_COOLDOWN = 300  # 庆祝动画/音效的冷却（秒）


def problem_summary(detail, exit_code=None):
    """Summarize a tool failure for the bubble, redacting anything secret-shaped."""
    raw = str(detail or '')
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            raw = str(parsed.get('message') or parsed.get('error') or '')
    except (ValueError, TypeError):
        pass
    lines = [s.strip() for s in raw.splitlines() if s.strip() and not re.search(r'authorization|api.?key|password|token|secret', s, re.I)]
    matches = [s for s in lines if re.search(r'error|exception|failed|timeout|timed out|denied|no such|错误|失败|不存在|无法|拒绝', s, re.I)]
    excerpt = '\n'.join(matches[-2:])[:500]
    low = excerpt.lower()
    if re.search(r'timeout|timed out|超时', low):
        reason = '请求超时'
    elif re.search(r'connect|network|failed to fetch|name_not_resolved|网络', low):
        reason = '网络连接异常'
    elif re.search(r'no such file|filenotfound|cannot find|不存在', low):
        reason = '文件或路径不存在'
    elif re.search(r'no module named|modulenotfound', low):
        reason = '缺少需要的程序模块'
    elif re.search(r'permission|access.*denied|权限|拒绝', low):
        reason = '权限不足或访问被拒绝'
    elif re.search(r'assertion|failed \(|test.*fail|检查.*未通过', low):
        reason = '执行检查未通过'
    else:
        reason = '工具执行异常' + (f'（返回码 {exit_code}）' if exit_code is not None else '')
    return '主人，这一步没有成功。\n原因：' + reason + ('\n错误摘要：' + excerpt if excerpt else '\n暂时没有更详细的错误信息。') + '\n任务是否完成会另外通知你。'


class DesktopTaskSync(QObject):
    def __init__(self, pet, sessions_root=None, clock=time.time):
        super().__init__(pet)
        self.pet = pet
        self.clock = clock
        if sessions_root is None:
            import os
            home = os.environ.get('KIMI_CODE_HOME')
            sessions_root = (Path(home) if home else Path.home() / '.kimi-code') / 'sessions'
        self.sessions_root = Path(sessions_root)
        self.born = clock() * 1000  # state.json timestamps are epoch ms
        self.known = {}
        self.running = set()
        self.mtimes = {}
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.poll)

    def start(self):
        self.timer.start()
        self.poll()

    def stop(self):
        self.timer.stop()

    def excluded(self):
        # Sessions created by the pet itself already report through the chat UI.
        controller = self.pet.chat
        ids = set()
        if controller:
            ids = {c.get('threadId') for c in controller.store.conversations}
        else:
            try:
                from chat_backend import data_directory
                chats = json.loads((data_directory() / 'conversations.json').read_text(encoding='utf-8'))
                ids = {c.get('threadId') for c in chats}
            except (OSError, ValueError):
                pass
        return {i for i in ids if i}

    def details(self, key):
        self.pet.say('主人，细节请到 Kimi 里查看哦。', 6000)

    def poll(self):
        try:
            self._poll()
        except (OSError, ValueError, RuntimeError):
            # Qt callbacks must not leak an exception into the event loop.
            pass

    def _poll(self):
        if not self.pet.settings.value('syncKimiTasks', True, type=bool):
            return
        if not self.sessions_root.is_dir():
            return
        excluded = self.excluded()
        for state in self.sessions_root.glob('*/*/state.json'):
            try:
                mtime = state.stat().st_mtime_ns
            except OSError:
                continue
            key = str(state)
            if self.mtimes.get(key) == mtime:
                continue
            self.mtimes[key] = mtime
            try:
                data = json.loads(state.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            self.handle_state(data, excluded)
        self._check_silent()

    def handle_state(self, data, excluded):
        session = str(data.get('id') or '')
        if not session or session in excluded:
            return
        updated = data.get('updatedAt') or 0
        if data.get('archived'):
            # 被归档的会话不再有后续状态；若还在跟踪中，安静地收尾（不庆祝不报警）。
            if session in self.running:
                self.running.discard(session)
                if not self.running and not (self.pet.chat and self.pet.chat.running_turn):
                    self.pet.task_finished()
            self.known.pop(session, None)
            return
        if updated < self.born - 60000:
            return
        reason = data.get('lastTurnReason')
        title = str(data.get('title') or '未命名任务')[:45]
        record = self.known.get(session)
        if record and record.get('reason') == reason and record.get('updatedAt') == updated:
            return
        prev_running = bool(record and record.get('running'))
        first_seen = record is None
        record = self.known.setdefault(session, {'seen': set()})
        record.update(reason=reason, updatedAt=updated, running=reason is None, title=title)
        if reason is None:
            # Turn in flight. 快问快答（未满 MIN_TASK_MS）不算任务，不打扰主人。
            record.setdefault('running_since', updated)
            if not record.get('announced') and updated - record['running_since'] >= MIN_TASK_MS:
                record['announced'] = True
                was_running = bool(self.running)
                self.running.add(session)
                if not was_running and not (self.pet.chat and self.pet.chat.running_turn):
                    self.pet.task_started()
                prompt = str(data.get('lastPrompt') or '').strip().replace('\n', ' ')[:80]
                self._progress(session, '主人，我收到啦！',
                               '这就认真帮你留意 Kimi 里的任务。' + ('\n' + prompt if prompt else ''))
        elif record.get('announced') or prev_running:
            self._finish(session, reason, title, record)
        record['reported_start'] = True

    def _finish(self, session, reason, title, record=None):
        self.running.discard(session)
        from platform_support import user_data
        from task_stats import record_task_outcome
        record_task_outcome(user_data(), 'synced', 'completed' if reason == TERMINAL_OK else 'failed')
        if not self.running and not (self.pet.chat and self.pet.chat.running_turn):
            self.pet.task_finished()
        if reason == TERMINAL_OK:
            now = self.clock()
            if now - getattr(self, 'last_celebration', 0) >= CELEBRATION_COOLDOWN:
                self.last_celebration = now
                self.pet.task_completed('Kimi 已报告「' + title + '」完成，细节请到 Kimi 查看。', lambda: self.details(session))
            else:
                self._progress(session, '主人，完成啦。', '「' + title + '」已报告完成，细节请到 Kimi 查看。')
        elif reason in ('cancelled', 'interrupted'):
            # 主人主动停下：不是失败，温和收工。
            self._progress(session, '主人，任务已停下。', '「' + title + '」已被中止，随时可以再叫我。')
        else:
            if not self.running and not (self.pet.chat and self.pet.chat.running_turn):
                self.pet.task_failed()
            self._progress(session, '主人，任务还没有完成。',
                           '「' + title + '」这次处理没有成功（' + str(reason) + '），请到 Kimi 查看并处理。', repeat=True)

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

    def _check_silent(self):
        now = self.clock()
        for key in list(self.running):
            record = self.known.get(key)
            if not record:
                continue
            if now * 1000 - record.get('updatedAt', 0) >= 300000 and now - record.get('silent_notice', 0) >= 300:
                record['silent_notice'] = now
                self._progress(key, '主人，我还在留意进展…',
                               '「' + record.get('title', '任务') + '」已经有一会儿没有新动静了，你可以到 Kimi 看看是否需要处理。', repeat=True)
