# Metrics Collection — VictoriaMetrics + Exporters

Three-layer metrics pipeline: external exporters for OS/MongoDB, bot exposes
business metrics only (message counts, matcher/API latencies).

## Architecture

```
VictoriaMetrics (systemd, :8428)
  │
  ├── scrape 15s → http://127.0.0.1:8080/metrics  (bot — business)
  ├── scrape 15s → http://127.0.0.1:9100/metrics  (node_exporter — OS)
  ├── scrape 15s → http://127.0.0.1:9216/metrics  (mongodb_exporter — DB)
  └── scrape 15s → http://127.0.0.1:9256/metrics  (process_exporter — processes)
```

### Scope Split

| Source | Responsibility | Example Metrics |
|--------|---------------|-----------------|
| Bot `/metrics` | Business only | `xiaoxiao_msg_received_total`, `xiaoxiao_matcher_duration_seconds`, `xiaoxiao_api_duration_seconds` |
| node_exporter | OS/hardware | `node_cpu_seconds_total`, `node_memory_MemAvailable_bytes`, `process_resident_memory_bytes` |
| mongodb_exporter | MongoDB health | `mongodb_up`, `mongodb_connections`, `mongodb_op_counters_total` |
| process_exporter | Per-process RSS/CPU | `namedprocess_namegroup_memory_bytes{groupname="mongod"}` |

Note: `prometheus_client` auto-registers `process_*` / `python_*` / `gc_*` metrics on import.
These appear in the bot's `/metrics` output alongside business metrics at no extra cost.

## VictoriaMetrics

### Install

```bash
VERSION=1.144.0
curl -LO https://github.com/VictoriaMetrics/VictoriaMetrics/releases/download/v${VERSION}/victoria-metrics-linux-amd64-v${VERSION}.tar.gz
tar xzf victoria-metrics-linux-amd64-v${VERSION}.tar.gz
sudo mv victoria-metrics-prod /usr/local/bin/victoria-metrics
```

### User and Directories

```bash
sudo useradd -r -s /usr/sbin/nologin -M victoria-metrics
sudo mkdir -p /var/lib/victoria-metrics /etc/victoria-metrics
sudo chown -R victoria-metrics:victoria-metrics /var/lib/victoria-metrics /etc/victoria-metrics
```

### Scrape Config

`/etc/victoria-metrics/scrape.yml`:

```yaml
scrape_configs:
  - job_name: xiaoxiao
    scrape_interval: 15s
    metrics_path: /metrics
    static_configs:
      - targets: ["127.0.0.1:8080"]

  - job_name: node
    scrape_interval: 15s
    static_configs:
      - targets: ["127.0.0.1:9100"]

  - job_name: mongodb
    scrape_interval: 15s
    static_configs:
      - targets: ["127.0.0.1:9216"]

  - job_name: process
    scrape_interval: 15s
    static_configs:
      - targets: ["127.0.0.1:9256"]
```

### Systemd Service

`/etc/systemd/system/victoria-metrics.service`:

```ini
[Unit]
Description=VictoriaMetrics
After=network.target

[Service]
Type=simple
User=victoria-metrics
Group=victoria-metrics
ExecStart=/usr/local/bin/victoria-metrics \
    -storageDataPath=/var/lib/victoria-metrics \
    -httpListenAddr=127.0.0.1:8428 \
    -promscrape.config=/etc/victoria-metrics/scrape.yml \
    -retentionPeriod=30 \
    -memory.allowedPercent=30
MemoryMax=200M
CPUQuota=100%
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now victoria-metrics
```

## Node Exporter

### Install

```bash
VERSION=1.11.1
curl -LO https://github.com/prometheus/node_exporter/releases/download/v${VERSION}/node_exporter-${VERSION}.linux-amd64.tar.gz
tar xzf node_exporter-${VERSION}.linux-amd64.tar.gz
sudo cp node_exporter-${VERSION}.linux-amd64/node_exporter /usr/local/bin/
sudo chmod +x /usr/local/bin/node_exporter
rm -rf node_exporter-${VERSION}*
```

### Systemd Service

`/etc/systemd/system/node_exporter.service`:

```ini
[Unit]
Description=Node Exporter
After=network.target

[Service]
Type=simple
User=nobody
Group=nogroup
ExecStart=/usr/local/bin/node_exporter \
    --web.listen-address=127.0.0.1:9100 \
    --no-collector.nfs \
    --no-collector.netstat
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now node_exporter
```

Expected RSS: ~20 MB.

## MongoDB Exporter

### Install

```bash
VERSION=0.51.0
curl -LO https://github.com/percona/mongodb_exporter/releases/download/v${VERSION}/mongodb_exporter-${VERSION}.linux-amd64.tar.gz
tar xzf mongodb_exporter-${VERSION}.linux-amd64.tar.gz
sudo cp mongodb_exporter-${VERSION}.linux-amd64/mongodb_exporter /usr/local/bin/
sudo chmod +x /usr/local/bin/mongodb_exporter
rm -rf mongodb_exporter-${VERSION}*
```

### Systemd Service

`/etc/systemd/system/mongodb_exporter.service`:

```ini
[Unit]
Description=MongoDB Exporter
After=network.target mongod.service

[Service]
Type=simple
User=nobody
Group=nogroup
ExecStart=/usr/local/bin/mongodb_exporter \
    --mongodb.uri=mongodb://localhost:27017 \
    --web.listen-address=127.0.0.1:9216 \
    --collect-all
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mongodb_exporter
```

Expected RSS: ~33 MB.

## Process Exporter

Tracks per-process metrics (RSS, CPU) for named processes. Configured to
monitor `mongod`.

### Install

```bash
VERSION=0.8.7
curl -LO https://github.com/ncabatoff/process-exporter/releases/download/v${VERSION}/process-exporter-${VERSION}.linux-amd64.tar.gz
tar xzf process-exporter-${VERSION}.linux-amd64.tar.gz
sudo cp process-exporter-${VERSION}.linux-amd64/process-exporter /usr/local/bin/
sudo chmod +x /usr/local/bin/process-exporter
rm -rf process-exporter-${VERSION}*
```

### Config

`/etc/process_exporter/config.yml`:

```yaml
process_names:
  - name: "mongod"
    cmdline:
      - ".+mongod.+"
```

### Systemd Service

`/etc/systemd/system/process_exporter.service`:

```ini
[Unit]
Description=Process Exporter
After=network.target

[Service]
Type=simple
User=nobody
Group=nogroup
ExecStart=/usr/local/bin/process-exporter \
    --config.path=/etc/process_exporter/config.yml \
    --web.listen-address=127.0.0.1:9256
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now process_exporter
```

Expected RSS: ~8 MB.

## Operations

```bash
# All service statuses
sudo systemctl status victoria-metrics node_exporter mongodb_exporter process_exporter

# Check target health
curl -s http://127.0.0.1:8428/targets

# Bot message rate (last 5 min)
curl -s "http://127.0.0.1:8428/api/v1/query?query=rate(xiaoxiao_msg_received_total[5m])"

# Matcher latency p50 (last 1 hour)
curl -s "http://127.0.0.1:8428/api/v1/query?query=histogram_quantile(0.5,rate(xiaoxiao_matcher_duration_seconds_bucket[1h]))"

# System CPU usage
curl -s "http://127.0.0.1:8428/api/v1/query?query=100-avg(rate(node_cpu_seconds_total{mode=\"idle\"}[5m]))*100"

# Available memory
curl -s "http://127.0.0.1:8428/api/v1/query?query=node_memory_MemAvailable_bytes"

# MongoDB connection count
curl -s "http://127.0.0.1:8428/api/v1/query?query=mongodb_connections"

# Mongod process RSS (via process_exporter)
curl -s "http://127.0.0.1:8428/api/v1/query?query=namedprocess_namegroup_memory_bytes{groupname=\"mongod\",memtype=\"resident\"}"

# Storage usage
du -sh /var/lib/victoria-metrics
```

## Bot Business Metrics

| Metric | Type | Labels |
|--------|------|--------|
| `xiaoxiao_msg_received_total` | Counter | `group_id`, `handled` |
| `xiaoxiao_msg_sent_total` | Counter | `group_id` |
| `xiaoxiao_matcher_duration_seconds` | Histogram | `matcher`, `matcher_type`, `sub_command`, `status` |
| `xiaoxiao_api_duration_seconds` | Histogram | `api`, `status` |

prometheus_client also auto-registers: `process_cpu_seconds_total`,
`process_resident_memory_bytes`, `process_start_time_seconds`, `process_open_fds`,
`python_gc_*`, `python_info`.

## Resource Budget (runtime RSS)

| Service | RSS |
|---------|-----|
| VictoriaMetrics | ~43 MB |
| node_exporter | ~20 MB |
| mongodb_exporter | ~33 MB |
| process_exporter | ~8 MB |
| vmalert | ~15 MB |
| alertmanager | ~15 MB |
| alert-bridge | ~30 MB |
| **Total** | **~164 MB** |

## XiaoBot Systemd Service

```ini
# /etc/systemd/system/xiaoxiao.service
[Unit]
Description=XiaoBot
After=network.target mongod.service victoria-metrics.service
Wants=network.target
StartLimitBurst=5
StartLimitIntervalSec=120

[Service]
Type=simple
User=qmy
Group=qmy
WorkingDirectory=/home/qmy/XiaoBot
ExecStart=/home/qmy/.local/bin/uv run nb run
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now xiaoxiao
sudo journalctl -u xiaoxiao -f   # 查看日志
```

## Alerting (vmalert + alertmanager + alert_bridge)

告警管道：VM → vmalert（30s 评估）→ alertmanager（去重/分组）→ 邮件 + QQ 群。

### vmalert

从 vmutils 包提取，复用 VictoriaMetrics 版本。

```bash
VERSION=1.144.0
curl -LO https://github.com/VictoriaMetrics/VictoriaMetrics/releases/download/v${VERSION}/vmutils-linux-amd64-v${VERSION}.tar.gz
tar xzf vmutils-linux-amd64-v${VERSION}.tar.gz
sudo cp vmalert-prod /usr/local/bin/vmalert
```

`/etc/systemd/system/vmalert.service`:

```ini
[Unit]
Description=vmalert
After=network.target victoria-metrics.service

[Service]
Type=simple
User=nobody
ExecStart=/usr/local/bin/vmalert \
    -rule=/etc/vmalert/rules.yml \
    -datasource.url=http://127.0.0.1:8428 \
    -notifier.url=http://127.0.0.1:9093 \
    -remoteWrite.url=http://127.0.0.1:8428 \
    -remoteRead.url=http://127.0.0.1:8428
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

`/etc/vmalert/rules.yml` — 告警规则（示例：BotDown / MongodDown / HighCPU / LowMemory / LowDisk 等 7 条）。

### alertmanager

```bash
VERSION=0.28.1
curl -LO https://github.com/prometheus/alertmanager/releases/download/v${VERSION}/alertmanager-${VERSION}.linux-amd64.tar.gz
tar xzf alertmanager-${VERSION}.linux-amd64.tar.gz
sudo cp alertmanager-${VERSION}.linux-amd64/alertmanager /usr/local/bin/
```

`/etc/systemd/system/alertmanager.service`:

```ini
[Unit]
Description=Alertmanager
After=network.target

[Service]
Type=simple
User=nobody
WorkingDirectory=/tmp
ExecStart=/usr/local/bin/alertmanager \
    --config.file=/etc/alertmanager/alertmanager.yml \
    --web.listen-address=127.0.0.1:9093 \
    --storage.path=/tmp/alertmanager-data
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

`/etc/alertmanager/alertmanager.yml` — SMTP + webhook 配置。SMTP 密码权限 600。

### alert_bridge

接收 alertmanager webhook，通过 LLBot OneBot HTTP API（`:3000`）发送 QQ 群消息。

仓库文件：`alert_bridge.py`（根目录）。`/etc/systemd/system/alert-bridge.service`:

```ini
[Unit]
Description=Alert Bridge (webhook → QQ)
After=network.target

[Service]
Type=simple
User=qmy
WorkingDirectory=/home/qmy/XiaoBot
ExecStart=/home/qmy/XiaoBot/.venv/bin/python /home/qmy/XiaoBot/alert_bridge.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Upgrade

```bash
# VictoriaMetrics
VERSION=1.144.0
curl -LO https://github.com/VictoriaMetrics/VictoriaMetrics/releases/download/v${VERSION}/victoria-metrics-linux-amd64-v${VERSION}.tar.gz
tar xzf victoria-metrics-linux-amd64-v${VERSION}.tar.gz
sudo systemctl stop victoria-metrics
sudo mv victoria-metrics-prod /usr/local/bin/victoria-metrics
sudo systemctl start victoria-metrics

# node_exporter
VERSION=1.11.1
# ... same pattern, stop → replace binary → start
```

## Uninstall

```bash
for svc in victoria-metrics node_exporter mongodb_exporter process_exporter vmalert alertmanager alert-bridge; do
    sudo systemctl stop $svc
    sudo systemctl disable $svc
    sudo rm -f /etc/systemd/system/$svc.service
done
sudo rm -f /usr/local/bin/victoria-metrics /usr/local/bin/node_exporter /usr/local/bin/mongodb_exporter /usr/local/bin/process-exporter /usr/local/bin/vmalert /usr/local/bin/alertmanager
sudo rm -rf /var/lib/victoria-metrics /etc/victoria-metrics /etc/vmalert /etc/alertmanager /etc/process_exporter /tmp/alertmanager-data
sudo userdel victoria-metrics
sudo systemctl daemon-reload
```
