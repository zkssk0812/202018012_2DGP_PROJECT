"""텅 빈 정령 — 실행 진입점.

실행: 프로젝트 폴더에서  python game/main.py
"""
from pico2d import open_canvas, close_canvas

import game_framework
import battle_mode
from config import SCREEN_W, SCREEN_H


def main():
    open_canvas(SCREEN_W, SCREEN_H)
    game_framework.run(battle_mode)
    close_canvas()


if __name__ == '__main__':
    main()
