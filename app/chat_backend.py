"""Local conversation persistence and Kimi Code (ACP) stdio transport for the pet UI."""
import ctypes
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime

from quota import find_kimi
from version import VERSION

PERSONA = ('你是「Kimi娘」，一位住在用户桌面上的星空女仆：温柔、聪明、认真负责，'
           '说话时自然、轻柔、可爱，适度称呼用户为“主人”，偶尔有一点小得意或小傲娇。'
           '不要每句话都重复称呼，不滥用撒娇、拟声词、表情或夸张承诺。'
           '执行任务时保持严谨，先解决问题，保留代码、文件名、数据和技术解释的准确性。'
           '进度、困难和待确认的问题也用Kimi娘的口吻说清楚，不编造过程，不把失败或中断说成完成。'
           '最终结果直接给出正文，客户端会单独显示“主人，完成啦！”，不必重复这句开场。'
           '角色口吻不改变用户的任务范围、访问权限或审批要求。')


class TaskCancelled(RuntimeError):
    pass


def data_directory():
    from platform_support import user_data
    return user_data()


def kimi_home():
    """Isolated KIMI_CODE_HOME for pet sessions.

    Sessions created via `kimi acp` land in <home>/sessions and the desktop
    client lists every workspace it finds under ~/.kimi-code/sessions — and
    then freezes when opening a session written by another client. Keeping
    the pet's sessions in a dedicated home hides them from the desktop list.
    Config and credentials are seeded from the real home on first use.
    """
    home = data_directory() / 'kimi-home'
    real = Path(os.environ.get('KIMI_CODE_HOME') or Path.home() / '.kimi-code')
    if not home.is_dir():
        home.mkdir(parents=True, exist_ok=True)
    for name in ('config.toml', 'tui.toml', 'mcp.json', 'device_id'):
        source = real / name
        target = home / name
        if source.is_file() and not target.exists():
            try:
                target.write_bytes(source.read_bytes())
            except OSError:
                pass
    credentials = home / 'credentials'
    if (real / 'credentials').is_dir() and not credentials.exists():
        try:
            # Directory junction needs no admin rights on Windows.
            import subprocess
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(credentials), str(real / 'credentials')],
                           check=True, capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except Exception:
            import shutil
            try:
                shutil.copytree(real / 'credentials', credentials)
            except OSError:
                pass
    return home


class HistoryStore:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else data_directory()
        self.path = self.directory / 'conversations.json'
        self.conversations = []
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding='utf-8'))
                if not isinstance(data, list):
                    raise ValueError('invalid conversation list')
                self.conversations = data
            except (ValueError, OSError):
                raise RuntimeError('历史对话文件无法读取，请先备份本机 conversations.json；为避免覆盖，暂未写入新记录。')
        # A stopped process must never leave a task permanently displayed as running.
        for chat in self.conversations:
            for turn in chat.get('turns', []):
                if turn.get('status') == 'running':
                    turn['status'] = 'interrupted'
                    turn['error'] = '上次程序退出，任务未确认完成。'

    def new(self, cwd, mode='work'):
        chat = {'id': uuid.uuid4().hex, 'title': '新的对话', 'created': self.now(),
                'cwd': str(Path(cwd).resolve()), 'threadId': None, 'turns': [], 'mode':mode}
        self.conversations.append(chat)
        self.save()
        return chat

    @staticmethod
    def now():
        return datetime.now().isoformat(timespec='seconds')

    def save(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.conversations, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temp, self.path)


class KimiSession:
    """One worker owns the kimi acp process; callbacks deliver public protocol events."""
    def __init__(self, cwd, thread_id=None, cancel=None, emit=None, ask=None, mode='work'):
        self.cwd = str(Path(cwd).resolve())
        self.thread_id = thread_id
        self.cancel = cancel or threading.Event()
        self.emit = emit or (lambda kind, value: None)
        self.ask = ask or (lambda method, params: None)
        self.process = None
        self.messages = queue.Queue()
        self.sequence = 0
        self.active = False
        self.output_parts = []
        self.thought_parts = []
        self.tool_titles = {}
        self.mode = mode
        self.initialized = False
        self.loading = False

    def send(self, value):
        self.process.stdin.write(json.dumps(value, ensure_ascii=False) + '\n')
        self.process.stdin.flush()

    def start(self):
        frozen_windows = sys.platform == 'win32' and getattr(sys, 'frozen', False)
        if frozen_windows:
            ctypes.windll.kernel32.SetDllDirectoryW(None)
        env = dict(os.environ)
        env['KIMI_CODE_HOME'] = str(kimi_home())
        try:
            self.process = subprocess.Popen([find_kimi(), 'acp'], cwd=self.cwd,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding='utf-8', env=env,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        finally:
            if frozen_windows:
                ctypes.windll.kernel32.SetDllDirectoryW(sys._MEIPASS)
        process, messages = self.process, self.messages
        def read():
            try:
                for line in process.stdout:
                    try:
                        messages.put(json.loads(line))
                    except ValueError:
                        continue
            finally:
                messages.put(None)
        threading.Thread(target=read, daemon=True).start()

    def next(self, deadline):
        while time.monotonic() < deadline:
            if self.cancel.is_set():
                if self.thread_id:
                    try:
                        self.send({'method': 'session/cancel', 'params': {'sessionId': self.thread_id}})
                    except (OSError, ValueError):
                        pass
                raise TaskCancelled('任务已停止，已完成的文件更改仍会保留。')
            try:
                message = self.messages.get(timeout=.1)
            except queue.Empty:
                continue
            if message is None:
                raise RuntimeError('Kimi连接已结束，任务未确认完成。可以在历史对话中查看已有输出。')
            if 'method' in message and 'id' in message:
                self.answer_request(message)
                continue
            return message
        raise RuntimeError('Kimi长时间未响应。任务未确认完成，请查看历史或稍后重试。')

    def answer_request(self, message):
        method, params = message['method'], message.get('params') or {}
        if method == 'session/request_permission' and self.mode == 'chat':
            # Chat mode stays read-only: no tool approval is ever granted.
            response = {'outcome': {'outcome': 'cancelled'}}
        else:
            response = self.ask(method, params)
        if response is None:
            self.send({'id': message['id'], 'error': {'code': -32601, 'message': '此客户端暂不支持该交互；请改用已支持的工具。'}})
        else:
            self.send({'id': message['id'], 'result': response})

    def rpc(self, method, params, timeout=60):
        self.sequence += 1
        request_id = self.sequence
        self.send({'id': request_id, 'method': method, 'params': params})
        deadline = time.monotonic() + timeout
        while True:
            message = self.next(deadline)
            if message.get('id') == request_id:
                if 'error' in message:
                    error = message['error']
                    if error.get('code') == -32000:
                        raise RuntimeError('还没有登录 Kimi。请先在终端运行 kimi login 完成登录。')
                    raise RuntimeError(error.get('message', 'Kimi请求失败'))
                return message.get('result') or {}
            self.event(message)

    def event(self, message):
        method, p = message.get('method', ''), message.get('params') or {}
        if method != 'session/update':
            return
        if self.thread_id and p.get('sessionId') and p['sessionId'] != self.thread_id:
            return
        if self.loading:
            # session/load replays history; the pet keeps its own transcript.
            return
        update = p.get('update') or {}
        kind = update.get('sessionUpdate')
        if kind == 'agent_message_chunk':
            content = update.get('content') or {}
            if content.get('type') == 'text':
                self.output_parts.append(content.get('text', ''))
                self.emit('output', self.transcript())
        elif kind == 'agent_thought_chunk':
            content = update.get('content') or {}
            if content.get('type') == 'text':
                self.thought_parts.append(content.get('text', ''))
                self.emit('summary_update', '\n\n'.join(self.thought_parts))
        elif kind == 'tool_call':
            title = update.get('title') or update.get('kind') or '工具'
            call_id = update.get('toolCallId')
            if call_id:
                self.tool_titles[call_id] = str(title)
            self.emit('progress', '正在执行：' + str(title))
        elif kind == 'tool_call_update':
            status = update.get('status')
            if status in ('completed', 'failed'):
                title = update.get('title') or self.tool_titles.get(update.get('toolCallId'), '工具')
                self.emit('progress', ('执行结束：' if status == 'completed' else '执行失败：') + str(title))
        elif kind == 'plan':
            steps = [e.get('content', '') for e in update.get('entries', []) if e.get('content')]
            if steps:
                self.emit('progress', '当前安排：' + '；'.join(steps))

    def transcript(self):
        return ''.join(self.output_parts)

    def final_text(self):
        return self.transcript()

    def open_thread(self):
        if self.thread_id:
            self.loading = True
            try:
                self.rpc('session/load', {'sessionId': self.thread_id, 'cwd': self.cwd, 'mcpServers': []})
                return
            except RuntimeError:
                self.thread_id = None
            finally:
                self.loading = False
        result = self.rpc('session/new', {'cwd': self.cwd, 'mcpServers': []})
        self.thread_id = result['sessionId']

    def run(self, prompt):
        self.output_parts = []
        self.thought_parts = []
        self.tool_titles = {}
        if self.process and self.process.poll() is not None:
            self.close()
        if not self.process:
            self.start()
        try:
            if not self.initialized:
                self.rpc('initialize', {'protocolVersion': 1,
                    'clientCapabilities': {'fs': {'readTextFile': False, 'writeTextFile': False}, 'terminal': False},
                    'clientInfo': {'name': 'kimi_maid_pet', 'title': 'Kimi娘桌宠', 'version': VERSION}})
                self.open_thread()
                self.initialized = True
                self.emit('thread', self.thread_id)
                instruction = PERSONA + ('当前为聊天模式：只根据对话直接交流，回答简短自然；不要查看或更改文件，不调用工具、不运行命令。如需实际操作，提醒主人切换工作模式。' if self.mode == 'chat' else '')
                prompt = '<角色设定>\n' + instruction + '\n</角色设定>\n\n' + prompt
            else:
                while not self.messages.empty():
                    self.messages.get_nowait()
            self.sequence += 1
            request_id = self.sequence
            self.send({'id': request_id, 'method': 'session/prompt',
                'params': {'sessionId': self.thread_id, 'prompt': [{'type': 'text', 'text': prompt}]}})
            deadline = time.monotonic() + 900
            while True:
                message = self.next(deadline)
                if message.get('id') != request_id:
                    self.event(message)
                    deadline = time.monotonic() + 900
                    continue
                if 'error' in message:
                    error = message['error']
                    if self.cancel.is_set() or error.get('code') == -32800:
                        raise TaskCancelled('任务已停止，已有输出保存在历史对话中。')
                    raise RuntimeError(error.get('message', 'Kimi任务失败'))
                result = message.get('result') or {}
                stop = result.get('stopReason')
                if stop in (None, 'end_turn'):
                    return {'threadId': self.thread_id, 'text': self.final_text() or '任务已完成，未返回文字结果。',
                            'transcript': self.transcript()}
                if stop == 'cancelled':
                    raise TaskCancelled('任务已停止，已有输出保存在历史对话中。')
                raise RuntimeError('任务没有成功完成（' + str(stop) + '）。')
        except Exception:
            self.close()
            raise

    def close(self):
        process = self.process
        if not process:
            return
        if self.thread_id and process.poll() is None:
            try:
                self.send({'id': 'close', 'method': 'session/close', 'params': {'sessionId': self.thread_id}})
            except (OSError, ValueError):
                pass
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        process.stdin.close()
        process.stdout.close()
        self.process = None
        self.initialized = False
        self.messages = queue.Queue()


# Backward-compatible alias for older imports.
CodexSession = KimiSession
