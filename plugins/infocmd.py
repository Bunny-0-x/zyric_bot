#(©)Zyric Network — Pipeline Commands

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from config import ADMINS
from pipeline.metrics import format_stats, format_failed
from pipeline.redis_queue import requeue_failed

@Client.on_message(filters.command("pstats") & filters.private & filters.user(ADMINS), group=-1)
async def cmd_pipeline_stats(client, message):
    await message.reply(format_stats(), parse_mode=ParseMode.HTML)

@Client.on_message(filters.command("pfailed") & filters.private & filters.user(ADMINS), group=-1)
async def cmd_pipeline_failed(client, message):
    await message.reply(format_failed(), parse_mode=ParseMode.HTML)

@Client.on_message(filters.command("prequeue") & filters.private & filters.user(ADMINS), group=-1)
async def cmd_requeue(client, message):
    n = requeue_failed()
    await message.reply(f"✅ Requeued {n} failed jobs.")
