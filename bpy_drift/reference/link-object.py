import bpy
mesh = bpy.data.meshes.new('Tri')
mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
mesh.update()
obj = bpy.data.objects.new('Tri', mesh)
bpy.context.scene.collection.objects.link(obj)
