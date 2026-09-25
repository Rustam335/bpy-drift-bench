import bpy
group = bpy.data.node_groups.new('MyGroup', 'GeometryNodeTree')
group.inputs.new('NodeSocketGeometry', 'Geometry')
group.inputs.new('NodeSocketFloat', 'Scale')
group.outputs.new('NodeSocketGeometry', 'Geometry')
