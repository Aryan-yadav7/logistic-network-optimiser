import heapq

def dijkstra(graph, src, dest):
    dist = {}          # dist[node] = shortest distance from src
    prev = {}          # prev[node] = which node we came from (for path)
    
    # initialise all distances to infinity
    for node in graph:
        dist[node] = float('inf')
        prev[node] = None
    
    # set dist[src] = 0
    dist[src] = 0
    
    pq = [(0, src)]    # (distance, node)
    
    while pq:
        curr_dist, u = heapq.heappop(pq)
        
        # if curr_dist > dist[u], we already found better — skip
        if curr_dist > dist[u]:
            continue
        
        # if u == dest, we're done — break
        if u == dest:
            break
        
        for v, weight in graph[u]:
            # relax edge u → v
            if dist[u] + weight < dist[v]:
                dist[v] = dist[u] + weight
                prev[v] = u
                heapq.heappush(pq, (dist[v], v))
    
    # reconstruct path using prev[]
    path = []
    curr = dest
    
    if dist[dest] == float('inf'):
        return {"distance": float('inf'), "path": []}
    
    while curr is not None:
        path.append(curr)
        curr = prev[curr]
    
    path.reverse()
    
    return {"distance": dist[dest], "path": path}

def find_best_warehouse(graph, dest):
    warehouses = [0, 1, 2, 3, 4]
    best_warehouse = None
    best_distance = float('inf')

    for w in warehouses:
        result = dijkstra(graph, w, dest)
        if result["distance"] < best_distance:
            best_distance = result["distance"]
            best_warehouse = w

    if best_warehouse is None:
        raise ValueError(f"Destination node {dest} is unreachable from all warehouses")

    return {"warehouse": best_warehouse, "distance": best_distance}


def route_with_stops(graph, warehouse, stops):
    if not stops:
        return {"path": [], "distance": 0}
    
    full_path = []
    total_dist = 0

    all_points = [warehouse] + stops

    for i in range(len(all_points)-1):
        src = all_points[i]
        dest = all_points[i+1]

        leg = dijkstra(graph,src, dest)

        if leg["distance"] == float('inf'):
            return {"path": [], "distance": float('inf')}
        
        if i == 0:
            full_path += leg["path"]
        else:
            full_path += leg["path"][1:] #taking care of duplicates

        total_dist += leg["distance"]

    return{'path': full_path, "distance": round(total_dist, 2)}
