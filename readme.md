# DelhiDash — Logistics Network Optimiser

> A Delhi-based last-mile delivery simulation inspired by Zepto.  
> Full-stack Flask app with a 7-stage algorithmic pipeline covering  
> sorting, graph routing, greedy selection, DP packing, divide & conquer,  
> and live traffic rerouting.

---

## Quick Start

```bash
git clone https://github.com/Aryan-yadav7/logistic-network-optimiser
cd logistic-network-optimiser
pip install flask
python server.py
# → http://localhost:5000
```

Two views:
- **`/`** → Customer Dispatch Centre (`index.html`) — PC desktop UI, live map
- **`/operations`** → Operations Centre (`ops.html`) — dark terminal, sort visualiser

---

## File Structure

```
logistic-network-optimiser/
├── server.py                    # Flask app — all API routes
├── frontend/
│   ├── index.html               # Customer UI (Leaflet map + order tracker)
│   └── ops.html                 # Ops dashboard (sort engine + dispatch log)
└── backend/
    ├── delhi_graph.py           # Node/edge definitions + build_graph()
    ├── graph.py                 # Dijkstra, A*, Bellman-Ford, warehouse finders
    ├── sorting.py               # Merge Sort, Quick Sort, Heap Sort, Bubble Sort
    ├── data_generator.py        # Random order generator
    ├── dp.py                    # 0/1 Knapsack (weight + priority), activity selection
    ├── greedy.py                # Van selection, Prim's MST, fractional knapsack
    └── divide_conquer.py        # Closest pair — bonus stop finder
```

---

## The Full Pipeline

Every call to `/ops` or `/run` runs this 7-stage pipeline in `server.py → run_pipeline()`:

```
generate_deliveries(n)
        │
        ▼
sort_by_priority_then_deadline()   ← Quick Sort (pass 1) + Merge Sort (pass 2)
        │
        ▼
group_by_destination()             ← O(n) dict bucketing
        │
        ▼  [for each destination group]
find_best_warehouse()              ← Dijkstra × 5 warehouses
        │
        ▼
select_van()                       ← Greedy smallest-fit
        │
        ▼
pack_van_by_priority()             ← 0/1 Knapsack DP (priority-aware)
        │
        ▼
closest_delivery_node()            ← Divide & Conquer closest pair
        │
        ▼
build_route() → SQLite persist     ← Dijkstra legs chained
```

---

## Algorithm Reference

### 1. Two-Pass Sort — `backend/sorting.py`

**Function:** `sort_by_priority_then_deadline(packages)`  
**Returns:** `(sorted_list, steps)` — steps used by ops.html sort visualiser

**The problem:** Sort packages so that the most critical (P1) dispatch first, and within the same priority level, the earliest deadline goes first.

**Why two separate algorithms instead of one?**

A single sort on a tuple `(priority, deadline)` would work but wastes time doing stability work it doesn't need in the first pass. The two-pass design is deliberate:

| Pass | Algorithm | Key | Why this algo |
|------|-----------|-----|---------------|
| 1 | **Quick Sort** | `priority` ascending | Stability not needed — we're about to re-sort within groups anyway. Quick Sort's in-place partitioning avoids auxiliary array allocation. O(n log n) average. |
| 2 | **Merge Sort** | `deadline` ascending per group | **Must be stable** — equal-priority items must stay in their group position while deadlines are sorted. Merge Sort is inherently stable. O(n log n) guaranteed. |

**Result:** `P1/2h → P1/5h → P1/12h → P2/3h → P2/8h → ...`

---

**Other sort functions available:**

| Function | Algorithm | Use case |
|----------|-----------|----------|
| `sort_by_deadline(pkgs)` | Merge Sort | Stable sort by deadline alone |
| `sort_by_priority(pkgs)` | Heap Sort | Max-priority first (uses heap's natural max ordering) |
| `sort_by_weight(pkgs)` | Quick Sort | Ascending weight for knapsack input |

**Heap Sort detail:** `heap_sort()` builds a max-heap in O(n), then repeatedly extracts the max in O(log n) each time. Total O(n log n). Used for priority because the heap data structure naturally models "most urgent item next" — it IS a priority queue.

**Bubble Sort** (`bubble_sort()`) is implemented for completeness / educational display in ops.html. Not used in the live pipeline — O(n²) is too slow for production.

---

### 2. Dijkstra — `backend/graph.py`

**Function:** `dijkstra(graph, src, dest, traffic_multipliers=None)`  
**Returns:** `{"distance": float, "path": [node_ids]}`

**The problem:** Find the shortest (cheapest km) route from a warehouse to a delivery node, respecting live traffic conditions.

**How it works:**

Dijkstra maintains a **min-heap** of `(tentative_cost, node)` pairs. It repeatedly pops the cheapest unvisited node, relaxes all its outgoing edges, and pushes updated costs. The key insight: once a node is popped, its shortest path is finalized — no cheaper path to it can exist later (valid only when all weights ≥ 0).

```python
# Core relaxation loop
for v, weight in graph[u]:
    eff_weight = weight * traffic_multipliers.get((u,v), 1.0)
    if dist[u] + eff_weight < dist[v]:
        dist[v] = dist[u] + eff_weight
        heappush(pq, (dist[v], v))
```

**Traffic multipliers:** The `traffic_multipliers` dict `{(u,v): float}` is checked symmetrically (both `(u,v)` and `(v,u)`) so one blocked road affects both directions. A multiplier of 3.0 means that edge now costs 3× — making Dijkstra route around it.

**Complexity:** O((V + E) log V) with binary heap. For 20 nodes / 34 edges: instantaneous.

**When to use:** All edge weights ≥ 0. No coordinate data needed.

---

**Function:** `find_best_warehouse(graph, dest, traffic_multipliers=None)`  
**Returns:** `{"warehouse": int, "distance": float}`

Runs Dijkstra from each of the 5 warehouses (IDs 0–4) to `dest`, returns the nearest one. This is correct for a small fixed fleet — 5 Dijkstra runs on a 20-node graph is negligible cost.

---

**`/simulate` warehouse selection twist:** In the `/simulate` route, the code intentionally picks the warehouse with the **longest path** (most hops), not the shortest distance. This ensures the traffic event fires meaningfully in the middle of a real journey, not at node 1 of a 2-hop path.

---

### 3. A* — `backend/graph.py` *(new)*

**Function:** `astar(graph, src, dest, node_coords, traffic_multipliers=None)`  
**Returns:** `{"distance": float, "path": [node_ids], "nodes_explored": int}`

**The problem:** Same as Dijkstra — but faster when nodes have geographic coordinates.

**How it differs from Dijkstra:**

Dijkstra explores in all directions equally — it has no idea where the destination is. A* adds a **heuristic** `h(n)` that estimates the remaining distance from node `n` to the destination, biasing the search toward the goal.

```
f(n) = g(n) + h(n)
       ↑         ↑
  cost so far   estimated cost remaining
```

The heap is keyed by `f` instead of `g`. Nodes closer to the destination get explored first.

**Heuristic used:** `haversine_km(lat1, lon1, lat2, lon2)` — straight-line distance between two GPS coordinates on Earth's surface. This is **admissible**: it never overestimates actual road distance (roads are longer than straight lines), so A* always finds the true shortest path.

**When to use:** Any route query where `node_coords` (lat/lng) are available — which is always in DelhiDash. On a 20-node graph the difference is small, but if you expand to 200+ Delhi nodes, A* explores ~40–60% fewer nodes than Dijkstra.

**Function:** `find_best_warehouse_astar(graph, dest, node_coords, traffic_multipliers=None)`  
Drop-in replacement for `find_best_warehouse()` using A* internally.

---

### 4. Bellman-Ford — `backend/graph.py` *(new)*

**Function:** `bellman_ford(graph, src, dest, traffic_multipliers=None)`  
**Returns:** `{"distance": float, "path": [node_ids], "negative_cycle": bool}`

**The problem:** Dijkstra breaks silently if any edge weight is negative. Bellman-Ford handles negative weights correctly.

**When does this matter in logistics?**
- Backhaul discounts (a truck returning empty is effectively cheaper than a full outbound trip)
- Fuel subsidies applied as negative cost adjustments
- Penalty-subtracted route models

**How it works:** Relax ALL edges V−1 times (guaranteed to settle all shortest paths). Then do one more pass — if anything still improves, a negative cycle exists (impossible in physical routing — signals a broken cost model).

```python
for _ in range(len(nodes) - 1):
    for u, v, w in edges:
        if dist[u] + w < dist[v]:
            dist[v] = dist[u] + w
```

**Complexity:** O(V × E) — slower than Dijkstra's O((V+E) log V). Use only when negative weights are possible.

---

### 5. Greedy Van Selection — `backend/greedy.py`

**Function:** `select_van(fleet, total_weight)`  
**Returns:** van dict from fleet

**The problem:** Given packages totalling `total_weight` kg, which van minimises cost?

**Why greedy works here:**

The greedy choice property holds: picking the smallest van that fits is locally AND globally optimal. Each delivery trip is independent — there's no scenario where picking a larger van now saves cost on a future trip. So the greedy decision is always correct.

```python
sorted_fleet = sorted(fleet, key=lambda v: v["capacity"])
for van in sorted_fleet:
    if van["capacity"] >= total_weight:
        return van
return sorted_fleet[-1]  # fallback: largest van (triggers multi-trip splitting)
```

Fleet: Small (30 kg) → Medium (60 kg) → Large (100 kg).  
If nothing fits, the largest van is returned and `run_pipeline`'s `while remaining:` loop handles splitting.

---

### 6. Prim's MST — `backend/greedy.py` *(new)*

**Function:** `prim_mst(graph)`  
**Returns:** `{"mst_edges": [(u,v,w),...], "total_cost": float, "nodes_covered": int}`

**The problem:** Which routes are essential vs redundant for keeping the whole Delhi network connected?

**How it works:**

Prim's grows the MST from a seed node using a min-heap:
1. Start at node 0. Mark it in-MST.
2. Push all its edges onto the heap.
3. Pop cheapest edge (u→v). If v already in MST: skip (would create a cycle).
4. Add v, push its edges. Repeat until all nodes covered.

**Why Prim's over Kruskal's?**

Both find the same MST. Prim's is O(E log V) and better for dense graphs. Kruskal's is O(E log E) with Union-Find and better for sparse graphs. The Delhi graph (20 nodes, 34 edges) is sparse — either works, but Prim's is easier to extend incrementally (adding a new hub = just push its edges and continue).

**Use case:** Run `prim_mst()` on the full graph to see which 19 routes form the backbone of the Delhi network. Any route NOT in the MST is a redundant edge — the network remains connected without it.

---

### 7. 0/1 Knapsack DP — `backend/dp.py`

**Function:** `pack_van(orders, capacity)`  
**Returns:** `(packed_list, leftover_list)`

**Function:** `pack_van_by_priority(orders, capacity)` *(new — recommended)*  
**Returns:** `(packed_list, leftover_list)`

**The problem:** Fill a van with packages without exceeding weight capacity, maximising the "value" loaded.

**Why DP and not greedy?**

Greedy (always take heaviest) fails:
- Capacity = 10 kg, packages = [6 kg, 5 kg, 5 kg]
- Greedy: takes 6 kg → 4 kg wasted → total loaded = 6 kg ❌
- DP: takes 5+5 kg → zero waste → total loaded = 10 kg ✓

**The DP table:**

`dp[i][w]` = maximum value achievable using first `i` packages with remaining capacity `w`.

```
dp[i][w] = dp[i-1][w]                          ← skip package i
dp[i][w] = max(dp[i][w], dp[i-1][w-wi] + vi)  ← take package i (if wi ≤ w)
```

Then traceback through the table to find which packages were selected.

**`pack_van` vs `pack_van_by_priority`:**

| Function | Maximises | Risk |
|----------|-----------|------|
| `pack_van` | Total weight loaded | A 10 kg P5 (minimal) beats a 2 kg P1 (critical) |
| `pack_van_by_priority` | Priority score (P1=5pts, P5=1pt) | Critical packages always go first |

**`pack_van_by_priority`** uses an inverted score `(6 - priority)` so P1 → 5 points, P5 → 1 point. The knapsack maximises this score with weight as the constraint — ensuring CRITICAL packages always load before MINIMAL ones.

**Complexity:** O(n × capacity) time and space. For n=60 orders, capacity=100 kg: 6,000 table cells — instantaneous.

---

### 8. Divide & Conquer Closest Pair — `backend/divide_conquer.py`

**Function:** `closest_delivery_node(primary_node, all_nodes, served_nodes)`  
**Returns:** `{"node_id", "x", "y"}` dict or `None`

**The problem:** After packing packages for destination D, is there a nearby unserved node we can add as a bonus stop using leftover van capacity?

**How it works:**

Uses the classical **closest pair of points** divide & conquer algorithm — O(n log n):

1. Sort all nodes by x-coordinate (longitude). Sort again by y-coordinate (latitude).
2. Split at midpoint. Recursively find closest pair in left half and right half.
3. Take `d = min(left_result, right_result)`.
4. **The key insight:** Only points within a vertical strip of width `2d` around the midpoint can possibly beat `d`. Geometrically, at most 7 points per side can fit in this strip — so the strip check is O(1) per recursion level.
5. Result: O(n log n) overall vs O(n²) brute force.

**Base case:** For ≤ 3 points, brute force all pairs directly.

**In the pipeline:** `primary_node` is added to the candidate pool so `closest_pair` can find its nearest neighbour. Whichever of the returned pair isn't the primary node is the bonus stop. The `served_nodes` set filters out already-dispatched destinations.

**Real-world effect:** A van heading to Connaught Place (node 8) might also deliver to Chandni Chowk (node 6, 1.8 km away) on the same trip if capacity allows — exactly how Zepto-style batching works.

---

### 9. Activity Selection — `backend/dp.py` *(now integrated)*

**Function:** `activity_selection(deliveries)`  
**Returns:** `{"selected": list, "count": int, "rejected": list}`

**The problem:** When total order volume is very high and exceeds all van capacity, which orders should be accepted to maximise deliveries completed before deadline?

**Algorithm:** Sort by deadline ascending. Greedily accept each order if `deadline > current_time` (where each accepted order costs 1 time unit). This is provably optimal for maximising the count of non-overlapping intervals.

**Where to use in DelhiDash:**

```python
# In server.py, before run_pipeline(), when load is extreme:
feasible = activity_selection(all_orders)["selected"]
sorted_orders, steps, trips, groups = run_pipeline(len(feasible), feasible)
```

This prevents the `while remaining:` van-splitting loop from running indefinitely on impossible batches.

---

## API Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Serves `index.html` (customer UI) |
| `/operations` | GET | Serves `ops.html` (operations UI) |
| `/nodes` | GET | All nodes + edges for Leaflet map base layer |
| `/run?n=20` | GET | Full pipeline for N orders, returns trips array |
| `/ops?n=20` | GET | Full pipeline + sort steps + priority groups (used by both UIs) |
| `/simulate?dest=7` | GET | Single-trip simulation with live traffic rerouting |
| `/place_order` | POST | Customer order placement → queued in SQLite |
| `/history?limit=50` | GET | Completed sessions, trips, customer orders |
| `/stats` | GET | Aggregate totals (kg dispatched, km travelled, etc.) |

---

## `/ops` Response Shape

```json
{
  "session_id": "uuid",
  "total_orders": 20,
  "total_trips": 8,
  "sort_steps": [
    {
      "pass": 1,
      "label": "Pass 1 — Quick Sort by Priority",
      "algo": "Quick Sort",
      "description": "...",
      "result": [{"package_id", "priority", "deadline", "weight", "dest_node"}]
    },
    {
      "pass": 2,
      "label": "Pass 2 — Merge Sort by Deadline within each Priority Group",
      "algo": "Merge Sort",
      "groups": [{"priority", "count", "deadlines_before", "deadlines_after"}],
      "result": [...]
    }
  ],
  "sorted_orders": [{"id", "priority", "deadline", "weight", "dest", "dest_node"}],
  "priority_groups": {
    "1": {"count": 3, "min_deadline": 2, "max_deadline": 8, "packages": [...]}
  },
  "trips": [
    {
      "destination": "Connaught Place",
      "dest_node": 8,
      "warehouse": "Naraina Industrial Area",
      "van": "Medium",
      "load": 45.2,
      "distance": 12.4,
      "route_nodes": [0, 8],
      "route_names": ["Naraina Industrial Area", "Connaught Place"],
      "packages": [{"id", "weight", "priority", "deadline"}],
      "has_bonus": true,
      "bonus_name": "Chandni Chowk"
    }
  ],
  "injected_customer_orders": 2
}
```

---

## `/simulate` Response Shape

```json
{
  "warehouse": 0,
  "warehouse_name": "Naraina Industrial Area",
  "destination": 7,
  "dest_name": "Delhi University",
  "planned_path": [0, 8, 15, 7],
  "final_path": [0, 8, 15, 16, 7],
  "planned_distance": 18.4,
  "traffic_event": {
    "at_node": 15,
    "at_node_name": "New Delhi Railway Station",
    "congested_edges": [{"u": 15, "v": 7, "multiplier": 3.2}],
    "original_suffix": [15, 7],
    "new_path_suffix": [15, 16, 7],
    "reroute_happened": true,
    "new_distance": 5.1
  },
  "nodes": {"0": {"name", "lat", "lng", "type"}, ...},
  "edges": [{"u", "v", "base_weight"}]
}
```

**Traffic rerouting logic:**
1. Traffic fires at `planned_path[len//2]` — guaranteed mid-journey
2. 1–3 random edges get 2.5–5.0× multipliers
3. Dijkstra reruns from `at_node` with updated multipliers
4. `final_path = travelled_nodes + new_path_suffix[1:]`

---

## Database Schema (SQLite — `delhidash.db`)

```sql
sessions        (id, created_at, total_orders, total_trips)
orders          (id, session_id, package_id, priority, deadline, weight,
                 dest_node, dest_name, status, created_at, completed_at)
trips           (id, session_id, destination, dest_node, warehouse, van,
                 load_kg, distance_km, route_nodes, route_names,
                 package_ids, has_bonus, bonus_name, completed_at)
customer_orders (id, name, phone, dest_node, dest_name, weight,
                 priority, deadline, status, created_at)
```

---

## Node Map (Delhi Network)

### Warehouses (IDs 0–4)

| ID | Name | Location |
|----|------|----------|
| 0 | Naraina Industrial Area | West Delhi |
| 1 | Okhla Industrial Estate | South Delhi |
| 2 | Patparganj Industrial Area | East Delhi |
| 3 | Mundka Industrial Area | Far West Delhi |
| 4 | Badarpur Border Depot | South-East Delhi |

### Delivery Nodes (IDs 5–19)

| ID | Name | Notes |
|----|------|-------|
| 5 | IGI Airport | |
| 6 | Chandni Chowk | |
| 7 | Delhi University | |
| 8 | Connaught Place | Central hub |
| 9 | AIIMS | |
| 10 | Select Citywalk Saket | |
| 11 | Cyberhub Gurugram | Longest edge (4,11 = 14.3 km) |
| 12 | Noida Sector 18 | |
| 13 | Lajpat Nagar | |
| 14 | Dwarka Sector 21 | |
| 15 | New Delhi Railway Station | |
| 16 | Kashmere Gate ISBT | Shortest edge (6,16 = 1.8 km) |
| 17 | Jawaharlal Nehru Stadium | |
| 18 | ITO | |
| 19 | Rohini Sector 18 | |

---

## Algorithm Complexity Summary

| Algorithm | Function | Time | Space | Where Used |
|-----------|----------|------|-------|------------|
| Quick Sort | `sort_by_weight`, Pass 1 of `sort_by_priority_then_deadline` | O(n log n) avg | O(log n) | Sorting pipeline |
| Merge Sort | `sort_by_deadline`, Pass 2 of `sort_by_priority_then_deadline` | O(n log n) | O(n) | Sorting pipeline |
| Heap Sort | `sort_by_priority` | O(n log n) | O(1) | Ops dashboard |
| Dijkstra | `dijkstra`, `find_best_warehouse` | O((V+E) log V) | O(V) | All routing |
| A* | `astar`, `find_best_warehouse_astar` | O((V+E) log V) | O(V) | Geo-guided routing |
| Bellman-Ford | `bellman_ford` | O(V×E) | O(V) | Negative-weight routes |
| Prim's MST | `prim_mst` | O(E log V) | O(V+E) | Network planning |
| 0/1 Knapsack DP | `pack_van`, `pack_van_by_priority` | O(n×C) | O(n×C) | Van packing |
| Closest Pair | `closest_delivery_node` | O(n log n) | O(n) | Bonus stop finding |
| Activity Selection | `activity_selection` | O(n log n) | O(n) | Demand filtering |
| Greedy Fit-First | `select_van` | O(k log k) | O(k) | Van selection |

*n = packages, V = nodes, E = edges, C = van capacity, k = fleet size (3)*

---

## Key Design Decisions

| Decision | Reason |
|----------|--------|
| Two-pass sort (Quick Sort then Merge Sort) | Pass 1 doesn't need stability; Pass 2 must be stable to preserve priority groups while sorting deadlines |
| Dijkstra over BFS/DFS | Weighted edges — BFS only works on unweighted graphs |
| Dijkstra over Bellman-Ford for main routing | All edge weights ≥ 0 in base graph; Bellman-Ford's O(VE) cost unnecessary |
| A* added alongside Dijkstra | Drop-in improvement when lat/lng available; doesn't change correctness |
| `pack_van_by_priority` over `pack_van` | Ensures critical (P1) packages always dispatch before minimal (P5) ones |
| `closest_delivery_node` using D&C | O(n log n) vs O(n²) brute force; correct algorithmic choice even if graph is small |
| `/simulate` picks longest-path warehouse | Ensures traffic event fires mid-journey on a meaningful route, not a 2-hop path |
| Traffic multipliers applied symmetrically | A road blocked in one direction is blocked both ways — realistic |
| `while remaining:` loop in `run_pipeline` | Handles packages that don't fit in one van trip by splitting into multiple trips |
| SQLite persistence | Sessions + trips survive server restarts; enables `/history` and `/stats` |

---

## How to Extend

### Add a new delivery node

1. Add to `NODES` in `delhi_graph.py` with a new ID, lat/lng, and `"type": "delivery"`
2. Add edges to `EDGES` list (at minimum connect it to 1–2 existing nodes)
3. `build_graph()` is called fresh on each request — no restart needed

### Switch to priority-aware packing

In `server.py → run_pipeline()`, change:
```python
# Old:
packed, leftover = pack_van(remaining_sorted, van["capacity"])
# New:
from backend.dp import pack_van_by_priority
packed, leftover = pack_van_by_priority(remaining_sorted, van["capacity"])
```

### Use A* instead of Dijkstra for routing

In `server.py → run_pipeline()`:
```python
from backend.graph import find_best_warehouse_astar
from backend.delhi_graph import NODES

node_coords = NODES  # already has lat/lng
result = find_best_warehouse_astar(graph, dest, node_coords)
```

### Add demand filtering for overloaded batches

In `server.py → run_pipeline()`, before the main loop:
```python
from backend.dp import activity_selection
if len(raw) > 50:  # only filter under extreme load
    feasible = activity_selection(raw)["selected"]
    raw = feasible
```

---

## External Dependencies

```
Flask       pip install flask
Leaflet     1.9.4 via CDN (cdnjs.cloudflare.com)
CartoDB     light tile layer (no API key needed)
Google Fonts Syne + JetBrains Mono (index.html), IBM Plex (ops.html)
```

No npm, no build step, no other Python packages.