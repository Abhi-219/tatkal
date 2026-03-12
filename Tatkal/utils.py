"""
Utility helpers – NTP time sync, human-like delays, logging setup.
"""

import time
import random
import logging
import ntplib
from datetime import datetime, timedelta

logger = logging.getLogger("TatkalBot")


# ------------------------------------------------------------------ #
#  NTP precise clock
# ------------------------------------------------------------------ #
class PreciseClock:
    """Get real IST time from NTP so your system clock offset doesn't matter."""

    def __init__(self, ntp_server="time.google.com"):
        self.offset = 0.0
        self.ntp_server = ntp_server
        self._sync()

    def _sync(self):
        servers = [self.ntp_server, "pool.ntp.org", "time.windows.com", "time.nist.gov"]
        for server in servers:
            try:
                client = ntplib.NTPClient()
                resp = client.request(server, version=3, timeout=3)
                self.offset = resp.offset
                logger.info(f"NTP sync OK via {server}. Clock offset: {self.offset:.3f}s")
                return
            except Exception:
                continue
        logger.warning("NTP sync failed on all servers. Using system clock.")
        self.offset = 0.0

    def now(self) -> datetime:
        """Current IST time corrected by NTP offset."""
        utc = datetime.utcnow() + timedelta(seconds=self.offset)
        ist = utc + timedelta(hours=5, minutes=30)
        return ist

    def wait_until(self, target_hour: int, target_minute: int, target_second: int = 0):
        """
        Block until IST reaches the given time.
        Shows a countdown in the console.
        """
        while True:
            now = self.now()
            target = now.replace(hour=target_hour, minute=target_minute,
                                 second=target_second, microsecond=0)
            if now >= target:
                logger.info(f"Target time {target_hour}:{target_minute:02d}:{target_second:02d} reached!")
                return
            remaining = (target - now).total_seconds()
            if remaining > 60:
                print(f"\r⏳ Waiting... {remaining:.0f}s remaining (IST: {now.strftime('%H:%M:%S')})", end="", flush=True)
                time.sleep(1)
            elif remaining > 5:
                print(f"\r🔥 Almost there! {remaining:.1f}s (IST: {now.strftime('%H:%M:%S.%f')[:12]})", end="", flush=True)
                time.sleep(0.1)
            else:
                # Ultra-precise last 5 seconds – busy wait
                print(f"\r🚀 {remaining:.3f}s ...", end="", flush=True)
                time.sleep(0.01)


# ------------------------------------------------------------------ #
#  Human-like helpers (anti-detection)
# ------------------------------------------------------------------ #
def human_delay(min_ms=80, max_ms=250):
    """Small random delay to appear human."""
    time.sleep(random.randint(min_ms, max_ms) / 1000)


def human_type(element, text, min_ms=30, max_ms=90):
    """Type text into a Selenium element character-by-character with jitter."""
    element.clear()
    for ch in text:
        element.send_keys(ch)
        time.sleep(random.randint(min_ms, max_ms) / 1000)


# ------------------------------------------------------------------ #
#  Logging
# ------------------------------------------------------------------ #
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s │ %(levelname)-7s │ %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("tatkal_bot.log", mode="w", encoding="utf-8"),
        ],
    )
    # Silence noisy libs
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    return logging.getLogger("TatkalBot")
