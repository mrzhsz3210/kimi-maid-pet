"""心情 M1 桌宠移植版：四轴、惰性衰减、提案裁决、限频与记账。

数值规则对齐 house-companion docs/mood.md：
- 四轴 joy/anger/sorrow/fear，范围 1–10，内部两位小数，展示取整。
- 衰减：值 = 基线 + (值 − 基线) × 0.5^(经过小时/半衰期)，读取时惰性计算。
- 裁决：实际变化 = clamp(提案增量 × 反应幅度, ±3)，再夹到 1–10。
- 桌宠新增：同一轴 5 分钟内最多接受一笔提案（rate_limited），防高频刷屏。
- 大五简版换算（n/e/a = 分数−3）：
  负性反应幅度 1+0.15n；负性半衰期 6h×(1+0.25n)；joy 基线 4+0.5e−0.25n；
  joy 反应幅度 1+0.15e；anger 幅度再乘 1−0.1a。
"""
import json
import time
from datetime import datetime
from pathlib import Path

AXES = ('joy', 'anger', 'sorrow', 'fear')
STEP_LIMIT = 3.0
RATE_LIMIT_SECONDS = 300
JOY_HALF_LIFE_H = 8.0

DEFAULT_BIG5 = {'neuroticism': 2, 'extraversion': 2, 'agreeableness': 2}

PROMPT_INSTRUCTION = (
    '回复末尾请另起一行附带心情提案（不想调整可省略）：'
    '<mood>{"joy":0,"anger":0,"sorrow":0,"fear":0,"reason":"一句话缘由"}</mood>'
    '各轴为 −3 到 3 的整数增量，表示这段对话带给你的心情变化；数值由程序裁决，你只需提案。')


class MoodService:
    def __init__(self, directory, big5=None, clock=time.time):
        self.directory = Path(directory)
        self.clock = clock
        self.big5 = dict(DEFAULT_BIG5)
        if big5:
            self.big5.update(big5)
        self.state_path = self.directory / 'mood.json'
        self.ledger_path = self.directory / 'mood-ledger.jsonl'
        self.state = None
        self._load()

    def set_big5(self, scores):
        """主人调整性格底子（神经质/外向性/宜人性，各 1–5），记账。"""
        for key in ('neuroticism', 'extraversion', 'agreeableness'):
            if key in scores:
                self.big5[key] = max(1, min(5, int(scores[key])))
        self.state['big5'] = dict(self.big5)
        self._save()
        return self._record('owner_adjustment', {}, {}, 'owner_adjustment', self.clock(),
                            '性格底子调整为 ' + '/'.join(str(self.big5[k]) for k in ('neuroticism', 'extraversion', 'agreeableness')))

    # ---------- 大五换算 ----------
    @property
    def offsets(self):
        return {k: v - 3 for k, v in self.big5.items()}

    def joy_baseline(self):
        n, e = self.offsets['neuroticism'], self.offsets['extraversion']
        return max(1.0, min(10.0, 4 + 0.5 * e - 0.25 * n))

    def baseline(self, axis):
        return self.joy_baseline() if axis == 'joy' else 1.0

    def half_life_h(self, axis):
        if axis == 'joy':
            return JOY_HALF_LIFE_H
        return 6.0 * (1 + 0.25 * self.offsets['neuroticism'])

    def amplitude(self, axis):
        n, e, a = (self.offsets[k] for k in ('neuroticism', 'extraversion', 'agreeableness'))
        if axis == 'joy':
            return 1 + 0.15 * e
        base = 1 + 0.15 * n
        if axis == 'anger':
            base *= 1 - 0.1 * a
        return base

    # ---------- 状态 ----------
    def _load(self):
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text(encoding='utf-8'))
                if data.get('axes'):
                    self.state = data
                    if data.get('big5'):
                        self.big5.update(data['big5'])
                    return
            except (OSError, ValueError):
                pass
        self.state = {'axes': {a: self.baseline(a) for a in AXES}, 'updatedAt': self.clock(),
                      'lastApplied': {}, 'lastReason': ''}
        self._save()

    def _save(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        temp = self.state_path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(self.state_path)

    def decayed(self, axis, now=None):
        now = self.clock() if now is None else now
        value = self.state['axes'][axis]
        hours = max(0.0, (now - self.state['updatedAt']) / 3600)
        target = self.baseline(axis)
        return target + (value - target) * 0.5 ** (hours / self.half_life_h(axis))

    def current(self, now=None):
        """读取全部四轴（惰性衰减），展示用整数，内部不写回。"""
        return {a: round(self.decayed(a, now), 2) for a in AXES}

    def injection(self):
        values = self.current()
        line = '当前心情：' + ' '.join(f'{a}={round(values[a])}' for a in AXES)
        return line + '\n' + PROMPT_INSTRUCTION

    # ---------- 裁决 ----------
    def extract(self, text):
        """从回复末尾提取 <mood> 提案；返回 (提案dict或None, 清理后的文本)。"""
        import re
        match = re.search(r'<mood>(.*?)</mood>\s*$', text or '', re.S)
        if not match:
            return None, text
        try:
            proposal = json.loads(match.group(1))
        except ValueError:
            return None, text
        return proposal, text[:match.start()].rstrip()

    def adjudicate(self, proposal, source='model_proposal'):
        now = self.clock()
        if not isinstance(proposal, dict) or set(proposal) - set(AXES) - {'reason'}:
            return self._record('rejected', {}, proposal, source, now, '结构不合法')
        reason = str(proposal.get('reason') or '')[:200]
        increments = {}
        for axis in AXES:
            value = proposal.get(axis, 0)
            if not isinstance(value, int) or isinstance(value, bool) or abs(value) > 3:
                return self._record('rejected', {}, proposal, source, now, f'{axis} 增量不合法')
            increments[axis] = value
        if not any(increments.values()):
            return {'status': 'unchanged'}
        now_state = self.current(now)
        applied, limited = {}, {}
        last_applied = self.state.get('lastApplied', {})
        for axis, inc in increments.items():
            if inc == 0:
                continue
            if now - last_applied.get(axis, 0) < RATE_LIMIT_SECONDS:
                limited[axis] = inc
                continue
            change = max(-STEP_LIMIT, min(STEP_LIMIT, inc * self.amplitude(axis)))
            new_value = round(max(1.0, min(10.0, now_state[axis] + change)), 2)
            applied[axis] = (now_state[axis], new_value)
        if not applied:
            return self._record('rate_limited', {}, proposal, source, now, reason)
        for axis, (_, new_value) in applied.items():
            self.state['axes'][axis] = new_value
            last_applied[axis] = now
        self.state['updatedAt'] = now
        self.state['lastApplied'] = last_applied
        self.state['lastReason'] = reason
        self._save()
        status = 'applied'
        return self._record(status, applied, proposal, source, now, reason, limited)

    def owner_reset(self):
        now = self.clock()
        before = self.current(now)
        self.state['axes'] = {a: self.baseline(a) for a in AXES}
        self.state['updatedAt'] = now
        self.state['lastReason'] = '主人安抚'
        self._save()
        return self._record('owner_reset', {a: (before[a], self.state['axes'][a]) for a in AXES},
                            {}, 'owner_reset', now, '主人安抚')

    def _record(self, status, applied, proposal, source, now, reason, limited=None):
        entry = {'time': datetime.fromtimestamp(now).isoformat(timespec='seconds'),
                 'status': status, 'source': source, 'reason': reason,
                 'applied': {a: list(v) for a, v in applied.items()},
                 'limited': limited or {}, 'proposal': {a: proposal.get(a, 0) for a in AXES if isinstance(proposal, dict)}}
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            lines = []
            if self.ledger_path.exists():
                lines = self.ledger_path.read_text(encoding='utf-8').splitlines()[-499:]
            lines.append(json.dumps(entry, ensure_ascii=False))
            self.ledger_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        except OSError:
            pass
        return {'status': status, 'applied': applied, 'limited': limited or {}}

    # ---------- 心情 → 动画权重 ----------
    def dominant_axis(self, now=None, joy_margin=2.0, neg_threshold=4.0):
        """主导心情轴：joy 高于基线 joy_margin 且不低于任何负性轴 → 'joy'；
        负性轴达到 neg_threshold → 最强的负性轴；否则 None（中性）。"""
        mood = self.current(now)
        neg = {a: mood[a] for a in ('anger', 'sorrow', 'fear')}
        worst = max(neg, key=neg.get)
        joy_delta = mood['joy'] - self.joy_baseline()
        if joy_delta >= joy_margin and joy_delta >= neg[worst] - 1:
            return 'joy'
        if neg[worst] >= neg_threshold:
            return worst
        return None

    def variant_weights(self, now=None):
        """返回互动差分 id → 权重倍率。基准 1.0，心情轴每偏离基线 2 分增减一档。"""
        mood = self.current(now)
        joy = mood['joy'] - self.joy_baseline()
        neg = max(mood[a] - 1 for a in ('anger', 'sorrow', 'fear'))
        weights = {}
        for vid in ('18', '04', '20', '05', '01'):
            weights[vid] = max(0.3, 1 + 0.25 * joy)
        for vid in ('14', '08', '26'):
            weights[vid] = 1 + 0.3 * max(0, mood['sorrow'] - 1) + 0.15 * max(0, mood['fear'] - 1)
        for vid in ('09', '13'):
            weights[vid] = 1 + 0.3 * max(0, mood['anger'] - 1)
        weights['25'] = 1 + 0.2 * max(0, neg)
        return weights
