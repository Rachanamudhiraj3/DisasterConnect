import os
import osmnx as ox
import networkx as nx

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

ROAD_FILE = os.path.join(
    BASE_DIR,
    "data",
    "roads",
    "hyderabad_drive.graphml"
)

print("=" * 60)
print("DISASTER CONNECT - OFFLINE ROUTE TEST")
print("=" * 60)

print("\nLoading local road network...")

graph = ox.io.load_graphml(ROAD_FILE)

print("Road network loaded!")
print(f"Nodes : {len(graph.nodes)}")
print(f"Edges : {len(graph.edges)}")


# Demo starting location
START_LAT = 17.4425
START_LON = 78.5280

# Demo destination / shelter
DEST_LAT = 17.3600
DEST_LON = 78.5500


print("\nFinding nearest roads...")

start_node = ox.distance.nearest_nodes(
    graph,
    X=START_LON,
    Y=START_LAT
)

destination_node = ox.distance.nearest_nodes(
    graph,
    X=DEST_LON,
    Y=DEST_LAT
)

print(f"Start node       : {start_node}")
print(f"Destination node: {destination_node}")


print("\nCalculating route using LOCAL database...")

route = nx.shortest_path(
    graph,
    start_node,
    destination_node,
    weight="length"
)

print("\nOFFLINE ROUTE FOUND!")
print(f"Number of road points: {len(route)}")


# Convert route to coordinates
coordinates = []

for node in route:

    latitude = float(graph.nodes[node]["y"])
    longitude = float(graph.nodes[node]["x"])

    coordinates.append(
        (latitude, longitude)
    )


print("\nFirst 5 route points:")

for point in coordinates[:5]:
    print(point)


# Calculate total distance
total_distance = 0

for u, v in zip(route[:-1], route[1:]):

    edge_data = graph.get_edge_data(u, v)

    if edge_data:

        # MultiDiGraph can contain multiple edges
        edge = min(
            edge_data.values(),
            key=lambda x: x.get("length", 0)
        )

        total_distance += float(
            edge.get("length", 0)
        )


print("\n" + "=" * 60)
print("ROUTE TEST SUCCESSFUL")
print("=" * 60)

print(
    f"\nRoute distance: "
    f"{total_distance / 1000:.2f} km"
)

print(
    f"Route points: "
    f"{len(coordinates)}"
)

print("\nThe route was calculated from the")
print("LOCAL Hyderabad road database.")