def merge_sort(arr, key):
    if len(arr) <= 1:
        return arr

    mid = len(arr) // 2
    left = merge_sort(arr[:mid], key)
    right = merge_sort(arr[mid:], key)

    return merge(left, right, key)


def merge(left, right, key):
    result = []
    i = j = 0

    while i < len(left) and j < len(right):
        if key(left[i]) <= key(right[j]):
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1

    result.extend(left[i:])
    result.extend(right[j:])
    return result

def sort_by_deadline(packages):
    return merge_sort(packages, key=lambda p: p["deadline"])

def quick_sort(arr, key, low=None, high=None):
    if low is None: low = 0
    if high is None: high = len(arr) - 1

    if low < high:
        pi = partition(arr, key, low, high)
        quick_sort(arr, key, low, pi - 1)
        quick_sort(arr, key, pi + 1, high)

    return arr


def partition(arr, key, low, high):
    pivot = arr[high]
    i = low - 1

    for j in range(low, high):
        if key(arr[j]) <= key(pivot):
            i += 1
            arr[i], arr[j] = arr[j], arr[i]

    arr[i + 1], arr[high] = arr[high], arr[i + 1]
    return i + 1


def heap_sort(arr, key):
    n = len(arr)

    for i in range(n // 2 - 1, -1, -1):
        heapify(arr, n, i, key)

    for i in range(n - 1, 0, -1):
        arr[0], arr[i] = arr[i], arr[0]
        heapify(arr, i, 0, key)

    return arr


def heapify(arr, n, i, key):
    largest = i
    left = 2 * i + 1
    right = 2 * i + 2

    if left < n and key(arr[left]) > key(arr[largest]):
        largest = left

    if right < n and key(arr[right]) > key(arr[largest]):
        largest = right

    if largest != i:
        arr[i], arr[largest] = arr[largest], arr[i]
        heapify(arr, n, largest, key)


def bubble_sort(arr, key):
    n = len(arr)

    for i in range(n):
        swapped = False
        for j in range(0, n - i - 1):
            if key(arr[j]) > key(arr[j + 1]):
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
        if not swapped:
            break

    return arr

def sort_by_priority(packages):
    """Heap sort — max priority first. Heap naturally models 'most urgent next'."""
    arr = packages[:]
    heap_sort(arr, key=lambda p: p["priority"])
    return arr[::-1]  # heap_sort gives ascending, reverse for highest priority first

def sort_by_weight(packages):
    """Quick sort — ascending weight. Random float data, stability not needed."""
    arr = packages[:]
    return quick_sort(arr, key=lambda p: p["weight"])

def sort_by_priority_then_deadline(packages):
    """
    Two-pass compound sort:
      Pass 1 — Quick Sort by priority ascending (1 = highest, 5 = lowest).
               Quick Sort is used first because we don't need stability here;
               we're about to re-sort within groups anyway.
      Pass 2 — Merge Sort by deadline within each priority group.
               Merge Sort is stable, so equal-priority packages already in
               priority order come out sorted by deadline without disrupting
               the priority grouping.

    Result: priority-1 packages first (sorted by deadline asc),
            then priority-2 (sorted by deadline asc), ... down to priority-5.

    Returns (sorted_list, steps) where steps captures intermediate states
    for UI visualisation.
    """
    arr = packages[:]
    steps = []

    # ── Pass 1: Quick Sort by priority ───────────────────────────────────────
    pass1 = quick_sort(arr[:], key=lambda p: p["priority"])
    steps.append({
        "pass": 1,
        "label": "Pass 1 — Quick Sort by Priority",
        "algo": "Quick Sort",
        "description": (
            "Quick Sort partitions packages around a pivot priority value. "
            "After this pass all priority-1 orders sit before priority-2, "
            "priority-2 before priority-3, and so on. "
            "O(n log n) average. Unstable — ties within the same priority "
            "are not yet deadline-ordered."
        ),
        "result": [_pkg_summary(p) for p in pass1]
    })

    # ── Pass 2: Merge Sort by deadline within each priority group ─────────────
    # Group by priority, merge-sort each group, then concatenate
    groups = {}
    for p in pass1:
        groups.setdefault(p["priority"], []).append(p)

    pass2 = []
    group_steps = []
    for prio in sorted(groups.keys()):
        grp = groups[prio]
        sorted_grp = merge_sort(grp[:], key=lambda p: p["deadline"])
        pass2.extend(sorted_grp)
        group_steps.append({
            "priority": prio,
            "count": len(sorted_grp),
            "deadlines_before": [p["deadline"] for p in grp],
            "deadlines_after":  [p["deadline"] for p in sorted_grp],
        })

    steps.append({
        "pass": 2,
        "label": "Pass 2 — Merge Sort by Deadline within each Priority Group",
        "algo": "Merge Sort",
        "description": (
            "Merge Sort is applied independently to each priority bucket. "
            "Because Merge Sort is stable, packages already in priority order "
            "remain so — only the within-group order changes. "
            "O(n log n) worst case. Result: globally sorted by (priority ASC, deadline ASC)."
        ),
        "groups": group_steps,
        "result": [_pkg_summary(p) for p in pass2]
    })

    return pass2, steps


def _pkg_summary(p):
    return {
        "package_id": p["package_id"],
        "priority":   p["priority"],
        "deadline":   p["deadline"],
        "weight":     p["weight"],
        "dest_node":  p["dest_node"],
    }