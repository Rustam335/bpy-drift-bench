import bpy
cube = bpy.data.objects['Cube']
bevel = cube.modifiers.new('Bevel', 'BEVEL')
bevel.width = 0.1
bevel.segments = 3
subsurf = cube.modifiers.new('Subdivision', 'SUBSURF')
subsurf.levels = 2
