#(©)Zyric Network — Download Worker

import asyncio
import os
import time
import logging
import signal
from pipeline.redis_queue import pop_job, complete_job, fail_job

log = logging.getLogger(__name__)
WORKER_ID     = os.environ.get("WORKER_ID", "w1")
SHUTDOWN_FLAG = False

def _handle_signal(sig, frame):
    global SHUTDOWN_FLAG
    log.info(f"[Worker {WORKER_ID}] Shutdown signal received...")
    SHUTDOWN_FLAG = True

async def run_worker():
    from scrapper import AnimePaheScraper
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT,  _handle_signal)

    log.info(f"[Worker {WORKER_ID}] Starting...")
    scraper = AnimePaheScraper()
    await scraper.start()

    try:
        while not SHUTDOWN_FLAG:
            job = pop_job(timeout=5)
            if not job: continue

            anime, ep_num, url = job["anime"], job["ep_num"], job["url"]
            log.info(f"[Worker {WORKER_ID}] Intercepting: {anime} EP{ep_num}")
            
            try:
                # 1. Intercept to find all resolutions
                streams = await scraper.intercept_video_stream(url)
                if not streams:
                    fail_job(job, "No streams intercepted")
                    continue

                log.info(f"[Worker {WORKER_ID}] Found {len(streams)} qualities: {list(streams.keys())}")

                # 2. Prepare concurrent downloads
                tasks = []
                qualities_ordered = list(streams.keys())
                for q in qualities_ordered:
                    tasks.append(scraper.download_stream(streams[q], q, anime, ep_num))

                # 3. Download ALL concurrently
                results = await asyncio.gather(*tasks, return_exceptions=True)

                total_mb = 0
                successful_uploads = 0

                # 4. Push successful ones to Telegram Uploader
                for q, res in zip(qualities_ordered, results):
                    if isinstance(res, Exception) or not res or not os.path.exists(res):
                        log.error(f"[Worker {WORKER_ID}] Failed to download {q}")
                        continue
                    
                    size_mb = os.path.getsize(res) / 1024 / 1024
                    total_mb += size_mb
                    successful_uploads += 1
                    
                    # Push this specific file to the bot's upload queue
                    await _notify_bot(job, res, q, len(streams))

                # 5. Mark Job Complete
                if successful_uploads > 0:
                    complete_job(job, total_mb)
                else:
                    fail_job(job, "All resolution downloads failed")

            except Exception as e:
                log.error(f"[Worker {WORKER_ID}] Job error: {e}")
                fail_job(job, str(e))
    finally:
        await scraper.stop()
        log.info(f"[Worker {WORKER_ID}] Stopped cleanly.")

async def _notify_bot(job: dict, file_path: str, quality: str, total_expected: int):
    import redis, json
    r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
    payload = {
        **job, 
        "file_path": file_path, 
        "quality": quality, 
        "total_expected": total_expected
    }
    r.lpush("zyric:uploads:pending", json.dumps(payload))
    log.info(f"[Worker {WORKER_ID}] Upload queued: {job['anime']} EP{job['ep_num']} [{quality}]")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=f"[%(asctime)s] [Worker {WORKER_ID}] %(levelname)s — %(message)s", datefmt="%H:%M:%S")
    asyncio.run(run_worker())
