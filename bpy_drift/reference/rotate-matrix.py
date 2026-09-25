import bpy, math
from mathutils import Matrix
cube = bpy.data.objects['Cube']
rotation = Matrix.Rotation(math.radians(90), 4, 'Z')
cube.matrix_world = rotation @ cube.matrix_world
