#(©)Zyric Network

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

from bot import Bot
from config import ADMINS
from ui_templates import type_d


@Bot.on_message(filters.command("promo") & filters.private & filters.user(ADMINS))
async def cmd_promo(client: Bot, message: Message):
    """
    /promo
    Posts the Type D network promo to the current chat or configured promo channel.
    Edit NETWORK_* and SISTER_CHANNELS below to match your network.
    """
    NETWORK_NAME = "ZYRIC NETWORK"
    TAGLINE      = "where anime lives"
    SLOGAN       = "One Stop For Anime!"

    # Configure your sister channels here
    SISTER_CHANNELS = [
        {"name": "Anime Channel",        "url": "https://t.me/yourchannel1"},
        {"name": "Ongoing Channel",      "url": "https://t.me/yourchannel2"},
        {"name": "Anime Movies Channel", "url": "https://t.me/yourchannel3"},
        {"name": "Adult Channel",        "url": "https://t.me/yourchannel4"},
        {"name": "Movies & Series",      "url": "https://t.me/yourchannel5"},
        {"name": "Manga & Manhwas",      "url": "https://t.me/yourchannel6"},
    ]

    caption = type_d(
        network_name = NETWORK_NAME,
        tagline      = TAGLINE,
        channels     = SISTER_CHANNELS,
        slogan       = SLOGAN,
    )

    # Send with banner GIF/video if configured
    PROMO_BANNER = ""  # Set to a file_id or URL of your banner GIF/video

    if PROMO_BANNER:
        await client.send_video(
            chat_id    = message.chat.id,
            video      = PROMO_BANNER,
            caption    = caption,
            parse_mode = ParseMode.HTML
        )
    else:
        await client.send_message(
            chat_id            = message.chat.id,
            text               = caption,
            parse_mode         = ParseMode.HTML,
            disable_web_page_preview = True
        )
