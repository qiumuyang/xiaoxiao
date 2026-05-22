# XiaoBot

鸮鸮鸮鸮鸮鸮鸮鸮

基于 [NoneBot2](https://github.com/nonebot/nonebot2) 的 QQ 机器人。

## 环境要求

- **Python** >= 3.12
- **[uv](https://docs.astral.sh/uv/)** — 包管理和虚拟环境
- **MongoDB** — 数据持久化
- **[LLBot](https://github.com/LLOneBot)** - pmhq QQ 协议引擎 + llbot OneBot V11 适配器

## 快速开始

> [!TIP]
> 需先部署 [LLBot](https://luckylillia.com/guide/choice_install)，详见 [部署指南](docs/deploy/llbot.md)。

```bash
# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env，填写 SUPERUSERS、DB 等

# 启动
uv run nb run
```

## 开发

```bash
uv sync --group dev      # 安装开发依赖（ruff, pytest 等）

ruff format .            # 格式化代码
ruff check .             # 静态检查
ruff check --fix .       # 自动修复可修问题

pytest                   # 运行测试
pytest --cov=src         # 含覆盖率报告
```

## 致谢

- [NoneBot2](https://github.com/nonebot/nonebot2)
- [LLBot](https://github.com/LLOneBot)
- [LagrangeDev](https://github.com/LagrangeDev)
