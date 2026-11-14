import unittest
import tempfile
from task_stats import load_task_stats, record_task_outcome, conscientiousness


class TaskStatsTests(unittest.TestCase):
    def test_record_and_load(self):
        with tempfile.TemporaryDirectory() as folder:
            record_task_outcome(folder, 'pet', 'completed')
            record_task_outcome(folder, 'pet', 'completed')
            record_task_outcome(folder, 'pet', 'failed')
            record_task_outcome(folder, 'synced', 'completed')
            record_task_outcome(folder, 'pet', 'bogus')  # 非法状态不记
            stats = load_task_stats(folder)
            self.assertEqual(stats['pet'], {'completed': 2, 'failed': 1, 'interrupted': 0})
            self.assertEqual(stats['synced']['completed'], 1)

    def test_conscientiousness_threshold_and_scale(self):
        self.assertEqual(conscientiousness({}), (None, 0))
        stats = {'pet': {'completed': 2, 'failed': 0, 'interrupted': 0}}
        self.assertEqual(conscientiousness(stats), (None, 2))  # 样本不足
        stats = {'pet': {'completed': 3, 'failed': 0, 'interrupted': 0}}
        self.assertEqual(conscientiousness(stats), (5, 3))
        stats = {'pet': {'completed': 1, 'failed': 1, 'interrupted': 1}}
        self.assertEqual(conscientiousness(stats), (2, 3))
        stats = {'pet': {'completed': 0, 'failed': 3, 'interrupted': 0}}
        self.assertEqual(conscientiousness(stats), (1, 3))

    def test_empty_or_corrupt_file(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(load_task_stats(folder), {})


if __name__ == '__main__':
    unittest.main()
