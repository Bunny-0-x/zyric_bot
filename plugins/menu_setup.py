from pyrogram import Client, filters
from pyrogram.types import BotCommand

@Client.on_message(filters.command("setmenu"))
async def setup_menu(client, message):
    commands = [
        BotCommand("start", "start the bot or get posts"),
        BotCommand("batch", "create link for more than one posts"),
        BotCommand("genlink", "create link for one post"),
        BotCommand("users", "view bot statistics"),
        BotCommand("broadcast", "broadcast any messages to bot users"),
        BotCommand("stats", "checking your bot up")
    ]
    await client.set_bot_commands(commands)
    await message.reply("✅ Bot menu updated successfully! (Restart your Telegram app if the button doesn't appear instantly).")
