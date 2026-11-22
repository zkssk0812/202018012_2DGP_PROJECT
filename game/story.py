"""숲에서 보여 주는 이야기 연출의 대사 (psd 2.3 · 6.3).

대본 한 줄: (말하는 쪽, 대사, 보여 주는 시간[, 이 줄이 시작될 때 할 일 이름])
    말하는 쪽: 'moa' · 'boss' (그 숲의 상위 정령) · 'banner' (화면 위 큰 글씨)
    할 일 이름은 연출을 만드는 쪽(field_mode)이 함수로 바꾼다. 예) 'shake', 'glint', 'calm'
build() 가 대본을 Cutscene 에 넣을 대사 목록 (시작, 끝, 말하는 쪽, 대사) 과 할 일 목록으로 바꾼다.
"""

LINE_GAP = 0.25              # 대사 사이 틈
START = 0.5                  # 첫 대사까지

# 실프 · 보스전 전 (숲1 → 숲2 길목)
SYLPH_BEFORE = [
    ('boss', '...', 1.3),
    ('boss', '......', 1.3),
    ('boss', '아이야... 너는 이곳을 지나갈 수 없단다.', 2.6),
    ('moa', '실프님...? 저는 이 길을 지나가야 해요!', 2.4),
    ('boss', '이 너머엔 대정령님의 분노가 소용돌이치고 있단다.', 2.8),
    ('boss', '너처럼 작은 정령은 금세 삼켜지고 말 거야.', 2.6),
    ('moa', '그래도 갈 거예요! 모두를 구할 거예요!', 2.4),
    ('moa', '토리도 구했는걸요. 실프님도 꼭 구해 드릴게요!', 2.6),
    ('boss', '...어쩔 수 없구나.', 2.0, 'shake'),
    ('boss', '그 각오가 진짜인지, 이 바람으로 시험해 주마!', 2.6, 'glint'),
    ('banner', '바람의 상위 정령 실프', 2.0),
]

# 실프 · 보스전 뒤 (구하고 숲으로 돌아왔을 때)
SYLPH_AFTER = [
    ('boss', '......', 1.3, 'calm'),
    ('boss', '...따뜻한 바람이구나. 검은 기운이 걷혔어.', 2.6),
    ('boss', '고맙다, 아이야. 오랜만에 숨을 쉬는 것 같구나.', 2.6),
    ('moa', '실프님! 이 너머엔 대체 무슨 일이 있는 거예요?', 2.6),
    ('boss', '숲의 대정령님께서 분노에 삼켜지셨단다.', 2.6),
    ('boss', '그 분노가 숲의 정령들을 검게 물들이고 있지.', 2.6),
    ('boss', '다음 숲은 바위의 정령 노움이 지키고 있을 게다.', 2.6),
    ('boss', '그 아이도 아마... 검은 기운에 붙잡혀 있겠지.', 2.6),
    ('moa', '노움도 꼭 구할게요. 대정령님도요!', 2.4),
    ('boss', '...그래. 네 바람이라면 닿을지도 모르겠구나.', 2.6),
    ('boss', '조심하거라...', 2.0),
    ('moa', '네! 다녀올게요, 실프님!', 2.0, 'step_aside'),
    ('banner', '숲2로 가는 길이 열렸다', 2.0),
]


def build(script, actors):
    """대본 → (lines, events, 길이). actors: {'moa': 객체, 'boss': 객체, 할 일 이름: 함수}"""
    lines, events = [], []
    t = START
    for row in script:
        who, text, dur = row[:3]
        if len(row) > 3 and row[3] in actors:
            events.append((t, actors[row[3]]))
        lines.append((t, t + dur, who if who == 'banner' else actors[who], text))
        t += dur + LINE_GAP
    return lines, events, t + 0.2


# 보스 종류 → 대본
BOSS_STORY = {
    'sylph': dict(before=SYLPH_BEFORE, after=SYLPH_AFTER),
}
