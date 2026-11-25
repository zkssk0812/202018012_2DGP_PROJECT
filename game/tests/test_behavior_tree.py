"""행동 트리 노드의 동작 확인."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from behavior_tree import (BehaviorTree, Selector, Sequence, Action, Condition,
                           SUCCESS, FAIL, RUNNING)


class Counter:
    """n 번 RUNNING 뒤 SUCCESS 를 돌려주는 동작."""
    def __init__(self, n):
        self.n, self.calls, self.resets = n, 0, 0

    def __call__(self):
        self.calls += 1
        return SUCCESS if self.calls > self.n else RUNNING


class TestNodes(unittest.TestCase):
    def test_condition(self):
        self.assertEqual(Condition('t', lambda: True).run(), SUCCESS)
        self.assertEqual(Condition('f', lambda: False).run(), FAIL)

    def test_sequence_all_success(self):
        seq = Sequence('s', Action('a', lambda: SUCCESS), Action('b', lambda: SUCCESS))
        self.assertEqual(seq.run(), SUCCESS)

    def test_sequence_stops_at_fail(self):
        hit = []
        seq = Sequence('s', Condition('no', lambda: False), Action('a', lambda: hit.append(1) or SUCCESS))
        self.assertEqual(seq.run(), FAIL)
        self.assertEqual(hit, [])

    def test_sequence_resumes_running_child_without_rechecking(self):
        checks = []
        work = Counter(2)
        seq = Sequence('s', Condition('c', lambda: checks.append(1) or True), Action('w', work))
        self.assertEqual(seq.run(), RUNNING)
        self.assertEqual(seq.run(), RUNNING)
        self.assertEqual(seq.run(), SUCCESS)
        self.assertEqual(len(checks), 1)            # 조건은 처음에만

    def test_selector_first_non_fail(self):
        sel = Selector('x', Condition('no', lambda: False), Action('yes', lambda: SUCCESS))
        self.assertEqual(sel.run(), SUCCESS)

    def test_selector_all_fail(self):
        sel = Selector('x', Condition('a', lambda: False), Condition('b', lambda: False))
        self.assertEqual(sel.run(), FAIL)

    def test_selector_higher_priority_interrupts_running(self):
        urgent = [False]
        slow = Counter(10)
        low = Sequence('low', Condition('go', lambda: True), Action('slow', slow))
        sel = Selector('root', Sequence('high', Condition('urgent', lambda: urgent[0]),
                                        Action('react', lambda: SUCCESS)), low)
        self.assertEqual(sel.run(), RUNNING)
        self.assertEqual(low.running, 1)
        urgent[0] = True
        self.assertEqual(sel.run(), SUCCESS)        # 높은 우선순위가 끼어듦
        self.assertIsNone(low.running)              # 끊긴 동작은 처음부터

    def test_tree_str(self):
        tree = BehaviorTree(Selector('root', Action('a', lambda: SUCCESS)))
        self.assertIn('Selector root', str(tree))
        self.assertIn('Action a', str(tree))


if __name__ == '__main__':
    unittest.main()
