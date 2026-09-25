import bpy
mat = bpy.data.materials.new('Glass')
mat.use_nodes = True
bsdf = mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Alpha'].default_value = 0.5
mat.blend_method = 'BLEND'
cube = bpy.data.objects['Cube']
cube.data.materials.append(mat)
