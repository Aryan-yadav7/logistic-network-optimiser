import heapq

def dijkstra(graph, src, dest, traffic_multipliers=None):
    """
    Standard Dijkstra. Optionally accepts traffic_multipliers:
      { (u,v): multiplier }  — applied symmetrically to both directions.
    """
    dist = {node: float('inf') for node in graph}
    prev = {node: None for node in graph}
    dist[src] = 0
    pq = [(0, src)]

    while pq:
        curr_dist, u = heapq.heappop(pq)
        if curr_dist > dist[u]:
            continue
        if u == dest:
            break
        for v, weight in graph[u]:
            eff_weight = weight
            if traffic_multipliers:
                mult = traffic_multipliers.get((u, v)) or traffic_multipliers.get((v, u)) or 1.0
                eff_weight = weight * mult
            new_dist = dist[u] + eff_weight
            if new_dist < dist[v]:
                dist[v] = new_dist
                prev[v] = u
                heapq.heappush(pq, (dist[v], v))

    if dist[dest] == float('inf'):
        return {"distance": float('inf'), "path": []}

    path = []
    curr = dest
    while curr is not None:
        path.append(curr)
        curr = prev[curr]
    path.reverse()

    return {"distance": round(dist[dest], 2), "path": path}


def find_best_warehouse(graph, dest, traffic_multipliers=None):
    warehouses = [0, 1, 2, 3, 4]
    best_warehouse = None
    best_distance = float('inf')

    for w in warehouses:
        result = dijkstra(graph, w, dest, traffic_multipliers)
        if result["distance"] < best_distance:
            best_distance = result["distance"]
            best_warehouse = w

    if best_warehouse is None:
        raise ValueError(f"Destination node {dest} is unreachable from all warehouses")

    return {"warehouse": best_warehouse, "distance": best_distance}


def route_with_stops(graph, warehouse, stops, traffic_multipliers=None):
    if not stops:
        return {"path": [], "distance": 0}

    full_path = []
    total_dist = 0.0
    all_points = [warehouse] + stops

    for i in range(len(all_points) - 1):
        leg = dijkstra(graph, all_points[i], all_points[i + 1], traffic_multipliers)
        if leg["distance"] == float('inf'):
            return {"path": [], "distance": float('inf')}
        if i == 0:
            full_path += leg["path"]
        else:
            full_path += leg["path"][1:]
        total_dist += leg["distance"]

    return {"path": full_path, "distance": round(total_dist, 2)}


def reroute_from(graph, current_node, dest, traffic_multipliers):
    """Re-run Dijkstra from current_node to dest with updated traffic."""
    return dijkstra(graph, current_node, dest, traffic_multipliers)