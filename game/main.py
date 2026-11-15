"""텅 빈 정령 — 실행 진입점.

실행: 프로젝트 폴더에서  python game/main.py
"""
from pico2d import open_canvas, close_canvas

import game_framework
import battle_mode
import field_mode
from config import SCREEN_W, SCREEN_H, TUTORIAL


def main():
    open_canvas(SCREEN_W, SCREEN_H)
    game_framework.run(field_mode if TUTORIAL else battle_mode)   # 튜토리얼이면 숲에서 시작
    close_canvas()


if __name__ == '__main__':
    main()
