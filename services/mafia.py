# -*- coding: utf-8 -*-
"""Мафия: движок игры (чистый Python, без Telegram). Роли, ночь, голосование, победа."""

import random

MIN_PLAYERS, MAX_PLAYERS = 5, 12

# ключ: (название, эмодзи, команда, описание способности)
ROLES = {
    "mafia":  ("Мафия", "🔫", "mafia", "Каждую ночь вместе с командой выбираешь жертву. Днём притворяйся мирным."),
    "don":    ("Дон мафии", "🎩", "mafia", "Глава мафии. Комиссар видит тебя как мирного жителя."),
    "jason":  ("Джейсон Вурхис", "🪓", "solo", "Маньяк-одиночка. Убиваешь каждую ночь, доктор тебя не остановит. "
                                               "Первое линчевание не убьёт тебя, но выдаст. Победа: остаться последним."),
    "freddy": ("Фредди Крюгер", "😈", "solo", "Убийца снов. Каждую ночь усыпляешь одного: он теряет ночное действие. "
                                              "Две ночи подряд одного и того же — кошмар убивает. Победа: остаться последним."),
    "comm":   ("Комиссар", "🕵️", "town", "Каждую ночь проверяешь одного игрока: мафия, убийца или мирный."),
    "doc":    ("Доктор", "💉", "town", "Каждую ночь лечишь одного от пули мафии (себя — один раз). От Джейсона не спасёшь."),
    "beauty": ("Красотка", "💃", "town", "Каждую ночь отвлекаешь одного игрока: он не сможет действовать."),
    "witch":  ("Ведьма", "🧙", "town", "Одно зелье спасения и одно зелье яда на всю игру."),
    "hunter": ("Охотник", "🏹", "town", "Если тебя убьют или повесят, ты успеваешь выстрелить в любого."),
    "civ":    ("Мирный житель", "🙂", "town", "Ночью спишь, днём ищешь мафию и голосуешь."),
}
NIGHT_ROLES = {"mafia", "don", "jason", "freddy", "comm", "doc", "beauty", "witch"}
KILL_TEXT = {
    "mafia": "🔫 Выстрелы в темноте: {n} ({r}) не пережил(а) ночь.",
    "jason": "🪓 Ночью слышали цепь и топор… {n} ({r}) найден(а) мёртвым(ой). Это Вурхис.",
    "nightmare": "😈 {n} ({r}) не проснулся(ась). Кошмар оказался смертельным.",
    "poison": "🧪 {n} ({r}) отравлен(а) зельем.",
    "lynch": "⚖️ Город повесил {n} ({r}).",
    "hunter": "🏹 Предсмертный выстрел охотника сразил {n} ({r}).",
}


def assign_roles(n, horror=True):
    order = ["mafia", "comm", "doc", "civ", "civ", "beauty", "jason" if horror else "civ", "don", "witch",
             "freddy" if horror else "civ", "hunter", "mafia"]
    roles = order[:n]
    while len(roles) < n:
        roles.append("civ")
    random.shuffle(roles)
    return roles


class Player:
    def __init__(self, uid, name, role="civ"):
        self.uid, self.name, self.role, self.alive = uid, name, role, True
        self.doc_self = False           # доктор уже лечил себя
        self.heal_used = False          # ведьма: зелье спасения
        self.poison_used = False        # ведьма: зелье яда
        self.spared = False             # Джейсон: пережил первое линчевание

    @property
    def team(self):
        return ROLES[self.role][2]

    @property
    def title(self):
        return ROLES[self.role][0]


class Game:
    def __init__(self, gid, chat_id, host, host_name):
        self.gid, self.chat_id, self.host = gid, chat_id, host
        self.players = {host: Player(host, host_name)}
        self.phase = "lobby"
        self.horror = True
        self.day = 0
        self.actions = {}              # ночные действия: uid -> (код, цель)
        self.votes = {}                # дневные голоса: uid -> цель или 0 (воздержался)
        self.dream_prev = None         # кого Фредди усыплял прошлой ночью
        self.msg_id = None
        self.task = None
        self.started_at = 0.0
        self.hunter_pending = []
        self.hunter_choice = {}
        self.night_ev = self.vote_ev = self.hunter_ev = None

    # ---------- состав ----------
    def add(self, uid, name):
        if self.phase != "lobby" or uid in self.players or len(self.players) >= MAX_PLAYERS:
            return False
        self.players[uid] = Player(uid, name)
        return True

    def remove(self, uid):
        if self.phase == "lobby" and uid in self.players and uid != self.host:
            del self.players[uid]
            return True
        return False

    def start(self):
        roles = assign_roles(len(self.players), self.horror)
        for p, r in zip(self.players.values(), roles):
            p.role = r
        self.phase = "night"
        self.day = 1

    def alive(self):
        return [p for p in self.players.values() if p.alive]

    def alive_ids(self):
        return [p.uid for p in self.alive()]

    def by_role(self, role):
        return [p for p in self.alive() if p.role == role]

    def mafia_team(self):
        return [p for p in self.alive() if p.team == "mafia"]

    # ---------- кто должен действовать ночью ----------
    def night_actors(self):
        out = []
        for p in self.alive():
            if p.role in NIGHT_ROLES:
                if p.role == "witch" and p.heal_used and p.poison_used:
                    continue
                out.append(p.uid)
        return out

    def targets_for(self, p):
        """Список допустимых целей ночью для роли."""
        ids = self.alive_ids()
        if p.role in ("mafia", "don"):
            return [u for u in ids if self.players[u].team != "mafia"]
        if p.role in ("jason", "freddy", "comm", "beauty"):
            return [u for u in ids if u != p.uid]
        if p.role == "doc":
            return [u for u in ids if u != p.uid or not p.doc_self]
        if p.role == "witch":
            return [u for u in ids if u != p.uid]
        return []

    def set_action(self, uid, code, target):
        if self.phase != "night" or uid not in self.players or not self.players[uid].alive:
            return False
        p = self.players[uid]
        if code in ("k", "j", "f", "c", "d", "b", "wp"):
            if target not in self.targets_for(p):
                return False
        self.actions[uid] = (code, target)
        return True

    # ---------- итог ночи ----------
    def resolve_night(self):
        """-> dict(deaths=[(uid, cause)], checks={uid: текст}, notes=[...])"""
        A = self.actions
        blocked, notes, checks = set(), [], {}
        for uid, (code, tg) in A.items():                       # красотка
            if code == "b" and self.players[uid].alive:
                blocked.add(tg)
        deaths = []
        dream_now = None
        for uid, (code, tg) in A.items():                       # фредди
            if code == "f" and uid not in blocked:
                dream_now = tg
                blocked.add(tg)
                if self.dream_prev == tg:
                    deaths.append((tg, "nightmare"))
        self.dream_prev = dream_now
        votes = {}
        for uid, (code, tg) in A.items():                       # мафия
            if code == "k" and uid not in blocked:
                votes[tg] = votes.get(tg, 0) + 1
        mafia_victim = None
        if votes:
            top = max(votes.values())
            mafia_victim = random.choice([t for t, v in votes.items() if v == top])
        saved = set()
        for uid, (code, tg) in A.items():                       # доктор
            if code == "d" and uid not in blocked:
                saved.add(tg)
                if tg == uid:
                    self.players[uid].doc_self = True
        for uid, (code, tg) in A.items():                       # ведьма
            if uid in blocked:
                continue
            w = self.players[uid]
            if code == "ws" and not w.heal_used and mafia_victim is not None:
                saved.add(mafia_victim)
                w.heal_used = True
            elif code == "wp" and not w.poison_used:
                w.poison_used = True
                deaths.append((tg, "poison"))
        if mafia_victim is not None and mafia_victim not in saved:
            deaths.append((mafia_victim, "mafia"))
        elif mafia_victim is not None:
            notes.append("saved")
        for uid, (code, tg) in A.items():                       # джейсон
            if code == "j" and uid not in blocked:
                deaths.append((tg, "jason"))
        for uid, (code, tg) in A.items():                       # комиссар
            if code == "c":
                if uid in blocked:
                    checks[uid] = "😴 Тебя отвлекли этой ночью, проверка не удалась."
                else:
                    r = self.players[tg].role
                    verdict = ("🔫 МАФИЯ" if r == "mafia" else "🪓 ОПАСНЫЙ УБИЙЦА" if r in ("jason", "freddy")
                               else "🙂 мирный (не мафия)")
                    checks[uid] = f"🕵️ Проверка: {self.players[tg].name} — {verdict}"
        final, seen = [], set()
        for uid, cause in deaths:
            if uid in seen or not self.players[uid].alive:
                continue
            seen.add(uid)
            self.players[uid].alive = False
            final.append((uid, cause))
        self.actions = {}
        return {"deaths": final, "checks": checks, "notes": notes, "blocked": blocked}

    # ---------- голосование ----------
    def set_vote(self, uid, target):
        if self.phase != "vote" or uid not in self.players or not self.players[uid].alive:
            return False
        if target and (target not in self.players or not self.players[target].alive or target == uid):
            return False
        self.votes[uid] = target
        return True

    def resolve_vote(self):
        """-> (повешенный uid или None, джейсон_выжил: uid или None)"""
        tally = {}
        for v in self.votes.values():
            if v:
                tally[v] = tally.get(v, 0) + 1
        self.votes = {}
        if not tally:
            return None, None
        top = max(tally.values())
        leaders = [u for u, c in tally.items() if c == top]
        if len(leaders) > 1:
            return None, None
        u = leaders[0]
        p = self.players[u]
        if p.role == "jason" and not p.spared:
            p.spared = True
            return None, u
        p.alive = False
        return u, None

    def kill(self, uid):
        if self.players[uid].alive:
            self.players[uid].alive = False
            return True
        return False

    # ---------- победа ----------
    def winner(self):
        al = self.alive()
        m = sum(1 for p in al if p.team == "mafia")
        s = sum(1 for p in al if p.team == "solo")
        t = len(al) - m - s
        if m == 0 and s == 0:
            return "town"
        if s and m == 0 and (t == 0 or len(al) <= 2):
            return "solo"
        if m and m >= t + s and s == 0:
            return "mafia"
        if m and s == 0 and t == 0:
            return "mafia"
        return None

    def winners(self, side):
        if side == "solo":
            return [p.uid for p in self.alive() if p.team == "solo"]
        return [p.uid for p in self.players.values() if p.team == side or (side == "town" and p.team == "town")]
