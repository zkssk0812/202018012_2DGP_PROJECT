"""모드(장면) 스택과 메인 루프.

각 모드 모듈은 init / finish / handle_events / update / draw 를 가진다.
update 에는 지난 프레임에서 흐른 시간(frame_time, 초)을 넘긴다.
"""
from pico2d import clear_canvas, update_canvas, get_time, delay

from config import MAX_FRAME_TIME

running = False
stack = []
frame_time = 0.0


def change_mode(mode):
    if stack:
        stack.pop().finish()
    stack.append(mode)
    mode.init()


def push_mode(mode):
    stack.append(mode)
    mode.init()


def pop_mode():
    if stack:
        stack.pop().finish()


def quit():
    global running
    running = False


def run(start_mode):
    global running, frame_time
    running = True
    stack.append(start_mode)
    start_mode.init()

    last = get_time()
    while running and stack:
        now = get_time()
        frame_time = min(now - last, MAX_FRAME_TIME)
        last = now

        mode = stack[-1]
        mode.handle_events()
        mode.update(frame_time)
        clear_canvas()
        mode.draw()
        update_canvas()
        delay(0.001)

    while stack:
        stack.pop().finish()
