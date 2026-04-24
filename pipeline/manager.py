#(©)Zyric Network — Worker Manager

import subprocess
import os
import sys
import time
import logging
import signal

log = logging.getLogger(__name__)

WORKER_COUNT  = int(os.environ.get("WORKER_COUNT", "3"))
VENV_PYTHON   = "/root/zyric_bot/venv/bin/python3" if os.path.exists("/root/zyric_bot/venv/bin/python3") else "python3"
WORKER_SCRIPT = os.path.join(os.path.dirname(__file__), "worker.py")
PROJECT_ROOT  = os.path.dirname(os.path.dirname(__file__)) # Gets /root/zyric_bot

_workers: dict[str, subprocess.Popen] = {}

def start_workers():
    for i in range(1, WORKER_COUNT + 1):
        _spawn_worker(f"w{i}")
    log.info(f"[Manager] {WORKER_COUNT} workers started.")

def _spawn_worker(wid: str):
    env = os.environ.copy()
    env["WORKER_ID"] = wid
    env["PYTHONPATH"] = PROJECT_ROOT # Forces Python to look in the main folder
    
    proc = subprocess.Popen(
        [VENV_PYTHON, WORKER_SCRIPT],
        env=env,
        cwd=PROJECT_ROOT, # Sets the working directory to main folder
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    _workers[wid] = proc
    log.info(f"[Manager] Worker {wid} spawned (PID {proc.pid})")

def monitor_workers():
    for wid, proc in list(_workers.items()):
        if proc.poll() is not None:
            log.warning(f"[Manager] Worker {wid} died (exit {proc.returncode}), restarting...")
            _spawn_worker(wid)

def stop_workers():
    for wid, proc in _workers.items():
        proc.send_signal(signal.SIGTERM)
        log.info(f"[Manager] Sent SIGTERM to worker {wid}")
    for wid, proc in _workers.items():
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            log.warning(f"[Manager] Worker {wid} force-killed")
    log.info("[Manager] All workers stopped.")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    start_workers()
    try:
        while True:
            time.sleep(10)
            monitor_workers()
    except KeyboardInterrupt:
        log.info("[Manager] Shutting down...")
        stop_workers()
