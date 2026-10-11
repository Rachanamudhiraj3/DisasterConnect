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


# Load once when the server starts
print("Loading local Hyderabad road network...")

ROAD_GRAPH = ox.io.load_graphml(ROAD_FILE)

print(
    f"Local road network loaded: "
    f"{len(ROAD_GRAPH.nodes)} nodes, "
    f"{len(ROAD_GRAPH.edges)} edges"
)


def find_route(
    start_lat: float,
    start_lon: float,
    destination_lat: float,
    destination_lon: float,
):
    """Calculate a route using only the local road database."""

    start_node = ox.distance.nearest_nodes(
        ROAD_GRAPH,
        X=start_lon,
        Y=start_lat,
    )

    destination_node = ox.distance.nearest_nodes(
        ROAD_GRAPH,
        X=destination_lon,
        Y=destination_lat,
    )

    route = nx.shortest_path(
        ROAD_GRAPH,
        start_node,
        destination_node,
        weight="length",
    )

    coordinates = []

    for node in route:
        coordinates.append({
            "lat": float(ROAD_GRAPH.nodes[node]["y"]),
            "lon": float(ROAD_GRAPH.nodes[node]["x"]),
        })

    # Calculate total distance
    distance_m = 0.0

    for u, v in zip(route[:-1], route[1:]):
        edge_data = ROAD_GRAPH.get_edge_data(u, v)

        if edge_data:
            edge = min(
                edge_data.values(),
                key=lambda x: x.get("length", 0)
            )

            distance_m += float(
                edge.get("length", 0)
            )

    return {
        "route": coordinates,
        "distance_km": round(distance_m / 1000, 2),
        "points": len(coordinates),
        "offline": True,
    }