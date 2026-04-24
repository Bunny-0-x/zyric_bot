#(©)Zyric Network

import asyncio
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

from bot import Bot
from config import ADMINS, START_MSG, START_PIC, FORCE_MSG, PROTECT_CONTENT, JOIN_REQUEST_ENABLE
from helper_func import subscribed, decode, get_messages
from database.database import add_user, present_user
from ui_templates import type_b_warning, type_b_deleted
from config import AUTO_DELETE_SECONDS


@Bot.on_message(filters.command("start") & filters.private & subscribed)
async def start_command(client: Bot, message: Message):
    uid = message.from_user.id
    if not await present_user(uid):
        await add_user(uid)

    text = message.text
    if len(text) > 7:
        # ── Deep-link: deliver files ──────────────────────────────────
        try:
            base64_string = text.split(" ", 1)[1]
        except IndexError:
            return

        string   = await decode(base64_string)
        argument = string.split("-")

        if len(argument) == 3:
            try:
                start = int(int(argument[1]) / abs(client.db_channel.id))
                end   = int(int(argument[2]) / abs(client.db_channel.id))
            except Exception:
                return
            ids = range(start, end + 1) if start <= end else range(start, end - 1, -1)
        elif len(argument) == 2:
            try:
                ids = [int(int(argument[1]) / abs(client.db_channel.id))]
            except Exception:
                return
        else:
            return

        wait_msg = await message.reply("Wait A Sec..")
        try:
            messages = await get_messages(client, list(ids))
        except Exception:
            await message.reply("Something went wrong..!")
            return
        await wait_msg.delete()

        # ── Send each file + its own warning immediately after ────────
        file_warning_pairs: list[tuple] = []   # (file_msg, warning_msg)

        for msg in messages:
            caption = msg.caption.html if msg.caption else ""

            try:
                file_msg = await msg.copy(
                    chat_id=uid,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=None,
                    protect_content=PROTECT_CONTENT
                )
            except FloodWait as e:
                await asyncio.sleep(e.value)
                file_msg = await msg.copy(
                    chat_id=uid,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=None,
                    protect_content=PROTECT_CONTENT
                )
            except Exception:
                continue

            # Send blockquote warning immediately after file
            warn_msg = await client.send_message(
                chat_id=uid,
                text=type_b_warning(),
                parse_mode=ParseMode.MARKDOWN
            )
            file_warning_pairs.append((file_msg, warn_msg))
            await asyncio.sleep(0.5)

        # ── Schedule deletion for all pairs ───────────────────────────
        if file_warning_pairs:
            asyncio.create_task(
                _auto_delete(client, uid, file_warning_pairs)
            )
        return

    # ── Normal /start ─────────────────────────────────────────────────
    reply_markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("😊 About Me", callback_data="about"),
        InlineKeyboardButton("🔒 Close",    callback_data="close")
    ]])
    fmt = dict(
        first    = message.from_user.first_name,
        last     = message.from_user.last_name,
        username = None if not message.from_user.username else "@" + message.from_user.username,
        mention  = message.from_user.mention,
        id       = message.from_user.id,
    )
    if START_PIC:
        await message.reply_photo(
            photo=START_PIC,
            caption=START_MSG.format(**fmt),
            reply_markup=reply_markup,
            quote=True
        )
    else:
        await message.reply_text(
            text=START_MSG.format(**fmt),
            reply_markup=reply_markup,
            disable_web_page_preview=True,
            quote=True
        )


async def _auto_delete(client: Bot, chat_id: int, pairs: list[tuple]):
    """
    Non-blocking: waits 600 seconds then deletes every file+warning pair
    and sends the ghosting message in place of each.
    """
    await asyncio.sleep(AUTO_DELETE_SECONDS)
    for file_msg, warn_msg in pairs:
        try:
            await client.delete_messages(chat_id=chat_id,
                                          message_ids=[file_msg.id, warn_msg.id])
        except Exception:
            pass
        try:
            await client.send_message(chat_id=chat_id, text=type_b_deleted())
        except Exception:
            pass
        await asyncio.sleep(0.3)


@Bot.on_message(filters.command("start") & filters.private)
async def not_joined(client: Bot, message: Message):
    if JOIN_REQUEST_ENABLE:
        invite = await client.create_chat_invite_link(
            chat_id=client.fsub_channels[0]["id"] if client.fsub_channels else 0,
            creates_join_request=True
        )
        btn_url = invite.invite_link
    else:
        btn_url = client.invitelink if hasattr(client, "invitelink") else "#"

    buttons = []
    for ch in client.fsub_channels:
        buttons.append([InlineKeyboardButton(f"Join {ch['title']} 📢", url=ch["invite_link"])])

    try:
        buttons.append([InlineKeyboardButton(
            "Try Again 🔄",
            url=f"https://t.me/{client.username}?start={message.command[1]}"
        )])
    except IndexError:
        pass

    if START_PIC:
        await message.reply_photo(
            photo=START_PIC,
            caption=FORCE_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name,
                username=None if not message.from_user.username else "@" + message.from_user.username,
                mention=message.from_user.mention,
                id=message.from_user.id,
            ),
            reply_markup=InlineKeyboardMarkup(buttons),
            quote=True
        )
    else:
        await message.reply(
            text=FORCE_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name,
                username=None if not message.from_user.username else "@" + message.from_user.username,
                mention=message.from_user.mention,
                id=message.from_user.id,
            ),
            reply_markup=InlineKeyboardMarkup(buttons),
            quote=True,
            disable_web_page_preview=True
        )
