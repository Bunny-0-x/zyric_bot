#(©)Zyric Network

import re
import aiohttp

ANILIST_URL = "https://graphql.anilist.co"

MEDIA_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id
    title { english romaji }
    status
    genres
    format
    averageScore
    startDate { year month day }
    endDate   { year month day }
    duration
    episodes
    description(asHtml: false)
    coverImage { extraLarge }
    bannerImage
    studios { nodes { name isAnimationStudio } }
  }
}
"""


def _clean(text: str | None) -> str:
    if not text:
        return "N/A"
    return re.sub(r"<[^>]+>", "", text).strip()


def _date(d: dict) -> str:
    if not d or not d.get("year"):
        return "N/A"
    return f"{d['year']}-{d.get('month', '??')}-{d.get('day', '??')}"


async def fetch_anime(anilist_id: int) -> dict | None:
    async with aiohttp.ClientSession() as s:
        async with s.post(
            ANILIST_URL,
            json={"query": MEDIA_QUERY, "variables": {"id": anilist_id}},
            headers={"Content-Type": "application/json", "Accept": "application/json"}
        ) as r:
            if r.status != 200:
                return None
            data = await r.json()

    media = data.get("data", {}).get("Media")
    if not media:
        return None

    title_en  = media["title"].get("english") or media["title"].get("romaji", "Unknown")
    title_ro  = media["title"].get("romaji", "")
    genres    = media.get("genres", [])
    studio    = next(
        (n["name"] for n in media["studios"]["nodes"] if n.get("isAnimationStudio")),
        "Unknown"
    )

    return {
        "id":           media["id"],
        "title_en":     title_en,
        "title_ro":     title_ro,
        "status":       media.get("status", "N/A"),
        "genres":       genres,
        "format":       media.get("format", "TV"),
        "rating":       media.get("averageScore") or "N/A",
        "start_date":   _date(media.get("startDate")),
        "end_date":     _date(media.get("endDate")),
        "duration":     media.get("duration") or "N/A",
        "episodes":     media.get("episodes") or "N/A",
        "synopsis":     _clean(media.get("description")),
        "poster_url":   media["coverImage"]["extraLarge"],
        "banner_url":   media.get("bannerImage") or media["coverImage"]["extraLarge"],
        "studio":       studio,
    }
