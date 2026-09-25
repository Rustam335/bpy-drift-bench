import bpy
scene = bpy.context.scene
parts = bpy.data.collections.new('Parts')
scene.collection.children.link(parts)
cube = bpy.data.objects['Cube']
for col in list(cube.users_collection):
    col.objects.unlink(cube)
parts.objects.link(cube)
inst = bpy.data.objects.new('Inst', None)
inst.instance_type = 'COLLECTION'
inst.instance_collection = parts
scene.collection.objects.link(inst)
