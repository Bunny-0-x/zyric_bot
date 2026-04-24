#(©)Zyric Network

import sqlite3
import pymongo
import os
from config import DB_URI, DB_NAME

# ── MongoDB (user/fsub/bot data) ──────────────────────────────────────
dbclient  = pymongo.MongoClient(DB_URI)
_db       = dbclient[DB_NAME]

user_data      = _db["users"]
fsub_data      = _db["fsub_channels"]
settings_data  = _db["settings"]
bot_data       = _db["bots"]

# ── SQLite (anime state ledger) ───────────────────────────────────────
SQLITE_PATH = "zyric_ledger.db"

def _init_sqlite():
    con = sqlite3.connect(SQLITE_PATH)
    cur = con.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS anime_channels (
            anilist_id   INTEGER PRIMARY KEY,
            title        TEXT,
            channel_id   INTEGER,
            invite_link  TEXT,
            synced       INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS synced_episodes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            anilist_id   INTEGER,
            season       INTEGER,
            episode      INTEGER,
            dump_msg_id  INTEGER,
            sub_msg_id   INTEGER,
            UNIQUE(anilist_id, season, episode)
        );
    """)
    con.commit()
    con.close()

_init_sqlite()


def _con():
    return sqlite3.connect(SQLITE_PATH)


# ── Anime Channel Ledger ──────────────────────────────────────────────

def ledger_get_channel(anilist_id: int) -> dict | None:
    with _con() as con:
        row = con.execute(
            "SELECT * FROM anime_channels WHERE anilist_id=?", (anilist_id,)
        ).fetchone()
    if not row:
        return None
    return {"anilist_id": row[0], "title": row[1], "channel_id": row[2],
            "invite_link": row[3], "synced": row[4]}


def ledger_set_channel(anilist_id: int, title: str, channel_id: int, invite_link: str):
    with _con() as con:
        con.execute("""
            INSERT INTO anime_channels (anilist_id, title, channel_id, invite_link)
            VALUES (?,?,?,?)
            ON CONFLICT(anilist_id) DO UPDATE SET
                channel_id=excluded.channel_id,
                invite_link=excluded.invite_link
        """, (anilist_id, title, channel_id, invite_link))


def ledger_mark_synced(anilist_id: int):
    with _con() as con:
        con.execute(
            "UPDATE anime_channels SET synced=1 WHERE anilist_id=?", (anilist_id,)
        )


def ledger_episode_exists(anilist_id: int, season: int, episode: int) -> bool:
    with _con() as con:
        row = con.execute(
            "SELECT 1 FROM synced_episodes WHERE anilist_id=? AND season=? AND episode=?",
            (anilist_id, season, episode)
        ).fetchone()
    return bool(row)


def ledger_add_episode(anilist_id: int, season: int, episode: int,
                        dump_msg_id: int, sub_msg_id: int):
    with _con() as con:
        con.execute("""
            INSERT OR IGNORE INTO synced_episodes
            (anilist_id, season, episode, dump_msg_id, sub_msg_id)
            VALUES (?,?,?,?,?)
        """, (anilist_id, season, episode, dump_msg_id, sub_msg_id))


# ── MongoDB: Users ────────────────────────────────────────────────────

async def present_user(user_id: int) -> bool:
    return bool(user_data.find_one({"_id": user_id}))


async def add_user(user_id: int):
    if not await present_user(user_id):
        user_data.insert_one({"_id": user_id})


async def full_userbase() -> list[int]:
    return [d["_id"] for d in user_data.find()]


async def del_user(user_id: int):
    user_data.delete_one({"_id": user_id})


# ── MongoDB: FSub ─────────────────────────────────────────────────────

async def add_fsub_channel(channel_id: int, invite_link: str = None, title: str = None):
    if not fsub_data.find_one({"_id": channel_id}):
        fsub_data.insert_one({"_id": channel_id, "invite_link": invite_link, "title": title})


async def remove_fsub_channel(channel_id: int):
    fsub_data.delete_one({"_id": channel_id})


async def get_fsub_channels() -> list:
    return list(fsub_data.find())


async def update_fsub_link(channel_id: int, invite_link: str):
    fsub_data.update_one({"_id": channel_id}, {"$set": {"invite_link": invite_link}})
