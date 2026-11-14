"""办事记录（尽责性观察指标）：统计任务完成率，仅展示，不参与心情换算。"""
import json
from pathlib import Path


def load_task_stats(directory):
    try:
        data = json.loads((Path(directory) / 'task-stats.json').read_text(encoding='utf-8'))
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {}


def record_task_outcome(directory, origin, status):
    """origin 为 pet（桌宠派发）或 synced（本机 Kimi 会话）；status 为 completed/failed/interrupted。"""
    if status not in ('completed', 'failed', 'interrupted'):
        return
    stats = load_task_stats(directory)
    bucket = stats.setdefault(origin, {'completed': 0, 'failed': 0, 'interrupted': 0})
    bucket[status] = bucket.get(status, 0) + 1
    path = Path(directory) / 'task-stats.json'
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding='utf-8')
    except OSError:
        pass


def conscientiousness(stats):
    """尽责性观察值：由桌宠派发任务的真实完成率换算成 1–5；样本少于 3 件不评分。"""
    bucket = (stats or {}).get('pet', {})
    done = bucket.get('completed', 0)
    total = done + bucket.get('failed', 0) + bucket.get('interrupted', 0)
    if total < 3:
        return None, total
    return round(1 + 4 * done / total), total
