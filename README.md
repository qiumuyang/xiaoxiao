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

# 启动（开发）
uv run nb run
```

## 生产部署

生产环境通过 systemd 管理，支持崩溃自恢复、告警通知。

额外依赖：

| 服务 | 用途 | 部署文档 |
|------|------|----------|
| VictoriaMetrics | 指标收集与存储 | [victoria-metrics.md](docs/deploy/victoria-metrics.md) |
| vmalert | 告警规则评估 | 同上 |
| alertmanager | 告警路由（邮件 + QQ） | 同上 |
| alert_bridge | 告警转 QQ 群消息 | `alert_bridge.py`（本仓库） |
| node_exporter | 系统指标导出 | 同上 |
| mongodb_exporter | MongoDB 指标导出 | 同上 |
| process_exporter | 进程内存监控 | 同上 |

快速验证：

```bash
sudo systemctl status xiaoxiao        # bot 状态
sudo journalctl -u xiaoxiao -f        # bot 日志
sudo systemctl status vmalert         # 告警规则
sudo journalctl -u alert-bridge -f    # QQ 通知日志
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
