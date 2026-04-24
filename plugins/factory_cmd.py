#(©)Zyric Network

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message

from bot import Bot
from config import ADMINS
from userbot.factory import AutoFactory

_factory: AutoFactory | None = None


def _get_factory(client: Bot) -> AutoFactory:
    global _factory
    if _factory is None:
        _factory = AutoFactory(bot_client=client)
    return _factory


@Bot.on_message(filters.command("sync") & filters.private & filters.user(ADMINS))
async def cmd_sync(client: Bot, message: Message):
    """
    /sync <AniList ID> [| Season] [| Audio]
    Example: /sync 113415 | 1 | Japanese [Eng-Sub]
    """
    try:
        raw   = message.text.split("/sync", 1)[1].strip()
        parts = [p.strip() for p in raw.split("|")]
        anilist_id = int(parts[0])
        season     = int(parts[1]) if len(parts) > 1 else 1
        audio      = parts[2] if len(parts) > 2 else "Japanese [Eng-Sub]"
    except (IndexError, ValueError):
        return await message.reply(
            "❌ <b>Usage:</b>\n"
            "<code>/sync &lt;AniList ID&gt; [| Season] [| Audio]</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/sync 113415 | 1 | Japanese [Eng-Sub]</code>"
        )

    status_msg = await message.reply(
        f"🏭 <b>Auto-Factory starting sync...</b>\n"
        f"AniList ID: <code>{anilist_id}</code> | Season: <code>{season}</code>",
        quote=True
    )

    factory = _get_factory(client)

    async def update_status(text: str):
        try:
            await status_msg.edit(text)
        except Exception:
            pass

    # Start userbot if not running
    try:
        await factory.start_userbot()
    except Exception:
        pass   # Already started

    asyncio.create_task(
        factory.sync_anime(
            anilist_id      = anilist_id,
            season          = season,
            audio           = audio,
            status_callback = update_status,
        )
    )
