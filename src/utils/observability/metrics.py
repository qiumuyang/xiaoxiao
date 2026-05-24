from enum import StrEnum

from prometheus_client import REGISTRY, Counter, Gauge, Histogram, generate_latest


class MatcherOutcome(StrEnum):
    SUCCESS = "success"
    ERROR = "error"


class ApiStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"


MATCHER_DURATION = Histogram(
    "xiaoxiao_matcher_duration_seconds",
    "Time spent processing a matcher",
    ["matcher", "matcher_type", "sub_command", "group_id", "status"],
    buckets=(
        0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
        float("inf"),
    ),
)

API_DURATION = Histogram(
    "xiaoxiao_api_duration_seconds",
    "Time spent calling OneBot APIs",
    ["api", "status"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, float("inf")),
)

MSG_RECEIVED_TOTAL = Counter(
    "xiaoxiao_msg_received_total",
    "Total received messages",
    ["group_id", "handled"],
)
MSG_SENT_TOTAL = Counter(
    "xiaoxiao_msg_sent_total",
    "Total sent messages",
    ["group_id"],
)

CPU_PERCENT = Gauge("xiaoxiao_cpu_percent", "Process CPU usage percent")
MEMORY_RSS_BYTES = Gauge("xiaoxiao_memory_rss_bytes", "Process RSS memory in bytes")
MEMORY_AVAILABLE_BYTES = Gauge(
    "xiaoxiao_memory_available_bytes", "System available memory in bytes"
)
PROCESS_START_TIME = Gauge(
    "xiaoxiao_process_start_time_seconds",
    "Process start time in seconds since epoch",
)

MONGODB_UP = Gauge("xiaoxiao_mongodb_up", "MongoDB connection status (1=up, 0=down)")


def get_metrics_text() -> bytes:
    return generate_latest(REGISTRY)
