from datetime import datetime, timedelta
from functools import lru_cache
from hashlib import md5
from typing import TypedDict

import numpy as np
import requests


class Fortune(TypedDict):
    user_id: int
    user_name: str
    date: str
    fortune: str
    event_good: list[str]
    event_bad: list[str]
    lucky_color: tuple[int, int, int]


FORTUNE_GOOD = ("大吉", "中吉", "小吉", "吉", "半吉", "末吉")
FORTUNE_BAD = ("大凶", "小凶", "凶", "半凶", "末凶")
EVENT = ("祭祀", "祈福", "酬神", "开光", "入宅", "分手", "乘船", "驾车", "出行", "赴任", "开市",
         "摆烂", "修造", "盖屋", "嫁娶", "上分", "睡觉", "抽卡", "写作业", "水群", "告白", "做舔狗",
         "单推", "dd", "打游戏", "女装", "复读", "玩bot", "打工")
FORTUNE = FORTUNE_GOOD + FORTUNE_BAD


@lru_cache()
def get_sunrise_sunset(
    latitude: float,
    longitude: float,
) -> tuple[datetime, datetime]:
    r = requests.get(
        f"https://api.sunrise-sunset.org/json?lat={latitude}&lng={longitude}")
    results = r.json()["results"]
    sunrise = datetime.strptime(results["sunrise"], "%I:%M:%S %p")
    sunset = datetime.strptime(results["sunset"], "%I:%M:%S %p")
    sunrise += timedelta(hours=8)
    sunset += timedelta(hours=8)
    today = datetime.now()
    sunrise = sunrise.replace(year=today.year,
                              month=today.month,
                              day=today.day)
    sunset = sunset.replace(year=today.year, month=today.month, day=today.day)
    return sunrise, sunset


def get_seed(user_id: int, date: str) -> int:
    return int(md5(f"{user_id}{date}".encode()).hexdigest(), 16)


def get_fortune(
    user_id: int,
    user_name: str,
    date: datetime | None = None,
) -> Fortune:
    if date is None:
        date = datetime.now()
    date_str = date.strftime("%Y-%m-%d")
    rng = np.random.default_rng(seed=get_seed(user_id, date_str))

    fortune = rng.choice(FORTUNE)
    events = rng.choice(EVENT, size=6, replace=False)
    event_good, event_bad = events[:3], events[3:]

    r, g, b = rng.integers(0, 256, size=3)
    return {
        "user_id": user_id,
        "user_name": user_name,
        "date": date_str,
        "fortune": fortune,
        "event_good": event_good.tolist(),
        "event_bad": event_bad.tolist(),
        "lucky_color": (r, g, b),
    }
