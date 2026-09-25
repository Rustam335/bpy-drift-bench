import bpy
mat = bpy.data.materials.new('Skin')
mat.use_nodes = True
bsdf = mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.8, 0.5, 0.4, 1.0)
bsdf.inputs['Subsurface'].default_value = 0.3
bsdf.inputs['Subsurface Color'].default_value = (0.9, 0.3, 0.2, 1.0)
cube = bpy.data.objects['Cube']
cube.data.materials.append(mat)
