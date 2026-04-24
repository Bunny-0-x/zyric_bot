#(©)Zyric Network — Pipeline Metrics Formatter

from pipeline.redis_queue import get_stats, get_failed_jobs

def format_stats() -> str:
    stats = get_stats()
    m = stats.get("metrics", {})
    
    total_mb = float(m.get("total_size_mb", 0))
    total_gb = total_mb / 1024
    
    return (
        f"<b>📊 Pipeline Stats</b>\n"
        f"├ <b>Pending Jobs:</b> {stats['pending']}\n"
        f"├ <b>Active Jobs:</b> {stats['active']}\n"
        f"├ <b>Failed Jobs:</b> {stats['failed']}\n"
        f"└ <b>Done Jobs:</b> {stats['done']}\n\n"
        f"<b>📈 All-Time Metrics</b>\n"
        f"├ <b>Completed Files:</b> {m.get('total_completed', 0)}\n"
        f"├ <b>Permanently Failed:</b> {m.get('total_failed', 0)}\n"
        f"└ <b>Total Downloaded:</b> {total_gb:.2f} GB"
    )

def format_failed() -> str:
    failed = get_failed_jobs(10)
    if not failed:
        return "✅ <b>No failed jobs in the queue!</b>"
        
    text = "<b>❌ Recent Failed Jobs:</b>\n\n"
    for j in failed:
        text += f"• <b>{j['anime']} EP{j['ep_num']}</b>\n  └ <i>{j['error']}</i>\n"
    
    return text
