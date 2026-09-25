import bpy
light = bpy.data.lights['Light']
light.use_shadow = False
light.cycles.cast_shadow = False
