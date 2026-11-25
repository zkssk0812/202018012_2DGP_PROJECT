"""디버깅용 관리자 모드 (psd 4.8).

T 로 켜고 끈다. 켜져 있으면 화면 구석에 ADMIN 을 띄우고 arena 와 공격 판정 도형을 그린다.
U 로 피격 범위(몸 원)를 붉은색으로 보여 준다. 관리자 모드와 따로 켜고 끈다.
관리자 모드에서만: G = 전투 중 상대 즉사(기절), K = 기술 선택 창,
                 1 / 2 = (숲, 튜토리얼이 끝난 뒤) 실프 앞 (Lv10) / 노움 앞 (Lv18) 으로 이동 + 기술 준비,
                 I = 무적 켜기/끄기 (모아가 공격 · 즉사 · 지속 피해를 받지 않음. 관리자 모드를 끄면 같이 꺼짐).
"""
from pico2d import draw_rectangle

import ui
from config import SCREEN_W, SCREEN_H

enabled = False
show_hurtbox = False
god = False                # 무적 (관리자 모드가 켜져 있을 때만 효과)


def toggle():
    global enabled
    enabled = not enabled


def toggle_god():
    global god
    if enabled:
        god = not god


def is_god():
    """지금 모아가 무적인지."""
    return enabled and god


def toggle_hurtbox():
    global show_hurtbox
    show_hurtbox = not show_hurtbox


def draw_label():
    """오른쪽 아래(기술 칸 옆)에 관리자 모드 안내. 화면 위의 보스 HP 바를 가리지 않게."""
    if ui.font(16):
        x, y = SCREEN_W - 400, 126
        ui.text(x, y, 'ADMIN' + ('   무적 ON' if god else ''), 18, (255, 230, 0) if not god else (255, 140, 120))
        ui.text(x, y - 24, 'G 즉사 · K 기술 선택 · U 피격 범위', 15, (255, 230, 0))
        ui.text(x, y - 44, '1 실프 앞 · 2 노움 앞 · I 무적', 15, (255, 230, 0))
    else:                                  # 글꼴이 없으면 노란 네모로 표시
        draw_rectangle(10, SCREEN_H - 30, 80, SCREEN_H - 10, 255, 230, 0)
