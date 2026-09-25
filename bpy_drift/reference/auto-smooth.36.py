import bpy, math
mesh = bpy.data.objects['Cube'].data
for poly in mesh.polygons:
    poly.use_smooth = True
mesh.use_auto_smooth = True
mesh.auto_smooth_angle = math.radians(30)
