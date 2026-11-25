"""게임 전체에서 쓰는 상수.

수치는 docs/psd.md 의 초안 값이다. 플레이테스트하면서 여기 한 곳만 고친다.
단위: 거리 = 맵 픽셀, 시간 = 초, 속도 = 픽셀/초.
"""
import os

# ── 경로 ─────────────────────────────────────────────
GAME_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(GAME_DIR)
RESOURCE_DIR = os.path.join(ROOT_DIR, 'Resource')

# ── 화면 ─────────────────────────────────────────────
SCREEN_W, SCREEN_H = 1280, 720
SPRITE_SCALE = 0.5            # 스프라이트 시트는 0.5배로 그린다 (psd 5.3)
MAX_FRAME_TIME = 0.05         # 프레임이 길게 끊겨도 한 번에 이만큼만 진행

# ── 모아 ─────────────────────────────────────────────
MOA_SPEED = 300               # 이동 속도
MOA_BODY_RADIUS = 28          # 몸 원 반지름 (psd 5.3)
MOA_SPRITE_OFFSET_Y = 20      # 몸 중심에서 그림 중심까지 (그림이 몸보다 위로 올라가 보이게)

# ── 회피 (Space) ── psd 4.4: 대시, 0.3초 무적, 쿨다운 1.0초
DODGE_TIME = 0.3              # 대시 시간 = 무적 시간
DODGE_SPEED = 800             # 대시 속도 → 거리 약 240
DODGE_COOLDOWN = 1.0          # 회피를 시작한 순간부터 센다

# ── 피격 ── psd 4.4: 넉백 + 0.5초 무적
HURT_TIME = 0.2               # 넉백되는 동안 조작 불가
KNOCKBACK_SPEED = 450         # → 거리 약 90
HIT_INVINCIBLE = 0.5
FAINT_RESTART_TIME = 2.0      # 쓰러진 뒤 다시 시작하기까지

# ── 능력치 ── psd 4.7: HP / 공격 / 방어
MOA_BASE_STATS = (45, 12, 10)
MOA_LEVEL = 1
MOA_MAX_LEVEL = 15

# ── 경험치 (임시값, psd 에 수치가 없어 정함) ──
# 다음 레벨까지 필요한 경험치 = EXP_BASE + EXP_PER_LEVEL × 지금 레벨
# 정령을 쓰러뜨리면 얻는 경험치 = EXP_REWARD_BASE + EXP_REWARD_PER_LEVEL × 정령 레벨
EXP_BASE = 20
EXP_PER_LEVEL = 10
EXP_REWARD_BASE = 10
EXP_REWARD_PER_LEVEL = 5

# ── 기술 칸 ── psd 4.2: Q·W 시작, E Lv10, R Lv15
SLOT_KEYS = ('Q', 'W', 'E', 'R')
SLOT_UNLOCK_LEVELS = (1, 1, 10, 15)
MOA_START_SKILLS = (None, None, None, None)       # psd: 기술 0개로 시작, 첫 기술은 토리를 흡수해서 얻음
MOA_SKILL_WINDUP = 0.1        # 모아 기술: 누르고 판정이 켜지기까지 (적은 더 길게 예고)

# ── 숲(필드) 맵 ──
START_FIELD = 'tutorial'      # 처음 시작하는 숲 맵 (Resource/forest_maps)
FIELD_FEET_W = 28             # 숲에서 벽에 막히는 발밑 상자
FIELD_FEET_H = 14
FIELD_FEET_OFFSET = 36        # 몸 중심에서 발밑까지 (그림의 발 위치)
FRUIT_HEAL = 0.3              # 회복 열매: 최대 HP 30% (psd 4.3)
FRUIT_REGROW = 60.0           # 먹은 뒤 다시 열리기까지
FADE_TIME = 0.6               # 숲 ↔ 전투 화면 전환 (어두워지는/밝아지는 시간)
FIELD_ENTRY = {'forest1': (310, 200), 'forest2': (3770, 200)}   # 다른 숲에서 넘어왔을 때 나타나는 자리 (맵 start 는 아래쪽 나무 그늘에 가려짐)

# ── 튜토리얼 (숲 tutorial 에서 시작할 때) ──
TUTORIAL = START_FIELD == 'tutorial'
TUTORIAL_BATTLE_MAP = 'battle_tutorial'   # 토리와 싸우는 빈터 전투 맵
TUTORIAL_TORI_LEVEL = 2                   # 토리 Lv2 (psd 6.1)
TUTORIAL_SURVIVE_TIME = 10.0     # 이만큼 버티면 토리가 타락에 저항 (남은 시간은 보여 주지 않음)
TUTORIAL_FRAGMENT_DIST = 110     # 저항할 때 떨어져 나온 검은 기운이 토리 앞 이만큼에 떨어짐

# ── 숲의 조우 (psd 4.3) ── 수풀 안에서 새 칸에 들어설 때마다 확률(맵 json 의 encounter_rate)로 조우
ENCOUNTERS = {
    # 숲 이름: 전투 맵, 나오는 정령, 레벨 범위, 한 번에 나오는 수
    'forest1': dict(battle_map='battle_forest1', spirits=('thorn', 'dew'), levels=(3, 7), count=(2, 3)),
    'forest2': dict(battle_map='battle_forest2', spirits=('dark_thorn', 'dark_dew'), levels=(10, 13), count=(2, 3)),
}
ENCOUNTER_COOLDOWN = 2.0      # 전투에서 돌아온 뒤 이 시간 동안은 조우하지 않음
BATTLE_END_DELAY = 1.2        # 마지막 정령이 원래 색으로 돌아오고 숲으로 돌아가기까지

# ── 정령 배틀 AI (psd 4.6) ── 정령 종류별 데이터는 spirit.py 의 SPIRITS
SPIRIT_SPEED = 160
SPIRIT_ATTACK_GAP = 0.6       # 기술 사이 짧은 틈
SPIRIT_SKILL_WINDUP = 0.15    # 적 기술: 동작 시작 → 판정 (그 앞에 예고 SPIRIT_TELEGRAPH 가 따로 있음)
SPIRIT_TELEGRAPH = 0.35       # 공격 예고 (머리 위 ❗): 이 동안 보고 피할 수 있다
SPIRIT_MAX_ATTACKERS = 2      # 한 번에 공격(예고·공격 중)할 수 있는 정령 수
SPIRIT_BACKOFF_TIME = 0.4     # 공격 뒤 물러나기 (근접형은 뒤로, 원거리형은 옆으로)
SPIRIT_RETREAT_TIME = 1.5     # 위험(HP 낮음 + 방어 기술 못 씀)하면 거리를 벌리는 시간
SPIRIT_RETREAT_COOLDOWN = 5.0
SPIRIT_LEAD = 0.5             # 원거리 예측 사격: 모아가 움직일 곳을 이만큼만 앞서 노림 (1 = 정확히)
SPIRIT_SPREAD_ANGLE = 70      # 근접형끼리 모아 둘레에서 이 각도(도)보다 붙지 않게 벌어짐 (포위)
SPIRIT_WAIT_RING = 90         # 공격 차례가 아닌 근접형: 사거리보다 이만큼 바깥에서 맴돎
# 적 회피: 모아의 공격이 날아오면 확률로 옆으로 대시 (모아보다 쿨타임 길고 무적 짧게)
SPIRIT_DODGE_CHANCE = 0.4
SPIRIT_DODGE_COOLDOWN = 4.0
SPIRIT_DODGE_TIME = 0.25
SPIRIT_DODGE_SPEED = 620
SPIRIT_NEAR = 200             # "플레이어와 가깝다" = 몸 중심 사이 거리 ≤ 200 (psd 5.3)
SPIRIT_LOW_HP = 0.3           # HP 30% 이하면 방어 기술
RANGED_KEEP = (260, 520)      # 원거리형은 이 거리 사이를 유지 (가까우면 물러나고 멀면 다가감)
SPIRIT_FIRST_DELAY = (0.8, 2.0)   # 전투가 시작되고 첫 기술까지 (여러 마리가 한꺼번에 때리지 않게 흩어 놓음)

# ── 보스 · 실프 (psd 6.3) ── 숲1 → 숲2 길목을 막는다
BOSSES = {
    # 숲 이름: 길목을 막는 상위 정령 (자리는 숲 맵 json 의 boss.pos)
    'forest1': dict(kind='sylph', level=9, battle_map='battle_forest1'),
    'forest2': dict(kind='gnome', level=14, battle_map='battle_forest2'),
}
# 관리자 P (튜토리얼이 끝난 뒤): Lv10 + 기술 + 실프 앞 (보스 범위 바로 밖, 위로 걸으면 보스전)
ADMIN_WARP = dict(field='forest1', pos=(3730, 2470), skills=('thorn_stab', 'dew_shot'))
BOSS_TRIGGER_RADIUS = 260     # 숲에서 이 거리 안으로 들어서면 보스전
BOSS_REWARD_LEVEL = 10        # 관리자 P 워프의 레벨 (실프를 구했을 때와 같은 Lv10). 보스별 보상 레벨은 spirit.SPIRITS 의 reward_level
# 즉사 패턴: HP 50% 이하가 되면 한 번. 실프는 무적, 전방위 즉사 바람 칼날 3번 → "끝이다" → 맵 전체 즉사 폭발
#   마지막 폭발은 폭풍 위에 떠 있어야만 산다
TEMPEST_HP = 0.5
TEMPEST_WAVES = (1.0, 2.6, 4.2)  # 칼날 예고가 시작되는 시각 (패턴 시작 기준)
TEMPEST_FINAL_AT = 5.6        # "끝이다" — 힘을 모으기 시작
TEMPEST_FINAL_CHARGE = 2.2    # 힘을 모으는 시간 → 맵 전체 즉사 폭발
TEMPEST_TIME = 9.2            # 패턴이 끝나는 시각
TEMPEST_WARN = 0.8            # 예고선이 뜨고 칼날이 나가기까지
TEMPEST_BLADES = 8            # 한 번에 쏘는 칼날 수 (전방향, 웨이브마다 반 칸씩 돌아감)
TEMPEST_BLADE_LENGTH = 2400   # 맵 끝까지 닿는 길이
TEMPEST_BLADE_R = 30
# 폭풍: 즉사 패턴 동안 실프 둘레를 돈다. 닿으면 2초간 띄워 올려 무적, 내려오면 그 폭풍은 사라진다
STORM_COUNT = 3
STORM_RADIUS = 34             # 닿는 판정 반지름
STORM_ORBIT = (240, 460)      # 실프에서 떨어진 거리 (이 사이를 오간다)
STORM_SPEED = 0.55            # 도는 빠르기 (rad/s)
STORM_LIFT_TIME = 2.0
STORM_LIFT_HEIGHT = 70        # 띄워 올라가는 높이 (그림만)
# 광폭화: HP 10% 이하가 되면 한 번, 20초 동안 기술 쿨다운 50% 감소
RAGE_HP = 0.1
RAGE_TIME = 20.0
RAGE_COOLDOWN_RATE = 0.5

# ── 보스 · 노움 (psd 6.4) ── 즉사급 = 최대 HP 의 HEAVY_HIT 만큼 (방어 기술로 줄일 수 있음, 실프의 즉사와 다름)
HEAVY_HIT = 0.85
# 대지 균열: HP 70% 이하가 되면 한 번. 모아 둘레 바닥 칸 일부가 깜빡이다 바위 기둥이 솟는다. 3번, 안전한 칸이 매번 바뀜
QUAKE_HP = 0.7
QUAKE_TILE = 240              # 바닥 칸 크기
QUAKE_COLS, QUAKE_ROWS = 7, 5 # 모아를 가운데 두고 깔리는 칸 수
QUAKE_WAVES = (0.8, 2.6, 4.4) # 균열이 생기는 시각 (패턴 시작 기준)
QUAKE_WARN = 1.0              # 균열 → 바위 기둥이 솟기까지
QUAKE_SAFE = (0.45, 0.3, 2)   # 웨이브마다 안전한 칸 (비율, 마지막은 칸 수)
QUAKE_TIME = 6.0

# 적이 맞았을 때: 짧게 밀려나고 하던 공격(예고 중)은 취소. 연속 주먹이 다 맞도록 적은 무적 없음
ENEMY_HURT_TIME = 0.15
ENEMY_KNOCKBACK_SPEED = 300

# ── 흡수 (F) ── psd 4.1
ABSORB_RADIUS = 80            # 검은 기운 흡수 범위 원 반지름 (psd 5.3)
ABSORB_TIME = 0.85            # 모아의 흡수 동작 시간 = 기운이 날아오는 시간
ESSENCE_FLOAT_Y = 40          # 검은 기운이 적 몸 위로 떠 있는 높이

# ── 기술 이펙트 ──
FX_SKIP = 0.06                # 판정이 켜질 때 이펙트의 흐린 첫 프레임을 건너뜀
