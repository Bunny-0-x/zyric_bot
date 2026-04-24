import asyncio
import logging
from pyrogram import Client, filters
from pipeline.uploader import upload_loop

_uploader_started = False
log = logging.getLogger(__name__)

@Client.on_message(filters.all, group=-999)
async def auto_start_uploader(client, message):
    global _uploader_started
    if not _uploader_started:
        _uploader_started = True
        log.info("🚀 Auto-starting Uploader Loop...")
        asyncio.create_task(upload_loop(client))
