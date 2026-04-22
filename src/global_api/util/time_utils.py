from datetime import datetime, timezone


SIMULATED_TIME_FORMAT = "%d/%m/%Y %H:%M:%S"


def compute_simulated_now(start_time_simulated: str, start_time_real: str) -> datetime:
    """Compute current simulated time.

    simulated_now = parsed(start_time_simulated) + (utc_now - parsed(start_time_real))
    """
    now_utc = datetime.now(timezone.utc)

    simulated_start = datetime.strptime(start_time_simulated.strip(), SIMULATED_TIME_FORMAT).replace(
        tzinfo=timezone.utc
    )
    real_start = datetime.fromisoformat(start_time_real.replace("Z", "+00:00"))
    if real_start.tzinfo is None:
        real_start = real_start.replace(tzinfo=timezone.utc)
    else:
        real_start = real_start.astimezone(timezone.utc)

    elapsed = now_utc - real_start
    return simulated_start + elapsed
