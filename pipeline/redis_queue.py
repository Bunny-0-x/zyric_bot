#(©)Zyric Network — Redis Job Queue

import json
import time
import redis
import logging

log = logging.getLogger(__name__)
r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

QUEUE_PENDING  = "zyric:jobs:pending"
QUEUE_ACTIVE   = "zyric:jobs:active"
QUEUE_FAILED   = "zyric:jobs:failed"
QUEUE_DONE     = "zyric:jobs:done"
METRICS_KEY    = "zyric:metrics"

def push_job(anime_title: str, ep_num, play_url: str,
             anilist_id: int = 0, season: int = 1) -> str:
    job = {
        "id":          f"{anilist_id}_{season}_{ep_num}_{int(time.time())}",
        "anime":       anime_title,
        "ep_num":      ep_num,
        "url":         play_url, # The AnimePahe /play/... URL
        "anilist_id":  anilist_id,
        "season":      season,
        "retries":     0,
        "created_at":  time.time(),
        "error":       None,
    }
    r.lpush(QUEUE_PENDING, json.dumps(job))
    log.info(f"[Queue] Pushed Episode: {anime_title} EP{ep_num}")
    return f"{job.get("anime", "unknown")}_ep{job.get("ep_num", 0)}"

def pop_job(timeout: int = 5) -> dict | None:
    result = r.brpop(QUEUE_PENDING, timeout=timeout)
    if not result:
        return None
    _, raw = result
    job = json.loads(raw)
    r.hset(QUEUE_ACTIVE, f"{job.get("anime", "unknown")}_ep{job.get("ep_num", 0)}", json.dumps(job))
    return job

def complete_job(job: dict, total_size_mb: float):
    job["completed_at"] = time.time()
    r.hdel(QUEUE_ACTIVE, f"{job.get("anime", "unknown")}_ep{job.get("ep_num", 0)}")
    r.lpush(QUEUE_DONE, json.dumps(job))
    r.ltrim(QUEUE_DONE, 0, 999)
    r.hincrby(METRICS_KEY, "total_completed", 1)
    r.hincrbyfloat(METRICS_KEY, "total_size_mb", total_size_mb)
    log.info(f"[Queue] Done Episode: {job['anime']} EP{job['ep_num']} — {total_size_mb:.1f}MB Total")

def fail_job(job: dict, error: str, max_retries: int = 3):
    job["retries"] += 1
    job["error"]    = error
    r.hdel(QUEUE_ACTIVE, f"{job.get("anime", "unknown")}_ep{job.get("ep_num", 0)}")
    if job["retries"] < max_retries:
        r.lpush(QUEUE_PENDING, json.dumps(job))
        log.warning(f"[Queue] Retry {job['retries']}/{max_retries}: {job['anime']} EP{job['ep_num']}")
    else:
        r.lpush(QUEUE_FAILED, json.dumps(job))
        r.ltrim(QUEUE_FAILED, 0, 499)
        r.hincrby(METRICS_KEY, "total_failed", 1)
        log.error(f"[Queue] Permanently failed: {job['anime']} EP{job['ep_num']} — {error}")

def get_stats() -> dict:
    return {
        "pending": r.llen(QUEUE_PENDING), "active": r.hlen(QUEUE_ACTIVE),
        "failed": r.llen(QUEUE_FAILED), "done": r.llen(QUEUE_DONE),
        "metrics": r.hgetall(METRICS_KEY),
    }

def get_failed_jobs(limit: int = 20) -> list:
    return [json.loads(j) for j in r.lrange(QUEUE_FAILED, 0, limit - 1)]

def requeue_failed():
    jobs = r.lrange(QUEUE_FAILED, 0, -1)
    r.delete(QUEUE_FAILED)
    for raw in jobs:
        job = json.loads(raw)
        job["retries"] = 0; job["error"] = None
        r.lpush(QUEUE_PENDING, json.dumps(job))
    return len(jobs)
