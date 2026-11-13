"""真实连通测试：KimiSession 走 kimi acp 发一条最小任务并复用会话再来一条。

会真实消耗一次 Kimi 请求额度。用法：python work/test_e2e_backend.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))

from chat_backend import KimiSession

def main():
    folder = tempfile.mkdtemp(prefix='maid-e2e-')
    events = []
    session = KimiSession(folder, emit=lambda k, v: events.append(k))
    try:
        result = session.run('这是桌宠连接验收。不要使用任何工具，不要读写文件，只回复：没药对话连接成功。')
        print('THREAD:', result['threadId'])
        print('TEXT:', result['text'][:200])
        assert '连接成功' in result['text'], result['text']
        result2 = session.run('再回复一次：连接仍然正常。')
        print('TEXT2:', result2['text'][:200])
        assert '正常' in result2['text'], result2['text']
        print('EVENTS:', sorted(set(events)))
        print('E2E BACKEND OK')
    finally:
        session.close()

if __name__ == '__main__':
    main()
