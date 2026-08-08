import trimesh
import os

pole = trimesh.creation.cylinder(radius=0.15, height=4.0)
pole.apply_translation([0, 0, 2.0])
pole.visual.vertex_colors = [50, 50, 50, 255]

box = trimesh.creation.box(extents=[0.5, 0.5, 1.2])
box.apply_translation([0, 0, 4.6])
box.visual.vertex_colors = [255, 255, 255, 255] # White to take color from DeckGL

tl = trimesh.util.concatenate([pole, box])
out_path = "../../frontend/public/traffic_light.glb"
os.makedirs(os.path.dirname(out_path), exist_ok=True)
tl.export(out_path)
print("Exported traffic_light.glb")
