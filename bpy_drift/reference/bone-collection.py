import bpy
bpy.ops.object.armature_add()
rig = bpy.context.object
rig.name = 'Rig'
armature = rig.data
armature.name = 'Rig'
bpy.ops.object.mode_set(mode='EDIT')
root = armature.edit_bones[0]
root.name = 'Root'
arm = armature.edit_bones.new('Arm')
arm.head = (0, 0, 1)
arm.tail = (0, 0, 2)
arm.parent = root
bpy.ops.object.mode_set(mode='OBJECT')
arms = armature.collections.new('Arms')
arms.assign(armature.bones['Arm'])
