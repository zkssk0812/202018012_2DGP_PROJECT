"""디버깅용 관리자 모드 (psd 4.8).

T 로 켜고 끈다. 켜져 있으면 화면 구석에 ADMIN 을 띄우고 arena 와 공격 판정 도형을 그린다.
U 로 피격 범위(몸 원)를 붉은색으로 보여 준다. 관리자 모드와 따로 켜고 끈다.
관리자 모드에서만: G = 전투 중 상대 즉사(기절), K = 기술 선택 창,
                 P = (숲, 튜토리얼이 끝난 뒤) Lv10 + 가시찌르기 · 이슬탄 + 실프 앞으로 이동.
"""
from pico2d import draw_rectangle

import ui
from config import SCREEN_H

enabled = False
show_hurtbox = False


def toggle():
    global enabled
    enabled = not enabled


def toggle_hurtbox():
    global show_hurtbox
    show_hurtbox = not show_hurtbox


def draw_label():
    if ui.font(18):
        ui.text(14, SCREEN_H - 20, 'ADMIN   G 즉사 · K 기술 선택 · U 피격 범위 · P 실프 앞으로', 18, (255, 230, 0))
    else:                                  # 글꼴이 없으면 노란 네모로 표시
        draw_rectangle(10, SCREEN_H - 30, 80, SCREEN_H - 10, 255, 230, 0)
