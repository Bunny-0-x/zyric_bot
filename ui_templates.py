#(©)Zyric Network

SEPARATOR = "➖➖➖➖➖➖➖➖➖➖➖➖"


def type_a(
    title: str,
    status: str,
    season: int,
    episode: int,
    audio: str,
    qualities: list,
    powered_by: str = "@ZyricNetwork",
) -> str:
    """
    TYPE A — Episode Release Post
    Used in sub-channel per anime.
    """
    qualities_str = " | ".join(qualities)
    return (
        f"<b>✦ {title}</b>\n\n"
        f"<b>✦ Status :</b> {status}\n"
        f"<b>✦ Season :</b> {season:02d}\n"
        f"<b>✦ Episode :</b> {episode:02d}\n"
        f"<b>✦ Audio :</b> {audio}\n"
        f"<b>✦ Quality :</b> {qualities_str}\n"
        f"{SEPARATOR}\n"
        f"✨ <b>Powered By :</b> {powered_by}"
    )


def type_b_warning(delete_minutes: int = 10) -> str:
    """
    TYPE B — Auto-delete warning sent after file delivery.
    """
    return (
        f"> ⚠️ **This file will be automatically deleted in {delete_minutes} minutes.**\n"
        f"> Forward it to your **Saved Messages** to keep it permanently!"
    )


def type_b_deleted() -> str:
    """
    TYPE B — Ghost message sent after file is deleted.
    """
    return (
        "🗑️ <b>File Deleted</b>\n\n"
        "This file has been automatically removed.\n"
        "Request it again using the original link."
    )


def type_c(
    title_en: str,
    title_ro: str,
    genres: list,
    fmt: str,
    rating,
    status: str,
    start_date: str,
    end_date: str,
    duration,
    episodes,
    synopsis: str,
    powered_by: str = "@ZyricNetwork",
) -> str:
    """
    TYPE C — Anime Info Card
    Posted to main channel with Download Episodes button.
    """
    genres_str = ", ".join(genres) if genres else "N/A"
    return (
        f"<b>✦ {title_en}</b>\n"
        f"<i>{title_ro}</i>\n\n"
        f"<b>✦ Genres :</b> {genres_str}\n"
        f"<b>✦ Type :</b> {fmt}\n"
        f"<b>✦ Rating :</b> {rating}/100\n"
        f"<b>✦ Status :</b> {status}\n"
        f"<b>✦ Episodes :</b> {episodes}\n"
        f"<b>✦ Duration :</b> {duration} min/ep\n"
        f"<b>✦ Aired :</b> {start_date} → {end_date}\n"
        f"{SEPARATOR}\n"
        f"<blockquote><b>Synopsis:</b> {synopsis[:700]}{'...' if len(str(synopsis)) > 700 else ''}</blockquote>\n"
        f"{SEPARATOR}\n"
        f"✨ <b>Powered By :</b> {powered_by}"
    )


def type_d(
    network_name: str,
    tagline: str,
    channels: list[dict],
    slogan: str,
    powered_by: str = "@ZyricNetwork",
) -> str:
    """
    TYPE D — Network Promo Post
    channels: list of {"name": str, "url": str}
    """
    channel_lines = "\n".join(
        f"  ╰┈➤ <a href='{ch['url']}'>{ch['name']}</a>"
        for ch in channels
    )
    return (
        f"<b>🌐 {network_name}</b>\n"
        f"<i>{tagline}</i>\n\n"
        f"<b>{slogan}</b>\n\n"
        f"{SEPARATOR}\n"
        f"<b>🔗 Our Channels:</b>\n"
        f"{channel_lines}\n"
        f"{SEPARATOR}\n"
        f"✨ <b>Powered By :</b> {powered_by}"
    )
