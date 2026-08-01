import math
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class Pricing:
    input_price_per_ktok: float  # 元 / 千 input tokens
    output_price_per_ktok: float  # 元 / 千 output tokens

    def cost(self, input_tokens: int, output_tokens: int) -> int:
        """返回消费金额，单位：分（fen）。

        向上取整：分以下的小额（如 0.3 分）记 1 分，避免预算对低频小额调用失效。
        """
        fen = (
            input_tokens / 1000 * self.input_price_per_ktok
            + output_tokens / 1000 * self.output_price_per_ktok
        ) * 100
        return math.ceil(fen)


class PricingRegistry:
    """模型定价表。价格易变，需随官方报价人工维护（元/千 tokens，人民币口径）。"""

    _table: ClassVar[dict[str, Pricing]] = {
        "deepseek-chat": Pricing(
            0.001, 0.002
        ),  # = 1/2 元每百万（2026 与 v4-flash 同价）
        "deepseek-v4-flash": Pricing(0.001, 0.002),  # DeepSeek 官方 1/2 元每百万
        "deepseek-reasoner": Pricing(0.004, 0.016),  # R1 时代 4/16 元每百万
        "deepseek-v4-pro": Pricing(0.003, 0.006),  # DeepSeek 官方 3/6 元每百万
        "qwen-turbo": Pricing(0.0003, 0.0006),  # 阿里云 0.3/0.6 元每百万
    }

    @classmethod
    def get(cls, model: str) -> Pricing:
        return cls._table[model]

    @classmethod
    def override(cls, model: str, pricing: Pricing) -> None:
        cls._table[model] = pricing
