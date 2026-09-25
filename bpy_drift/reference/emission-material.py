import bpy
mat = bpy.data.materials.new('Glow')
mat.use_nodes = True
bsdf = mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Emission Color'].default_value = (1.0, 0.4, 0.0, 1.0)
bsdf.inputs['Emission Strength'].default_value = 5.0
cube = bpy.data.objects['Cube']
cube.data.materials.append(mat)
