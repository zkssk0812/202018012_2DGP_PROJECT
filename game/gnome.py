"""바위의 상위 정령 노움 (숲2 보스, psd 6.4). 행동 트리로 싸운다.

평소에는 일반 정령의 근접형 행동 트리를 그대로 쓴다 (돌진 박치기 · 흙먼지 회오리 · 연속 주먹 · 내려찍기).
바위라서 회피는 하지 않는다. 특별 패턴은 Spirit 트리의 '보스 패턴 가지'로 더해진다.
"""
from spirit import Spirit


class Gnome(Spirit):
    def pattern_text(self):
        """HUD 에 보여 줄 지금 패턴 (없으면 None)."""
        return None
