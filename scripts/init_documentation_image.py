import sys

sys.path.append(".")
sys.path.append("..")

import nonebot

nonebot.init()
nonebot.load_plugins("src/plugins")

from src.plugins.help.load import init_cache

init_cache()
