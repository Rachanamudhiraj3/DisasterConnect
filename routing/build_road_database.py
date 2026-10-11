import osmnx as ox
import os

# Project root
BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

OUTPUT_DIR = os.path.join(BASE_DIR, "data", "roads")
OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    "hyderabad_drive.graphml"
)

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 60)
print("DISASTER CONNECT - LOCAL ROAD DATABASE")
print("=" * 60)

print("\nDownloading Hyderabad road network...")
print("This requires internet ONLY during this step.\n")

graph = ox.graph.graph_from_place(
    "Hyderabad, Telangana, India",
    network_type="drive",
    simplify=True
)

print("\nRoad network downloaded successfully!")

print(f"Nodes : {len(graph.nodes)}")
print(f"Edges : {len(graph.edges)}")

print("\nSaving local road network...")

ox.io.save_graphml(
    graph,
    OUTPUT_FILE
)

print("\n" + "=" * 60)
print("ROAD DATABASE CREATED SUCCESSFULLY")
print("=" * 60)

print(f"\nSaved at:")
print(OUTPUT_FILE)

print("\nThis file can now be used for offline routing.")