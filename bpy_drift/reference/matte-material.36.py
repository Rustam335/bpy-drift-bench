import bpy
mat = bpy.data.materials.new('Matte')
mat.use_nodes = True
bsdf = mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, 1.0)
bsdf.inputs['Roughness'].default_value = 1.0
bsdf.inputs['Specular'].default_value = 0.0
cube = bpy.data.objects['Cube']
cube.data.materials.append(mat)
