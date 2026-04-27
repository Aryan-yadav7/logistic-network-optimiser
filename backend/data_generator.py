import random

def generate_deliveries(n, dest_pool=None):
    """
    Generate n random delivery orders.
    dest_pool: list of valid dest node IDs. Defaults to nodes 5–34 (all delivery nodes).
    """
    if dest_pool is None:
        dest_pool = list(range(5, 35))   # 30 delivery nodes

    deliveries = []
    for i in range(n):
        delivery = {
            "package_id":  "PKG" + str(i + 1),
            "weight":      round(random.uniform(0.5, 30), 2),
            "deadline":    random.randint(1, 72),
            "priority":    random.randint(1, 5),
            "source_node": random.randint(0, 4),
            "dest_node":   random.choice(dest_pool),
        }
        deliveries.append(delivery)
    return deliveries