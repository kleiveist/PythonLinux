#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mini-Spaceshooter in einer Datei – modular aufgebaut
"""
import curses
import random
import time

# ── Konfiguration ────────────────────────────────────────────────────────────
FPS                 = 60
TARGET_DT           = 1.0 / FPS
SPACESHIP_SYMBOL    = "===>"
SHIELD_PICKUP_SYM   = "=[)(]="
SHIELD_SPAWN_CHANCE = 0.004      # pro Frame
SHIELD_COOLDOWN     = 5.0       # Sekunden

ASTEROID_SMALL      = ["#", "##", "###", "####", "#####"]
ASTEROID_BIG_X      = ["####", "##", "#", "###", "#####"]
ASTEROID_BIG_Y      = ["####", "##", "#", "###", "#####"]

NEUTRON_STAR_SPRITE = [
    "  OOOO  ",
    " OOOOOO ",
    "OOOOOOOO",
    "OOOOOOOO",
    "OOOOOOOO",
    "OOOOOOOO",
    " OOOOOO ",
    "  OOOO  "
]

# ── Basis-Entity ─────────────────────────────────────────────────────────────
class Entity:
    def __init__(self, x: int, y: int, symbol: str):
        self.x, self.y = x, y
        self.symbol    = symbol  # kann auch multi-line sein

    def move(self, dx=0, dy=0):
        self.x += dx
        self.y += dy

    def draw(self, scr: curses.window):
        h, w = scr.getmaxyx()
        if isinstance(self.symbol, list):        # mehrzeilig (Neutron-Star)
            for i, row in enumerate(self.symbol):
                ry = self.y + i
                if 0 <= ry < h and 0 <= self.x < w:
                    try:
                        scr.addstr(ry, self.x, row)
                    except curses.error:
                        pass
        else:                                    # einzeilig
            if 0 <= self.y < h and 0 <= self.x < w:
                try:
                    scr.addstr(self.y, self.x, self.symbol)
                except curses.error:
                    pass

# ── Spezielle Entities ───────────────────────────────────────────────────────
class Spaceship(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, SPACESHIP_SYMBOL)
        self.shield   = 0
        self.god_mode = False
        self.key_buf  = []

    def toggle_god(self):
        self.god_mode = not self.god_mode
        if self.god_mode:
            self.shield = 3

class Asteroid(Entity):
    """h = 1 kleiner, h = 2 großer (2-zeiliger) Asteroid"""
    def __init__(self, x, y, h=1):
        if h == 1:
            sym = random.choice(ASTEROID_SMALL)
            super().__init__(x, y, sym)
        else:
            sx = random.choice(ASTEROID_BIG_X)
            sy = random.choice(ASTEROID_BIG_Y)
            super().__init__(x, y, [sx, sy])
        self.h = h

class ShieldPickup(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, SHIELD_PICKUP_SYM)

class Stream(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, "///")

class NeutronStar(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, NEUTRON_STAR_SPRITE)

# ── Haupt-Game-Klasse ────────────────────────────────────────────────────────
class Game:
    def __init__(self, scr: curses.window):
        self.scr = scr
        curses.curs_set(0)
        self.scr.nodelay(True)
        self.h, self.w = self.scr.getmaxyx()

        # Spielobjekte
        self.ship      = Spaceship(self.w // 2, self.h // 2)
        self.asteroids = []
        self.pickups   = []
        self.streams   = []
        self.star      = None

        # Timing / Status
        self.start_time        = time.perf_counter()
        self.last_shield_spawn = self.start_time - SHIELD_COOLDOWN
        self.star_used         = False
        self.second_star_used  = False

    # ── Spawner ────────────────────────────────────────────────────────────
    def spawn_shield(self, now):
        if (now - self.last_shield_spawn >= SHIELD_COOLDOWN and
                random.random() < SHIELD_SPAWN_CHANCE):
            y = random.randint(1, self.h - 2)
            self.pickups.append(ShieldPickup(self.w - len(SHIELD_PICKUP_SYM) - 1, y))
            self.last_shield_spawn = now

    def spawn_asteroid(self, elapsed: float):
        # 0–25 s: 20 % Dust-Phase (nur '#')
        if 3 <= elapsed < 25:
            if random.random() < 0.2:                      # hier 0.5 = 50 %; änderbar auf 0.1–1.0
                y = random.randint(1, self.h - 2)
                a = Asteroid(self.w - 2, y, h=1)
                a.symbol = "#"                            # zwingt '#'
                self.asteroids.append(a)
            return
        # 25–60 s: 50 % Mini
        if 25 <= elapsed < 60:
            if random.random() < 0.3:
                y = random.randint(1, self.h-2)
                self.asteroids.append(Asteroid(self.w-2, y, h=1))
            return
        # 60–80 s: 20 % Große
        if 60 <= elapsed < 80:
            if random.random() < 0.2:
                y = random.randint(1, self.h-3)
                self.asteroids.append(Asteroid(self.w-6, y, h=2))
            return
        # 80–100 s: 80 % Mini
        if 80 <= elapsed < 98:
            if random.random() < 0.5:
                y = random.randint(1, self.h-2)
                self.asteroids.append(Asteroid(self.w-2, y, h=1))
            return
        # 100–125 s: 100 % Dust-Phase (nur '#')
        if 100 <= elapsed < 130:
            if random.random() < 0.4:                      # hier 1.0 = 100 %; änderbar auf 0.1–1.0
                y = random.randint(1, self.h - 2)
                a = Asteroid(self.w - 2, y, h=1)
                a.symbol = "#"                            # zwingt '#'
                self.asteroids.append(a)
            return
        # 125–150 s: 100 % Mini-Asteroiden
        if 140 <= elapsed < 150:
            if random.random() < 0.6:               # <- hier auf 0.8 ändern für 80 %
                y = random.randint(1, self.h-2)
                self.asteroids.append(Asteroid(self.w-2, y, h=1))
            return
        # 150–155 s: 100 % Große Asteroiden
        if 150 <= elapsed < 155:
            if random.random() < 0.5:               # <- hier 0.5 für 50 %, etc.
                y = random.randint(1, self.h-3)
                self.asteroids.append(Asteroid(self.w-6, y, h=2))
            return
        # 100–125 s: 100 % Dust-Phase (nur '#')
        if 160 <= elapsed < 182:
            if random.random() < 0.4:                      # hier 1.0 = 100 %; änderbar auf 0.1–1.0
                y = random.randint(1, self.h - 2)
                a = Asteroid(self.w - 2, y, h=1)
                a.symbol = "#"                            # zwingt '#'
                self.asteroids.append(a)
            return
        # 190–200 s: 100 % Große Asteroiden
        if 185 <= elapsed < 200:
            if random.random() < 0.4:               # <- ebenfalls anpassbar
                y = random.randint(1, self.h-3)
                self.asteroids.append(Asteroid(self.w-6, y, h=2))
            return
        # 100–125 s: 100 % Dust-Phase (nur '#')
        if 202 <= elapsed < 250:
            if random.random() < 0.4:                      # hier 1.0 = 100 %; änderbar auf 0.1–1.0
                y = random.randint(1, self.h - 2)
                a = Asteroid(self.w - 2, y, h=1)
                a.symbol = "#"                            # zwingt '#'
                self.asteroids.append(a)
            return
        # 125–150 s: 100 % Mini-Asteroiden
        if 210 <= elapsed < 300:
            if random.random() < 0.4:               # <- hier auf 0.8 ändern für 80 %
                y = random.randint(1, self.h-2)
                self.asteroids.append(Asteroid(self.w-2, y, h=1))
            return
        # 100–125 s: 100 % Dust-Phase (nur '#')
        if 300 <= elapsed < 1200:
            if random.random() < 1.4:                      # hier 1.0 = 100 %; änderbar auf 0.1–1.0
                y = random.randint(1, self.h - 2)
                a = Asteroid(self.w - 2, y, h=1)
                a.symbol = "#"                            # zwingt '#'
                self.asteroids.append(a)
            return
    def spawn_neutron_star(self, elapsed):
        # erster Spawn ab 135 s
        if not self.star_used and elapsed >= 135:
            self.star = NeutronStar(self.w, 1)
            self.star_used = True
            self.streams.clear()
        # zweiter Spawn ab 180 s
        if not self.second_star_used and elapsed >= 180:
            self.star = NeutronStar(self.w, 1)
            self.second_star_used = True
            self.streams.clear()
        # Dritter Spawn ab 220 s
        if not self.second_star_used and elapsed >= 220:
            self.star = NeutronStar(self.w, 1)
            self.second_star_used = True
            self.streams.clear()
        # Spawn ab 310 s
        if not self.second_star_used and elapsed >= 310:
            self.star = NeutronStar(self.w, 1)
            self.second_star_used = True
            self.streams.clear()
        # Spawn ab 312 s
        if not self.second_star_used and elapsed >= 312:
            self.star = NeutronStar(self.w, 1)
            self.second_star_used = True
            self.streams.clear()

    # ── Eingabe ─────────────────────────────────────────────────────────────
    def handle_input(self):
        key = self.scr.getch()
        if key == curses.KEY_UP and self.ship.y > 1:
            self.ship.move(dy=-1)
        elif key == curses.KEY_DOWN and self.ship.y < self.h - 2:
            self.ship.move(dy=1)
        elif key == ord('q'):
            return False
        elif key != -1:
            self.ship.key_buf.append(key)
            if len(self.ship.key_buf) > 3:
                self.ship.key_buf.pop(0)
            if self.ship.key_buf == [ord('g'), ord('o'), ord('d')]:
                self.ship.toggle_god()
                self.ship.key_buf.clear()
        return True

    # ── Bewegung / Bereinigung ──────────────────────────────────────────────
    def update_objects(self):
        for a in self.asteroids:
            a.move(dx=-1)
        for p in self.pickups:
            p.move(dx=-1)
        for s in self.streams:
            s.move(dy=1)

        # Neutron-Star Bewegung + Stream-Spawn
        if self.star:
            self.star.move(dx=-1)
            if self.star.x + len(self.star.symbol[0]) < 0:
                self.star = None
                self.streams.clear()
            else:
                for col in range(len(self.star.symbol[0])):
                    if random.random() < 0.3:
                        self.streams.append(Stream(self.star.x + col,
                                                   self.star.y + len(self.star.symbol)))

        # Off-Screen entfernen
        self.asteroids = [a for a in self.asteroids
                          if a.x + (len(a.symbol[0]) if a.h == 2 else len(a.symbol)) - 1 >= 0]
        self.pickups   = [p for p in self.pickups if p.x + len(p.symbol) - 1 >= 0]
        self.streams   = [s for s in self.streams if s.y < self.h]

    # ── Kollisionslogik ─────────────────────────────────────────────────────
    def check_collisions(self):
        # Shield-Pickup
        for p in self.pickups[:]:
            if (p.y == self.ship.y and
                    not (p.x + len(p.symbol) - 1 < self.ship.x or
                         p.x > self.ship.x + len(self.ship.symbol) - 1)):
                self.ship.shield = min(3, self.ship.shield + 1)
                self.pickups.remove(p)

        # Streams (vom Neutron-Star)
        for s in self.streams[:]:
            if s.y == self.ship.y and self.ship.x <= s.x < self.ship.x + len(self.ship.symbol):
                if self.ship.shield < 3 and not self.ship.god_mode:
                    return True
                else:
                    self.ship.shield = 0
                    self.streams.clear()
                    break

        # Asteroiden
        for a in self.asteroids[:]:
            rows = ([ (a.y, a.symbol) ] if a.h == 1
                    else [ (a.y, a.symbol[0]), (a.y + 1, a.symbol[1]) ])
            for ry, sym in rows:
                if ry != self.ship.y:
                    continue
                if not (a.x + len(sym) - 1 < self.ship.x or
                        a.x > self.ship.x + len(self.ship.symbol) - 1):
                    if self.ship.god_mode:
                        self.ship.shield = 3
                        self.asteroids.remove(a)
                    elif self.ship.shield > 0:
                        self.ship.shield -= 1
                        self.asteroids.remove(a)
                    else:
                        return True
                    break
        return False

    # ── Rendering ───────────────────────────────────────────────────────────
    def draw_hud(self, elapsed):
        timer = time.strftime("%M:%S", time.gmtime(elapsed))
        self.scr.addstr(0, self.w - len(timer) - 1, timer)
        if self.ship.god_mode:
            txt = "GODMODE AKTIV"
            self.scr.addstr(1, self.w - len(txt) - 1, txt)

    def draw(self, elapsed):
        self.scr.clear()
        self.draw_hud(elapsed)

        # Entities
        if self.star:
            self.star.draw(self.scr)
        for obj in self.asteroids + self.pickups + self.streams + [self.ship]:
            obj.draw(self.scr)

        # Schild-Balken
        if self.ship.shield > 0:
            bar = ")" * self.ship.shield
            sx  = self.ship.x + len(self.ship.symbol) + 1
            if sx + len(bar) < self.w:
                self.scr.addstr(self.ship.y, sx, bar)

        self.scr.refresh()

    # ── Haupt-Loop ──────────────────────────────────────────────────────────
    def run(self):
        prev_time = time.perf_counter()
        while True:
            now     = time.perf_counter()
            dt      = now - prev_time
            prev_time = now
            elapsed = now - self.start_time

            if not self.handle_input():
                break
            self.spawn_shield(now)
            self.spawn_asteroid(elapsed)
            self.spawn_neutron_star(elapsed)

            self.update_objects()
            if self.check_collisions():
                self.scr.addstr(self.h//2, self.w//2 - 4, "BOOM!")
                self.scr.refresh()
                time.sleep(1)
                break

            self.draw(elapsed)

            # Framerate begrenzen
            sleep = TARGET_DT - (time.perf_counter() - now)
            if sleep > 0:
                time.sleep(sleep)

# ── Einstieg ────────────────────────────────────────────────────────────────
def main(stdscr):
    Game(stdscr).run()

if __name__ == "__main__":
    curses.wrapper(main)
