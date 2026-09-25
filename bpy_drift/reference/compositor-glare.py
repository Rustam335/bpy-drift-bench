import bpy
scene = bpy.context.scene
scene.use_nodes = True
tree = scene.node_tree
render_layers = next(n for n in tree.nodes if n.type == 'R_LAYERS')
composite = next(n for n in tree.nodes if n.type == 'COMPOSITE')
glare = tree.nodes.new('CompositorNodeGlare')
for link in list(tree.links):
    if link.to_node == composite and link.to_socket.name == 'Image':
        tree.links.remove(link)
tree.links.new(render_layers.outputs['Image'], glare.inputs['Image'])
tree.links.new(glare.outputs['Image'], composite.inputs['Image'])
