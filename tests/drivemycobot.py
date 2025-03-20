# https://github.com/elephantrobotics/pymycobot
# pip_install('pymycobot --upgrade')
from pymycobot.mycobot280 import MyCobot280 as MyCobot
import time

mc = MyCobot('COM5',115200)

mc.send_angles([0,0,0,0,0,0],20)


mc.send_angles([8.08, -28.12, -135.26, 76.11, 4.48, 61.17],5)
mc.send_angles([52, -28.12, -135.26, 76.11, 4.48, 72],5)









#mc.send_angles([0,0,0,0,0,0],20)

mc.send_coords([150, 0, 80, 175, 0, -45], 10, 1)
mc.send_coords([210, 0, 80, 175, 0, -45], 10, 1)
mc.send_coords([280, 0, 80, 175, 0, -45], 10, 1)

# Good, side to side
mc.send_coords([200, -60, 80, 175, 0, 45], 10, 1)
mc.send_coords([200, 60, 80, 175, 0, 45], 10, 1)


# for count in range(5):
#   time.sleep(5)
#   mc.send_angles([0,(-80.24),7.73,(-9.4),(-1.93),132.24],20)
#   time.sleep(5)
#   mc.send_angles([(-0.43),(-47.81),(-71.27),30,(-2.81),132.24],20)
#   time.sleep(5)
#   mc.send_angles([0.96,(-1.58),(-133.68),46.88,(-0.79),132.24],20)

slicer.angles = (
    [0,0,0,0,0,0],
    [0,(-80.24),7.73,(-9.4),(-1.93),132.24],
    [(-0.43),(-47.81),(-71.27),30,(-2.81),132.24],
    [0.96,(-1.58),(-133.68),46.88,(-0.79),132.24],
)

def moveRobot():
    angles = slicer.angles[slicer.angleIndex]
    mc.send_angles(angles, 20)
    slicer.angleIndex = slicer.angleIndex + 1
    if slicer.angleIndex > len(slicer.angles):
        qt.QTimer.singleShot(5000, moveRobot)

slicer.angleIndex = 0
moveRobot()


def updateProbeToRobotBaseTransform():
    probeToRobotBaseTransform = slicer.mrmlScene.GetFirstNodeByName("ProbeToRobotBase")
    if not probeToRobotBaseTransform:
        probeToRobotBaseTransform = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode", "ProbeToRobotBase")
    angles = mc.get_angles()
    position = mc.angles_to_coords(angles)
    #transform = vtk.vtkTransform()
    #transform.Translate(position[0], position[1], position[2])
    #probeToRobotBaseTransform.SetMatrixTransformToParent(transform.GetMatrix())
    matrix = vtk.vtkMatrix4x4()
    matrix.SetElement(0, 3, position[0])
    matrix.SetElement(1, 3, position[1])
    matrix.SetElement(2, 3, position[2])
    probeToRobotBaseTransform.SetMatrixTransformToParent(matrix)
    probeToRobotBaseTransform.Modified()
    slicer.app.processEvents()
    if slicer.updateProbeToRobotBaseTransformActive:
        qt.QTimer.singleShot(100, updateProbeToRobotBaseTransform)


slicer.updateProbeToRobotBaseTransformActive = True
updateProbeToRobotBaseTransform()

slicer.updateProbeToRobotBaseTransformActive = False
