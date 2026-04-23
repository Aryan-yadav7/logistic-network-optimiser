def knapsack01(deliveries, capacity, value_key="priority"):
    n = len(deliveries)
    
    # build dp table — (n+1) x (capacity+1), filled with 0
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]
    
    for i in range(1, n + 1):
        wt  = deliveries[i-1]["weight"]          # weight of deliveries[i-1]
        val = deliveries[i-1][value_key]         # value
        
        for w in range(capacity + 1):
            # option 1: skip this item
            dp[i][w] = dp[i-1][w]
            
            # option 2: take it (only if wt <= w)
            if wt <= w:
                dp[i][w] = max(dp[i][w], dp[i-1][w - wt] + val)
    
    # traceback — which items were selected?
    selected = []
    w = capacity
    for i in range(n, 0, -1):
        if dp[i][w] != dp[i-1][w]:   # this item was taken
            selected.append(deliveries[i-1])
            w -= deliveries[i-1]["weight"]   # reduce remaining capacity
    
    selected.reverse()  # optional: to keep original order
    
    return {
        "max_value": dp[n][capacity],
        "selected":  selected,
        "total_weight": sum(d["weight"] for d in selected)
    }

def pack_van(orders, capacity):
    n = len(orders)
    weights = [int(round(o["weight"])) for o in orders] 

    # Build DP table — dp[i][w] = max weight achievable
    # using first i orders with capacity w
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        w = weights[i - 1]
        for c in range(capacity + 1):
            # Don't take item i
            dp[i][c] = dp[i - 1][c]
            # Take item i — only if it fits
            if w <= c:
                take = dp[i - 1][c - w] + w
                if take > dp[i][c]:
                    dp[i][c] = take

    # Traceback — which orders were actually picked?
    packed = []
    leftover = []
    c = capacity

    for i in range(n, 0, -1):
        if dp[i][c] != dp[i - 1][c]:  # item i was taken
            packed.append(orders[i - 1])
            c -= weights[i - 1]
        else:
            leftover.append(orders[i - 1])

    return packed, leftover