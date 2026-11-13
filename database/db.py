# -*- coding: utf-8 -*-
"""SQLite connection and initial schema. Existing DB file and tables are preserved."""
import os
import sqlite3

from config import BASE, DB_FILE

DATA_DIR = os.environ.get("DATA_DIR", BASE)
os.makedirs(DATA_DIR, exist_ok=True)
db = sqlite3.connect(os.path.join(DATA_DIR, DB_FILE), check_same_thread=False)
db.row_factory = sqlite3.Row
db.executescript("""
CREATE TABLE IF NOT EXISTS users(
  user_id INTEGER PRIMARY KEY, name TEXT, username TEXT DEFAULT '',
  total INTEGER DEFAULT 0, xp INTEGER DEFAULT 0,
  streak INTEGER DEFAULT 0, best_streak INTEGER DEFAULT 0, last_day TEXT,
  first_seen REAL, last_seen REAL,
  quiz_pts INTEGER DEFAULT 0, game_pts INTEGER DEFAULT 0, quest_pts INTEGER DEFAULT 0,
  rep INTEGER DEFAULT 0, rep_given INTEGER DEFAULT 0,
  tag TEXT DEFAULT '', registered INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS daily(
  day TEXT, user_id INTEGER, cnt INTEGER DEFAULT 0, replies INTEGER DEFAULT 0,
  plays INTEGER DEFAULT 0, repgiven INTEGER DEFAULT 0,
  PRIMARY KEY(day, user_id));
CREATE TABLE IF NOT EXISTS msgs(
  message_id INTEGER PRIMARY KEY, user_id INTEGER, day TEXT, reactions INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS quest_done(
  day TEXT, user_id INTEGER, qid TEXT, PRIMARY KEY(day, user_id, qid));
CREATE TABLE IF NOT EXISTS rep_log(
  day TEXT, giver INTEGER, target INTEGER, PRIMARY KEY(day, giver, target));
CREATE TABLE IF NOT EXISTS words(
  day TEXT, word TEXT, cnt INTEGER DEFAULT 0, PRIMARY KEY(day, word));
CREATE TABLE IF NOT EXISTS mutes(
  user_id INTEGER PRIMARY KEY, name TEXT, until REAL, reason TEXT,
  by_name TEXT, created REAL);
CREATE TABLE IF NOT EXISTS cmd_access(cmd TEXT PRIMARY KEY, rank INTEGER);
CREATE TABLE IF NOT EXISTS rp_media(
  id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT, kind TEXT, file_id TEXT,
  file_unique TEXT, added_by TEXT, created REAL);
CREATE TABLE IF NOT EXISTS pairs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, a INTEGER, b INTEGER, love INTEGER DEFAULT 30,
  since REAL, last_action REAL, gain_day TEXT, gain INTEGER DEFAULT 0, date_day TEXT);
CREATE TABLE IF NOT EXISTS proposals(
  to_id INTEGER PRIMARY KEY, from_id INTEGER, created REAL, msg_id INTEGER);
CREATE TABLE IF NOT EXISTS kids(
  id INTEGER PRIMARY KEY AUTOINCREMENT, pair_id INTEGER, name TEXT, gender TEXT, born REAL);
CREATE TABLE IF NOT EXISTS spark_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, pair_id INTEGER, delta INTEGER, reason TEXT, who TEXT,
  ts REAL, bal INTEGER);
CREATE TABLE IF NOT EXISTS job_tasks(
  user_id INTEGER PRIMARY KEY, job TEXT, kind TEXT, answer TEXT, target_id INTEGER,
  created REAL, expires REAL);
CREATE TABLE IF NOT EXISTS marry_proposals(
  to_id INTEGER PRIMARY KEY, from_id INTEGER, created REAL);
CREATE TABLE IF NOT EXISTS pets(
  id INTEGER PRIMARY KEY AUTOINCREMENT, owner INTEGER, kind TEXT, name TEXT, fed_day TEXT, bought REAL);
CREATE TABLE IF NOT EXISTS shop_items(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price INTEGER, stock INTEGER DEFAULT -1,
  active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT, item TEXT, price INTEGER,
  created REAL, status TEXT);
CREATE TABLE IF NOT EXISTS reports(
  id INTEGER PRIMARY KEY AUTOINCREMENT, target_id INTEGER, target_name TEXT, msg_id INTEGER,
  reporter TEXT, reason TEXT, created REAL, status TEXT);
""")
for _col in ("arank INTEGER DEFAULT 0", "coins INTEGER DEFAULT 0", "duel_w INTEGER DEFAULT 0",
             "duel_l INTEGER DEFAULT 0", "bonus_day TEXT DEFAULT ''",
             "job TEXT DEFAULT ''", "job_shifts INTEGER DEFAULT 0", "last_work REAL DEFAULT 0",
             "house TEXT DEFAULT ''", "gender TEXT DEFAULT ''"):
    try:
        db.execute("ALTER TABLE users ADD COLUMN " + _col)
    except sqlite3.OperationalError:
        pass
for _col in ("married_at REAL DEFAULT 0", "anniv_day TEXT DEFAULT ''", "actions INTEGER DEFAULT 0",
             "offended INTEGER DEFAULT 0"):
    try:
        db.execute("ALTER TABLE pairs ADD COLUMN " + _col)
    except sqlite3.OperationalError:
        pass
db.commit()


# ---- таблицы и миграции, добавленные в более поздних версиях ----
db.executescript("""
CREATE TABLE IF NOT EXISTS challenge_done(
  chat_id INTEGER, message_id INTEGER, ts REAL, PRIMARY KEY(chat_id, message_id));
CREATE TABLE IF NOT EXISTS game_wins(user_id INTEGER PRIMARY KEY, wins INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS custom_jobs(key TEXT PRIMARY KEY, name TEXT, pay INTEGER, cd INTEGER, req TEXT);
CREATE TABLE IF NOT EXISTS admin_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, actor INTEGER, actor_name TEXT, cmd TEXT, text TEXT);
""")

# CREATE TABLE IF NOT EXISTS не добавляет новые столбцы в уже существующую таблицу.
_admin_log_cols = {r["name"] for r in db.execute("PRAGMA table_info(admin_log)").fetchall()}
if "ts" not in _admin_log_cols:
    db.execute("ALTER TABLE admin_log ADD COLUMN ts REAL NOT NULL DEFAULT 0")
    # Если старая схема хранила время под другим именем, переносим его.
    _legacy_time_col = next((c for c in ("created", "timestamp", "time") if c in _admin_log_cols), None)
    if _legacy_time_col:
        db.execute(f'UPDATE admin_log SET ts = "{_legacy_time_col}" WHERE ts = 0')

for _table, _col in (("marry_proposals", "pair_id INTEGER"),
                     ("pairs", "maint_day TEXT"),
                     ("pairs", "bank INTEGER DEFAULT 0")):
    try:
        db.execute(f"ALTER TABLE {_table} ADD COLUMN {_col}")
    except sqlite3.OperationalError:
        pass
db.commit()
