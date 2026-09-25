import bpy, bmesh
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
mesh = bpy.data.meshes.new('Ico')
bm.to_mesh(mesh)
bm.free()
mesh.update()
obj = bpy.data.objects.new('Ico', mesh)
bpy.context.scene.collection.objects.link(obj)
