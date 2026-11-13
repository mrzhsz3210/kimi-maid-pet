import unittest
from types import SimpleNamespace
from chat_backend import KimiSession


class FakeSession(KimiSession):
    def __init__(self, mode='work'):
        super().__init__('.', mode=mode)
        self.calls = []
        self.starts = 0
        self.sent = []
    def start(self):
        self.starts += 1
        self.process = SimpleNamespace(poll=lambda: None)
    def send(self, value):
        self.sent.append(value)
        if value.get('method') == 'session/prompt':
            self._prompt_id = value['id']
    def rpc(self, method, params, timeout=60):
        self.calls.append((method, params))
        if method == 'session/new':
            return {'sessionId': 'test-thread'}
        if method == 'session/load':
            return {}
        return {}
    def next(self, deadline):
        if not getattr(self, '_fed', False):
            self._fed = True
            return {'method': 'session/update', 'params': {'sessionId': self.thread_id,
                    'update': {'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': '回答'}}}}
        return {'id': self._prompt_id, 'result': {'stopReason': 'end_turn'}}


class Tests(unittest.TestCase):
    def test_reuses_connection_and_resets_reply(self):
        s = FakeSession()
        self.assertEqual(s.run('一')['text'], '回答')
        s._fed = False
        self.assertEqual(s.run('二')['text'], '回答')
        self.assertEqual(s.starts, 1)
        self.assertEqual([m for m, p in s.calls].count('initialize'), 1)
        self.assertEqual([m for m, p in s.calls].count('session/new'), 1)
        prompts = [v for v in s.sent if v.get('method') == 'session/prompt']
        self.assertEqual(len(prompts), 2)

    def test_chat_prompt_carries_chat_instruction(self):
        s = FakeSession('chat')
        s.run('你好')
        prompt = next(v for v in s.sent if v.get('method') == 'session/prompt')
        text = prompt['params']['prompt'][0]['text']
        self.assertIn('角色设定', text)
        self.assertIn('聊天模式', text)

    def test_work_prompt_carries_persona_once(self):
        s = FakeSession('work')
        s.run('一')
        s._fed = False
        s.run('二')
        prompts = [v['params']['prompt'][0]['text'] for v in s.sent if v.get('method') == 'session/prompt']
        self.assertIn('角色设定', prompts[0])
        self.assertNotIn('角色设定', prompts[1])


if __name__ == '__main__':
    unittest.main()
