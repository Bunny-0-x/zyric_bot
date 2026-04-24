#(©)Zyric Network

import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

from bot import Bot
from config import ADMINS, MAIN_CHANNEL_ID
from helper_func import encode
from scrapper import search_anime, intercept_streams, download_episode, QUALITIES
from anilist import fetch_anime
from graphics import generate_thumbnail, fetch_poster_bytes
from ui_templates import type_a, type_c, SEPARATOR
from config import POWERED_BY
from database.database import (
    ledger_get_channel, ledger_set_channel, ledger_mark_synced,
    ledger_episode_exists, ledger_add_episode
)


def _quality_buttons(uploaded: dict) -> InlineKeyboardMarkup:
    """
    Build quality buttons exactly as video shows:
    Row 1: up to 3 qualities side by side  e.g. [480p ↗️] [720p ↗️] [1080p ↗️]
    Row 2+: remaining qualities full-width  e.g. [HDRip ↗️]
    """
    keys   = list(uploaded.keys())
    rows   = []
    first_row = [
        InlineKeyboardButton(f"{q} ↗️", url=uploaded[q]["link"])
        for q in keys[:3]
    ]
    if first_row:
        rows.append(first_row)
    for q in keys[3:]:
        rows.append([InlineKeyboardButton(f"{q} ↗️", url=uploaded[q]["link"])])
    return InlineKeyboardMarkup(rows)


async def process_and_post(
    client: Bot,
    status_msg: Message,
    anilist_id: int,
    season: int,
    episode: int,
    audio: str = "Japanese [Eng-Sub]",
    sub_channel_id: int = None,
):
    """
    Full pipeline for one episode:
    1. Fetch AniList metadata
    2. Search AnimePahe & intercept streams
    3. Download all available qualities
    4. Upload each to dump channel → generate deep link
    5. Post Type A to sub-channel with quality buttons
    6. Return uploaded dict
    """

    async def log(text: str):
        try:
            await status_msg.edit(text)
        except Exception:
            pass

    # ── 1. AniList ────────────────────────────────────────────────────
    await log("🔍 Fetching AniList metadata...")
    anime = await fetch_anime(anilist_id)
    if not anime:
        await log("❌ AniList fetch failed.")
        return None

    title    = anime["title_en"]
    genres   = anime["genres"]
    synopsis = anime["synopsis"]

    # ── 2. Search & intercept ─────────────────────────────────────────
    await log(f"🕵️ Searching AnimePahe for <b>{title}</b> EP{episode}...")
    episodes = await search_anime(title)
    ep_data  = next((e for e in episodes if str(e["ep_num"]) == str(episode)), None)
    if not ep_data:
        await log(f"❌ EP{episode} not found on AnimePahe.")
        return None

    await log(f"📡 Intercepting streams for EP{episode}...")
    streams = await intercept_streams(ep_data["url"])
    if not streams:
        await log("❌ Stream interception failed.")
        return None

    available = [q for q in QUALITIES if q in streams]
    await log(f"✅ Found: {', '.join(available)}")

    # ── 3. Generate thumbnail ─────────────────────────────────────────
    poster_bytes = await fetch_poster_bytes(anime["poster_url"])
    thumb_path   = None
    if poster_bytes:
        thumb_path = generate_thumbnail(
            poster_bytes = poster_bytes,
            title        = title,
            genres       = genres[:3],
            synopsis     = synopsis,
            episode_num  = episode,
            output_filename = f"{anilist_id}_s{season}_ep{episode}.jpg"
        )

    # ── 4. Download + upload each quality ─────────────────────────────
    uploaded = {}   # quality → {"link": ..., "size": ...}

    for quality in available:
        await log(f"📥 Downloading <b>{quality}</b>...")
        dl_path = await download_episode(streams[quality], title, episode, quality)
        if not dl_path:
            await log(f"⚠️ {quality} download failed, skipping.")
            continue

        await log(f"☁️ Uploading <b>{quality}</b> to dump channel...")
        try:
            file_size = os.path.getsize(dl_path)
            safe      = title.replace(":", "").replace("/", "")
            filename  = f"{safe} S{season:02d} - {episode:02d} [{quality}] [Sub].mkv"

            post = await client.send_document(
                chat_id   = client.db_channel.id,
                document  = dl_path,
                file_name = filename,
                thumb     = thumb_path,
                caption   = filename,
                disable_notification = True,
                parse_mode = ParseMode.HTML
            )

            converted_id  = post.id * abs(client.db_channel.id)
            base64_string = await encode(f"get-{converted_id}")
            link          = f"https://t.me/{client.username}?start={base64_string}"

            uploaded[quality] = {"link": link, "size": file_size, "msg_id": post.id}

        except Exception as e:
            await log(f"❌ Upload failed for {quality}: {e}")
        finally:
            if os.path.exists(dl_path):
                os.remove(dl_path)
        await asyncio.sleep(2)

    if not uploaded:
        await log("❌ All uploads failed.")
        return None

    # ── 5. Post Type A to sub-channel ────────────────────────────────
    caption_a = type_a(
        title     = title,
        status    = anime["status"],
        season    = season,
        episode   = episode,
        audio     = audio,
        qualities = list(uploaded.keys()),
    )
    buttons = _quality_buttons(uploaded)

    sub_msg = None
    if sub_channel_id:
        try:
            sub_msg = await client.send_photo(
                chat_id      = sub_channel_id,
                photo        = thumb_path or anime["poster_url"],
                caption      = caption_a,
                reply_markup = buttons,
                parse_mode   = ParseMode.HTML
            )
        except Exception as e:
            print(f"[Release] Sub-channel post failed: {e}")

    # ── Cleanup thumbnail ─────────────────────────────────────────────
    if thumb_path and os.path.exists(thumb_path):
        os.remove(thumb_path)

    await log(
        f"✅ <b>Done!</b>\n\n"
        f"<b>Anime:</b> {title}\n"
        f"<b>Episode:</b> {episode}\n"
        f"<b>Qualities:</b> {', '.join(uploaded.keys())}"
    )

    return {"uploaded": uploaded, "sub_msg_id": sub_msg.id if sub_msg else None}


@Bot.on_message(filters.command("process") & filters.private & filters.user(ADMINS))
async def cmd_process(client: Bot, message: Message):
    """
    /process <AniList ID> | <Season> | <Episode> [| <Audio>]
    Example: /process 113415 | 1 | 2 | Japanese [Eng-Sub]
    """
    try:
        raw   = message.text.split("/process", 1)[1].strip()
        parts = [p.strip() for p in raw.split("|")]
        anilist_id = int(parts[0])
        season     = int(parts[1]) if len(parts) > 1 else 1
        episode    = int(parts[2]) if len(parts) > 2 else 1
        audio      = parts[3] if len(parts) > 3 else "Japanese [Eng-Sub]"
    except (IndexError, ValueError):
        return await message.reply(
            "❌ <b>Usage:</b>\n"
            "<code>/process &lt;AniList ID&gt; | &lt;Season&gt; | &lt;Episode&gt; [| Audio]</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/process 113415 | 1 | 2</code>"
        )

    status_msg = await message.reply("⏳ Starting pipeline...", quote=True)
    ledger     = ledger_get_channel(anilist_id)
    sub_ch_id  = ledger["channel_id"] if ledger else None

    await process_and_post(
        client         = client,
        status_msg     = status_msg,
        anilist_id     = anilist_id,
        season         = season,
        episode        = episode,
        audio          = audio,
        sub_channel_id = sub_ch_id,
    )
