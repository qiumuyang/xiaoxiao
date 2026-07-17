import asyncio
import os
import subprocess
import time
from pathlib import Path

import dotenv
import nonebot
import pytest

MONGOD_BIN = "/opt/mongodb/bin/mongod"


def _mongo_running() -> bool:
    try:
        from pymongo import MongoClient

        MongoClient(serverSelectionTimeoutMS=500).server_info()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session", autouse=True)
def _mongod():
    started_by_us = False
    if os.path.exists(MONGOD_BIN) and not _mongo_running():
        dbpath = Path.home() / "data" / "db"
        logpath = Path.home() / "data" / "mongod.log"
        dbpath.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [MONGOD_BIN, "--dbpath", str(dbpath), "--fork", "--logpath", str(logpath)],
            check=True,
        )
        for _ in range(30):
            if _mongo_running():
                break
            time.sleep(0.1)
        started_by_us = True
    yield
    if started_by_us:
        try:
            from pymongo import MongoClient

            MongoClient().admin.command("shutdown")
        except Exception:
            pass


def pytest_configure(config):
    nonebot.init()
    dotenv.load_dotenv(".env.dev")


# without this, asyncio related tests will fail with:
#   RuntimeError: Event loop is closed
@pytest.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()
