# server.py — DelhiDash with persistent storage, order placement, parallel vans

import os, sys, json, sqlite3, uuid
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from flask import Flask, jsonify, send_from_directory, request

from backend.delhi_graph    import build_graph, NODES
from backend.data_generator import generate_deliveries
from backend.sorting        import sort_by_weight, sort_by_priority_then_deadline
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

# ─── SQLite persistence ───────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(__file__), "delhidash.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT PRIMARY KEY,
            created_at  TEXT NOT NULL,
            total_orders INTEGER,
            total_trips  INTEGER
        );

        CREATE TABLE IF NOT EXISTS orders (
            id          TEXT PRIMARY KEY,
            session_id  TEXT,
            package_id  TEXT,
            priority    INTEGER,
            deadline    INTEGER,
            weight      REAL,
            dest_node   INTEGER,
            dest_name   TEXT,
            status      TEXT DEFAULT 'pending',
            created_at  TEXT NOT NULL,
            completed_at TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS trips (
            id           TEXT PRIMARY KEY,
            session_id   TEXT,
            destination  TEXT,
            dest_node    INTEGER,
            warehouse    TEXT,
            van          TEXT,
            load_kg      REAL,
            distance_km  REAL,
            route_nodes  TEXT,
            route_names  TEXT,
            package_ids  TEXT,
            has_bonus    INTEGER,
            bonus_name   TEXT,
            completed_at TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS customer_orders (
            id          TEXT PRIMARY KEY,
            name        TEXT,
            phone       TEXT,
            dest_node   INTEGER,
            dest_name   TEXT,
            weight      REAL,
            priority    INTEGER,
            deadline    INTEGER,
            status      TEXT DEFAULT 'queued',
            created_at  TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()

init_db()

# ─── Helpers ──────────────────────────────────────────────────────────────────

def group_by_destination(packages):
    groups = {}
    for pkg in packages:
        groups.setdefault(pkg["dest_node"], []).append(pkg)
    return groups

def total_weight(packages):
    return round(sum(p["weight"] for p in packages), 2)

def build_route(graph, warehouse, stops):
    path        = [warehouse] + stops
    route_names = [NODES[n]["name"] for n in path]
    total_dist  = 0.0
    for i in range(len(path) - 1):
        total_dist += dijkstra(graph, path[i], path[i + 1])["distance"]
    return path, route_names, round(total_dist, 2)

def _fmt_order(p):
    return {
        "id":         p["package_id"],
        "package_id": p["package_id"],
        "priority":   p["priority"],
        "deadline":   p["deadline"],
        "weight":     round(p["weight"], 1),
        "dest":       NODES[p["dest_node"]]["name"],
        "dest_name":  NODES[p["dest_node"]]["name"],
        "dest_node":  p["dest_node"],
    }

def run_pipeline(n, extra_orders=None):
    """
    Core logistics pipeline. Returns (sorted_orders, sort_steps, trips, priority_groups).
    extra_orders: list of customer-placed orders to inject into the batch.
    """
    graph = build_graph()
    raw   = generate_deliveries(n)

    # Inject customer orders
    if extra_orders:
        for o in extra_orders:
            raw.append({
                "package_id":  o["id"],
                "priority":    o["priority"],
                "deadline":    o["deadline"],
                "weight":      o["weight"],
                "dest_node":   o["dest_node"],
                "source_node": 0,
            })

    sorted_orders, sort_steps = sort_by_priority_then_deadline(raw)
    groups       = group_by_destination(sorted_orders)
    trips        = []
    served_nodes = set(range(5))

    for dest, pkgs in groups.items():
        result    = find_best_warehouse(graph, dest)
        warehouse = result["warehouse"]
        remaining = pkgs[:]

        while remaining:
            w_rem            = total_weight(remaining)
            van              = select_van(FLEET, w_rem)
            remaining_sorted = sort_by_weight(remaining)
            packed, leftover = pack_van(remaining_sorted, van["capacity"])

            if not packed:
                packed   = [remaining[0]]
                leftover = remaining[1:]

            served_nodes.add(dest)
            bonus_node   = closest_delivery_node(dest, NODE_COORDS, served_nodes)
            bonus_packed = []
            bonus_stop   = None
            bonus_name   = None

            if bonus_node:
                bonus_id   = bonus_node["node_id"]
                bonus_pkgs = groups.get(bonus_id, [])
                rem_cap    = van["capacity"] - total_weight(packed)
                if bonus_pkgs and rem_cap > 0:
                    extra, _ = pack_van(bonus_pkgs, int(rem_cap))
                    if extra:
                        bonus_packed = extra
                        bonus_stop   = bonus_id
                        bonus_name   = NODES[bonus_id]["name"]
                        packed_ids   = {p["package_id"] for p in extra}
                        groups[bonus_id] = [p for p in bonus_pkgs if p["package_id"] not in packed_ids]
                        served_nodes.add(bonus_id)

            stops = [dest] + ([bonus_stop] if bonus_stop else [])
            route_nodes, route_names, dist = build_route(graph, warehouse, stops)
            all_packed = packed + bonus_packed

            trips.append({
                "destination": NODES[dest]["name"],
                "dest_node":   dest,
                "warehouse":   NODES[warehouse]["name"],
                "van":         van["name"],
                "load":        total_weight(all_packed),
                "distance":    dist,
                "route_nodes": route_nodes,
                "route_names": route_names,
                "packages": [
                    {"id": p["package_id"], "weight": p["weight"],
                     "priority": p["priority"], "deadline": p["deadline"]}
                    for p in all_packed
                ],
                "has_bonus": bonus_stop is not None,
                "bonus_name": bonus_name,
            })
            remaining = leftover

    priority_groups = {}
    for p in sorted_orders:
        g = priority_groups.setdefault(p["priority"], {
            "count": 0, "min_deadline": 999, "max_deadline": 0, "packages": []
        })
        g["count"] += 1
        g["min_deadline"] = min(g["min_deadline"], p["deadline"])
        g["max_deadline"] = max(g["max_deadline"], p["deadline"])
        g["packages"].append({
            "id":       p["package_id"],
            "priority": p["priority"],
            "deadline": p["deadline"],
            "weight":   p["weight"],
            "dest":     NODES[p["dest_node"]]["name"],
        })

    return sorted_orders, sort_steps, trips, priority_groups

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")

@app.route("/operations")
def operations():
    return send_from_directory("frontend", "ops.html")

# ─── /nodes — static node + edge data ────────────────────────────────────────

@app.route("/nodes")
def nodes_data():
    from backend.delhi_graph import EDGES
    nodes_out = [
        {"id": nid, "name": info["name"], "lat": info["lat"],
         "lng": info["lng"], "type": info["type"]}
        for nid, info in NODES.items()
    ]
    edges_out = [{"u": u, "v": v, "base_weight": w} for u, v, w in EDGES]
    return jsonify({"nodes": nodes_out, "edges": edges_out})

# ─── /ops — multi-order operations dashboard ─────────────────────────────────

@app.route("/ops")
def ops():
    n = int(request.args.get("n", 20))
    n = max(8, min(n, 60))

    # Pull pending customer orders into batch
    conn = get_db()
    cust_rows = conn.execute(
        "SELECT * FROM customer_orders WHERE status='queued' ORDER BY created_at ASC LIMIT 10"
    ).fetchall()
    conn.close()

    extra_orders = []
    cust_ids     = []
    for row in cust_rows:
        extra_orders.append({
            "id":       "CUST-" + row["id"][:6].upper(),
            "priority": row["priority"],
            "deadline": row["deadline"],
            "weight":   row["weight"],
            "dest_node":row["dest_node"],
        })
        cust_ids.append(row["id"])

    sorted_orders, sort_steps, trips, priority_groups = run_pipeline(n, extra_orders)

    # Persist session
    session_id = str(uuid.uuid4())
    now        = datetime.utcnow().isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO sessions VALUES (?,?,?,?)",
        (session_id, now, len(sorted_orders), len(trips))
    )

    for p in sorted_orders:
        conn.execute(
            "INSERT OR IGNORE INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), session_id, p["package_id"], p["priority"],
             p["deadline"], p["weight"], p["dest_node"],
             NODES[p["dest_node"]]["name"], "completed", now, now)
        )

    for t in trips:
        conn.execute(
            "INSERT INTO trips VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), session_id, t["destination"], t["dest_node"],
             t["warehouse"], t["van"], t["load"], t["distance"],
             json.dumps(t["route_nodes"]), json.dumps(t["route_names"]),
             json.dumps([p["id"] for p in t["packages"]]),
             int(t["has_bonus"]), t["bonus_name"], now)
        )

    # Mark customer orders as dispatched
    for cid in cust_ids:
        conn.execute("UPDATE customer_orders SET status='dispatched' WHERE id=?", (cid,))

    conn.commit()
    conn.close()

    return jsonify({
        "session_id":      session_id,
        "total_orders":    len(sorted_orders),
        "total_trips":     len(trips),
        "sort_steps":      sort_steps,
        "sorted_orders":   [_fmt_order(p) for p in sorted_orders],
        "priority_groups": priority_groups,
        "trips":           trips,
        "injected_customer_orders": len(extra_orders),
    })

# ─── /run — same as /ops but lighter ─────────────────────────────────────────

@app.route("/run")
def run():
    n = int(request.args.get("n", 20))
    n = max(5, min(n, 60))
    sorted_orders, _, trips, _ = run_pipeline(n)
    return jsonify({
        "packages_generated": n,
        "packages_sorted":    len(sorted_orders),
        "destinations":       len(set(p["dest_node"] for p in sorted_orders)),
        "trips":              trips,
    })

# ─── /simulate — single trip with dynamic traffic rerouting ──────────────────

@app.route("/simulate")
def simulate():
    import random
    from backend.delhi_graph import EDGES

    graph          = build_graph()
    delivery_nodes = [nid for nid, info in NODES.items() if info["type"] == "delivery"]
    dest           = int(request.args.get("dest", random.choice(delivery_nodes)))

    best_warehouse = None
    best_path      = []
    for wh in range(5):
        candidate = dijkstra(graph, wh, dest)
        if candidate["distance"] != float("inf") and len(candidate["path"]) > len(best_path):
            best_path      = candidate["path"]
            best_warehouse = wh

    if best_warehouse is None:
        result         = find_best_warehouse(graph, dest)
        best_warehouse = result["warehouse"]
        best_path      = dijkstra(graph, best_warehouse, dest)["path"]

    warehouse       = best_warehouse
    planned_path    = best_path
    planned_dist    = dijkstra(graph, warehouse, dest)["distance"]

    traffic_event = None
    if len(planned_path) >= 3:
        mid_idx   = max(1, len(planned_path) // 2)
        at_node   = planned_path[mid_idx]

        remaining_edges = [(planned_path[i], planned_path[i+1])
                          for i in range(mid_idx, len(planned_path) - 1)]
        all_edges       = [(u, v) for u, v, _ in EDGES]
        extra_e         = random.sample(all_edges, min(2, len(all_edges)))
        candidate_edges = list(set(remaining_edges + extra_e))

        num_congested       = random.randint(1, min(3, len(candidate_edges)))
        congested           = random.sample(candidate_edges, num_congested)
        traffic_multipliers = {}
        congested_out       = []
        for u, v in congested:
            mult = round(random.uniform(2.5, 5.0), 1)
            traffic_multipliers[(u, v)] = mult
            traffic_multipliers[(v, u)] = mult
            congested_out.append({"u": u, "v": v, "multiplier": mult})

        rerouted         = dijkstra(graph, at_node, dest, traffic_multipliers)
        new_suffix       = rerouted["path"]
        original_suffix  = planned_path[mid_idx:]
        reroute_happened = new_suffix != original_suffix

        traffic_event = {
            "at_node":          at_node,
            "at_node_name":     NODES[at_node]["name"],
            "congested_edges":  congested_out,
            "original_suffix":  original_suffix,
            "new_path_suffix":  new_suffix,
            "reroute_happened": reroute_happened,
            "new_distance":     rerouted["distance"],
        }
    else:
        traffic_event = {
            "at_node": None, "congested_edges": [],
            "original_suffix": [], "new_path_suffix": planned_path,
            "reroute_happened": False, "new_distance": planned_dist,
        }

    if traffic_event["at_node"] is not None:
        mid_idx    = planned_path.index(traffic_event["at_node"])
        travelled  = planned_path[:mid_idx + 1]
        final_path = travelled + traffic_event["new_path_suffix"][1:]
    else:
        final_path = planned_path

    from backend.delhi_graph import EDGES as EDGES_LIST
    nodes_out = {
        str(nid): {"name": info["name"], "lat": info["lat"],
                   "lng": info["lng"], "type": info["type"]}
        for nid, info in NODES.items()
    }
    edges_out = [{"u": u, "v": v, "base_weight": w} for u, v, w in EDGES_LIST]

    return jsonify({
        "warehouse":        warehouse,
        "warehouse_name":   NODES[warehouse]["name"],
        "destination":      dest,
        "dest_name":        NODES[dest]["name"],
        "planned_path":     planned_path,
        "final_path":       final_path,
        "planned_distance": planned_dist,
        "traffic_event":    traffic_event,
        "nodes":            nodes_out,
        "edges":            edges_out,
    })

# ─── /place_order — customer order placement ─────────────────────────────────

@app.route("/place_order", methods=["POST"])
def place_order():
    data = request.get_json(force=True)
    required = ["name", "dest_node", "weight", "priority", "deadline"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    dest_node = int(data["dest_node"])
    if dest_node not in NODES or NODES[dest_node]["type"] != "delivery":
        return jsonify({"error": "Invalid destination node"}), 400

    order_id = str(uuid.uuid4())
    now      = datetime.utcnow().isoformat()
    conn     = get_db()
    conn.execute(
        "INSERT INTO customer_orders VALUES (?,?,?,?,?,?,?,?,?,?)",
        (order_id, data.get("name",""), data.get("phone",""),
         dest_node, NODES[dest_node]["name"],
         float(data["weight"]), int(data["priority"]),
         int(data["deadline"]), "queued", now)
    )
    conn.commit()
    conn.close()

    return jsonify({
        "success":   True,
        "order_id":  order_id,
        "dest_name": NODES[dest_node]["name"],
        "message":   f"Order placed for {NODES[dest_node]['name']}. Will be dispatched in next batch.",
    })

# ─── /history — completed trips log ──────────────────────────────────────────

@app.route("/history")
def history():
    limit = int(request.args.get("limit", 50))
    conn  = get_db()

    sessions = conn.execute(
        "SELECT * FROM sessions ORDER BY created_at DESC LIMIT 20"
    ).fetchall()

    trips = conn.execute(
        """SELECT t.*, s.created_at as session_time
           FROM trips t JOIN sessions s ON t.session_id = s.id
           ORDER BY t.completed_at DESC LIMIT ?""",
        (limit,)
    ).fetchall()

    customer_orders = conn.execute(
        "SELECT * FROM customer_orders ORDER BY created_at DESC LIMIT 30"
    ).fetchall()

    conn.close()

    sessions_out = [dict(s) for s in sessions]
    trips_out    = []
    for t in trips:
        row = dict(t)
        row["route_nodes"] = json.loads(row["route_nodes"] or "[]")
        row["route_names"] = json.loads(row["route_names"] or "[]")
        row["package_ids"] = json.loads(row["package_ids"] or "[]")
        trips_out.append(row)

    cust_out = [dict(c) for c in customer_orders]

    return jsonify({
        "sessions":        sessions_out,
        "trips":           trips_out,
        "customer_orders": cust_out,
        "total_sessions":  len(sessions_out),
        "total_trips":     len(trips_out),
    })

# ─── /stats — aggregate stats ─────────────────────────────────────────────────

@app.route("/stats")
def stats():
    conn = get_db()
    row  = conn.execute("""
        SELECT
            COUNT(DISTINCT session_id) as sessions,
            COUNT(*) as total_trips,
            SUM(load_kg) as total_kg,
            SUM(distance_km) as total_km,
            AVG(distance_km) as avg_km
        FROM trips
    """).fetchone()
    pending_cust = conn.execute(
        "SELECT COUNT(*) as cnt FROM customer_orders WHERE status='queued'"
    ).fetchone()
    conn.close()
    d = dict(row)
    d["pending_customer_orders"] = pending_cust["cnt"]
    return jsonify(d)

# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)