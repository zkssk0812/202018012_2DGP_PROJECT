"""stats.py 단위 테스트: psd 4.7 / 6.2 표의 값과 맞는지 확인한다."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stats import stats_at, damage


class StatsTest(unittest.TestCase):
    def test_moa_table(self):
        self.assertEqual(stats_at((45, 12, 10), 1), (45, 12, 10))
        self.assertEqual(stats_at((45, 12, 10), 10), (86, 23, 19))
        self.assertEqual(stats_at((45, 12, 10), 15), (108, 29, 24))

    def test_spirit_table(self):
        self.assertEqual(stats_at((40, 10, 8), 7), (64, 16, 13))       # 가시몽 Lv7
        self.assertEqual(stats_at((80, 13, 11), 9), (144, 23, 20))     # 실프 Lv9
        self.assertEqual(stats_at((90, 16, 14), 14), (207, 37, 32))    # 노움 Lv14

    def test_damage(self):
        self.assertEqual(damage(40, 12, 10), 12)       # 가시몽 Lv3 할퀴기 → 모아 Lv1
        self.assertEqual(damage(1, 1, 100), 1)         # 최소 1


if __name__ == '__main__':
    unittest.main()
