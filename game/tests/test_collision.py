"""collision.py 단위 테스트.

실행: 프로젝트 폴더에서  python -m unittest discover game/tests
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collision import Circle, Sector, Capsule, angle_diff, point_segment_distance, separate


class Body:
    def __init__(self, x, y, radius):
        self.x, self.y, self.radius = x, y, radius


class CircleTest(unittest.TestCase):
    def test_touching_counts_as_hit(self):
        self.assertTrue(Circle(0, 0, 60).hits(100, 0, 40))       # 거리 100 = 60 + 40

    def test_apart(self):
        self.assertFalse(Circle(0, 0, 60).hits(101, 0, 40))


class SectorTest(unittest.TestCase):
    def setUp(self):
        self.s = Sector(0, 0, 120, 0.0, math.radians(90))        # 할퀴기: 오른쪽, 90°

    def test_in_front(self):
        self.assertTrue(self.s.hits(150, 0, 40))                  # 거리 150 ≤ 120 + 40

    def test_too_far(self):
        self.assertFalse(self.s.hits(170, 0, 40))

    def test_edge_angle(self):
        d = 100
        inside = math.radians(44)
        outside = math.radians(46)
        self.assertTrue(self.s.hits(d * math.cos(inside), d * math.sin(inside), 40))
        self.assertFalse(self.s.hits(d * math.cos(outside), d * math.sin(outside), 40))

    def test_behind(self):
        self.assertFalse(self.s.hits(-100, 0, 40))

    def test_body_covering_origin(self):
        self.assertTrue(self.s.hits(-20, 0, 40))                  # 뒤쪽이어도 꼭짓점을 덮으면 맞음

    def test_wraps_around_pi(self):
        left = Sector(0, 0, 120, math.pi, math.radians(90))
        self.assertTrue(left.hits(-100, -10, 40))
        self.assertTrue(left.hits(-100, 10, 40))


class CapsuleTest(unittest.TestCase):
    def setUp(self):
        self.c = Capsule.from_origin(0, 0, 0.0, 700, 25)         # 빛줄기: 오른쪽, 길이 700

    def test_on_line(self):
        self.assertTrue(self.c.hits(400, 0, 40))

    def test_side_distance(self):
        self.assertTrue(self.c.hits(400, 65, 40))                 # 65 = 25 + 40
        self.assertFalse(self.c.hits(400, 66, 40))

    def test_past_end(self):
        self.assertTrue(self.c.hits(765, 0, 40))
        self.assertFalse(self.c.hits(766, 0, 40))

    def test_behind_start(self):
        self.assertFalse(self.c.hits(-70, 0, 40))


class HelperTest(unittest.TestCase):
    def test_angle_diff(self):
        self.assertAlmostEqual(angle_diff(math.radians(170), math.radians(-170)), math.radians(20))
        self.assertAlmostEqual(angle_diff(0, math.pi), math.pi)

    def test_point_segment_degenerate(self):
        self.assertAlmostEqual(point_segment_distance(3, 4, 0, 0, 0, 0), 5)

    def test_separate(self):
        a, b = Body(0, 0, 40), Body(60, 0, 40)
        separate(a, b)
        self.assertAlmostEqual(b.x - a.x, 80)
        self.assertAlmostEqual(a.y, 0)

    def test_separate_same_point(self):
        a, b = Body(10, 10, 40), Body(10, 10, 40)
        separate(a, b)
        self.assertAlmostEqual(math.hypot(b.x - a.x, b.y - a.y), 80)


if __name__ == '__main__':
    unittest.main()
