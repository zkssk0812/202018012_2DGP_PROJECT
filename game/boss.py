"""상위 정령(보스). 지금은 숲1 의 바람의 상위 정령 실프 (psd 6.3).

평소에는 일반 정령의 원거리형 AI 를 그대로 쓴다 (바람탄 · 독바람탄 · 세 갈래 바람 · 바람 칼날, 회피).
여기에 특별 패턴 두 가지가 더해진다.

즉사 패턴 (HP 50% 이하가 되면 한 번, 약 9초)
    · 실프는 그 자리에 떠서 무적이 된다.
    · 전방위(8갈래)로 예고선이 뜨고, 0.8초 뒤 맵 끝까지 닿는 즉사 바람 칼날이 나간다. 3번.
      매번 반 칸씩 돌아가서, 칼날 사이 빈틈이 바뀐다 (한 번은 모아 쪽이 빈틈, 다음엔 모아 쪽에 칼날).
    · 3번 쏜 뒤 "끝이다...!" — 2.2초 동안 힘을 모으고(화면이 어두워지며 맥박), 맵 전체를 터뜨린다.
      이 폭발은 어디에 있든 즉사. 폭풍 위에 떠 있어야만 산다.
    · 실프 둘레를 폭풍 3개가 돈다. 폭풍에 닿으면 2초 동안 띄워 올라가 무적 (조작 불가),
      내려오면 그 폭풍은 사라진다. 힘을 모으는 동안 올라탄 폭풍은 폭발이 지나갈 때까지 내려주지 않는다.
광폭화 (HP 10% 이하가 되면 한 번, 20초)
    · 기술 쿨다운이 50% 줄어든다. 발밑에 붉은 오라.

행동 트리 (Spirit 의 트리에 보스 패턴 가지 하나 추가, 피격보다 우선):
    Sequence 즉사 패턴 : HP 50% 이하가 됐나? (한 번) → 즉사 패턴 (약 9초 RUNNING, 그동안 무적)
광폭화는 행동이 아니라 상태 변화라 매 프레임 update 에서 확인한다.
"""
import math
import random

import combat
from attack import Attack
from collision import Capsule
from cutscene import bubble
from pico2d import draw_rectangle
from sdl2 import SDL_SetRenderDrawBlendMode, SDL_BLENDMODE_BLEND
import pico2d

from config import (TEMPEST_HP, TEMPEST_TIME, TEMPEST_WAVES, TEMPEST_WARN, TEMPEST_BLADES,
                    TEMPEST_FINAL_AT, TEMPEST_FINAL_CHARGE, SCREEN_W, SCREEN_H,
                    TEMPEST_BLADE_LENGTH, TEMPEST_BLADE_R, STORM_COUNT, STORM_RADIUS, STORM_ORBIT,
                    STORM_SPEED, STORM_LIFT_TIME, RAGE_HP, RAGE_TIME, RAGE_COOLDOWN_RATE)
from effect import Effect
from skills import combat_fx_length
from behavior_tree import Sequence, Action, Condition, SUCCESS, RUNNING
from spirit import Spirit

STORM_SCALE = 0.6           # 폭풍 그림 크기
STORM_GROW = 0.4            # 생길 때 커지는 시간
FLASH_TIME = 1.0            # 맵 전체 폭발 섬광이 사라지는 시간


class Storm:
    """즉사 패턴 동안 실프 둘레를 도는 폭풍. 닿은 모아를 띄워 올리고, 내려오면 사라진다."""

    def __init__(self, owner, angle, phase):
        self.owner = owner
        self.angle = angle
        self.phase = phase
        self.time = 0.0
        self.carrying = None
        self.done = False
        self.fx = Effect('boss', 'storm', owner.x, owner.y, scale=STORM_SCALE)
        self.place()

    def place(self):
        lo, hi = STORM_ORBIT
        r = lo + (hi - lo) * (0.5 + 0.5 * math.sin(self.time * 0.9 + self.phase))
        area = self.owner.battle_map
        x = self.owner.x + math.cos(self.angle) * r
        y = self.owner.y + math.sin(self.angle) * r
        self.x, self.y = area.clamp(x, y, STORM_RADIUS)

    @property
    def sort_y(self):
        return self.y + 1                       # 같은 자리의 모아(띄워진)보다 뒤에 그림

    def update(self, dt, moa):
        self.time += dt
        self.fx.update(dt)
        if self.carrying:                       # 모아를 띄운 채 멈춰 있다가, 내려오면 사라짐
            if moa.state != 'lifted' or moa.lift_storm is not self:
                self.vanish()
            return
        self.angle += STORM_SPEED * dt
        self.place()
        if (moa and not moa.is_down and moa.state != 'lifted'
                and math.hypot(moa.x - self.x, moa.y - self.y) < STORM_RADIUS + moa.radius):
            if moa.lift_by(self):
                self.carrying = moa

    def vanish(self):
        if not self.done:
            self.done = True
            combat.add_effect(Effect('monster', 'wind_hit', self.x, self.y + 30, scale=1.2))

    def draw(self, camera):
        grow = min(1.0, self.time / STORM_GROW)
        self.fx.x, self.fx.y = self.x, self.y - 6
        self.fx.scale = self.fx.scale_y = STORM_SCALE * grow
        self.fx.draw(camera)


class Sylph(Spirit):
    def __init__(self, kind, level, x, y, area, target):
        self.tempest_done = False
        super().__init__(kind, level, x, y, area, target)
        self.rage_done = False
        self.rage_time = 0.0
        self.storms = []
        self.waves = []             # 이번 패턴의 웨이브: [시작 시각, 예고 했나, 쐈나, 각도들]
        self.final = None           # 마지막 폭발: None → 'charge'(힘 모으기) → 'done'
        self.flash = 0.0            # 폭발 섬광 남은 시간
        self.speech, self.speech_time = '', 0.0   # 머리 위 말풍선
        self.aura = Effect('boss', 'rage_aura', x, y, scale=0.85)               # 실프 뒤 (뒤쪽 불꽃 · 바닥 빛)
        self.aura_front = Effect('boss', 'rage_aura_front', x, y, scale=0.85)   # 실프 앞 (앞쪽 불꽃)

    def world_objects(self):
        return self.storms

    def pattern_branches(self):
        return [Sequence('즉사 패턴', Condition('HP 50% 이하가 됐나', self.want_tempest),
                         Action('즉사 패턴', self.do_tempest))]

    @property
    def is_invincible(self):
        return super().is_invincible or self.act == 'tempest'

    @property
    def raging(self):
        return self.rage_time > 0

    def cooldown_rate(self):
        return RAGE_COOLDOWN_RATE if self.raging else 1.0

    def pattern_text(self):
        """HUD 에 보여 줄 지금 패턴 (없으면 None)."""
        if self.act == 'tempest':
            if self.final == 'charge':
                return f'폭풍 위로!  {max(0.0, self.blast_at - self.state_time):.1f}초', (255, 80, 160)
            return '즉사 패턴', (255, 120, 200)
        if self.raging:
            return f'광폭화  {self.rage_time:.0f}초', (255, 90, 90)
        return None

    def say(self, text, duration=3.0):
        if self.notify:
            self.notify(text, duration)

    # ── 매 프레임 ────────────────────────────────────
    def update(self, dt):
        self.check_patterns()
        if self.raging:
            self.rage_time = max(0.0, self.rage_time - dt)
            if self.rage_time == 0:
                self.say('실프의 광폭화가 풀렸다', 2.0)
        self.flash = max(0.0, self.flash - dt)
        self.speech_time = max(0.0, self.speech_time - dt)
        super().update(dt)
        for st in self.storms:
            st.update(dt, self.opponent)
        self.storms = [st for st in self.storms if not st.done]
        if self.raging:
            self.aura.update(dt)
            self.aura_front.update(dt)

    def check_patterns(self):
        """광폭화: HP 10% 이하 (즉사 패턴 중이 아닐 때, 한 번)."""
        if self.is_down or self.held or self.act == 'tempest':
            return
        if not self.rage_done and self.hp <= self.max_hp * RAGE_HP:
            self.rage_done = True
            self.rage_time = RAGE_TIME
            for s in self.skill_cd:                     # 남은 쿨다운도 바로 반으로
                self.skill_cd[s] *= RAGE_COOLDOWN_RATE
            self.say('실프가 광폭화했다! (기술이 더 자주 나온다)', 3.0)

    # ── 즉사 패턴 ────────────────────────────────────
    def want_tempest(self):
        return not self.tempest_done and not self.held and self.hp <= self.max_hp * TEMPEST_HP

    def start_tempest(self):
        self.tempest_done = True
        self.cancel_pending()
        self.dots.clear()
        self.look_at_target()
        self.sprite.play('idle', self.face)
        self.waves = [[t, False, False, None] for t in TEMPEST_WAVES]
        self.final = None
        self.blast_at = TEMPEST_FINAL_AT + TEMPEST_FINAL_CHARGE
        a0 = random.uniform(0, math.tau)
        self.storms = [Storm(self, a0 + k * math.tau / STORM_COUNT, k * 2.1) for k in range(STORM_COUNT)]
        combat.add_effect(Effect('monster', 'warn_glint', self.x, self.y + 70, scale=1.6))
        self.say('실프: "다가오지 마!"  — 즉사 칼날! 빈틈·회피·폭풍으로 버티자', 3.5)

    def exit_tempest(self):
        self.shake = 0.0
        for st in self.storms:                          # 모아를 띄우고 있는 폭풍만 남긴다
            if not st.carrying:
                st.vanish()
        self.gap = 1.0

    def do_tempest(self):
        if self.begin('tempest'):
            self.start_tempest()
        t = self.state_time
        self.shake = 1.5
        for w in self.waves:
            start, warned, fired, angles = w
            if not warned and t >= start:
                w[1] = True
                w[3] = self.blade_angles(self.waves.index(w))
                for a in w[3]:
                    combat.add_effect(Effect('boss', 'blade_warn', self.x, self.y, a,
                                             scale=TEMPEST_BLADE_LENGTH / 256, scale_y=1.0,
                                             lifetime=TEMPEST_WARN))
                self.sprite.play('attack', self.face, restart=True)
            if warned and not fired and t >= start + TEMPEST_WARN:
                w[2] = True
                for a in w[3]:
                    self.fire_blade(a)
        if self.final is None and t >= TEMPEST_FINAL_AT:
            self.start_final()
        if self.final == 'charge':
            self.hold_riders()
            if t >= self.blast_at:
                self.blast()
        if self.sprite.done:
            self.sprite.play('idle', self.face)
        if t >= TEMPEST_TIME:
            self.shake = 0.0
            return SUCCESS                              # 다음 행동이 시작될 때 exit_tempest 로 정리
        return RUNNING

    # ── 마지막: 맵 전체 폭발 ──────────────────────────
    def start_final(self):
        self.final = 'charge'
        self.shake = 4.0
        self.speech, self.speech_time = '끝이다...!', TEMPEST_FINAL_CHARGE
        combat.add_effect(Effect('boss', 'final_charge', self.x, self.y + 20, scale=1.1,
                                 follow=self, offset_y=20, lifetime=TEMPEST_FINAL_CHARGE))
        combat.add_effect(Effect('monster', 'warn_glint', self.x, self.y + 80, scale=2.0))
        self.say('맵 전체가 터진다! 폭풍 위로 피하자!', TEMPEST_FINAL_CHARGE)

    def hold_riders(self):
        """힘을 모으는 동안 폭풍에 올라탄 모아는 폭발이 지나갈 때까지 내려오지 않는다."""
        for st in self.storms:
            moa = st.carrying
            if moa and moa.state == 'lifted':
                need = moa.state_time + (self.blast_at - self.state_time) + 0.5
                moa.lift_end = max(moa.lift_end, need)

    def blast(self):
        """맵 전체 즉사. 폭풍 위에 떠 있으면(lifted) 산다."""
        self.final = 'done'
        self.shake = 1.5
        self.flash = FLASH_TIME
        combat.add_effect(Effect('boss', 'final_burst', self.x, self.y, scale=6.0))    # 화면을 덮는 충격파
        moa = self.opponent
        if moa and not moa.is_down and moa.state != 'lifted':
            moa.guard_time = 0.0
            moa.apply_damage(moa.hp)                    # (관리자 무적이면 0)
            combat.add_effect(Effect('monster', 'wind_hit', moa.x, moa.y, scale=1.6))

    def draw_top(self, camera):
        """캐릭터 · 앞쪽 나무 위에 그리는 것: 힘 모으기 어둠, 폭발 섬광, 말풍선."""
        if self.act == 'tempest' and self.final == 'charge':
            k = min(1.0, (self.state_time - TEMPEST_FINAL_AT) / TEMPEST_FINAL_CHARGE)
            screen_fill((40, 0, 40), 0.15 + 0.35 * k + 0.08 * math.sin(self.state_time * 14))   # 점점 어두워지며 맥박
        if self.flash > 0:
            screen_fill((255, 225, 245), 0.95 * self.flash / FLASH_TIME)
        if self.speech_time > 0 and not self.is_down:
            sx, sy = camera.to_screen(self.x, self.y)
            w = 28 + len(self.speech) * 17
            sx = max(w / 2 + 10, min(SCREEN_W - w / 2 - 10, sx))           # 화면 밖으로 나가지 않게
            bubble(sx, max(80, min(sy + 100, SCREEN_H - 190)), self.speech)

    def blade_angles(self, i):
        """웨이브 i 의 칼날 방향. 짝수 웨이브는 모아가 빈틈에, 홀수 웨이브는 모아 쪽에 칼날."""
        step = math.tau / TEMPEST_BLADES
        base = self.angle_to_target() + (step / 2 if i % 2 == 0 else 0.0)
        return [base + k * step for k in range(TEMPEST_BLADES)]

    def fire_blade(self, a):
        cap = Capsule.from_origin(self.x, self.y, a, TEMPEST_BLADE_LENGTH, TEMPEST_BLADE_R)
        atk = Attack(self, cap, power=None, delay=0.0, active=0.2, skill_id='tempest_blade',
                     hit_fx='wind_hit')
        atk.lethal = True
        combat.add_attack(atk)
        cell = combat_fx_length('monster', 'wind_blade')
        combat.add_effect(Effect('monster', 'wind_blade', self.x, self.y, a,
                                 scale=TEMPEST_BLADE_LENGTH / cell, scale_y=0.8))

    # ── 그리기 ──────────────────────────────────────
    def draw(self, camera):
        raging = self.raging and not self.is_down
        if raging:
            self.aura.x, self.aura.y = self.x, self.y - 26          # 발밑 고리
            self.aura.draw(camera)
        super().draw(camera)
        if raging:
            self.aura_front.x, self.aura_front.y = self.x, self.y - 26
            self.aura_front.draw(camera)


def screen_fill(color, alpha):
    """화면 전체를 반투명 색으로 덮는다."""
    SDL_SetRenderDrawBlendMode(pico2d.pico2d.renderer, SDL_BLENDMODE_BLEND)
    draw_rectangle(0, 0, SCREEN_W, SCREEN_H, *color, int(255 * max(0.0, min(1.0, alpha))), filled=True)
