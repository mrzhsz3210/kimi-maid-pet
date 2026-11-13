"""Install Kimi Code hooks so the pet can observe local Kimi sessions.

Appends [[hooks]] rules to ~/.kimi-code/config.toml pointing at
app/hook_relay.py. Existing config is preserved; running twice is a no-op.
Remove the marked block with --uninstall.
"""
import re
import shutil
import sys
from pathlib import Path

EVENTS = ['TurnStarted', 'PostToolUse', 'PostToolUseFailure', 'PermissionRequest', 'Stop', 'StopFailure', 'Interrupt']
BEGIN = '# >>> kimi-maid-pet hooks >>>'
END = '# <<< kimi-maid-pet hooks <<<'


def config_path():
    import os
    home = os.environ.get('KIMI_CODE_HOME')
    return (Path(home) if home else Path.home() / '.kimi-code') / 'config.toml'


def block():
    relay = Path(__file__).resolve().parents[1] / 'app' / 'hook_relay.py'
    command = '"{}" "{}"'.format(sys.executable, relay)
    lines = [BEGIN]
    for event in EVENTS:
        lines.append('[[hooks]]')
        lines.append('event = "{}"'.format(event))
        lines.append('command = {}'.format(to_toml_string(command)))
        lines.append('timeout = 5')
    lines.append(END)
    return '\n'.join(lines) + '\n'


def to_toml_string(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def main():
    path = config_path()
    text = path.read_text(encoding='utf-8') if path.exists() else ''
    pattern = re.compile(re.escape(BEGIN) + '.*?' + re.escape(END) + '\n?', re.S)
    if '--uninstall' in sys.argv:
        if BEGIN not in text:
            print('没有找到已安装的桌宠 hooks。')
            return 0
        path.write_text(pattern.sub('', text), encoding='utf-8')
        print('已移除桌宠 hooks：' + str(path))
        return 0
    if BEGIN in text:
        print('桌宠 hooks 已安装过，无需重复操作。')
        return 0
    if path.exists():
        shutil.copy2(path, path.with_suffix('.toml.bak'))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        if text and not text.endswith('\n'):
            handle.write('\n')
        handle.write('\n' + block())
    print('已写入桌宠 hooks：' + str(path))
    print('原配置已备份为 config.toml.bak；新开的 Kimi 会话开始生效。')
    print('卸载：python work/install_hooks.py --uninstall')
    return 0


if __name__ == '__main__':
    sys.exit(main())
