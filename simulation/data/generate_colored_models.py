import trimesh
import os

out_dir = "../../frontend/public"
os.makedirs(out_dir, exist_ok=True)

def make_box(extents, pos, color):
    m = trimesh.creation.box(extents=extents)
    m.apply_translation(pos)
    m.visual.vertex_colors = color
    return m

def make_cyl(radius, height, pos, color):
    m = trimesh.creation.cylinder(radius=radius, height=height)
    m.apply_translation(pos)
    m.visual.vertex_colors = color
    return m

def make_sphere(radius, pos, color):
    m = trimesh.creation.icosphere(subdivisions=2, radius=radius)
    m.apply_translation(pos)
    m.visual.vertex_colors = color
    return m

# CAR MODEL (Crimson Red Sedan)
car_body = make_box([1.8, 4.5, 0.8], [0, 0, 0.4], [220, 30, 30, 255])
car_roof = make_box([1.6, 2.5, 0.7], [0, -0.3, 1.15], [40, 40, 40, 255])
car = trimesh.util.concatenate([car_body, car_roof])
car.export(os.path.join(out_dir, "car.glb"))

# BUS MODEL (Schoolbus Yellow)
bus_body = make_box([2.5, 12.0, 3.2], [0, 0, 1.6], [250, 210, 20, 255])
bus_windows = make_box([2.6, 11.5, 1.2], [0, 0, 1.8], [20, 20, 20, 255])
bus = trimesh.util.concatenate([bus_body, bus_windows])
bus.export(os.path.join(out_dir, "bus.glb"))

# PEDESTRIAN MODEL (Detailed Stick Figure)
torso = make_box([0.4, 0.2, 0.7], [0, 0, 1.05], [30, 120, 240, 255])
head = make_sphere(0.15, [0, 0, 1.55], [255, 200, 150, 255])
leg1 = make_cyl(0.08, 0.7, [0.1, 0, 0.35], [40, 40, 40, 255])
leg2 = make_cyl(0.08, 0.7, [-0.1, 0, 0.35], [40, 40, 40, 255])
ped = trimesh.util.concatenate([torso, head, leg1, leg2])
ped.export(os.path.join(out_dir, "person.glb"))

# TRAFFIC LIGHT MODEL
pole = make_cyl(0.1, 4.0, [0, 0, 2.0], [50, 50, 50, 255])
box = make_box([0.5, 0.5, 1.5], [0, 0, 4.75], [20, 20, 20, 255])

def make_bulb(pos):
    b = trimesh.creation.cylinder(radius=0.15, height=0.1)
    b.apply_transform(trimesh.transformations.rotation_matrix(1.5708, [1, 0, 0])) # Rotate FIRST
    b.apply_translation(pos) # Translate SECOND
    b.visual.vertex_colors = [255, 255, 255, 255]
    return b

bulb1 = make_bulb([0, 0.26, 5.2])
bulb2 = make_bulb([0, 0.26, 4.75])
bulb3 = make_bulb([0, 0.26, 4.3])

tl = trimesh.util.concatenate([pole, box, bulb1, bulb2, bulb3])
tl.export(os.path.join(out_dir, "traffic_light.glb"))

print("Exported baked single-mesh GLB models with vertex colors!")
