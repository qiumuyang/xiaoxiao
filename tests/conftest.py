import asyncio

import dotenv
import nonebot
import pytest


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
