import bpy
scene = bpy.context.scene
if scene.sequence_editor is None:
    scene.sequence_editor_create()
strip = scene.sequence_editor.strips.new_effect(name='Red', type='COLOR', channel=1, frame_start=1, length=50)
strip.color = (1.0, 0.0, 0.0)
print([s.name for s in scene.sequence_editor.strips_all])
