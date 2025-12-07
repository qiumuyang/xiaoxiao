import sys
from argparse import ArgumentParser
from typing import Sequence

sys.path.append(".")
sys.path.append("..")

import asyncio

import nonebot

nonebot.init()

from src.plugins.annual_report.statistics import AnnualStatistics
from src.utils.message.receive import ReceivedMessageTracker


async def main(group_ids: Sequence[int]):
    if not group_ids:
        group_ids = await ReceivedMessageTracker.list_distinct_groups()

    groups_str = '\n'.join(map(str, group_ids))
    print(f"Total {len(group_ids)} groups to process:\n{groups_str}")

    for group_id in group_ids:
        print(f"Processing group {group_id}...")
        try:
            await AnnualStatistics.process_group(int(group_id))
        except Exception as e:
            print(f"Error processing group {group_id}: {e}")
            raise e
        print(f"done")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("group_id",
                        nargs="*",
                        type=int,
                        help="Group ID to process (empty for all groups)")
    args = parser.parse_args()

    asyncio.run(main(args.group_id))
