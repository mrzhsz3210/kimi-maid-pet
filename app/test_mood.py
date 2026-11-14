import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import json
import tempfile
import unittest
from mood import MoodService, AXES, PROMPT_INSTRUCTION


class MoodTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = [100000.0]
        self.mood = MoodService(self.tmp.name, clock=lambda: self.now[0])

    def tearDown(self):
        self.tmp.cleanup()

    def test_baseline_with_big5_222(self):
        # n=e=a=-1：joy 基线 4-0.5+0.25=3.75，负性轴基线 1
        self.assertAlmostEqual(self.mood.joy_baseline(), 3.75)
        self.assertEqual(self.mood.baseline('anger'), 1.0)
        self.assertAlmostEqual(self.mood.amplitude('joy'), 0.85)
        self.assertAlmostEqual(self.mood.amplitude('sorrow'), 0.85)
        self.assertAlmostEqual(self.mood.amplitude('anger'), 0.85 * 1.1)
        self.assertAlmostEqual(self.mood.half_life_h('sorrow'), 4.5)

    def test_decay_towards_baseline_lazily(self):
        self.mood.state['axes']['sorrow'] = 9.0
        self.mood.state['updatedAt'] = self.now[0]
        self.now[0] += 4.5 * 3600  # 一个半衰期
        self.assertAlmostEqual(self.mood.decayed('sorrow'), 5.0)
        # 衰减不写回，账目不记
        self.assertEqual(self.mood.state['axes']['sorrow'], 9.0)

    def test_proposal_applied_with_amplitude(self):
        result = self.mood.adjudicate({'joy': 3, 'anger': 0, 'sorrow': 0, 'fear': 0, 'reason': '被夸奖'})
        self.assertEqual(result['status'], 'applied')
        # 3 × 0.85 = 2.55，基线 3.75 + 2.55 = 6.3
        self.assertAlmostEqual(self.mood.state['axes']['joy'], 6.3)
        self.assertEqual(self.mood.state['lastReason'], '被夸奖')
        lines = self.mood.ledger_path.read_text(encoding='utf-8').splitlines()
        self.assertEqual(json.loads(lines[-1])['status'], 'applied')

    def test_clamped_to_range(self):
        for _ in range(4):
            self.now[0] += 400
            self.mood.adjudicate({'joy': 3, 'reason': '开心'})
        self.assertLessEqual(self.mood.state['axes']['joy'], 10.0)

    def test_rate_limited_within_five_minutes(self):
        self.mood.adjudicate({'sorrow': 2, 'reason': '第一件事'})
        self.now[0] += 120
        result = self.mood.adjudicate({'sorrow': 2, 'reason': '第二件事'})
        self.assertEqual(result['status'], 'rate_limited')
        self.now[0] += 400
        result = self.mood.adjudicate({'sorrow': 2, 'reason': '第三件事'})
        self.assertEqual(result['status'], 'applied')

    def test_rate_limit_is_per_axis(self):
        self.mood.adjudicate({'sorrow': 2, 'reason': '难过'})
        result = self.mood.adjudicate({'joy': 2, 'reason': '另一轴不受限'})
        self.assertEqual(result['status'], 'applied')

    def test_rejected_on_bad_structure(self):
        result = self.mood.adjudicate({'joy': 5, 'reason': '超范围'})
        self.assertEqual(result['status'], 'rejected')
        result = self.mood.adjudicate({'joy': 1, 'unknown': 1})
        self.assertEqual(result['status'], 'rejected')

    def test_unchanged_when_all_zero(self):
        result = self.mood.adjudicate({'joy': 0, 'anger': 0, 'sorrow': 0, 'fear': 0})
        self.assertEqual(result['status'], 'unchanged')

    def test_extract_strips_mood_block(self):
        proposal, clean = self.mood.extract('正文内容。\n<mood>{"joy":1,"reason":"测试"}</mood>')
        self.assertEqual(proposal['joy'], 1)
        self.assertEqual(clean, '正文内容。')
        proposal, clean = self.mood.extract('没有提案的回复')
        self.assertIsNone(proposal)
        self.assertEqual(clean, '没有提案的回复')

    def test_owner_reset(self):
        self.mood.adjudicate({'sorrow': 3, 'reason': '难过的事'})
        result = self.mood.owner_reset()
        self.assertEqual(result['status'], 'owner_reset')
        for axis in AXES:
            self.assertAlmostEqual(self.mood.state['axes'][axis], self.mood.baseline(axis))

    def test_variant_weights_follow_mood(self):
        base = self.mood.variant_weights()
        self.mood.state['axes']['joy'] = 9.0
        self.mood.state['updatedAt'] = self.now[0]
        happy = self.mood.variant_weights()
        self.assertGreater(happy['18'], base['18'])
        self.mood.state['axes']['joy'] = self.mood.joy_baseline()
        self.mood.state['axes']['anger'] = 8.0
        angry = self.mood.variant_weights()
        self.assertGreater(angry['13'], 1.0)

    def test_injection_line(self):
        line = self.mood.injection()
        self.assertIn('当前心情', line)
        self.assertIn('<mood>', PROMPT_INSTRUCTION)


if __name__ == '__main__':
    unittest.main()
