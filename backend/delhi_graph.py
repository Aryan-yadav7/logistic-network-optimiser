NODES = {
    0:  {"name": "Naraina Industrial Area",     "lat": 28.6419, "lng": 77.1397, "type": "warehouse"},
    1:  {"name": "Okhla Industrial Estate",     "lat": 28.5355, "lng": 77.2720, "type": "warehouse"},
    2:  {"name": "Patparganj Industrial Area",  "lat": 28.6254, "lng": 77.3021, "type": "warehouse"},
    3:  {"name": "Mundka Industrial Area",      "lat": 28.6825, "lng": 77.0321, "type": "warehouse"},
    4:  {"name": "Badarpur Border Depot",       "lat": 28.5013, "lng": 77.2989, "type": "warehouse"},
    5:  {"name": "IGI Airport",                 "lat": 28.5562, "lng": 77.1000, "type": "delivery"},
    6:  {"name": "Chandni Chowk",               "lat": 28.6505, "lng": 77.2303, "type": "delivery"},
    7:  {"name": "Delhi University",            "lat": 28.6900, "lng": 77.2127, "type": "delivery"},
    8:  {"name": "Connaught Place",             "lat": 28.6315, "lng": 77.2167, "type": "delivery"},
    9:  {"name": "AIIMS",                       "lat": 28.5672, "lng": 77.2100, "type": "delivery"},
    10: {"name": "Select Citywalk Saket",       "lat": 28.5274, "lng": 77.2190, "type": "delivery"},
    11: {"name": "Cyberhub Gurugram",           "lat": 28.4950, "lng": 77.0890, "type": "delivery"},
    12: {"name": "Noida Sector 18",             "lat": 28.5706, "lng": 77.3219, "type": "delivery"},
    13: {"name": "Lajpat Nagar",                "lat": 28.5700, "lng": 77.2433, "type": "delivery"},
    14: {"name": "Dwarka Sector 21",            "lat": 28.5523, "lng": 77.0587, "type": "delivery"},
    15: {"name": "New Delhi Railway Station",   "lat": 28.6431, "lng": 77.2194, "type": "delivery"},
    16: {"name": "Kashmere Gate ISBT",          "lat": 28.6671, "lng": 77.2286, "type": "delivery"},
    17: {"name": "Jawaharlal Nehru Stadium",    "lat": 28.5664, "lng": 77.2431, "type": "delivery"},
    18: {"name": "ITO",                         "lat": 28.6289, "lng": 77.2446, "type": "delivery"},
    19: {"name": "Rohini Sector 18",            "lat": 28.7374, "lng": 77.1333, "type": "delivery"},
}

EDGES = [
    # Naraina (0) — west-central warehouse
    (0, 8,  6.2),   # Naraina → Connaught Place
    (0, 5,  8.1),   # Naraina → IGI Airport
    (0, 9,  9.3),   # Naraina → AIIMS
    (0, 15, 6.8),   # Naraina → New Delhi Railway Station

    # Okhla (1) — south warehouse
    (1, 4,  7.2),   # Okhla → Badarpur
    (1, 10, 5.1),   # Okhla → Saket
    (1, 13, 4.8),   # Okhla → Lajpat Nagar
    (1, 12, 8.9),   # Okhla → Noida Sector 18

    # Patparganj (2) — east warehouse
    (2, 12, 6.4),   # Patparganj → Noida Sector 18
    (2, 18, 7.1),   # Patparganj → ITO
    (2, 6,  9.8),   # Patparganj → Chandni Chowk

    # Mundka (3) — northwest warehouse
    (3, 19, 9.4),   # Mundka → Rohini
    (3, 14, 11.2),  # Mundka → Dwarka
    (3, 7,  13.5),  # Mundka → Delhi University

    # Badarpur (4) — south warehouse
    (4, 11, 14.3),  # Badarpur → Cyberhub
    (4, 10, 6.9),   # Badarpur → Saket
    (4, 17, 8.2),   # Badarpur → JN Stadium

    # Delivery point interconnections
    (5,  14, 7.3),  # IGI Airport → Dwarka
    (5,  11, 9.8),  # IGI Airport → Cyberhub
    (6,  16, 1.8),  # Chandni Chowk → Kashmere Gate (very close)
    (6,  15, 2.4),  # Chandni Chowk → New Delhi Railway Station
    (6,  7,  4.2),  # Chandni Chowk → Delhi University
    (7,  19, 8.1),  # Delhi University → Rohini
    (7,  16, 4.6),  # Delhi University → Kashmere Gate
    (8,  15, 1.9),  # Connaught Place → New Delhi Railway Station
    (8,  9,  6.5),  # Connaught Place → AIIMS
    (8,  18, 4.3),  # Connaught Place → ITO
    (9,  10, 4.1),  # AIIMS → Saket
    (9,  17, 3.8),  # AIIMS → JN Stadium
    (10, 13, 3.2),  # Saket → Lajpat Nagar
    (11, 14, 4.5),  # Cyberhub → Dwarka
    (12, 13, 7.6),  # Noida → Lajpat Nagar
    (13, 17, 2.9),  # Lajpat Nagar → JN Stadium
    (15, 16, 3.1),  # New Delhi RS → Kashmere Gate
    (16, 19, 11.2), # Kashmere Gate → Rohini
    (17, 18, 4.7),  # JN Stadium → ITO
    (18, 6,  3.9),  # ITO → Chandni Chowk
]

def build_graph():
    graph = {i: [] for i in range(20)}
    for u, v, w in EDGES:
        graph[u].append((v, w))
        graph[v].append((u, w))  # undirected
    return graph