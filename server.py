# server.py

from flask import Flask, jsonify, send_from_directory
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from backend.delhi_graph    import build_graph, NODES
from backend.data_generator import generate_deliveries
from backend.sorting        import sort_by_deadline, sort_by_priority, sort_by_weight
from backend.graph          import find_best_warehouse, dijkstra
from backend.greedy         import select_van
from backend.dp             import pack_van
from backend.divide_conquer import closest_delivery_node

app = Flask(__name__, static_folder="frontend")

# ─── Fleet & coords ───────────────────────────────────────────────────────────

FLEET = [
    {"van_id": 1, "name": "Small",  "capacity": 30},
    {"van_id": 2, "name": "Medium", "capacity": 60},
    {"van_id": 3, "name": "Large",  "capacity": 100},
]

NODE_COORDS = [
    {"node_id": nid, "x": info["lng"], "y": info["lat"]}
    for nid, info in NODES.items()
]

# ─── Helpers ──────────────────────────────────────────────────────────────────

def group_by_destination(packages):
    groups = {}
    for pkg in packages:
        groups.setdefault(pkg["dest_node"], []).append(pkg)
    return groups


def total_weight(packages):
    return round(sum(p["weight"] for p in packages), 2)


def build_route(graph, warehouse, stops):
    """
    Returns:
        route_nodes : [warehouse, stop1, stop2, ...]  (node ids)
        route_names : matching name list
        total_dist  : sum of leg distances
    """
    path        = [warehouse] + stops
    route_names = [NODES[n]["name"] for n in path]
    total_dist  = 0.0

    for i in range(len(path) - 1):
        total_dist += dijkstra(graph, path[i], path[i + 1])["distance"]

    return path, route_names, round(total_dist, 2)


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")


@app.route("/run")
def run():
    from flask import request
    n = int(request.args.get("n", 20))
    n = max(5, min(n, 60))   # clamp to slider range

    graph = build_graph()

    # Step 1 — generate & sort
    raw = generate_deliveries(n)
    packages = sort_by_deadline(raw)       # merge sort — stable, earliest deadline first
    packages = sort_by_priority(packages)  # heap sort — highest priority first within deadline order   

    # Step 2 — group by destination
    groups = group_by_destination(packages)

    trips        = []
    served_nodes = set(range(5))   # warehouses never become bonus stops
    total_pkgs   = 0

    # Step 3 — process each destination
    for dest, pkgs in groups.items():

        result    = find_best_warehouse(graph, dest)   # Step 4
        warehouse = result["warehouse"]

        remaining = pkgs[:]
        trip_num  = 1

        while remaining:

            w_rem = total_weight(remaining)
            van   = select_van(FLEET, w_rem)                      # Step 5 greedy
            remaining = sort_by_weight(remaining)  # quick sort — lightest first, helps knapsack packing
            packed, leftover = pack_van(remaining, van["capacity"])  # Step 6 DP

            if not packed:           # single package > largest van
                packed   = [remaining[0]]
                leftover = remaining[1:]

            # Step 7 — closest bonus stop
            served_nodes.add(dest)
            bonus_node   = closest_delivery_node(dest, NODE_COORDS, served_nodes)
            bonus_packed = []
            bonus_stop   = None
            bonus_name   = None

            if bonus_node:
                bonus_id     = bonus_node["node_id"]
                bonus_pkgs   = groups.get(bonus_id, [])
                rem_cap      = van["capacity"] - total_weight(packed)

                if bonus_pkgs and rem_cap > 0:
                    extra, _ = pack_van(bonus_pkgs, int(rem_cap))
                    if extra:
                        bonus_packed = extra
                        bonus_stop   = bonus_id
                        bonus_name   = NODES[bonus_id]["name"]
                        packed_ids   = {p["package_id"] for p in extra}
                        groups[bonus_id] = [
                            p for p in bonus_pkgs
                            if p["package_id"] not in packed_ids
                        ]
                        served_nodes.add(bonus_id)

            # Build route
            stops = [dest] + ([bonus_stop] if bonus_stop else [])
            route_nodes, route_names, dist = build_route(graph, warehouse, stops)

            all_packed  = packed + bonus_packed
            total_pkgs += len(all_packed)

            trips.append({
                "destination": NODES[dest]["name"],
                "trip_num":    trip_num,
                "van":         van["name"],
                "load":        total_weight(all_packed),
                "distance":    dist,
                "warehouse":   NODES[warehouse]["name"],
                "route_nodes": route_nodes,
                "route_names": route_names,
                "packages":    [p["package_id"] for p in all_packed],
                "has_bonus":   bonus_stop is not None,
                "bonus_name":  bonus_name,
            })

            remaining = leftover
            trip_num += 1

    return jsonify({
        "packages_generated": n,
        "packages_sorted":    total_pkgs,
        "destinations":       len(groups),
        "trips":              trips,
    })


@app.route("/steps")
def steps():
    from flask import request
    n = int(request.args.get("n", 20))
    n = max(5, min(n, 60))

    graph = build_graph()

    # ── Step 1: Generate ──────────────────────────────────────────────────────
    raw = generate_deliveries(n)
    step1 = {
        "step": 1,
        "title": "Generate Orders",
        "algo": "Data Generation",
        "explanation": "Random packages created with weight, deadline, priority and destination node.",
        "data": raw[:8]  # show first 8 for display
    }

    # ── Step 2: Sort ──────────────────────────────────────────────────────────
    before_sort = [{"package_id": p["package_id"], "deadline": p["deadline"]} for p in raw[:8]]
    sorted_pkgs = sort_by_deadline(raw)
    after_sort  = [{"package_id": p["package_id"], "deadline": p["deadline"]} for p in sorted_pkgs[:8]]
    priority_sorted = sort_by_priority(sorted_pkgs)
    weight_sorted   = sort_by_weight(sorted_pkgs[:8])

    step2 = {
        "step": 2,
        "title": "Sort Packages — 3 Algorithms",
        "algo": "Merge Sort → Heap Sort → Quick Sort",
        "explanation": (
            "Three sorts applied in sequence: "
            "(1) Merge Sort by deadline — stable, preserves tie order. "
            "(2) Heap Sort by priority — max-heap extracts most urgent first. "
            "(3) Quick Sort by weight — random floats, stability not needed, cache-efficient."
        ),
        "before": before_sort,
        "after": after_sort,
        "priority_sorted": [{"package_id": p["package_id"], "priority": p["priority"]} for p in priority_sorted[:8]],
        "weight_sorted":   [{"package_id": p["package_id"], "weight": p["weight"]}    for p in weight_sorted]
    }
    # ── Step 3: Group ─────────────────────────────────────────────────────────
    groups = group_by_destination(sorted_pkgs)
    group_summary = [
        {
            "dest_node": dest,
            "dest_name": NODES[dest]["name"],
            "count": len(pkgs),
            "total_weight": total_weight(pkgs)
        }
        for dest, pkgs in groups.items()
    ]
    step3 = {
        "step": 3,
        "title": "Group by Destination",
        "algo": "Hash Map Grouping",
        "explanation": "Packages sharing a destination are batched together to minimise trips.",
        "groups": group_summary
    }

    # ── Step 4: Best warehouse (show first destination only) ──────────────────
    first_dest = list(groups.keys())[0]
    warehouse_results = []
    for w in range(5):
        r = dijkstra(graph, w, first_dest)
        warehouse_results.append({
            "warehouse_id":   w,
            "warehouse_name": NODES[w]["name"],
            "distance":       round(r["distance"], 2) if r["distance"] != float('inf') else None,
            "reachable":      r["distance"] != float('inf')
        })
    best_w = min(warehouse_results, key=lambda x: x["distance"] if x["distance"] else float('inf'))
    step4 = {
        "step": 4,
        "title": "Auto-Select Best Warehouse",
        "algo": "Dijkstra × 5",
        "explanation": f"Dijkstra runs from all 5 warehouses to {NODES[first_dest]['name']}. Shortest path wins.",
        "destination": NODES[first_dest]["name"],
        "warehouse_distances": warehouse_results,
        "selected": best_w
    }

    # ── Step 5: Van selection (first destination) ─────────────────────────────
    first_pkgs   = groups[first_dest]
    dest_weight  = total_weight(first_pkgs)
    van_checks   = []
    for v in sorted(FLEET, key=lambda x: x["capacity"]):
        van_checks.append({
            "van":      v["name"],
            "capacity": v["capacity"],
            "fits":     v["capacity"] >= dest_weight
        })
    chosen_van = select_van(FLEET, dest_weight)
    step5 = {
        "step": 5,
        "title": "Select Van",
        "algo": "Greedy — Smallest Fit",
        "explanation": "Pick the smallest van whose capacity ≥ total destination weight. Saves larger vans for heavier loads.",
        "total_weight": dest_weight,
        "van_checks":   van_checks,
        "selected":     chosen_van["name"]
    }

    # ── Step 6: Pack van (DP) ─────────────────────────────────────────────────
    packed, leftover = pack_van(first_pkgs, chosen_van["capacity"])
    step6 = {
        "step": 6,
        "title": "Pack Van (0/1 Knapsack)",
        "algo": "Dynamic Programming",
        "explanation": "DP table maximises weight loaded without exceeding van capacity. Leftover packages go to a second van.",
        "van_capacity": chosen_van["capacity"],
        "packed":   [{"package_id": p["package_id"], "weight": p["weight"]} for p in packed],
        "leftover": [{"package_id": p["package_id"], "weight": p["weight"]} for p in leftover],
        "packed_weight":   total_weight(packed),
        "leftover_weight": total_weight(leftover)
    }

    # ── Step 7: Closest bonus stop ────────────────────────────────────────────
    served = set(range(5))
    served.add(first_dest)
    bonus = closest_delivery_node(first_dest, NODE_COORDS, served)
    step7 = {
        "step": 7,
        "title": "Find Bonus Stop",
        "algo": "Divide & Conquer — Closest Pair",
        "explanation": "After packing the primary stop, find the nearest unserved node using closest-pair. Fill remaining van space.",
        "primary_node": NODES[first_dest]["name"],
        "bonus_node":   NODES[bonus["node_id"]]["name"] if bonus else None,
        "remaining_capacity": round(chosen_van["capacity"] - total_weight(packed), 2)
    }

    # ── Step 8: Final dispatch (first trip) ───────────────────────────────────
    bonus_stop = bonus["node_id"] if bonus else None
    stops      = [first_dest] + ([bonus_stop] if bonus_stop else [])
    route_nodes, route_names, dist = build_route(graph, best_w["warehouse_id"], stops)
    step8 = {
        "step": 8,
        "title": "Dispatch",
        "algo": "Multi-Stop Routing",
        "explanation": "Van is dispatched from the optimal warehouse through all stops in order.",
        "warehouse":   NODES[best_w["warehouse_id"]]["name"],
        "route_names": route_names,
        "distance":    dist,
        "load":        total_weight(packed),
        "packages":    [p["package_id"] for p in packed]
    }

    return jsonify([step1, step2, step3, step4, step5, step6, step7, step8])


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)