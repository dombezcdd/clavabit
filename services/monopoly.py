# -*- coding: utf-8 -*-
"""Монополия: игровой движок (без Telegram). Упрощённые правила: покупка улиц, аренда, наборы и дома,
«Шанс», тюрьма, банкротство. Игроки: люди (ходят по кнопкам) и боты (ходят сами)."""

import random
import time

GROUPS = {
    "brown": ("#8b5a2b", 50), "lblue": ("#6cc6ff", 50), "pink": ("#ff7ac0", 100), "orange": ("#ff9f43", 100),
    "red": ("#ff5252", 150), "yellow": ("#ffe14d", 150), "green": ("#37c871", 200), "blue": ("#4a6cff", 200),
}


def _p(g, n, p):
    return {"t": "prop", "g": g, "n": n, "p": p}


TILES = [
    {"t": "start", "n": "СТАРТ"}, _p("brown", "Бульвар", 60), {"t": "chance", "n": "Шанс"}, _p("brown", "Переулок", 60),
    {"t": "tax", "n": "Налог", "amt": 150}, {"t": "station", "n": "Вокзал", "p": 200}, _p("lblue", "Набережная", 100),
    {"t": "jail", "n": "Тюрьма"}, _p("lblue", "Парк", 120), _p("pink", "Арбат", 140), {"t": "util", "n": "Электро", "p": 150},
    _p("pink", "Тверская", 160), {"t": "chance", "n": "Шанс"}, _p("orange", "Невский", 180), {"t": "parking", "n": "Отдых"},
    _p("orange", "Садовая", 200), _p("red", "Покровка", 220), {"t": "station", "n": "Аэропорт", "p": 200}, _p("red", "Петровка", 240),
    {"t": "chance", "n": "Шанс"}, _p("yellow", "Лубянка", 260), {"t": "gojail", "n": "В тюрьму"}, _p("yellow", "Маросейка", 280),
    {"t": "util", "n": "Водоканал", "p": 150}, _p("green", "Рублёвка", 300), _p("green", "Патриаршие", 320),
    _p("blue", "Кутузовский", 350), _p("blue", "Красная пл.", 400),
]
N = len(TILES)
CARDS = [
    {"t": "Банковская ошибка в вашу пользу: +150", "m": 150}, {"t": "Штраф за парковку: −60", "m": -60},
    {"t": "Конкурс красоты, вы победили: +100", "m": 100}, {"t": "Оплатите ремонт: −120", "m": -120},
    {"t": "Идите на СТАРТ и получите +200", "go": 0}, {"t": "Отправляйтесь в тюрьму!", "jail": True},
    {"t": "Вперёд на 3 клетки", "mv": 3}, {"t": "Назад на 3 клетки", "mv": -3},
    {"t": "День рождения: каждый дарит вам по 30", "each": 30}, {"t": "Благотворительность: заплатите каждому по 20", "pay_each": 20},
    {"t": "Идите к ближайшему вокзалу", "st": True},
]
RENT = [1, 2, 5, 15, 45, 80, 125]   # множители цены/30: нет набора, набор, 1-4 дома, отель
START_CASH, SALARY, JAIL_FINE = 1500, 200, 50
SEAT_COLORS = ["#e74c3c", "#3498db", "#2ecc71", "#f1c40f", "#9b59b6", "#e67e22"]


class Player:
    def __init__(self, pid, name, human):
        self.id, self.name, self.human = pid, name, human
        self.cash, self.pos, self.jail, self.dead, self.dbl = START_CASH, 0, 0, False, 0
        self.risk = 0.4 + random.random() * 0.5   # осторожность бота при покупках
        self.skips = 0                            # подряд пропущенных по времени ходов


class Game:
    def __init__(self, players, max_rounds=25, rng=None):
        """players: [(id, name, human)]"""
        self.rng = rng or random
        self.players = [Player(*x) for x in players]
        self.owner, self.houses = {}, {}
        self.turn, self.round, self.max_rounds = 0, 1, max_rounds
        self.phase, self.pending, self.winner = "roll", None, None
        self.dice, self.events, self.again = (0, 0), [], False
        self.last_act = time.time()
        self._start_turn()

    # ---------- запросы ----------
    def cur(self):
        return self.players[self.turn]

    def by_id(self, pid):
        return next((p for p in self.players if p.id == pid), None)

    def seat(self, p):
        return self.players.index(p)

    def say(self, t):
        self.events.append(t)

    def take_events(self):
        ev, self.events = self.events, []
        return ev

    def alive(self):
        return [p for p in self.players if not p.dead]

    def group(self, g):
        return [i for i, t in enumerate(TILES) if t.get("g") == g]

    def has_set(self, pid, g):
        return all(self.owner.get(i) == pid for i in self.group(g))

    def count_owned(self, pid, kind):
        return sum(1 for i, t in enumerate(TILES) if t["t"] == kind and self.owner.get(i) == pid)

    def rent(self, i, dsum=7):
        t, o = TILES[i], self.owner[i]
        if t["t"] == "station":
            return 25 * 2 ** (self.count_owned(o, "station") - 1)
        if t["t"] == "util":
            return dsum * (10 if self.count_owned(o, "util") == 2 else 4)
        h = self.houses.get(i, 0)
        lvl = 1 + h if h else (1 if self.has_set(o, t["g"]) else 0)
        return round(t["p"] / 30 * RENT[lvl])

    def worth(self, p):
        w = p.cash
        for i, t in enumerate(TILES):
            if self.owner.get(i) == p.id:
                w += t["p"] / 2 + self.houses.get(i, 0) * GROUPS[t["g"]][1] / 2 if t.get("g") else t["p"] / 2
        return w

    def house_cost(self, i):
        return GROUPS[TILES[i]["g"]][1]

    def can_build(self, pid, i):
        p, t = self.by_id(pid), TILES[i]
        if self.phase not in ("roll", "jail") or p is not self.cur() or not t.get("g"):
            return False
        if self.owner.get(i) != pid or not self.has_set(pid, t["g"]):
            return False
        h = self.houses.get(i, 0)
        if h >= 5 or p.cash < self.house_cost(i):
            return False
        return h <= min(self.houses.get(j, 0) for j in self.group(t["g"]))

    def build_options(self, pid):
        return [i for i in range(N) if self.can_build(pid, i)]

    # ---------- деньги ----------
    def _liquidate(self, p, need):
        mine = [i for i in range(N) if self.owner.get(i) == p.id]
        for i in sorted((i for i in mine if self.houses.get(i)), key=lambda k: -self.houses[k]):
            while self.houses.get(i, 0) > 0 and p.cash < need:
                self.houses[i] -= 1
                p.cash += self.house_cost(i) // 2
        for i in mine:
            if p.cash >= need:
                break
            if not self.houses.get(i):
                del self.owner[i]
                p.cash += TILES[i]["p"] // 2
                self.say(f"{p.name} продаёт «{TILES[i]['n']}» банку")

    def _pay(self, p, amt, to=None):
        if p.cash < amt:
            self._liquidate(p, amt)
        if p.cash >= amt:
            p.cash -= amt
            if to:
                to.cash += amt
            return True
        if to:
            to.cash += max(0, p.cash)
        for i in range(N):
            if self.owner.get(i) == p.id:
                if to:
                    self.owner[i] = to.id
                else:
                    del self.owner[i]
                self.houses[i] = 0
        p.cash, p.dead = 0, True
        self.say(f"💀 {p.name} банкрот!")
        return False

    def forfeit(self, pid):
        """Игрок вышел или заснул: его имущество возвращается банку."""
        p = self.by_id(pid)
        if not p or p.dead:
            return
        for i in range(N):
            if self.owner.get(i) == p.id:
                del self.owner[i]
                self.houses[i] = 0
        p.cash, p.dead = 0, True
        self.say(f"🚪 {p.name} выходит из игры")
        if p is self.cur() and self.phase != "over":
            self.again = False
            self._end_turn()

    # ---------- ход ----------
    def _start_turn(self):
        p = self.cur()
        self.pending, self.again = None, False
        self.phase = "jail" if p.jail > 0 else "roll"

    def _end_turn(self):
        w = self._check_end()
        if w:
            return self._finish(w)
        while True:
            self.turn = (self.turn + 1) % len(self.players)
            if self.turn == 0:
                self.round += 1
            if not self.players[self.turn].dead:
                break
        w = self._check_end()
        if w:
            return self._finish(w)
        self._start_turn()

    def _check_end(self):
        left = self.alive()
        if len(left) == 1:
            return left[0]
        if not any(p.human for p in left):
            return max(left, key=self.worth)
        if self.round > self.max_rounds:
            return max(left, key=self.worth)
        return None

    def _finish(self, w):
        self.winner, self.phase = w, "over"
        self.say(f"🏆 Побеждает {w.name}!")

    def _after_land(self):
        p = self.cur()
        if self.phase == "over":
            return
        if p.dead or not self.again or p.jail > 0:
            return self._end_turn()
        self.pending, self.phase = None, "roll"
        self.say(f"🎲 {p.name} выбросил дубль и ходит ещё раз")

    def _move(self, p, steps):
        d = -1 if steps < 0 else 1
        for _ in range(abs(steps)):
            p.pos = (p.pos + d) % N
            if d > 0 and p.pos == 0:
                p.cash += SALARY
                self.say(f"{p.name} проходит СТАРТ: +${SALARY}")

    def _to_jail(self, p):
        p.pos, p.jail, p.dbl = 7, 3, 0
        self.again = False
        self.say(f"🔒 {p.name} отправляется в тюрьму")

    def _bot_wants_buy(self, p, i):
        t = TILES[i]
        completes = t.get("g") and all(self.owner.get(j) == p.id for j in self.group(t["g"]) if j != i)
        return p.cash - t["p"] >= 200 * (1.1 - p.risk) or (completes and p.cash - t["p"] >= 40)

    def _land(self, p, dsum, depth=0):
        i = p.pos
        t = TILES[i]
        self.say(f"{p.name} → «{t['n']}»")
        if t["t"] in ("prop", "station", "util"):
            o = self.owner.get(i)
            if o is None:
                if p.cash < t["p"]:
                    self.say(f"{p.name}: не хватает денег на «{t['n']}» (${t['p']})")
                elif p.human:
                    self.phase, self.pending = "buy", i
                    return
                elif self._bot_wants_buy(p, i):
                    self._buy(p, i)
            elif o != p.id:
                r = self.rent(i, dsum)
                owner = self.by_id(o)
                self.say(f"{p.name} платит {owner.name} аренду ${r}")
                self._pay(p, r, owner)
        elif t["t"] == "tax":
            self.say(f"{p.name} платит налог ${t['amt']}")
            self._pay(p, t["amt"])
        elif t["t"] == "gojail":
            self._to_jail(p)
        elif t["t"] == "chance":
            c = self.rng.choice(CARDS)
            self.say("❓ " + c["t"])
            if "m" in c:
                if c["m"] > 0:
                    p.cash += c["m"]
                else:
                    self._pay(p, -c["m"])
            elif "go" in c:
                self._move(p, (N - p.pos) % N)
            elif c.get("jail"):
                self._to_jail(p)
            elif "mv" in c and depth < 2:
                self._move(p, c["mv"])
                self._land(p, 7, depth + 1)
                return
            elif c.get("st") and depth < 2:
                k = 0
                while TILES[(p.pos + k) % N]["t"] != "station":
                    k += 1
                self._move(p, k)
                self._land(p, 7, depth + 1)
                return
            elif "each" in c:
                for o in self.alive():
                    if o is not p:
                        d = min(c["each"], max(0, o.cash))
                        o.cash -= d
                        p.cash += d
            elif "pay_each" in c:
                for o in self.alive():
                    if o is not p and not p.dead:
                        self._pay(p, c["pay_each"], o)
        if self.phase != "buy":
            self._after_land()

    def _buy(self, p, i):
        p.cash -= TILES[i]["p"]
        self.owner[i] = p.id
        self.say(f"💰 {p.name} покупает «{TILES[i]['n']}» за ${TILES[i]['p']}")

    # ---------- действия игрока ----------
    def _roll_dice(self):
        self.dice = (self.rng.randint(1, 6), self.rng.randint(1, 6))
        return self.dice

    def act_roll(self):
        """Бросок кубиков (фаза roll)."""
        if self.phase != "roll":
            return
        p = self.cur()
        a, b = self._roll_dice()
        dbl = a == b
        self.say(f"🎲 {p.name}: {a}+{b}={a + b}")
        p.dbl = p.dbl + 1 if dbl else 0
        if p.dbl >= 3:
            self.say("Три дубля подряд!")
            self._to_jail(p)
            return self._end_turn()
        self.again = dbl
        self._move(p, a + b)
        self._land(p, a + b)

    def act_buy(self, yes):
        if self.phase != "buy":
            return
        p, i = self.cur(), self.pending
        if yes and p.cash >= TILES[i]["p"]:
            self._buy(p, i)
        else:
            self.say(f"{p.name} отказывается от покупки")
        self.pending = None
        self.phase = "roll"
        self._after_land()

    def act_jail(self, pay):
        if self.phase != "jail":
            return
        p = self.cur()
        if pay and p.cash >= JAIL_FINE:
            self._pay(p, JAIL_FINE)
            p.jail = 0
            self.say(f"{p.name} откупается из тюрьмы за ${JAIL_FINE}")
            self.phase = "roll"
            return
        a, b = self._roll_dice()
        self.say(f"🎲 {p.name} в тюрьме: {a}+{b}")
        if a == b:
            p.jail = 0
            self.say(f"{p.name} выбросил дубль и выходит")
            self.again = False
            self._move(p, a + b)
            return self._land(p, a + b)
        p.jail -= 1
        if p.jail == 0:
            self._pay(p, JAIL_FINE)
            self.say(f"{p.name} отсидел срок и заплатил штраф ${JAIL_FINE}")
        else:
            self.say(f"{p.name} остаётся в тюрьме (осталось ходов: {p.jail})")
        self.again = False
        self._end_turn()

    def act_build(self, pid, i):
        if not self.can_build(pid, i):
            return False
        p = self.by_id(pid)
        p.cash -= self.house_cost(i)
        self.houses[i] = self.houses.get(i, 0) + 1
        self.say(f"🏠 {p.name} строит на «{TILES[i]['n']}» (−${self.house_cost(i)})")
        return True

    def settle(self):
        """Проверяет конец игры (например, после выхода игрока)."""
        if self.phase != "over":
            w = self._check_end()
            if w:
                self._finish(w)

    # ---------- боты ----------
    def _bot_build(self, p):
        for _ in range(2):
            opts = [i for i in self.build_options(p.id) if p.cash - self.house_cost(i) >= 250]
            if not opts:
                break
            self.act_build(p.id, self.rng.choice(opts))

    def run_bots(self, limit=300):
        """Играет за ботов, пока не дойдёт очередь до человека или игра не закончится."""
        while self.phase != "over" and not self.cur().human and limit > 0:
            limit -= 1
            p = self.cur()
            if self.phase == "roll":
                self._bot_build(p)
                self.act_roll()
            elif self.phase == "jail":
                self.act_jail(p.cash > 500)
            elif self.phase == "buy":
                self.act_buy(True)
        return self.take_events()
