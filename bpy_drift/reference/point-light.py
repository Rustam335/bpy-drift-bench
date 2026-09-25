import bpy
light_data = bpy.data.lights.new('Key', type='POINT')
light_data.energy = 1000.0
light_data.color = (1.0, 0.9, 0.8)
light = bpy.data.objects.new('Key', light_data)
light.location = (4, -4, 6)
bpy.context.scene.collection.objects.link(light)
