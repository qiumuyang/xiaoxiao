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
        await AnnualStatistics.process_group(int(group_id))
        print(f"Group {group_id} processed")


if __name__ == "__main__":
    asyncio.run(main())
