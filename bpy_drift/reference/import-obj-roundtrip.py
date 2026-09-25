import bpy
for o in bpy.context.scene.objects:
    o.select_set(False)
cube = bpy.data.objects['Cube']
cube.select_set(True)
bpy.context.view_layer.objects.active = cube
import os
path = os.environ['BPY_OUT_OBJ']
bpy.ops.wm.obj_export(filepath=path, export_selected_objects=True)
bpy.ops.wm.obj_import(filepath=path)
