"""ui.py 의 조사 붙이기 테스트."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui import eul


class EulTest(unittest.TestCase):
    def test_no_final_consonant(self):
        self.assertEqual(eul('할퀴기'), '할퀴기를')

    def test_final_consonant(self):
        self.assertEqual(eul('이슬탄'), '이슬탄을')
        self.assertEqual(eul('물방울막'), '물방울막을')


if __name__ == '__main__':
    unittest.main()
