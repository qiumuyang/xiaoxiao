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
    ["matcher", "matcher_type", "sub_command", "status"],
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
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

GATEWAY_HEALTHY = Gauge(
    "xiaoxiao_gateway_healthy",
    "OneBot gateway connectivity (1=ok, 0=down)",
)


def get_metrics_text() -> bytes:
    return generate_latest(REGISTRY)


LLM_CALL_DURATION = Histogram(
    "xiaoxiao_llm_call_duration_seconds",
    "LLM API call duration",
    ["model", "provider", "status"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, float("inf")),
)

LLM_TOKEN_USAGE = Counter(
    "xiaoxiao_llm_token_usage_total",
    "LLM token consumption",
    ["model", "provider", "type"],
)

LLM_CALL_ERRORS = Counter(
    "xiaoxiao_llm_call_errors_total",
    "LLM call errors",
    ["model", "provider", "error_type"],
)

LLM_COST_FEN = Counter(
    "xiaoxiao_llm_cost_fen_total",
    "LLM API cost in fen (分)",
    ["model", "provider"],
)

LLM_BUDGET_REJECTED = Counter(
    "xiaoxiao_llm_budget_rejected_total",
    "LLM calls rejected by daily cost budget",
    ["model"],
)
