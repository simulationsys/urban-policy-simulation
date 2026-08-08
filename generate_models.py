import trimesh
import numpy as np

# 1. Generate Low-Poly Tree
trunk = trimesh.creation.cylinder(radius=0.4, height=3.0)
trunk.visual.vertex_colors = [101, 67, 33, 255]
trunk.apply_translation([0, 0, 1.5])

leaves = trimesh.creation.icosphere(subdivisions=2, radius=2.5)
leaves.visual.vertex_colors = [34, 139, 34, 255]
leaves.apply_translation([0, 0, 4.0])

tree = trimesh.util.concatenate([trunk, leaves])
tree.export('frontend/public/tree.glb')

# 2. Generate Sleek Sedan Car
chassis = trimesh.creation.box(extents=[4.0, 1.7, 0.5])
chassis.visual.vertex_colors = [200, 200, 210, 255] # Silver car
chassis.apply_translation([0, 0, 0.5])

cabin = trimesh.creation.box(extents=[2.0, 1.5, 0.5])
cabin.visual.vertex_colors = [30, 30, 30, 255] # Tinted windows
cabin.apply_translation([-0.2, 0, 1.0])

wheels = []
for x in [-1.3, 1.3]:
    for y in [-0.9, 0.9]:
        wheel = trimesh.creation.cylinder(radius=0.25, height=0.3)
        matrix = trimesh.transformations.rotation_matrix(np.pi/2, [1, 0, 0])
        wheel.apply_transform(matrix)
        wheel.visual.vertex_colors = [10, 10, 10, 255]
        wheel.apply_translation([x, y, 0.25])
        wheels.append(wheel)

car = trimesh.util.concatenate([chassis, cabin] + wheels)
car.export('frontend/public/car.glb')

# 3. Generate Realistic Bus
bus_chassis = trimesh.creation.box(extents=[12.0, 2.4, 3.2])
bus_chassis.visual.vertex_colors = [34, 197, 94, 255] # Green city bus
bus_chassis.apply_translation([0, 0, 1.9])

bus_windows = trimesh.creation.box(extents=[11.8, 2.5, 1.2])
bus_windows.visual.vertex_colors = [20, 20, 20, 255]
bus_windows.apply_translation([0, 0, 2.4])

wheels_bus = []
for x in [-4.0, 4.0]:
    for y in [-1.2, 1.2]:
        wheel = trimesh.creation.cylinder(radius=0.4, height=0.4)
        matrix = trimesh.transformations.rotation_matrix(np.pi/2, [1, 0, 0])
        wheel.apply_transform(matrix)
        wheel.visual.vertex_colors = [10, 10, 10, 255]
        wheel.apply_translation([x, y, 0.4])
        wheels_bus.append(wheel)

bus = trimesh.util.concatenate([bus_chassis, bus_windows] + wheels_bus)
bus.export('frontend/public/bus.glb')

print("Models generated successfully!")
