import bpy
mesh = bpy.data.objects['Cube'].data
mesh.use_auto_smooth = True
mesh.normals_split_custom_set([(0.0, 0.0, 1.0)] * len(mesh.loops))
