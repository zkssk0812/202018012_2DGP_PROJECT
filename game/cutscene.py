"""짧은 연출 장면: 정해진 시간에 할 일(events)과 말풍선(lines)을 차례로 보여 준다.

장면이 도는 동안 플레이어 입력은 막고, J 로 건너뛸 수 있다 (남은 할 일은 모두 바로 실행).
    events: [(시간, 함수)]
    lines:  [(시작, 끝, 말하는 쪽, 대사)]   말하는 쪽: 캐릭터 객체(x, y) 또는 'banner'(화면 가운데 큰 글씨)
"""
from pico2d import draw_rectangle

import ui
from config import SCREEN_W, SCREEN_H

BAR_H = 64                    # 위아래 검은 띠 높이


class Cutscene:
    def __init__(self, length, events, lines, on_end):
        self.length = length
        self.events = sorted(events, key=lambda e: e[0])
        self.lines = lines
        self.on_end = on_end
        self.time = 0.0
        self.next_event = 0
        self.done = False

    def _fire_until(self, t):
        while self.next_event < len(self.events) and self.events[self.next_event][0] <= t:
            self.events[self.next_event][1]()
            self.next_event += 1

    def update(self, dt):
        if self.done:
            return
        self.time += dt
        self._fire_until(self.time)
        if self.time >= self.length:
            self.finish()

    def skip(self):
        if not self.done:
            self._fire_until(float('inf'))
            self.finish()

    def finish(self):
        self.done = True
        self.on_end()

    # ── 그리기 ──────────────────────────────────────
    def draw_world(self, camera):
        """캐릭터 머리 위 말풍선."""
        for t0, t1, who, text in self.lines:
            if t0 <= self.time < t1 and who != 'banner':
                sx, sy = camera.to_screen(who.x, who.y)
                bubble(sx, sy + 90, text)

    def draw_overlay(self):
        """위아래 검은 띠, 가운데 큰 글씨, 건너뛰기 안내."""
        draw_rectangle(0, SCREEN_H - BAR_H, SCREEN_W, SCREEN_H, 0, 0, 0, filled=True)
        draw_rectangle(0, 0, SCREEN_W, BAR_H, 0, 0, 0, filled=True)
        for t0, t1, who, text in self.lines:
            if t0 <= self.time < t1 and who == 'banner':
                ui.text(SCREEN_W / 2 - len(text) * 13, SCREEN_H / 2 + 120, text, 28, (255, 220, 230))
        ui.text(SCREEN_W - 150, BAR_H / 2, 'J : 건너뛰기', 15, (170, 170, 170))


def bubble(cx, bottom, text):
    """말풍선: (cx, bottom) 이 꼬리 끝. 글자 수로 폭을 어림한다."""
    w = 28 + len(text) * 17
    h = 38
    x, y = cx - w / 2, bottom + 10
    draw_rectangle(x, y, x + w, y + h, 250, 250, 255, filled=True)
    draw_rectangle(x, y, x + w, y + h, 90, 70, 120)
    for k in range(8):                              # 꼬리 (아래로 좁아지는 삼각형)
        half = 8 - k
        draw_rectangle(cx - half, y - k - 1, cx + half, y - k, 250, 250, 255, filled=True)
    ui.text(x + 14, y + h / 2, text, 17, (40, 30, 60))
