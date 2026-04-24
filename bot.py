#(©)Zyric Network

from aiohttp import web
from plugins import web_server

import pyromod.listen
from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.raw import functions, types as raw_types
import sys
import asyncio
import aiohttp
from datetime import datetime

from config import API_HASH, APP_ID, LOGGER, TG_BOT_TOKEN, TG_BOT_WORKERS, CHANNEL_ID, OWNER_ID as CFG_OWNER, PORT
from database.database import add_fsub_channel, get_fsub_channels, update_fsub_link


ascii_art = """
███████╗██╗   ██╗██████╗ ██╗ ██████╗
╚══███╔╝╚██╗ ██╔╝██╔══██╗██║██╔════╝
  ███╔╝  ╚████╔╝ ██████╔╝██║██║     
 ███╔╝    ╚██╔╝  ██╔══██╗██║██║     
███████╗   ██║   ██║  ██║██║╚██████╗
╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝ ╚═════╝
"""


class Bot(Client):
    def __init__(self, token: str = None, db_channel_id: int = None, owner_id: int = None):
        _token   = token or TG_BOT_TOKEN
        _session = f"Bot_{_token.split(':')[0]}"

        super().__init__(
            name      = _session,
            api_hash  = API_HASH,
            api_id    = APP_ID,
            plugins   = {"root": "plugins"},
            workers   = TG_BOT_WORKERS,
            bot_token = _token
        )
        self.LOGGER        = LOGGER
        self.token         = _token
        self.db_channel_id = db_channel_id or CHANNEL_ID
        self.owner_id      = owner_id or CFG_OWNER
        self.bot_id        = _token.split(":")[0]
        self.fsub_channels = []
        self.settings      = {}
        self.uptime        = None

    async def seed_peer(self, channel_id: int):
        """
        Force resolves a channel peer via raw MTProto.
        Falls back to Bot API HTTP if session has no cache.
        Works on completely fresh sessions.
        """
        clean_id = int(str(channel_id).replace("-100", ""))

        # Method 1: Raw MTProto
        try:
            await self.invoke(functions.channels.GetChannels(
                id=[raw_types.InputChannel(channel_id=clean_id, access_hash=0)]
            ))
            return True
        except Exception:
            pass

        # Method 2: Bot API HTTP
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.telegram.org/bot{self.token}/getChat"
                async with session.get(url, params={"chat_id": channel_id}) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        try:
                            send_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
                            async with session.post(send_url, json={"chat_id": channel_id, "text": "."}) as sr:
                                sd = await sr.json()
                                if sd.get("ok"):
                                    msg_id = sd["result"]["message_id"]
                                    del_url = f"https://api.telegram.org/bot{self.token}/deleteMessage"
                                    await session.post(del_url, json={"chat_id": channel_id, "message_id": msg_id})
                        except Exception:
                            pass
                        try:
                            await self.invoke(functions.channels.GetChannels(
                                id=[raw_types.InputChannel(channel_id=clean_id, access_hash=0)]
                            ))
                        except Exception:
                            pass
                        return True
        except Exception as e:
            self.LOGGER(__name__).warning(f"[Bot {self.bot_id}] seed_peer failed for {channel_id}: {e}")

        return False

    async def load_fsub_channels(self):
        """Load all dynamic fsub channels from DB and seed their peers."""
        channels = await get_fsub_channels()
        self.fsub_channels = []
        for ch in channels:
            channel_id = ch["_id"]
            await self.seed_peer(channel_id)
            try:
                chat        = await self.get_chat(channel_id)
                invite_link = ch.get("invite_link")
                if not invite_link:
                    try:
                        invite_link = chat.invite_link or await self.export_chat_invite_link(channel_id)
                        await update_fsub_link(channel_id, invite_link)
                    except Exception:
                        pass
                self.fsub_channels.append({
                    "id":          channel_id,
                    "title":       chat.title,
                    "invite_link": invite_link
                })
                self.LOGGER(__name__).info(f"[Bot {self.bot_id}] Loaded fsub: {chat.title} ({channel_id})")
            except Exception as e:
                self.LOGGER(__name__).warning(f"[Bot {self.bot_id}] Could not load fsub {channel_id}: {e}")

    async def start(self):
        await super().start()
        usr_bot_me  = await self.get_me()
        self.uptime = datetime.now()
        self.username = usr_bot_me.username

        self.LOGGER(__name__).info(f"Starting bot: @{self.username} (ID: {self.bot_id})")

        # Load dynamic fsub channels
        await self.load_fsub_channels()

        # Setup DB channel
        try:
            await self.seed_peer(self.db_channel_id)
            db_channel      = await self.get_chat(self.db_channel_id)
            self.db_channel = db_channel
            test = await self.send_message(chat_id=db_channel.id, text="Test Message")
            await test.delete()
            self.LOGGER(__name__).info(f"[Bot @{self.username}] DB Channel: {db_channel.title}")
        except Exception as e:
            self.LOGGER(__name__).warning(e)
            self.LOGGER(__name__).warning(
                f"Make sure bot is Admin in DB Channel. "
                f"Current CHANNEL_ID: {self.db_channel_id}"
            )
            self.LOGGER(__name__).info("\nBot Stopped. Join https://t.me/ZyricSupport for support")
            sys.exit()

        self.set_parse_mode(ParseMode.HTML)
        from pipeline.uploader import upload_loop
        asyncio.create_task(upload_loop(self))
        self.LOGGER(__name__).info(f"[Bot @{self.username}] Running!")
        print(ascii_art)
        print("Welcome to Zyric Network File Sharing Bot")

        # Web server
        app = web.AppRunner(await web_server())
        await app.setup()
        await web.TCPSite(app, "0.0.0.0", PORT).start()

    async def stop(self, *args):
        await super().stop()
        self.LOGGER(__name__).info(f"[Bot @{self.username}] Stopped.")
