from enum import StrEnum

from prometheus_client import REGISTRY, Counter, Histogram, generate_latest


class MatcherOutcome(StrEnum):
    SUCCESS = "success"
    ERROR = "error"


class ApiStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"


MATCHER_DURATION = Histogram(
    "xiaoxiao_matcher_duration_seconds",
    "Time spent processing a matcher",
    ["matcher", "matcher_type", "sub_command", "status"],
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


def get_metrics_text() -> bytes:
    return generate_latest(REGISTRY)
