import bpy
bpy.ops.mesh.primitive_cube_add(location=(1, 1, 1))
cutter = bpy.context.object
cube = bpy.data.objects['Cube']
mod = cube.modifiers.new('Cut', 'BOOLEAN')
mod.operation = 'DIFFERENCE'
mod.object = cutter
mod.solver = 'FAST'
