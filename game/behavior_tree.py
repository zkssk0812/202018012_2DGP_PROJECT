"""행동 트리 (Behavior Tree). 정령 · 보스의 배틀 AI 를 짠다.

노드는 run() 을 부르면 SUCCESS · FAIL · RUNNING 중 하나를 돌려준다.
    Condition(이름, 함수, *인자)  함수가 참이면 SUCCESS, 아니면 FAIL
    Action(이름, 함수, *인자)     함수가 돌려준 결과 그대로 (여러 프레임 걸리는 동작은 RUNNING)
    Sequence(이름, *노드)         왼쪽부터 차례로. 하나라도 FAIL 이면 FAIL, 모두 SUCCESS 면 SUCCESS.
                                  RUNNING 이 나오면 거기서 멈추고, 다음 프레임에는 그 노드부터 이어서 한다
                                  (앞의 Condition 을 다시 확인하지 않음 → 시작한 동작은 끝까지 한다)
    Selector(이름, *노드)         왼쪽(우선순위 높음)부터 확인해 FAIL 이 아닌 첫 노드의 결과.
                                  매 프레임 처음부터 다시 확인하므로, 높은 우선순위(피격 · 기절 등)가
                                  진행 중인 낮은 우선순위 동작을 끊을 수 있다. 끊긴 노드는 reset() 된다.
BehaviorTree(루트).run() 을 매 프레임 한 번 부른다.
"""

SUCCESS, FAIL, RUNNING = 'SUCCESS', 'FAIL', 'RUNNING'


class Node:
    def __init__(self, name):
        self.name = name

    def run(self):
        raise NotImplementedError

    def reset(self):
        """진행 중이던 것을 잊는다 (끊겼을 때)."""

    def lines(self, depth=0):
        """트리 모양 (문서 · 디버그용)."""
        return ['    ' * depth + f'{type(self).__name__} {self.name}']


class Condition(Node):
    def __init__(self, name, func, *args):
        super().__init__(name)
        self.func, self.args = func, args

    def run(self):
        return SUCCESS if self.func(*self.args) else FAIL


class Action(Node):
    def __init__(self, name, func, *args):
        super().__init__(name)
        self.func, self.args = func, args

    def run(self):
        result = self.func(*self.args)
        assert result in (SUCCESS, FAIL, RUNNING), f'{self.name}: {result!r}'
        return result


class Composite(Node):
    def __init__(self, name, *children):
        super().__init__(name)
        self.children = list(children)
        self.running = None              # RUNNING 을 돌려준 자식 번호

    def reset(self):
        if self.running is not None:
            self.children[self.running].reset()
        self.running = None

    def lines(self, depth=0):
        out = super().lines(depth)
        for c in self.children:
            out += c.lines(depth + 1)
        return out


class Sequence(Composite):
    def run(self):
        start = self.running or 0
        for i in range(start, len(self.children)):
            result = self.children[i].run()
            if result == RUNNING:
                self.running = i
                return RUNNING
            if result == FAIL:
                self.running = None
                return FAIL
        self.running = None
        return SUCCESS


class Selector(Composite):
    def run(self):
        for i, child in enumerate(self.children):
            result = child.run()
            if result == FAIL:
                continue
            if self.running is not None and self.running != i:
                self.children[self.running].reset()          # 더 높은(또는 다른) 가지가 끼어듦
            self.running = i if result == RUNNING else None
            return result
        if self.running is not None:
            self.children[self.running].reset()
        self.running = None
        return FAIL


class BehaviorTree:
    def __init__(self, root):
        self.root = root

    def run(self):
        return self.root.run()

    def reset(self):
        self.root.reset()

    def __str__(self):
        return '\n'.join(self.root.lines())
