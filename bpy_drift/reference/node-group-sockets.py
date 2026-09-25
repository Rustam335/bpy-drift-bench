import bpy
group = bpy.data.node_groups.new('MyGroup', 'GeometryNodeTree')
group.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
group.interface.new_socket('Scale', in_out='INPUT', socket_type='NodeSocketFloat')
group.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
