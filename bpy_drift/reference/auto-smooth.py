import bpy
for o in bpy.context.scene.objects:
    o.select_set(False)
cube = bpy.data.objects['Cube']
cube.select_set(True)
bpy.context.view_layer.objects.active = cube
import math
bpy.ops.object.shade_smooth_by_angle(angle=math.radians(30))
