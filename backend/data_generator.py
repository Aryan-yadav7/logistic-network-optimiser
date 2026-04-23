import random

def generate_deliveries(n):
    deliveries = []

    for i in range(n):
        delivery = {
            "package_id": "PKG" + str(i+1),
            "weight":     round(random.uniform(0, 50), 2),
            "deadline":   random.randint(1, 72),
            "priority":   random.randint(1, 5),
            "distance":   round(random.uniform(1, 500), 2),
            "source_node": random.randint(0, 4),   # warehouses 0-4
            "dest_node":   random.randint(5, 19),   
        }
        deliveries.append(delivery)

    return deliveries