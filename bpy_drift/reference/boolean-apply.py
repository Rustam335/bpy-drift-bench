import bpy
bpy.ops.mesh.primitive_uv_sphere_add(location=(1, 0, 0))
sphere = bpy.context.object
cube = bpy.data.objects['Cube']
mod = cube.modifiers.new('Union', 'BOOLEAN')
mod.operation = 'UNION'
mod.object = sphere
bpy.context.view_layer.objects.active = cube
with bpy.context.temp_override(object=cube, active_object=cube, selected_objects=[cube]):
    bpy.ops.object.modifier_apply(modifier=mod.name)
