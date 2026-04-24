#(©)Zyric Network

import asyncio
import json
from config import (
    TG_BOT_TOKEN, CHANNEL_ID, OWNER_ID,
    TELEGRAM_FLEET, APP_ID, API_HASH, LOGGER
)
from bot import Bot

log = LOGGER(__name__)
running_bots: dict[str, Bot] = {}


async def launch_bot(token: str, dump_channel: int, owner_id: int) -> Bot | None:
    try:
        b = Bot(token=token, db_channel_id=dump_channel, owner_id=owner_id)
        await b.start()
        running_bots[token] = b
        log.info(f"✅ Bot @{b.username} launched.")
        return b
    except Exception as e:
        log.warning(f"❌ Bot launch failed ({token[:10]}...): {e}")
        return None


async def main():
    print("""
███████╗██╗   ██╗██████╗ ██╗ ██████╗
╚══███╔╝╚██╗ ██╔╝██╔══██╗██║██╔════╝
  ███╔╝  ╚████╔╝ ██████╔╝██║██║
 ███╔╝    ╚██╔╝  ██╔══██╗██║██║
███████╗   ██║   ██║  ██║██║╚██████╗
╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝ ╚═════╝
    Zyric Network — Multi-Bot Fleet
""")

    # Build fleet list: master bot + any additional from TELEGRAM_FLEET
    fleet = [{"token": TG_BOT_TOKEN, "dump_channel": CHANNEL_ID, "owner_id": OWNER_ID}]
    for entry in TELEGRAM_FLEET:
        if entry.get("token") and entry.get("dump_channel"):
            fleet.append({
                "token":        entry["token"],
                "dump_channel": int(entry["dump_channel"]),
                "owner_id":     int(entry.get("owner_id", OWNER_ID)),
            })

    log.info(f"Launching {len(fleet)} bot(s)...")
    results = await asyncio.gather(*[
        launch_bot(f["token"], f["dump_channel"], f["owner_id"])
        for f in fleet
    ], return_exceptions=True)

    alive = [r for r in results if isinstance(r, Bot)]
    log.info(f"{len(alive)}/{len(fleet)} bot(s) running.")

    if not alive:
        log.error("No bots launched. Exiting.")
        return

    await asyncio.Event().wait()   # Run forever


if __name__ == "__main__":
    asyncio.run(main())
