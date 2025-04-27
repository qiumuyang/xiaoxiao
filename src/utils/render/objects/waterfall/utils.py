from heapq import heappop, heappush
from itertools import combinations


def _brute_force(arr, k):
    n = len(arr)
    k = k - 1
    best_diff = float("inf")
    best_split = []

    for cuts in combinations(range(1, n), k):
        segments = []
        prev = 0
        for cut in cuts:
            segments.append(arr[prev:cut])
            prev = cut
        segments.append(arr[prev:])

        sums = [sum(seg) for seg in segments]
        diff = max(sums) - min(sums)
        if diff < best_diff:
            best_diff = diff
            best_split = cuts
    return list(best_split)


def _approx(arr, k):

    def can_split(max_sum_limit):
        count = 1
        curr_sum = 0
        sub_sums = []
        split_indices = []

        for i in range(len(arr)):
            if curr_sum + arr[i] > max_sum_limit:
                sub_sums.append(curr_sum)
                split_indices.append(i)
                curr_sum = arr[i]
                count += 1
            else:
                curr_sum += arr[i]

        sub_sums.append(curr_sum)
        return count, sub_sums, split_indices

    left, right = max(arr), sum(arr)
    best_diff = float("inf")
    best_splits = []

    while left <= right:
        mid = (left + right) // 2
        count, sub_sums, splits = can_split(mid)

        if count > k:
            left = mid + 1
        else:
            # Adjust if we have fewer than k subarrays
            while count < k:
                # Split the largest segment (most basic heuristic)
                max_idx = max(range(len(sub_sums)), key=lambda i: sub_sums[i])
                val = sub_sums.pop(max_idx)
                val_half = val // 2
                sub_sums.insert(max_idx, val_half)
                sub_sums.insert(max_idx + 1, val - val_half)
                # Not updating `splits` accurately here, approximate only
                count += 1

            curr_diff = max(sub_sums) - min(sub_sums)
            if curr_diff < best_diff:
                best_diff = curr_diff
                best_splits = splits[:]

            right = mid - 1

    # Postprocess: enforce exactly k-1 splits
    while len(best_splits) < k - 1:
        best_splits.append(len(arr))  # pad with end (won’t affect result)

    return best_splits[:k - 1]


def split_subarray(arr: list[int], num_subarrays: int) -> list[int]:
    if num_subarrays <= 1:
        return arr[:]
    if len(arr) <= 200 and num_subarrays <= 4:
        return _brute_force(arr, num_subarrays)
    return _approx(arr, num_subarrays)


def _approx_unordered(arr, k):
    indexed_nums = sorted(enumerate(arr), key=lambda x: -x[1])
    sublists = [[] for _ in range(k)]
    heap = [(0, i) for i in range(k)]

    for index, num in indexed_nums:
        current_sum, sublist_index = heappop(heap)
        sublists[sublist_index].append(index)
        heappush(heap, (current_sum + num, sublist_index))

    return sublists


def split_subarray_unordered(arr: list[int],
                             num_subarrays: int) -> list[list[int]]:
    if num_subarrays <= 1:
        return [list(range(len(arr)))]
    return _approx_unordered(arr, num_subarrays)


if __name__ == "__main__":
    import random
    import time
    from typing import Callable
    n = 20
    k = 3
    arr = [random.randint(5, 100) for _ in range(n)]

    def show_unordered(method: Callable):
        tik = time.perf_counter()
        result = method(arr, k)
        tok = time.perf_counter()
        sub_sums = [sum(arr[i] for i in sub) for sub in result]
        print(method.__name__)
        print(result)
        print(f"Elapsed: {(tok - tik) * 1000:.0f}ms, "
              f"Max Diff: {max(sub_sums) - min(sub_sums)}, "
              f"Sub Sums: {sub_sums}")

    show_unordered(_approx_unordered)
