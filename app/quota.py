"""Locate the Kimi Code CLI and report basic account status.

Kimi Code 目前没有公开的额度查询命令行接口，双击桌宠时改为确认
CLI 是否可用、是否已登录，并提示主人到 Kimi 客户端查看额度。
"""
import os, shutil, subprocess, sys, time
from pathlib import Path


class QuotaFailure(RuntimeError):
    def __init__(self, message, code, phase='request', retryable=False):
        super().__init__(message)
        self.code = code
        self.phase = phase
        self.retryable = retryable


def find_kimi():
    """Find the kimi CLI even when a startup process has a minimal PATH."""
    override = os.environ.get('MAID_KIMI', '').strip().strip('"')
    for candidate in (override, shutil.which('kimi.exe'), shutil.which('kimi')):
        if not candidate:
            continue
        resolved = Path(candidate).expanduser()
        if resolved.is_file():
            return str(resolved)
        located = shutil.which(candidate)
        if located:
            return located
    home = Path(os.environ.get('USERPROFILE') or Path.home())
    if sys.platform == 'darwin':
        for path in (Path('/opt/homebrew/bin/kimi'), Path('/usr/local/bin/kimi'), home / '.kimi-code/bin/kimi'):
            if path.is_file() and os.access(path, os.X_OK):
                return str(path)
        raise RuntimeError('没有找到 Kimi Code。请先安装 Kimi Code CLI，或设置 MAID_KIMI 指向 kimi 可执行文件。')
    candidates = [home / '.kimi-code/bin/kimi.exe', home / '.kimi-code/bin/kimi']
    local = Path(os.environ.get('LOCALAPPDATA') or home / 'AppData/Local')
    candidates.append(local / 'Programs/kimi/kimi.exe')
    for path in candidates:
        if path.is_file():
            return str(path)
    raise RuntimeError('没有找到 Kimi Code，请确认已安装 kimi CLI，或设置 MAID_KIMI 指向 kimi.exe。')


def read_quota(timeout=15, cancel=None, attempts=1, log_path=None):
    """Confirm the CLI runs and the account is logged in. Never sends a prompt."""
    executable = find_kimi()
    frozen_windows = sys.platform == 'win32' and getattr(sys, 'frozen', False)
    if frozen_windows:
        ctypes = __import__('ctypes')
        ctypes.windll.kernel32.SetDllDirectoryW(None)
    try:
        process = subprocess.Popen([executable, '--version'], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except OSError:
        raise QuotaFailure('Kimi 连接暂时中断，请稍后再试。', 'connection_io', 'transport', True)
    finally:
        if frozen_windows:
            ctypes.windll.kernel32.SetDllDirectoryW(sys._MEIPASS)
    try:
        out, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise QuotaFailure('Kimi 响应超时，请稍后再试。', 'timeout', 'version', True)
    version = (out or '').strip().splitlines()
    logged_in = (Path(os.environ.get('USERPROFILE') or Path.home()) / '.kimi-code').is_dir()
    return {'version': version[0] if version else '', 'loggedIn': logged_in}


def quota_windows(data):
    windows = []
    version = data.get('version') or '未知版本'
    windows.append({'name': 'Kimi Code CLI ' + version, 'remaining': None, 'resetsAt': None})
    return windows
