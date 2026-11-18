# -*- coding: utf-8 -*-
"""Преступления и суд: ограбления, тюрьма, дела, присяжные, адвокаты."""

import random
import time

from core.utils import urow
from database.db import db

ROB_CD = 3 * 3600
ROB_CHANCE = 0.35
ROB_MIN_VICTIM = 60          # у жертвы должно быть хотя бы столько
ROB_MIN_THIEF = 30           # у вора должен быть залог на штраф
ROB_MAX = 60
ROB_LEAVE = 30               # после кражи у жертвы остаётся не меньше
ROB_PCT = (0.02, 0.04)       # доля баланса жертвы
ROB_JAIL_CHANCE = 0.25       # шанс попасть в тюрьму при провале
ROB_JAIL_MIN = 20
ROB_DAY_MAX = 3              # попыток в сутки у одного вора
ROB_GUARD = 3600             # после ограбления жертву час не трогают
ROB_FINE_PCT = 0.10          # штраф при провале: 10% баланса вора (от 15 до 100), просто списывается
FILE_WINDOW = 30 * 60          # сколько после ограбления можно подать в суд
TRIAL_MIN = 5                  # минут идёт голосование
MIN_VOTES = 3
JAIL_HOURS = 1
BAIL = 100
LAWYER_FEE = 40
LAWYER_WEIGHT = 1.5


def jail_left(row):
    return max(0, int((row["jail_until"] or 0) - time.time())) if row else 0


def rob(thief_id, victim_id):
    """-> (код, данные). коды: jail, cd, poor, caught, ok"""
    t, v = urow(thief_id), urow(victim_id)
    if jail_left(t):
        return "jail", jail_left(t)
    left = (t["rob_at"] or 0) + ROB_CD - time.time()
    if left > 0:
        return "cd", int(left)
    if not v or (v["coins"] or 0) < ROB_MIN_VICTIM:
        return "poor", ROB_MIN_VICTIM
    if (t["coins"] or 0) < ROB_MIN_THIEF:
        return "broke", ROB_MIN_THIEF
    from core.utils import today
    from database.state import state_get, state_set
    key = f"rob_{today()}_{thief_id}"
    if int(state_get(key) or 0) >= ROB_DAY_MAX:
        return "limit", ROB_DAY_MAX
    day_start = time.time() - 86400
    if db.execute("SELECT 1 FROM crimes WHERE kind='rob' AND criminal=? AND victim=? AND ts>?",
                  (thief_id, victim_id, day_start)).fetchone():
        return "same", 0
    last = db.execute("SELECT MAX(ts) m FROM crimes WHERE kind='rob' AND victim=?", (victim_id,)).fetchone()["m"] or 0
    if last + ROB_GUARD > time.time():
        return "guard", int(last + ROB_GUARD - time.time())
    state_set(key, int(state_get(key) or 0) + 1)
    db.execute("UPDATE users SET rob_at=? WHERE user_id=?", (time.time(), thief_id))
    if random.random() > ROB_CHANCE:
        fine = min(100, max(15, int((t["coins"] or 0) * ROB_FINE_PCT)), t["coins"] or 0)
        db.execute("UPDATE users SET coins=coins-? WHERE user_id=?", (fine, thief_id))
        jailed = random.random() < ROB_JAIL_CHANCE
        if jailed:
            db.execute("UPDATE users SET jail_until=? WHERE user_id=?", (time.time() + ROB_JAIL_MIN * 60, thief_id))
        db.commit()
        return "caught", (fine, jailed)
    amount = min(ROB_MAX, max(5, int(v["coins"] * random.uniform(*ROB_PCT))), max(0, v["coins"] - ROB_LEAVE))
    db.execute("UPDATE users SET coins=coins-? WHERE user_id=?", (amount, victim_id))
    db.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (amount, thief_id))
    cur = db.execute("INSERT INTO crimes(kind,criminal,victim,amount,ts,status) VALUES('rob',?,?,?,?,'open')",
                     (thief_id, victim_id, amount, time.time()))
    db.commit()
    return "ok", (cur.lastrowid, amount)


def open_case(crime_id, plaintiff_id, chat_id):
    c = db.execute("SELECT * FROM crimes WHERE id=?", (crime_id,)).fetchone()
    if not c or c["status"] != "open" or c["victim"] != plaintiff_id or time.time() - c["ts"] > FILE_WINDOW:
        return None
    now = time.time()
    cur = db.execute("INSERT INTO court_cases(crime_id,plaintiff,defendant,amount,chat_id,created,end,status) "
                     "VALUES(?,?,?,?,?,?,?,'vote')",
                     (crime_id, plaintiff_id, c["criminal"], c["amount"], chat_id, now, now + TRIAL_MIN * 60))
    db.execute("UPDATE crimes SET status='filed' WHERE id=?", (crime_id,))
    db.commit()
    return db.execute("SELECT * FROM court_cases WHERE id=?", (cur.lastrowid,)).fetchone()


def case_by_id(cid):
    return db.execute("SELECT * FROM court_cases WHERE id=?", (cid,)).fetchone()


def active_case_of(uid):
    return db.execute("SELECT * FROM court_cases WHERE status='vote' AND (plaintiff=? OR defendant=?) "
                      "ORDER BY id DESC", (uid, uid)).fetchone()


def tally(case):
    g = i = 0.0
    for v in db.execute("SELECT * FROM court_votes WHERE case_id=?", (case["id"],)).fetchall():
        if v["vote"] == "g":
            g += 1
        else:
            i += 1
    n = g + i
    if case["lawyer_p"]:
        g += LAWYER_WEIGHT
    if case["lawyer_d"]:
        i += LAWYER_WEIGHT
    return g, i, int(n)


def vote(case, uid, v):
    """-> (ok, текст)"""
    if case["status"] != "vote" or time.time() > case["end"]:
        return False, "Голосование закончено"
    if uid in (case["plaintiff"], case["defendant"], case["lawyer_p"], case["lawyer_d"]):
        return False, "Участники дела и адвокаты не голосуют"
    db.execute("INSERT INTO court_votes(case_id,user_id,vote) VALUES(?,?,?) "
               "ON CONFLICT(case_id,user_id) DO UPDATE SET vote=?", (case["id"], uid, v, v))
    db.commit()
    return True, "Голос принят" if v == "g" else "Голос принят"


def hire_lawyer(case, payer, lawyer):
    """-> (ok, текст)"""
    if case["status"] != "vote":
        return False, "Дело уже закрыто"
    side = "lawyer_p" if payer == case["plaintiff"] else "lawyer_d" if payer == case["defendant"] else None
    if not side:
        return False, "Нанять адвоката могут только участники дела"
    if case[side]:
        return False, "У тебя уже есть адвокат"
    lr = urow(lawyer)
    if not lr or lr["job"] != "адвокат":
        return False, "Этот игрок не работает адвокатом"
    if lawyer in (case["plaintiff"], case["defendant"], case["lawyer_p"], case["lawyer_d"]):
        return False, "Этот адвокат не может участвовать"
    if (urow(payer)["coins"] or 0) < LAWYER_FEE:
        return False, f"Услуги адвоката стоят {LAWYER_FEE}"
    db.execute("UPDATE users SET coins=coins-? WHERE user_id=?", (LAWYER_FEE, payer))
    db.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (LAWYER_FEE, lawyer))
    db.execute(f"UPDATE court_cases SET {side}=? WHERE id=?", (lawyer, case["id"]))
    db.commit()
    return True, side


def close_case(case, force=None):
    """Подводит итог. -> (виновен: bool|None, текст-итог-для-логики) ; None если голосов мало."""
    g, i, n = tally(case)
    if force is None and n < MIN_VOTES:
        db.execute("UPDATE court_cases SET status='void' WHERE id=?", (case["id"],))
        db.execute("UPDATE crimes SET status='void' WHERE id=?", (case["crime_id"],))
        db.commit()
        return None, (g, i, n, 0)
    guilty = force if force is not None else g > i
    paid = 0
    if guilty:
        d = urow(case["defendant"])
        paid = min(case["amount"], d["coins"] or 0)
        db.execute("UPDATE users SET coins=coins-? WHERE user_id=?", (paid, case["defendant"]))
        db.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (paid, case["plaintiff"]))
        db.execute("UPDATE users SET jail_until=? WHERE user_id=?", (time.time() + JAIL_HOURS * 3600, case["defendant"]))
    db.execute("UPDATE court_cases SET status=? WHERE id=?", ("guilty" if guilty else "free", case["id"]))
    db.commit()
    return guilty, (g, i, n, paid)


def pay_bail(uid):
    r = urow(uid)
    if not jail_left(r):
        return False, "Ты не в тюрьме"
    if (r["coins"] or 0) < BAIL:
        return False, f"Залог {BAIL}, у тебя {r['coins'] or 0}"
    db.execute("UPDATE users SET coins=coins-?, jail_until=0 WHERE user_id=?", (BAIL, uid))
    db.commit()
    return True, BAIL
