#(©)Zyric Network — Production Scrapper v4

import asyncio
import urllib.parse
import os
import json
import subprocess
import aiohttp
import re
import logging
import random
from playwright.async_api import async_playwright

log = logging.getLogger(__name__)

QUALITIES    = ["1080p", "720p", "480p", "360p"]
BRAVE_PATH   = "/usr/bin/brave-browser"
STATE_FILE   = "zyric_state.json"
COOKIE_FILE  = "zyric_cookies.txt"   # Netscape format for yt-dlp
DOWNLOAD_DIR = "./downloads"
TEMP_DIR     = "./downloads/temp_ts"
MAX_DISK_GB  = 20

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

BROWSER_ARGS = [
    "--no-sandbox", "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
    "--disable-gpu",
]

AIOHTTP_TIMEOUT = aiohttp.ClientTimeout(total=60, connect=10)

# Domain-level rate limiting (1 req/sec per domain)
_DOMAIN_LOCKS: dict[str, asyncio.Lock] = {}
_DOMAIN_LAST:  dict[str, float]        = {}

async def _rate_limit(url: str, delay: float = 1.0):
    import time
    domain = urllib.parse.urlparse(url).netloc
    if domain not in _DOMAIN_LOCKS:
        _DOMAIN_LOCKS[domain] = asyncio.Lock()
        _DOMAIN_LAST[domain]  = 0.0
    async with _DOMAIN_LOCKS[domain]:
        elapsed = time.monotonic() - _DOMAIN_LAST[domain]
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        _DOMAIN_LAST[domain] = time.monotonic()


def _state_to_netscape(state_path: str, out_path: str):
    """Convert Playwright storage_state JSON → Netscape cookie file for yt-dlp."""
    try:
        with open(state_path) as f:
            state = json.load(f)
        cookies = state.get("cookies", [])
        with open(out_path, "w") as f:
            f.write("# Netscape HTTP Cookie File\n")
            for c in cookies:
                domain   = c.get("domain", "")
                flag     = "TRUE" if domain.startswith(".") else "FALSE"
                path     = c.get("path", "/")
                secure   = "TRUE" if c.get("secure") else "FALSE"
                expires  = str(int(c.get("expires", 0))) if c.get("expires", 0) > 0 else "0"
                name     = c.get("name", "")
                value    = c.get("value", "")
                f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")
        log.info(f"[Cookies] Converted {len(cookies)} cookies → Netscape format")
    except Exception as e:
        log.warning(f"[Cookies] Conversion failed: {e}")


def _check_and_clean_disk():
    """Auto-delete oldest downloads if disk exceeds MAX_DISK_GB."""
    try:
        files = []
        for dp, _, fnames in os.walk(DOWNLOAD_DIR):
            for fn in fnames:
                fp = os.path.join(dp, fn)
                files.append((os.path.getmtime(fp), fp, os.path.getsize(fp)))
        total_gb = sum(f[2] for f in files) / 1024 ** 3
        if total_gb > MAX_DISK_GB:
            log.warning(f"[Disk] {total_gb:.1f}GB used — auto-cleaning oldest files...")
            files.sort()  # oldest first
            for mtime, fp, size in files:
                if total_gb <= MAX_DISK_GB * 0.8:
                    break
                os.remove(fp)
                total_gb -= size / 1024 ** 3
                log.info(f"[Disk] Deleted {fp}")
    except Exception as e:
        log.warning(f"[Disk] Cleanup error: {e}")


class AnimePaheScraper:
    def __init__(self):
        self.base_url    = "https://animepahe.com"
        self._playwright = None
        self._browser    = None
        self._context    = None
        # Instance-level semaphores (no global bottleneck)
        self.page_sem    = asyncio.Semaphore(3)
        self.dl_sem      = asyncio.Semaphore(10)
        self.seg_sem     = asyncio.Semaphore(20)

    @property
    def _ua(self):
        return random.choice(USER_AGENTS)

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def start(self):
        self._playwright = await async_playwright().start()
        await self._launch_browser()
        log.info("[Browser] Started.")

    async def _launch_browser(self):
        # Cleanly close old context before creating new one
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        self._browser = await self._playwright.chromium.launch(**self._launch_kwargs())
        ctx_kwargs = {"user_agent": self._ua}
        if os.path.exists(STATE_FILE):
            ctx_kwargs["storage_state"] = STATE_FILE
        self._context = await self._browser.new_context(**ctx_kwargs)
        log.info("[Browser] (Re)launched with clean context.")

    def _launch_kwargs(self) -> dict:
        base = {"headless": True, "args": BROWSER_ARGS}
        if os.path.exists(BRAVE_PATH):
            base["executable_path"] = BRAVE_PATH
        return base

    async def _ensure_browser(self):
        try:
            if not self._browser or not self._browser.is_connected():
                log.warning("[Browser] Disconnected — recovering...")
                await self._launch_browser()
        except Exception as e:
            log.error(f"[Browser] Recovery failed: {e}")
            await self._launch_browser()

    async def stop(self):
        try:
            if self._context:
                await self._context.storage_state(path=STATE_FILE)
                _state_to_netscape(STATE_FILE, COOKIE_FILE)
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            log.info("[Browser] Stopped cleanly.")
        except Exception as e:
            log.warning(f"[Browser] Stop error: {e}")

    async def _new_page(self):
        await self._ensure_browser()
        return await self._context.new_page()

    # ── Phase 1: Search ───────────────────────────────────────────────

    async def search_and_get_episodes(self, anime_title: str) -> list:
        log.info(f"[Search] '{anime_title}'")
        encoded = urllib.parse.quote(anime_title)
        episodes = []

        async with self.page_sem:
            page = await self._new_page()
            try:
                await page.goto(
                    self.base_url, timeout=60_000,
                    wait_until="domcontentloaded"
                )
                await page.wait_for_timeout(2500)
                await page.wait_for_function(
                    "() => typeof fetch !== 'undefined'", timeout=15000
                )

                search_data = await page.evaluate(f"""async () => {{
                    try {{
                        const r = await fetch('/api?m=search&q={encoded}');
                        return await r.json();
                    }} catch(e) {{ return null; }}
                }}""")

                if not search_data or not search_data.get("data"):
                    log.warning("[Search] No results.")
                    return []

                anime      = search_data["data"][0]
                session_id = anime["session"]
                title      = anime["title"]
                log.info(f"[Search] Match: {title}")

                ep1 = await page.evaluate(f"""async () => {{
                    try {{
                        const r = await fetch('/api?m=release&id={session_id}&sort=episode_asc&page=1');
                        return await r.json();
                    }} catch(e) {{ return null; }}
                }}""")

                if not ep1 or not ep1.get("data"):
                    return []

                total_pages = ep1.get("last_page", 1)
                for ep in ep1["data"]:
                    episodes.append({
                        "title":   title,
                        "ep_num":  ep["episode"],
                        "session": ep["session"],
                        "url":     f"{self.base_url}/play/{session_id}/{ep['session']}"
                    })

                for pnum in range(2, total_pages + 1):
                    ep_data = await page.evaluate(f"""async () => {{
                        try {{
                            const r = await fetch('/api?m=release&id={session_id}&sort=episode_asc&page={pnum}');
                            return await r.json();
                        }} catch(e) {{ return null; }}
                    }}""")
                    if ep_data and ep_data.get("data"):
                        for ep in ep_data["data"]:
                            episodes.append({
                                "title":   title,
                                "ep_num":  ep["episode"],
                                "session": ep["session"],
                                "url":     f"{self.base_url}/play/{session_id}/{ep['session']}"
                            })

                log.info(f"[Search] {len(episodes)} episodes found.")
                return episodes

            except Exception as e:
                log.error(f"[Search] Error: {e}")
                return []
            finally:
                await page.close()

    # ── Phase 2: Interception ─────────────────────────────────────────

    async def intercept_video_stream(self, episode_url: str) -> dict:
        log.info(f"[Intercept] {episode_url}")
        m3u8_links = {}

        async with self.page_sem:
            page = await self._new_page()
            try:
                await page.goto(
                    episode_url, timeout=60_000,
                    wait_until="domcontentloaded"
                )
                await page.wait_for_timeout(2500)
                try:
                    await page.wait_for_selector("[data-src]", timeout=15_000)
                except Exception:
                    pass

                kwik_links = await page.evaluate("""() => {
                    const urls = {};
                    document.querySelectorAll('[data-src]').forEach(el => {
                        const res = el.getAttribute('data-resolution') || el.textContent.trim();
                        const src = el.getAttribute('data-src');
                        if (src && (src.includes('kwik') || src.includes('pahe') || src.includes('cdn'))) {
                            const m = res.match(/\\d+/);
                            urls[m ? m[0] + 'p' : 'unknown'] = src;
                        }
                    });
                    return urls;
                }""")

                if not kwik_links:
                    log.warning("[Intercept] No source links found.")
                    return {}

                captured  = {}
                ev_map    = {q: asyncio.Event() for q in kwik_links}
                current_q = {"v": None}

                async def handle_route(route, request):
                    url    = request.url
                    accept = request.headers.get("accept", "")
                    is_stream = (
                        ".m3u8" in url or
                        "m3u8" in accept or
                        ("owocdn" in url and "uwu" in url and "thumbs" not in url) or
                        bool(re.search(r'\.(m3u8|mpd)(\?|$)', url))
                    )
                    if is_stream and "thumbs" not in url:
                        q = current_q["v"]
                        if q and not captured.get(q):
                            captured[q] = url
                            ev_map[q].set()
                    await route.continue_()

                await page.route("**/*", handle_route)

                for quality, kwik_url in kwik_links.items():
                    current_q["v"] = quality
                    ev_map[quality].clear()
                    await _rate_limit(kwik_url, delay=1.0)
                    await page.set_extra_http_headers({"Referer": self.base_url})
                    await page.goto(kwik_url, timeout=60_000)

                    try:
                        await asyncio.wait_for(ev_map[quality].wait(), timeout=12.0)
                        if captured.get(quality):
                            m3u8_links[quality] = captured[quality]
                            log.info(f"[Intercept] Got {quality}")
                    except asyncio.TimeoutError:
                        try:
                            await page.wait_for_selector("video", state="attached", timeout=5000)
                            await page.evaluate("() => { const v = document.querySelector('video'); if(v) v.play(); }")
                            await asyncio.wait_for(ev_map[quality].wait(), timeout=8.0)
                            if captured.get(quality):
                                m3u8_links[quality] = captured[quality]
                                log.info(f"[Intercept] Got {quality} (JS fallback)")
                        except Exception:
                            log.warning(f"[Intercept] Timeout for {quality}")

                # Save state AND convert to Netscape for yt-dlp
                await self._context.storage_state(path=STATE_FILE)
                _state_to_netscape(STATE_FILE, COOKIE_FILE)
                return m3u8_links

            except Exception as e:
                log.error(f"[Intercept] Error: {e}")
                return {}
            finally:
                await page.close()

    # ── Phase 3: Download ─────────────────────────────────────────────

    async def download_stream(self, stream_url: str, quality: str,
                               anime_title: str, ep_num) -> str | None:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        _check_and_clean_disk()

        safe      = anime_title.replace(" ", "_").replace("/", "").replace(":", "")
        file_path = f"{DOWNLOAD_DIR}/{safe}_Ep{ep_num}_{quality}.mkv"

        async with self.dl_sem:
            for attempt in range(1, 4):
                log.info(f"[Download] Attempt {attempt}/3 — {quality} EP{ep_num}")

                # 1. yt-dlp + aria2c
                ok = await asyncio.to_thread(
                    self._yt_dlp_download, stream_url, file_path, True
                )
                if ok:
                    return file_path

                # 2. yt-dlp native (no aria2c — aria2 helps less with HLS)
                ok = await asyncio.to_thread(
                    self._yt_dlp_download, stream_url, file_path, False
                )
                if ok:
                    return file_path

                # 3. ffmpeg direct (no timeout — let it run)
                ok = await asyncio.to_thread(
                    self._ffmpeg_download, stream_url, file_path
                )
                if ok:
                    return file_path

                # 4. Segment downloader (last resort)
                ts_path = file_path.replace(".mkv", ".ts")
                result  = await self._segment_downloader(stream_url, ts_path)
                if result:
                    return result

                log.warning(f"[Download] Attempt {attempt} failed. Retrying in 10s...")
                await asyncio.sleep(10)

        log.error(f"[Download] All attempts exhausted for EP{ep_num} {quality}")
        return None

    def _yt_dlp_download(self, url: str, out_path: str, use_aria2: bool) -> bool:
        import yt_dlp
        ydl_opts = {
            "format":       "bestvideo+bestaudio/best",
            "outtmpl":      out_path,
            "concurrent_fragment_downloads": 25,
            "retries":      5,
            "quiet":        False,
            "no_warnings":  False,
            # Use properly converted Netscape cookie file
            "cookiefile":   COOKIE_FILE if os.path.exists(COOKIE_FILE) else None,
            "http_headers": {
                "Referer":    "https://kwik.cx/",
                "Origin":     "https://kwik.cx",
                "User-Agent": self._ua,
            }
        }
        has_aria2 = subprocess.run(
            ["which", "aria2c"], capture_output=True
        ).returncode == 0
        if use_aria2 and has_aria2:
            ydl_opts["external_downloader"] = "aria2c"
            ydl_opts["external_downloader_args"] = [
                "-x", "16", "-k", "1M",
                "--min-split-size=1M",
                "--max-connection-per-server=16",
            ]
            log.info("[yt-dlp] Using aria2c")
        else:
            log.info("[yt-dlp] Native mode")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            ok = os.path.exists(out_path) and os.path.getsize(out_path) > 10_000
            if ok:
                log.info(f"[yt-dlp] OK — {os.path.getsize(out_path)//1024//1024}MB")
            return ok
        except Exception as e:
            log.warning(f"[yt-dlp] Error: {e}")
            return False

    def _ffmpeg_download(self, m3u8_url: str, out_path: str) -> bool:
        cmd = [
            "ffmpeg", "-y",
            "-headers", "Referer: https://kwik.cx/\r\nOrigin: https://kwik.cx\r\n",
            "-i", m3u8_url,
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            out_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True)  # No timeout
            ok = os.path.exists(out_path) and os.path.getsize(out_path) > 10_000
            if ok:
                log.info(f"[ffmpeg] OK — {os.path.getsize(out_path)//1024//1024}MB")
            else:
                log.warning(f"[ffmpeg] Failed: {result.stderr.decode()[-300:]}")
            return ok
        except Exception as e:
            log.warning(f"[ffmpeg] Error: {e}")
            return False

    async def _segment_downloader(self, m3u8_url: str, output_path: str):
        log.info("[Segments] Last resort")
        headers = {
            "Referer":    "https://kwik.cx/",
            "Origin":     "https://kwik.cx",
            "User-Agent": self._ua,
        }
        async with aiohttp.ClientSession(
            headers=headers, timeout=AIOHTTP_TIMEOUT
        ) as session:
            async with session.get(m3u8_url) as resp:
                if resp.status != 200:
                    return None
                manifest = await resp.text()

            base = m3u8_url.rsplit("/", 1)[0] + "/"

            if "#EXT-X-STREAM-INF" in manifest:
                lines    = manifest.splitlines()
                variants = []
                for i, line in enumerate(lines):
                    if line.startswith("#EXT-X-STREAM-INF"):
                        bw  = int(re.search(r"BANDWIDTH=(\d+)", line).group(1)) if re.search(r"BANDWIDTH=(\d+)", line) else 0
                        uri = lines[i + 1].strip()
                        variants.append((bw, uri))
                if variants:
                    best    = max(variants, key=lambda x: x[0])[1]
                    sub_url = best if best.startswith("http") else base + best
                    async with session.get(sub_url) as sr:
                        manifest = await sr.text()
                        base     = sub_url.rsplit("/", 1)[0] + "/"

            segments = [l.strip() for l in manifest.splitlines() if l and not l.startswith("#")]
            if not segments:
                return None

            log.info(f"[Segments] {len(segments)} segments")
            os.makedirs(TEMP_DIR, exist_ok=True)

            async def dl_chunk(idx, seg):
                url  = seg if seg.startswith("http") else base + seg
                path = os.path.join(TEMP_DIR, f"seg_{idx:05d}.ts")
                await _rate_limit(url, delay=0.05)
                async with self.seg_sem:
                    for _ in range(3):
                        try:
                            async with session.get(url) as cr:
                                if cr.status == 200:
                                    with open(path, "wb") as f:
                                        f.write(await cr.read())
                                    return path
                        except Exception:
                            await asyncio.sleep(1)
                return None

            results = await asyncio.gather(*[dl_chunk(i, s) for i, s in enumerate(segments)])
            if None in results:
                log.warning("[Segments] Some segments failed")
                return None

            ts_list = os.path.join(TEMP_DIR, "list.txt")
            with open(ts_list, "w") as f:
                for ts in sorted(r for r in results if r):
                    f.write(f"file '{os.path.abspath(ts)}'\n")

            mkv_out = output_path.replace(".ts", ".mkv")
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                 "-i", ts_list, "-c", "copy", mkv_out],
                capture_output=True
            )

            for ts in results:
                if ts and os.path.exists(ts):
                    os.remove(ts)

            if os.path.exists(mkv_out) and os.path.getsize(mkv_out) > 10_000:
                log.info(f"[Segments] Done — {os.path.getsize(mkv_out)//1024//1024}MB")
                return mkv_out
            return None


# ── Singleton with async lock ─────────────────────────────────────────

_scraper = AnimePaheScraper()
_started = False
_lock    = asyncio.Lock()

async def _ensure_started():
    global _started
    async with _lock:
        if not _started:
            await _scraper.start()
            _started = True

async def search_anime(title: str) -> list:
    await _ensure_started()
    return await _scraper.search_and_get_episodes(title)

async def intercept_streams(episode_url: str) -> dict:
    await _ensure_started()
    return await _scraper.intercept_video_stream(episode_url)

async def download_episode(m3u8_url: str, anime_title: str, ep_num, quality: str):
    await _ensure_started()
    return await _scraper.download_stream(m3u8_url, quality, anime_title, ep_num)


# ── Standalone test ───────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s — %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("scrapper.log"),
        ]
    )

    async def run_test():
        s = AnimePaheScraper()
        await s.start()
        try:
            episodes = await s.search_and_get_episodes("Dandadan")
            if not episodes:
                print("No episodes.")
                return
            ep      = episodes[0]
            streams = await s.intercept_video_stream(ep["url"])
            if not streams:
                print("No streams.")
                return
            quality = next((q for q in QUALITIES if q in streams), None)
            if not quality:
                return
            result = await s.download_stream(
                streams[quality], quality, ep["title"], ep["ep_num"]
            )
            if result and os.path.exists(result):
                print(f"\n🎉 Done: {result} ({os.path.getsize(result)//1024//1024}MB)")
            else:
                print("\n❌ Download failed")
        finally:
            await s.stop()

    asyncio.run(run_test())
