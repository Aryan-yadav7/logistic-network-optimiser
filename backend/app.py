# app.py — Full Logistics Pipeline

from delhi_graph      import build_graph, NODES
from data_generator   import generate_deliveries
from sorting          import sort_by_deadline
from graph            import find_best_warehouse
from greedy           import select_van
from dp               import pack_van
from divide_conquer   import closest_delivery_node

# ─── Fleet ────────────────────────────────────────────────────────────────────

FLEET = [
    {"van_id": 1, "name": "Small",  "capacity": 30},
    {"van_id": 2, "name": "Medium", "capacity": 60},
    {"van_id": 3, "name": "Large",  "capacity": 100},
]

# ─── Node coordinates for closest-pair (lat/lng as x/y) ──────────────────────

NODE_COORDS = [
    {"node_id": nid, "x": info["lng"], "y": info["lat"]}
    for nid, info in NODES.items()
]

# ─── Helpers ──────────────────────────────────────────────────────────────────

def group_by_destination(packages):
    """{ dest_node: [pkg, pkg, ...] }"""
    groups = {}
    for pkg in packages:
        d = pkg["dest_node"]
        groups.setdefault(d, []).append(pkg)
    return groups


def total_weight(packages):
    return round(sum(p["weight"] for p in packages), 2)


def route_with_stops(graph, warehouse, stops):
    """
    Build a multi-stop route string and total distance.
    warehouse → stop1 → stop2 → ...
    Uses Dijkstra leg by leg.
    """
    from graph import dijkstra

    path   = [warehouse] + stops
    labels = [NODES[n]["name"] for n in path]
    route  = " → ".join(labels)

    total_dist = 0.0
    for i in range(len(path) - 1):
        total_dist += dijkstra(graph, path[i], path[i + 1])

    return route, round(total_dist, 2)


def dispatch_van(van, warehouse, stops, packed, graph, label=""):
    """Print one dispatch record."""
    route, dist = route_with_stops(graph, warehouse, stops)
    pkg_ids     = [p["package_id"] for p in packed]
    load        = total_weight(packed)

    print(f"\n  {'─'*60}")
    print(f"  {label}")
    print(f"  Van      : {van['name']} (capacity {van['capacity']} kg)")
    print(f"  Load     : {load} kg  |  Packages: {pkg_ids}")
    print(f"  Route    : {route}")
    print(f"  Distance : {dist} km")


# ─── Core Pipeline ────────────────────────────────────────────────────────────

def run_pipeline(n_packages=20):

    graph = build_graph()

    # ── Step 1: Generate & sort ───────────────────────────────────────────────
    print("=" * 65)
    print("  DELHI LOGISTICS PIPELINE")
    print("=" * 65)

    raw       = generate_deliveries(n_packages)
    packages  = sort_by_deadline(raw)           # sorted by deadline ascending
    print(f"\n✔  Generated {len(packages)} packages, sorted by deadline.")

    # ── Step 2: Group by destination ─────────────────────────────────────────
    groups = group_by_destination(packages)
    print(f"✔  {len(groups)} unique destinations.\n")

    dispatches   = []   # final dispatch records for summary
    served_nodes = set(range(5))   # warehouses never become bonus stops

    # ── Step 3: Process each destination ─────────────────────────────────────
    for dest, pkgs in groups.items():

        dest_name = NODES[dest]["name"]
        w_total   = total_weight(pkgs)

        print(f"\n{'━'*65}")
        print(f"  DESTINATION : {dest_name}  (node {dest})")
        print(f"  Orders      : {len(pkgs)} packages  |  Total weight: {w_total} kg")

        # Step 4: Auto-select best warehouse
        result    = find_best_warehouse(graph, dest)
        warehouse = result["warehouse"]
        print(f"  Warehouse   : {NODES[warehouse]['name']}  "
              f"(node {warehouse}, {result['distance']} km)")

        # Step 5 + 6: Pack vans — split if weight > 100 kg
        remaining = pkgs[:]
        trip_num  = 1

        while remaining:

            w_remaining = total_weight(remaining)
            van         = select_van(FLEET, w_remaining)     # greedy
            packed, leftover = pack_van(remaining, van["capacity"])  # DP

            if not packed:
                # Edge case: single package heavier than largest van
                packed    = [remaining[0]]
                leftover  = remaining[1:]

            # Step 7: Find bonus stop (closest unserved node)
            served_nodes.add(dest)
            bonus_node = closest_delivery_node(dest, NODE_COORDS, served_nodes)

            bonus_packed = []
            bonus_stop   = None

            if bonus_node:
                bonus_id      = bonus_node["node_id"]
                bonus_pkgs    = groups.get(bonus_id, [])
                van_used_cap  = total_weight(packed)
                remaining_cap = van["capacity"] - van_used_cap

                if bonus_pkgs and remaining_cap > 0:
                    # Fill remaining capacity with bonus node's packages (whole only)
                    extra, _ = pack_van(bonus_pkgs, int(remaining_cap))
                    if extra:
                        bonus_packed = extra
                        bonus_stop   = bonus_id
                        # Remove bonus packages from their group so they aren't re-dispatched
                        packed_ids = {p["package_id"] for p in extra}
                        groups[bonus_id] = [p for p in bonus_pkgs
                                            if p["package_id"] not in packed_ids]
                        served_nodes.add(bonus_id)

            # Build stops list
            stops = [dest]
            if bonus_stop is not None:
                stops.append(bonus_stop)

            all_packed = packed + bonus_packed
            label      = f"Trip {trip_num}"
            if bonus_stop:
                label += f"  +bonus stop → {NODES[bonus_stop]['name']}"

            dispatch_van(van, warehouse, stops, all_packed, graph, label)
            dispatches.append({
                "dest": dest_name,
                "van": van["name"],
                "load": total_weight(all_packed),
                "stops": stops,
            })

            remaining = leftover
            trip_num += 1

    # ── Step 8: Summary ───────────────────────────────────────────────────────
    print(f"\n\n{'='*65}")
    print("  DISPATCH SUMMARY")
    print(f"{'='*65}")
    print(f"  Total trips dispatched : {len(dispatches)}")

    van_usage = {}
    for d in dispatches:
        van_usage[d["van"]] = van_usage.get(d["van"], 0) + 1

    for van_name, count in van_usage.items():
        print(f"  {van_name:10} van used : {count}x")

    total_load = sum(d["load"] for d in dispatches)
    print(f"  Total weight shipped   : {round(total_load, 2)} kg")
    print(f"{'='*65}\n")


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_pipeline(n_packages=20)