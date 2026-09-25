import bpy
scene = bpy.context.scene
tree = scene.compositing_node_group
if tree is None:
    tree = bpy.data.node_groups.new('Compositing', 'CompositorNodeTree')
    scene.compositing_node_group = tree
if not any(i.item_type == 'SOCKET' and i.in_out == 'OUTPUT' for i in tree.interface.items_tree):
    tree.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
render_layers = next((n for n in tree.nodes if n.type == 'R_LAYERS'), None) or tree.nodes.new('CompositorNodeRLayers')
output = next((n for n in tree.nodes if n.type == 'GROUP_OUTPUT'), None) or tree.nodes.new('NodeGroupOutput')
glare = tree.nodes.new('CompositorNodeGlare')
for link in list(tree.links):
    if link.to_node == output and link.to_socket.name == 'Image':
        tree.links.remove(link)
tree.links.new(render_layers.outputs['Image'], glare.inputs['Image'])
tree.links.new(glare.outputs['Image'], output.inputs['Image'])
