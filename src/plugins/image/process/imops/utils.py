from . import ast


def calculate_real_size(total: int, *ratio: ast.Ratio | None) -> list[int]:
    if not ratio:
        return [total]
    result = [r.value if r and r.unit == "px" else 0 for r in ratio]
    # absolute pixels first
    remain = total - sum(result)
    if remain < 0:
        raise ValueError(
            f"Exceed total size {total} with absolute pixels {sum(result)}")

    weight = [
        r.value if r else 1.0 for r in ratio if not r or r.unit == "ratio"
    ]
    weight_sum = sum(weight)

    float_size = [remain * w / weight_sum for w in weight]
    int_size = [int(s) for s in float_size]
    remainder = remain - sum(int_size)
    remainders = [s - int_s for s, int_s in zip(float_size, int_size)]

    # Distribute the remaining pixels based on the largest remainders
    for i in sorted(range(len(remainders)),
                    key=lambda i: remainders[i],
                    reverse=True):
        if remainder <= 0:
            break
        int_size[i] += 1
        remainder -= 1

    j = 0
    int_result: list[int] = []
    for i, r in enumerate(ratio):
        if not r or r.unit == "ratio":
            int_result.append(int_size[j])
            j += 1
        else:
            int_result.append(int(r.value))
    return int_result
