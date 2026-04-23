# divide_conquer.py

import math


# ─── Closest Pair Core ────────────────────────────────────────────────────────

def euclidean_distance(p1, p2):
    """
    Distance between two nodes using their (x, y) coordinates.
    p1, p2 : dicts with 'node_id', 'x', 'y'
    """
    return math.sqrt((p1["x"] - p2["x"]) ** 2 + (p1["y"] - p2["y"]) ** 2)


def brute_force_closest(points):
    """
    For small sets (≤ 3 points) — check all pairs directly.
    Returns (dist, p1, p2)
    """
    min_dist = float('inf')
    pair = (None, None)

    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            d = euclidean_distance(points[i], points[j])
            if d < min_dist:
                min_dist = d
                pair = (points[i], points[j])

    return min_dist, pair[0], pair[1]


def strip_closest(strip, d):
    """
    Among points within vertical band of width 2d around midline,
    find any pair closer than d.
    Points must already be sorted by y.
    """
    min_dist = d
    pair = (None, None)

    for i in range(len(strip)):
        j = i + 1
        while j < len(strip) and (strip[j]["y"] - strip[i]["y"]) < min_dist:
            dist = euclidean_distance(strip[i], strip[j])
            if dist < min_dist:
                min_dist = dist
                pair = (strip[i], strip[j])
            j += 1

    return min_dist, pair[0], pair[1]


def closest_pair_recursive(pts_x, pts_y):
    """
    Divide and conquer closest pair.
    pts_x : points sorted by x
    pts_y : points sorted by y
    Returns (dist, p1, p2)
    """
    n = len(pts_x)

    # Base case
    if n <= 3:
        return brute_force_closest(pts_x)

    mid = n // 2
    mid_point = pts_x[mid]

    # Divide
    left_x  = pts_x[:mid]
    right_x = pts_x[mid:]

    mid_x = mid_point["x"]
    left_y  = [p for p in pts_y if p["x"] <= mid_x]
    right_y = [p for p in pts_y if p["x"] >  mid_x]

    # Conquer
    d_left,  l1, l2 = closest_pair_recursive(left_x,  left_y)
    d_right, r1, r2 = closest_pair_recursive(right_x, right_y)

    # Pick better of the two halves
    if d_left < d_right:
        d, p1, p2 = d_left,  l1, l2
    else:
        d, p1, p2 = d_right, r1, r2

    # Strip — points within distance d of the midline
    strip = [p for p in pts_y if abs(p["x"] - mid_x) < d]
    d_strip, s1, s2 = strip_closest(strip, d)

    if d_strip < d:
        return d_strip, s1, s2
    return d, p1, p2


def closest_pair(points):
    """
    Entry point for closest pair algorithm.
    points : list of dicts with 'node_id', 'x', 'y'
    Returns (dist, p1, p2)
    """
    if len(points) < 2:
        raise ValueError("Need at least 2 points to find closest pair")

    pts_x = sorted(points, key=lambda p: p["x"])
    pts_y = sorted(points, key=lambda p: p["y"])

    return closest_pair_recursive(pts_x, pts_y)


# ─── Pipeline-facing function ─────────────────────────────────────────────────

def closest_delivery_node(primary_node, all_nodes, served_nodes):
    """
    After packing the primary destination, find the nearest
    unserved delivery node to add as a bonus stop.

    primary_node  : int — node_id already being served this trip
    all_nodes     : list of dicts [{"node_id": int, "x": float, "y": float}, ...]
    served_nodes  : set of node_ids already dispatched or being dispatched

    Returns:
        dict  — the closest unserved node  {"node_id", "x", "y"}
        None  — if no unserved candidates exist
    """
    candidates = [
        n for n in all_nodes
        if n["node_id"] != primary_node
        and n["node_id"] not in served_nodes
    ]

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    # Need the primary node's coordinates as anchor
    primary = next((n for n in all_nodes if n["node_id"] == primary_node), None)
    if primary is None:
        raise ValueError(f"primary_node {primary_node} not found in all_nodes")

    # Add primary temporarily so closest_pair can find its nearest neighbour
    pool = [primary] + candidates
    _, p1, p2 = closest_pair(pool)

    # Whichever of the pair isn't primary is the closest candidate
    if p1["node_id"] == primary_node:
        return p2
    return p1