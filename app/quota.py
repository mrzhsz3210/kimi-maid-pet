"""Locate the Kimi Code CLI (used to launch chat sessions from the pet)."""
import os, shutil, sys
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
