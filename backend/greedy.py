def fractional_knapsack(deliveries, capacity, value_key="priority"):
    # sort by value/weight ratio descending
    items = sorted(deliveries, key=lambda x: x[value_key] / x["weight"], reverse=True)
    
    total_value = 0.0
    total_weight = 0.0
    selected = []       # {"package": delivery, "fraction": 0.0-1.0}
    remaining = capacity
    
    for item in items:
        if remaining <= 0:
            break
        
        wt = item["weight"]
        val = item[value_key]
        
        if wt <= remaining:
            # take whole item
            selected.append({"package": item, "fraction": 1.0})
            remaining -= wt
            total_value += val
            total_weight += wt
        else:
            # take fraction
            fraction = remaining / wt   # how much of item fits
            selected.append({"package": item, "fraction": fraction})
            total_value += val * fraction
            total_weight += wt * fraction
            remaining = 0   # bag is full
    
    return {
        "max_value":    round(total_value, 2),
        "total_weight": round(total_weight, 2),
        "selected":     selected
    }


def activity_selection(deliveries):
    # sort by deadline ascending
    items = sorted(deliveries, key=lambda x: x["deadline"])
    
    selected = []
    current_time = 0
    
    for item in items:
        # if this delivery's deadline > current_time, we can fit it
        if item["deadline"] > current_time:
            selected.append(item)
            current_time += 1    # each delivery takes 1 time unit
    
    return {
        "selected": selected,
        "count":    len(selected)
    }

def select_van(fleet, total_weight):
    # Sort by capacity ascending
    sorted_fleet = sorted(fleet, key=lambda v: v["capacity"])

    for van in sorted_fleet:
        if van["capacity"] >= total_weight:
            return van 

    # Nothing fits → return largest van
    return sorted_fleet[-1]