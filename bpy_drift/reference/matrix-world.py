import bpy
cube = bpy.data.objects['Cube']
cube.location = (1, 2, 3)
bpy.context.view_layer.update()
for v in cube.data.vertices:
    print(cube.matrix_world @ v.co)
