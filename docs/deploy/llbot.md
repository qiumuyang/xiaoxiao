# LLBot — QQ Protocol Adapter

[LLBot](https://luckylillia.com) is the QQ protocol layer that bridges NTQQ and OneBot V11.
XiaoBot requires it to send and receive messages.

This document covers the **Docker** deployment. For CLI or Desktop alternatives, see the
[official installation guide](https://luckylillia.com/guide/choice_install).

## Architecture

```
┌──────────────────────────────────────────┐
│              LLBot (Docker)              │
│                                          │
│  ┌──────────┐       ┌──────────────┐     │
│  │   pmhq   │──────►│    llbot     │     │
│  │ QQ Engine│       │OneBot Adapter│     │
│  │ headless │       │ WebUI :3080  │     │
│  │ QQ: xxx  │       │ ws-reverse   │     │
│  └──────────┘       └──────┬───────┘     │
│                            │             │
│        ws://host.docker.internal         │
│           :8080/onebot/v11/ws            │
└────────────────────────────┬─────────────┘
                             │
                             ▼
                      XiaoBot :8080
```

LLBot consists of two Docker containers:

| Container | Image | Role |
|-----------|-------|------|
| `pmhq` | `linyuchen/pmhq` | QQ protocol engine (headless) |
| `llbot` | `linyuchen/llbot` | OneBot V11 adapter + WebUI |

## Prerequisites

- Docker & Docker Compose v2
- XiaoBot (NoneBot2) listening on `0.0.0.0:8080`

## Quick Start

Use the official setup script for interactive configuration:

```bash
curl -O https://github.com/LLOneBot/LuckyLilliaBot/releases/latest/download/LLBot-Docker.sh
bash LLBot-Docker.sh
```

The script will prompt for QQ number, WebUI password, and protocol options.
See the [official documentation](https://luckylillia.com/guide/choice_install) for details.

## Manual Setup

### Docker Compose

```yaml
services:
  pmhq:
    image: linyuchen/pmhq:latest
    privileged: true
    environment:
      - ENABLE_HEADLESS=true
      - AUTO_LOGIN_QQ=<YOUR_QQ>
    networks:
      - app_network
    volumes:
      - qq_volume:/root/.config/QQ
      - ./llbot_config:/app/llbot/data:rw
    restart: unless-stopped

  llbot:
    image: linyuchen/llbot:latest
    ports:
      - "3080:3080"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - PMHQ_HOST=pmhq
      - WEBUI_PORT=3080
    networks:
      - app_network
    volumes:
      - qq_volume:/root/.config/QQ
      - ./llbot_config:/app/llbot/data:rw
    depends_on:
      - pmhq
    restart: unless-stopped

volumes:
  qq_volume:

networks:
  app_network:
    driver: bridge
```

> **Notes on the compose file:**
> - `ENABLE_HEADLESS=true`: run QQ in headless mode (no GUI, lower resource usage). See [pmhq config](https://github.com/linyuchen/PMHQ/blob/main/doc/config.md).
> - `AUTO_LOGIN_QQ`: set to your bot's QQ number for automatic login after first auth.
> - WebUI password is stored in `llbot_config/webui_token.txt` (created automatically on first startup).
> - `host.docker.internal` resolves to the host machine, required for `ws-reverse` to reach XiaoBot.
> - Image mirrors (for mainland China): prepend `docker.1ms.run/` to the image name, e.g. `docker.1ms.run/linyuchen/llbot:latest`.

### Volume Structure

| Path | Content |
|------|---------|
| `qq_volume:/root/.config/QQ` | QQ login session, device fingerprint (named volume) |
| `./llbot_config:/app/llbot/data:rw` | LLBot config, WebUI token (bind mount, editable) |

The bind mount at `./llbot_config` stores:

- `config_<QQ>.json` — OneBot protocol configuration
- `webui_token.txt` — WebUI login password
- Runtime database files

Configuration can be edited directly in these files or via the WebUI.
See the [official config guide](https://luckylillia.com/guide/config) for all options.

### OneBot V11 Configuration

In the WebUI (`http://<server>:3080`), add a reverse WebSocket connection:

| Field | Value |
|-------|-------|
| Type | `ws-reverse` |
| URL | `ws://host.docker.internal:8080/onebot/v11/ws` |
| Token | (leave empty) |
| Message format | `array` |

When connected, XiaoBot's log will show `Bot <QQ> connected`.

## Operations

```bash
cd /path/to/your/project

docker compose up -d                                # start
docker compose down                                 # stop
docker compose pull && docker compose up -d         # update images and restart
```

## Alternative: CLI Version

For environments without Docker, LLBot also provides a [CLI executable](https://luckylillia.com/guide/choice_install)
for Linux (x64/arm64), macOS, and Windows. Download from the
[releases page](https://github.com/LLOneBot/LuckyLilliaBot/releases).
