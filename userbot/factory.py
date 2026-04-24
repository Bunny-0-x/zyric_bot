#(©)Zyric Network — Userbot Factory (With Aesthetic Intro)

import asyncio
import json
import os
import redis
import logging
from pyrogram import Client
from pyrogram.types import ChatPrivileges

from config import USERBOT_PHONE, USERBOT_API_ID, USERBOT_API_HASH, TG_BOT_TOKEN
from anilist import fetch_anime
from scrapper import search_anime
from database.database import ledger_get_channel, ledger_set_channel
from graphics import download_image, fetch_anime_by_title, create_thumbnail

log = logging.getLogger(__name__)
r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

class AutoFactory:
    def __init__(self, bot_client):
        self.bot = bot_client
        self.userbot = Client(name="zyric_userbot", api_id=USERBOT_API_ID, api_hash=USERBOT_API_HASH, phone_number=USERBOT_PHONE)
        self._started = False

    async def start_userbot(self):
        if not self._started:
            await self.userbot.start()
            self._started = True
            log.info("[Factory] Userbot started.")

    async def sync_anime(self, anilist_id: int, season: int, audio: str, status_callback):
        try:
            await status_callback("🔍 Fetching AniList metadata...")
            anime = await fetch_anime(anilist_id)
            if not anime: return await status_callback("❌ AniList fetch failed.")

            title_en = anime["title_en"]
            synopsis = anime["synopsis"]
            poster_url = anime["poster_url"]

            poster_dir = './downloads/anilist_posters'
            if not os.path.exists(poster_dir): os.makedirs(poster_dir)
            poster_path = f"{poster_dir}/{anilist_id}.jpg"

            ledger = ledger_get_channel(anilist_id)
            if ledger:
                channel_id = ledger["channel_id"]
                await status_callback(f"✅ Channel exists. ID: <code>{channel_id}</code>")
                if not os.path.exists(poster_path): await download_image(poster_url, poster_path)
            else:
                await status_callback("🏗️ Creating Sub-Channel via Userbot...")
                chat = await self.userbot.create_channel(title=f"{title_en} | Episodes", description=f"{synopsis[:250]}")
                channel_id = chat.id

                bot_id = int(TG_BOT_TOKEN.split(":")[0])
                await self.userbot.promote_chat_member(
                    chat_id=channel_id, user_id=bot_id,
                    privileges=ChatPrivileges(can_post_messages=True, can_edit_messages=True, can_delete_messages=True, can_invite_users=True)
                )

                try:
                    await status_callback("🎨 Setting channel profile picture...")
                    downloaded = await download_image(poster_url, poster_path)
                    if downloaded and os.path.exists(downloaded):
                        await self.userbot.set_chat_photo(chat_id=channel_id, photo=downloaded)
                except Exception as e: log.warning(f"[Factory] Failed DP: {e}")

                try: invite_link = await self.userbot.export_chat_invite_link(channel_id)
                except: invite_link = f"https://t.me/c/{str(channel_id).replace('-100', '')}/1"
                try: ledger_set_channel(anilist_id, title_en, channel_id, invite_link)
                except TypeError: ledger_set_channel(title_en, anilist_id, channel_id, invite_link)

                # --- 📝 SEND AESTHETIC INTRO MESSAGE ---
                try:
                    await status_callback("📝 Generating & Posting Anime Introduction...")
                    full_info = await fetch_anime_by_title(title_en)
                    if full_info:
                        # SAFELY TRUNCATE SYNOPSIS TO AVOID TELEGRAM'S 1024 CHAR LIMIT
                        safe_synopsis = full_info['synopsis'][:400] + ("..." if len(full_info['synopsis']) > 400 else "")
                        
                        intro_text = (
                            f"<b>{full_info['title']}</b>\n\n"
                            f"▶️ <b>Genres :</b> {', '.join(full_info['genres'])}\n"
                            f"▶️ <b>Type :</b> {full_info['format']}\n"
                            f"▶️ <b>Average Rating :</b> {full_info['rating']}\n"
                            f"▶️ <b>Status :</b> {full_info['status']}\n"
                            f"▶️ <b>First aired :</b> {full_info['start_date']}\n"
                            f"▶️ <b>Last aired :</b> {full_info['end_date']}\n"
                            f"▶️ <b>Runtime :</b> {full_info['duration']} minutes\n"
                            f"▶️ <b>No of episodes :</b> {full_info['episodes']}\n\n"
                            f"▶️ <b>Synopsis :</b> <i>{safe_synopsis}</i>\n\n"
                            f"<i>(Source: AniList)</i>"
                        )
                        
                        # GENERATE THE CUSTOM IMAGE USING GRAPHICS.PY
                        intro_thumb = await create_thumbnail(
                            full_info['poster_url'], 
                            full_info['title'], 
                            full_info['genres'], 
                            full_info['synopsis'], 
                            full_info['episodes']
                        )
                        
                        await self.bot.send_photo(
                            chat_id=channel_id, 
                            photo=intro_thumb if intro_thumb and os.path.exists(intro_thumb) else poster_path, 
                            caption=intro_text
                        )
                        
                        # Cleanup the generated intro image to save space
                        if intro_thumb and os.path.exists(intro_thumb):
                            os.remove(intro_thumb)
                except Exception as intro_err:
                    log.error(f"[Factory] Intro failed: {intro_err}")

            await status_callback(f"🕵️ Searching AnimePahe for <b>{title_en}</b>...")
            episodes = await search_anime(title_en)
            if not episodes: return await status_callback("❌ No episodes found on AnimePahe.")

            r.setnx(f"zyric:next_ep:{anilist_id}", 1)

            queued_count = 0
            for ep in episodes:
                job = {"anime": title_en, "ep_num": int(ep["ep_num"]), "url": ep["url"], "anilist_id": anilist_id, "season": season, "audio": audio}
                r.lpush("zyric:jobs:pending", json.dumps(job))
                queued_count += 1

            await status_callback(f"✅ Queued {queued_count} episodes! Background workers are downloading now.")

        except Exception as e:
            log.error(f"[Factory] Sync failed: {e}")
            await status_callback(f"❌ Error during sync: {e}")
