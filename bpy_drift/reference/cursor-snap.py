import bpy
scene = bpy.context.scene
scene.cursor.location = (1, 1, 1)
bpy.data.objects['Cube'].location = scene.cursor.location.copy()
