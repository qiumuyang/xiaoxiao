import argparse
import sys

parser = argparse.ArgumentParser()
parser.add_argument("command", nargs="*")
args = parser.parse_args()

sys.path.append(".")
sys.path.append("..")

import nonebot

nonebot.init()
nonebot.load_plugins("src/plugins")

from src.plugins.help.load import init_cache

init_cache(*args.command)
