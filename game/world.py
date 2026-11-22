"""모드(숲 ↔ 전투)를 오가도 이어지는 게임 상태.

모아는 한 번만 만들고, 숲과 전투 맵을 오갈 때 같은 모아를 옮겨 쓴다 (HP · 레벨 · 경험치 · 기술 칸 유지).
"""
from config import START_FIELD

moa = None
current_field = START_FIELD  # 지금 있는(돌아갈) 숲 맵 이름
field_return = None          # 전투에서 돌아올 숲 위치 (x, y). None 이면 맵의 시작 위치
encounter = None             # 지금 전투의 정보 dict(battle_map, spirits=[(종류, 레벨), ...]). 튜토리얼은 None
defeated = False             # 전투에서 쓰러져 돌아왔는지 (숲에서 알림용)
cleared = set()              # 구한 보스 (정령 종류). 구하면 그 숲의 다음 길이 열린다
boss_saved = None            # 방금 구한 보스 (숲으로 돌아가면 이야기 연출, 그 뒤 None)
arrive_notice = None         # 숲에 들어섰을 때 띄울 알림 (보스를 구했을 때, 관리자 워프 등)


def get_moa(area, x, y):
    """모아를 (처음이면 만들어서) area 의 (x, y) 에 둔다."""
    global moa
    if moa is None:
        from moa import Moa
        moa = Moa(x, y, area)
    else:
        moa.enter_area(area, x, y)
    return moa
