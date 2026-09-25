import bpy
mesh = bpy.data.meshes.new('Quad')
mesh.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [], [(0, 1, 2, 3)])
mesh.update()
mesh.validate()
obj = bpy.data.objects.new('Quad', mesh)
bpy.context.scene.collection.objects.link(obj)
for poly in mesh.polygons:
    print(poly.index, tuple(poly.normal))
