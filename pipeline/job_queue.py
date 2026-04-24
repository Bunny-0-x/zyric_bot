#(©)Zyric Network — Fault-Tolerant Redis Job Queue v2

import json
import time
import redis
import logging

log = logging.getLogger(__name__)

_r = None

def get_redis():
    global _r
    if _r is None:
        _r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
    try:
        _r.ping()
    except Exception:
        log.warning("[Redis] Reconnecting...")
        _r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
    return _r

QUEUE_PENDING  = "zyric:jobs:pending"
QUEUE_ACTIVE   = "zyric:jobs:active"   # now a LIST not HASH
QUEUE_FAILED   = "zyric:jobs:failed"
QUEUE_DONE     = "zyric:jobs:done"
QUEUE_PROGRESS = "zyric:jobs:progress" # hash: job_id → progress json
METRICS_KEY    = "zyric:metrics"

MAX_QUEUE_SIZE  = 500     # backpressure limit
JOB_TIMEOUT_SEC = 1800    # 30 min — stuck job threshold
UPLOAD_MAX_RETRY = 3


def push_job(anime_title: str, ep_num, quality: str, m3u8_url: str,
             anilist_id: int = 0, season: int = 1) -> str | None:
    r = get_redis()
    # Backpressure — don't overload queue
    pending = r.llen(QUEUE_PENDING)
    if pending >= MAX_QUEUE_SIZE:
        log.warning(f"[Queue] Backpressure: {pending} jobs pending, not pushing.")
        return None
    job = {
        "id":         f"{anilist_id}_{season}_{ep_num}_{quality}_{int(time.time())}",
        "anime":      anime_title,
        "ep_num":     ep_num,
        "quality":    quality,
        "url":        m3u8_url,
        "anilist_id": anilist_id,
        "season":     season,
        "retries":    0,
        "created_at": time.time(),
        "error":      None,
    }
    r.lpush(QUEUE_PENDING, json.dumps(job))
    log.info(f"[Queue] Pushed: {anime_title} EP{ep_num} {quality} (pending: {pending+1})")
    return job["id"]


def pop_job(timeout: int = 5) -> dict | None:
    r = get_redis()
    # ATOMIC: move directly from pending → active (no data loss on crash)
    raw = r.brpoplpush(QUEUE_PENDING, QUEUE_ACTIVE, timeout)
    if not raw:
        return None
    job = json.loads(raw)
    job["_raw"]       = raw   # keep original for removal
    job["started_at"] = time.time()
    # Update the active entry with start time
    r.lrem(QUEUE_ACTIVE, 1, raw)
    updated_raw = json.dumps({k: v for k, v in job.items() if k != "_raw"})
    r.lpush(QUEUE_ACTIVE, updated_raw)
    job["_raw"] = updated_raw
    return job


def update_progress(job_id: str, percent: float, speed_mbps: float,
                    eta_sec: int, downloaded_mb: float, total_mb: float):
    r = get_redis()
    r.hset(QUEUE_PROGRESS, job_id, json.dumps({
        "percent":      round(percent, 1),
        "speed_mbps":   round(speed_mbps, 2),
        "eta_sec":      eta_sec,
        "downloaded_mb": round(downloaded_mb, 1),
        "total_mb":     round(total_mb, 1),
        "updated_at":   time.time(),
    }))
    r.expire(QUEUE_PROGRESS, 3600)


def complete_job(job: dict, file_path: str, size_mb: float, speed_mbps: float):
    r = get_redis()
    raw = job.get("_raw")
    if raw:
        r.lrem(QUEUE_ACTIVE, 1, raw)
    r.hdel(QUEUE_PROGRESS, job["id"])
    job_clean = {k: v for k, v in job.items() if k != "_raw"}
    job_clean.update({
        "completed_at": time.time(),
        "file_path":    file_path,
        "size_mb":      round(size_mb, 2),
        "speed_mbps":   round(speed_mbps, 2),
    })
    r.lpush(QUEUE_DONE, json.dumps(job_clean))
    r.ltrim(QUEUE_DONE, 0, 999)
    r.hincrby(METRICS_KEY, "total_completed", 1)
    r.hincrbyfloat(METRICS_KEY, "total_size_mb", size_mb)
    log.info(f"[Queue] Done: {job['anime']} EP{job['ep_num']} {job['quality']} — {size_mb:.1f}MB @ {speed_mbps:.2f}MB/s")


def fail_job(job: dict, error: str, max_retries: int = 3):
    r = get_redis()
    raw = job.get("_raw")
    if raw:
        r.lrem(QUEUE_ACTIVE, 1, raw)
    r.hdel(QUEUE_PROGRESS, job["id"])
    job_clean = {k: v for k, v in job.items() if k != "_raw"}
    job_clean["retries"] += 1
    job_clean["error"]    = error
    if job_clean["retries"] < max_retries:
        r.lpush(QUEUE_PENDING, json.dumps(job_clean))
        log.warning(f"[Queue] Retry {job_clean['retries']}/{max_retries}: {job['anime']} EP{job['ep_num']}")
    else:
        r.lpush(QUEUE_FAILED, json.dumps(job_clean))
        r.ltrim(QUEUE_FAILED, 0, 499)
        r.hincrby(METRICS_KEY, "total_failed", 1)
        log.error(f"[Queue] Permanently failed: {job['anime']} EP{job['ep_num']} — {error}")


def recover_stuck_jobs():
    """Move jobs stuck in ACTIVE > JOB_TIMEOUT_SEC back to PENDING."""
    r = get_redis()
    active_jobs = r.lrange(QUEUE_ACTIVE, 0, -1)
    recovered   = 0
    now         = time.time()
    for raw in active_jobs:
        try:
            job = json.loads(raw)
            started = job.get("started_at", now)
            if now - started > JOB_TIMEOUT_SEC:
                r.lrem(QUEUE_ACTIVE, 1, raw)
                job["retries"] = job.get("retries", 0) + 1
                job["error"]   = "stuck_job_recovered"
                if job["retries"] < 3:
                    r.lpush(QUEUE_PENDING, json.dumps(job))
                    recovered += 1
                    log.warning(f"[Queue] Recovered stuck job: {job['anime']} EP{job['ep_num']}")
                else:
                    r.lpush(QUEUE_FAILED, json.dumps(job))
        except Exception:
            pass
    return recovered


def get_progress_all() -> dict:
    r = get_redis()
    raw = r.hgetall(QUEUE_PROGRESS)
    return {k: json.loads(v) for k, v in raw.items()}


def get_stats() -> dict:
    r = get_redis()
    return {
        "pending":  r.llen(QUEUE_PENDING),
        "active":   r.llen(QUEUE_ACTIVE),
        "failed":   r.llen(QUEUE_FAILED),
        "done":     r.llen(QUEUE_DONE),
        "metrics":  r.hgetall(METRICS_KEY),
        "progress": get_progress_all(),
    }


def get_failed_jobs(limit: int = 20) -> list:
    r = get_redis()
    return [json.loads(j) for j in r.lrange(QUEUE_FAILED, 0, limit - 1)]


def requeue_failed() -> int:
    r = get_redis()
    jobs = r.lrange(QUEUE_FAILED, 0, -1)
    r.delete(QUEUE_FAILED)
    for raw in jobs:
        job = json.loads(raw)
        job["retries"] = 0
        job["error"]   = None
        r.lpush(QUEUE_PENDING, json.dumps(job))
    log.info(f"[Queue] Requeued {len(jobs)} failed jobs")
    return len(jobs)
