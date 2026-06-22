from datetime import datetime, timedelta

def time_until(hours=24, last_time=None):
    if not last_time:
        return None
    next_time = last_time + timedelta(hours=hours)
    remaining = next_time - datetime.now()
    if remaining.total_seconds() <= 0:
        return None
    hours = remaining.seconds // 3600
    minutes = (remaining.seconds % 3600) // 60
    seconds = remaining.seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
