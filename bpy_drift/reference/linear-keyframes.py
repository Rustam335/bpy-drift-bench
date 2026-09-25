import bpy
cube = bpy.data.objects['Cube']
cube.location.x = 0.0
cube.keyframe_insert(data_path='location', frame=1)
cube.location.x = 5.0
cube.keyframe_insert(data_path='location', frame=24)
action = cube.animation_data.action
for fcurve in action.fcurves:
    for point in fcurve.keyframe_points:
        point.interpolation = 'LINEAR'
