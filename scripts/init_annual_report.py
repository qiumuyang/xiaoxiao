import sys

sys.path.append(".")
sys.path.append("..")

import asyncio

import nonebot

nonebot.init()

from src.plugins.annual_report.statistics import AnnualStatistics
from src.utils.message.receive import ReceivedMessageTracker


async def main():

    for group_id in await ReceivedMessageTracker.list_distinct_groups():
        print(f"Processing group {group_id}...")
        try:
            await AnnualStatistics.process_group(int(group_id))
        except Exception as e:
            print(f"Error processing group {group_id}: {e}")
            raise e
        print(f"done")


if __name__ == "__main__":
    asyncio.run(main())
