import bpy
bpy.ops.object.empty_add(location=(2, 0, 0))
empty = bpy.context.object
cube = bpy.data.objects['Cube']
cube.parent = empty
cube.location = (0, 0, 1)
bpy.context.view_layer.update()
print(cube.matrix_world.translation)
