"""Kimi Code hook relay: append each hook event to the pet's sync log.

Configured in ~/.kimi-code/config.toml as a [[hooks]] command. Kimi passes
the event JSON on stdin; this script must stay fast and never block the CLI
(hooks are fail-open, but a slow relay would still delay the session).
"""
import json
import sys
from pathlib import Path


def log_path():
    try:
        from platform_support import user_data
        root = user_data()
    except Exception:
        import os
        root = Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.local/share') / 'KimiMaidPet'
    root.mkdir(parents=True, exist_ok=True)
    return root / 'sync-events.jsonl'


def main():
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except ValueError:
        return 0
    try:
        path = log_path()
        lines = path.read_text(encoding='utf-8').splitlines()[-1999:] if path.exists() else []
        path.write_text('\n'.join(lines + [json.dumps(event, ensure_ascii=False)]) + '\n', encoding='utf-8')
    except OSError:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
