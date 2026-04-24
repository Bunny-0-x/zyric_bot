#(©)Zyric Network — Unique Visuals & Duplication Shield

import asyncio
import os
import json
import logging
import redis
from pyrogram.enums import ParseMode
from helper_func import encode
from ui_templates import type_a
from graphics import create_thumbnail
try:
    from image import fetch_anime_by_title
except ImportError:
    from graphics import fetch_anime_by_title
from database.database import ledger_episode_exists, ledger_get_channel, ledger_add_episode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

log = logging.getLogger(__name__)
r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

async def upload_loop(bot):
    log.info("[Uploader] Aesthetic loop started, watching queue...")
    while True:
        try:
            raw = r.rpop("zyric:uploads:pending")
            if not raw:
                await asyncio.sleep(2)
                continue
            job = json.loads(raw)
            await _process_upload(bot, job)
        except Exception as e:
            log.error(f"[Uploader] Loop error: {e}")
            await asyncio.sleep(5)

async def _process_upload(bot, job: dict):
    anime, ep_num, quality = job["anime"], job["ep_num"], job["quality"]
    file_path, total_expected = job["file_path"], job["total_expected"]
    anilist_id, season = job.get("anilist_id", 0), job.get("season", 1)

    if ledger_episode_exists(anilist_id, season, ep_num):
        log.warning(f"[Uploader] 🛑⏩⏩ {anime} EP{ep_num} [S{season:02d}] already in Database! SKIPPING upload!")
        if os.path.exists(file_path): os.remove(file_path)
        return

    if not os.path.exists(file_path):
        log.warning(f"[Uploader] 👻 GHOST FILE detected! Skipping job: {file_path}")
        return

    log.info(f"[Uploader] ☁️ Aesthetic Upload: {anime} EP{ep_num} [{quality}]")
    thumb_path = None
    try:
        # 🎨 1. GENERATE CUSTOM THUMBNAIL & MAKE IT UNIQUE PER EPISODE
        anime_info = await fetch_anime_by_title(anime)
        if anime_info:
            base_thumb = await create_thumbnail(anime_info['poster_url'], anime_info['title'], anime_info['genres'], anime_info['synopsis'], anime_info['episodes'])
            if base_thumb and os.path.exists(base_thumb):
                unique_thumb = f"{base_thumb}_ep{ep_num}.jpg"
                os.rename(base_thumb, unique_thumb)
                thumb_path = unique_thumb

        # 🖼️ 2. GET RAW POSTER (For the MKV Telegram Thumbnail)
        raw_poster_path = f"./downloads/anilist_posters/{anilist_id}.jpg"
        mkv_thumb = raw_poster_path if os.path.exists(raw_poster_path) else None

        safe = anime.replace(":", "").replace("/", "")
        filename = f"{safe} S{season:02d} - {ep_num:02d} [{quality}] [Sub].mkv"
        size_mb = os.path.getsize(file_path) / 1024 / 1024

        post = await bot.send_document(
            chat_id=bot.db_channel.id, document=file_path, file_name=filename,
            caption=filename, thumb=mkv_thumb, disable_notification=True, parse_mode=ParseMode.HTML,
        )

        converted_id = post.id * abs(bot.db_channel.id)
        link = f"https://t.me/{bot.username}?start={await encode(f'get-{converted_id}')}"
        agg_key = f"zyric:agg:{anilist_id}:{season}:{ep_num}"
        upload_data = {"quality": quality, "link": link, "size_mb": round(size_mb, 2)}
        r.hset(agg_key, quality, json.dumps(upload_data))
        r.expire(agg_key, 7200)

        await _check_and_post(bot, job, agg_key, anilist_id, season, ep_num, total_expected, thumb_path)

    except Exception as e:
        log.error(f"[Uploader] ❌ Aesthetic Upload failed: {e}")
        r.lpush("zyric:uploads:pending", json.dumps(job))
    finally:
        if os.path.exists(file_path): os.remove(file_path)

async def _check_and_post(bot, job: dict, agg_key: str, anilist_id: int, season: int, ep_num, total_expected: int, thumb_path: str):
    uploaded_raw = r.hgetall(agg_key)
    if len(uploaded_raw) < total_expected:
        return # WAIT! Do NOT delete the thumbnail yet!

    ledger = ledger_get_channel(anilist_id)
    if not ledger: return
    channel_id = ledger["channel_id"]
    await bot.seed_peer(channel_id)

    uploaded = {q: json.loads(v) for q, v in uploaded_raw.items()}
    sorted_quals = sorted(uploaded.keys(), key=lambda x: int(x.replace('p', '')), reverse=True)
    caption = type_a(title=job["anime"], status="RELEASING", season=season, episode=ep_num, audio="Japanese [Eng-Sub]", qualities=sorted_quals)
    
    raw_buttons = [{"text": f"{q} ↗️", "url": uploaded[q]["link"]} for q in sorted_quals]
    
    room_key = f"zyric:waiting_room:{anilist_id}"
    aesthetic_data = {"caption": caption, "buttons": raw_buttons, "thumb_path": thumb_path}
    r.hset(room_key, str(ep_num), json.dumps(aesthetic_data))
    r.delete(agg_key)

    ledger_add_episode(anilist_id, season, ep_num, 0, 0)

    next_ep_key = f"zyric:next_ep:{anilist_id}"
    while True:
        expected_ep = int(r.get(next_ep_key) or 1)
        if r.hexists(room_key, str(expected_ep)):
            ep_raw = r.hget(room_key, str(expected_ep))
            data = json.loads(ep_raw)
            
            markup_post = InlineKeyboardMarkup([[InlineKeyboardButton(b["text"], url=b["url"]) for b in data["buttons"]]])
            thumb_post = data.get("thumb_path")

            try:
                if thumb_post and os.path.exists(thumb_post):
                    await bot.send_photo(
                        chat_id=channel_id, photo=thumb_post, caption=data["caption"],
                        reply_markup=markup_post, parse_mode=ParseMode.HTML
                    )
                else:
                    await bot.send_message(
                        chat_id=channel_id, text=data["caption"],
                        reply_markup=markup_post, parse_mode=ParseMode.HTML
                    )
                
                r.hdel(room_key, str(expected_ep))
                if thumb_post and os.path.exists(thumb_post): os.remove(thumb_post)
                r.incr(next_ep_key)
                log.info(f"[Uploader] ✅✅ PERFECT ORDER POSTED: {job['anime']} EP{expected_ep} in aesthetic mode!")
                try:
                    new_title = f"{job["anime"]} | Episode {expected_ep}"
                    await bot.set_chat_title(chat_id=channel_id, title=new_title[:128])
                    log.info(f"[Uploader] ✏️ Channel renamed: {new_title}")
                except Exception as e:
                    log.warning(f"[Uploader] Failed to rename channel: {e}")
            except Exception as e:
                log.error(f"[Uploader] Aesthetic post failed for EP{expected_ep}: {e}")
                break
        else:
            break
