import bpy
cube = bpy.data.objects['Cube']
mod = cube.modifiers.new('Array', 'ARRAY')
mod.count = 3
mod.use_relative_offset = True
mod.relative_offset_displace = (1.5, 0.0, 0.0)
