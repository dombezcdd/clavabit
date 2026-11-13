# -*- coding: utf-8 -*-
"""Простое хранилище ключ-значение в таблице state."""
from database.db import db


def state_get(k, default=None):
    r = db.execute("SELECT value FROM state WHERE key=?", (k,)).fetchone()
    return r["value"] if r else default


def state_set(k, v):
    db.execute("INSERT INTO state(key,value) VALUES(?,?) "
               "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))
    db.commit()


def state_del(k):
    db.execute("DELETE FROM state WHERE key=?", (k,))
    db.commit()
