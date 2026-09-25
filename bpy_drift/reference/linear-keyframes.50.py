import bpy
from bpy_extras import anim_utils
cube = bpy.data.objects['Cube']
cube.location.x = 0.0
cube.keyframe_insert(data_path='location', frame=1)
cube.location.x = 5.0
cube.keyframe_insert(data_path='location', frame=24)
action = cube.animation_data.action
channelbag = anim_utils.action_get_channelbag_for_slot(action, cube.animation_data.action_slot)
for fcurve in channelbag.fcurves:
    for point in fcurve.keyframe_points:
        point.interpolation = 'LINEAR'
