import copy
import logging
import os
from typing import Annotated, Optional

import qt
import vtk

import slicer
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from slicer.parameterNodeWrapper import (
    parameterNodeWrapper,
    WithinRange,
)

from slicer import vtkMRMLScalarVolumeNode


#
# RobotUltrasound
#


class RobotUltrasound(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("Robot Ultrasound")
        self.parent.categories = [translate("qSlicerAbstractCoreModule", "IGT")]
        self.parent.dependencies = []
        self.parent.contributors = ["Nora Lasso (Skeleton Crew)"]
        # TODO: update with short description of the module and a link to online module documentation
        # _() function marks text as translatable to other languages
        self.parent.helpText = _("""
This is an example of scripted loadable module bundled in an extension.
See more information in <a href="https://github.com/organization/projectname#RobotUltrasound">module documentation</a>.
""")
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = _("""
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc., Andras Lasso, PerkLab,
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
""")


#
# RobotUltrasoundParameterNode
#


@parameterNodeWrapper
class RobotUltrasoundParameterNode:
    """
    The parameters needed by module.

    inputVolume - The volume to threshold.
    imageThreshold - The value at which to threshold the input volume.
    invertThreshold - If true, will invert the threshold.
    thresholdedVolume - The output volume that will contain the thresholded volume.
    invertedVolume - The output volume that will contain the inverted thresholded volume.
    """

    inputVolume: vtkMRMLScalarVolumeNode
    imageThreshold: Annotated[float, WithinRange(-100, 500)] = 100
    speed: Annotated[float, WithinRange(1, 50)] = 5
    angleRange: Annotated[float, WithinRange(0, 90)] = 30
    invertThreshold: bool = False
    thresholdedVolume: vtkMRMLScalarVolumeNode
    invertedVolume: vtkMRMLScalarVolumeNode
    centerAngles: list[float]
    liveUpdates: bool = True

#
# RobotUltrasoundWidget
#


class RobotUltrasoundWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.logic = None
        self._parameterNode = None
        self._parameterNodeGuiTag = None
        self._defaultCenterAngles = [0, -28, -135, 76, 5, 45]

    def setup(self) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.setup(self)

        # Load widget from .ui file (created by Qt Designer).
        # Additional widgets can be instantiated manually and added to self.layout.
        uiWidget = slicer.util.loadUI(self.resourcePath("UI/RobotUltrasound.ui"))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

        # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
        # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
        # "setMRMLScene(vtkMRMLScene*)" slot.
        uiWidget.setMRMLScene(slicer.mrmlScene)

        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.
        self.logic = RobotUltrasoundLogic()

        # Connections

        # These connections ensure that we update parameter node when scene is closed
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        # Buttons
        self.ui.connectButton.connect("clicked(bool)", self.onConnectButton)
        self.ui.disconnectButton.connect("clicked(bool)", self.onDisconnectButton)
        self.ui.homeButton.connect("clicked(bool)", self.onHomeButton)
        self.ui.stopButton.connect("clicked(bool)", self.onStopButton)
        self.ui.relaxButton.connect("clicked(bool)", self.onRelaxButton)

        self.ui.setAsCenterButton.connect("clicked(bool)", self.onSetAsCenterButton)
        self.ui.setCenterManuallyButton.connect("clicked(bool)", self.onSetCenterManuallyButton)
        self.ui.resetCenterToDefaultButton.connect("clicked(bool)", self.onResetCenterToDefaultButton)
        self.ui.startButton.connect("clicked(bool)", self.onStartButton)
        self.ui.centerButton.connect("clicked(bool)", self.onCenterButton)
        self.ui.endButton.connect("clicked(bool)", self.onEndButton)
        self.ui.flyButton.connect("clicked(bool)", self.onFlyButton)
        self.ui.landButton.connect("clicked(bool)", self.onLandButton)

        self.ui.resetVolumeReconstructionButton.connect("clicked(bool)", self.onResetVolumeReconstructionButton)
        self.ui.startVolumeReconstructionButton.connect("clicked(bool)", self.onStartVolumeReconstructionButton)
        self.ui.stopVolumeReconstructionButton.connect("clicked(bool)", self.onStopVolumeReconstructionButton)

        # Make sure parameter node is initialized (needed for module reload)
        self.initializeParameterNode()

        slicer.updateProbeHolderToRobotBaseTransformActive = False

        if not self._parameterNode.centerAngles:
            self._parameterNode.centerAngles = copy.copy(self._defaultCenterAngles)

        if hasattr(slicer, 'mc') and slicer.mc:
            self.onConnectButton()

    def cleanup(self) -> None:
        """Called when the application closes and the module widget is destroyed."""
        self.removeObservers()
        slicer.updateProbeHolderToRobotBaseTransformActive = False

    def enter(self) -> None:
        """Called each time the user opens this module."""
        # Make sure parameter node exists and observed
        self.initializeParameterNode()

    def exit(self) -> None:
        """Called each time the user opens a different module."""
        # Do not react to parameter node changes (GUI will be updated when the user enters into the module)
        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self._parameterNodeGuiTag = None
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._parameterNodeModified)

    def onSceneStartClose(self, caller, event) -> None:
        """Called just before the scene is closed."""
        # Parameter node will be reset, do not use it anymore
        self.setParameterNode(None)

    def onSceneEndClose(self, caller, event) -> None:
        """Called just after the scene is closed."""
        # If this module is shown while the scene is closed then recreate a new parameter node immediately
        if self.parent.isEntered:
            self.initializeParameterNode()

    def initializeParameterNode(self) -> None:
        """Ensure parameter node exists and observed."""
        # Parameter node stores all user choices in parameter values, node selections, etc.
        # so that when the scene is saved and reloaded, these settings are restored.

        self.setParameterNode(self.logic.getParameterNode())

        # Select default input nodes if nothing is selected yet to save a few clicks for the user
        if not self._parameterNode.inputVolume:
            firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
            if firstVolumeNode:
                self._parameterNode.inputVolume = firstVolumeNode

    def setParameterNode(self, inputParameterNode: Optional[RobotUltrasoundParameterNode]) -> None:
        """
        Set and observe parameter node.
        Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
        """

        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._parameterNodeModified)
        self._parameterNode = inputParameterNode
        if self._parameterNode:
            # Note: in the .ui file, a Qt dynamic property called "SlicerParameterName" is set on each
            # ui element that needs connection.
            self._parameterNodeGuiTag = self._parameterNode.connectGui(self.ui)
            self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._parameterNodeModified)
            self._parameterNodeModified()

    def _parameterNodeModified(self, caller=None, event=None) -> None:
        pass

    def onConnectButton(self) -> None:
        self.ui.connectionStatusLabel.text = "<font color='yellow'>Status: Connecting...</font>"
        self.ui.connectionStatusLabel.toolTip = ""
        slicer.app.processEvents()
        try:
            from pymycobot.mycobot280 import MyCobot280 as MyCobot
            if not hasattr(slicer, 'mc') or not slicer.mc:
                slicer.mc = MyCobot('COM5',115200)
            version = slicer.mc.get_system_version()
            # green text
            self.ui.connectionStatusLabel.text = "<font color='green'>Status: Connected.</font>"
            self.ui.connectionStatusLabel.toolTip = f"System version: {version}"

            # Start robot position updates
            slicer.updateProbeHolderToRobotBaseTransformActive = True
            self.updateProbeHolderToRobotBaseTransform()

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.ui.connectionStatusLabel.text = f"<font color='red'>Status: Connection failed.</font>"
            self.ui.connectionStatusLabel.toolTip = str(e)
            slicer.mc = None

    def onDisconnectButton(self) -> None:
        if hasattr(slicer, 'mc') and slicer.mc:
            slicer.mc.close()
        slicer.mc = None
        slicer.updateProbeHolderToRobotBaseTransformActive = False
        self.ui.connectionStatusLabel.text = "<font color='gray'>Status: Disconnected.</font>"
        self.ui.connectionStatusLabel.toolTip = ""

    def onHomeButton(self):
        slicer.mc.send_angles([0, 0, 0, 0, 0, 0],15)

    def onStopButton(self):
        slicer.mc.stop()

    def onSetAsCenterButton(self):
        self._parameterNode.centerAngles = copy.copy(slicer.mc.get_angles())

    def onResetCenterToDefaultButton(self):
        self._parameterNode.centerAngles = copy.copy(self._defaultCenterAngles)
        self.onCenterButton()

    def _moveByAngle(self, angle, waitToArrive=False, speed=None):
        angles = copy.copy(list(self._parameterNode.centerAngles))
        angles[0] = angles[0] + angle
        angles[5] = angles[5] + angle
        if speed is None:
            speed = int(self.ui.speedSlider.value)
        if waitToArrive:
            slicer.mc.sync_send_angles(angles, speed)
        else:
            slicer.mc.send_angles(angles, speed)

    def onStartButton(self, waitToArrive=False, speed=None):
        self._moveByAngle(-self.ui.angleRangeSlider.value / 2, waitToArrive, speed)

    def onCenterButton(self, waitToArrive=False, speed=None):
        self._moveByAngle(0, waitToArrive, speed)

    def onEndButton(self, waitToArrive=False, speed=None):
        self._moveByAngle(self.ui.angleRangeSlider.value / 2, waitToArrive, speed)

    def onRelaxButton(self):
        # wait 3 seconds, to give time the user to get hold of the robot
        slicer.util.delayDisplay("Relax the arm in 3 seconds...", 3000)
        slicer.mc.release_all_servos()

    def onSetCenterManuallyButton(self):
        # wait 3 seconds, to give time the user to get hold of the robot
        slicer.util.delayDisplay("Relax the arm in 3 seconds...", 3000)
        slicer.mc.release_all_servos()
        slicer.util.delayDisplay("Position the arm for 5 seconds...", 5000)
        slicer.mc.focus_all_servos()
        slicer.util.delayDisplay("Arm position is locked", 2000)

    def onFlyButton(self):
        angles = slicer.mc.get_angles()
        coords = slicer.mc.angles_to_coords(angles)
        coords[2] = coords[2] + 5
        slicer.mc.send_coords(coords, 10, 0)

    def onLandButton(self):
        angles = slicer.mc.get_angles()
        coords = slicer.mc.angles_to_coords(angles)
        coords[2] = coords[2] - 5
        slicer.mc.send_coords(coords, 10, 0)

    def updateProbeHolderToRobotBaseTransform(self):
        if not hasattr(slicer, 'mc') or not slicer.mc or not slicer.mc.is_controller_connected():
            if slicer.updateProbeHolderToRobotBaseTransformActive:
                qt.QTimer.singleShot(1000, updateProbeHolderToRobotBaseTransform)
        probeHolderToRobotBaseTransform = slicer.mrmlScene.GetFirstNodeByName("ProbeHolderToRobotBase")
        if not probeHolderToRobotBaseTransform:
            probeHolderToRobotBaseTransform = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTransformNode", "ProbeHolderToRobotBase")
        angles = slicer.mc.get_angles()
        position = slicer.mc.angles_to_coords(angles)
        #transform = vtk.vtkTransform()
        #transform.Translate(position[0], position[1], position[2])
        #probeHolderToRobotBaseTransform.SetMatrixTransformToParent(transform.GetMatrix())
        matrix = vtk.vtkMatrix4x4()
        matrix.SetElement(0, 3, position[0])
        matrix.SetElement(1, 3, position[1])
        matrix.SetElement(2, 3, position[2])
        probeHolderToRobotBaseTransform.SetMatrixTransformToParent(matrix)
        probeHolderToRobotBaseTransform.Modified()
        slicer.app.processEvents()
        if slicer.updateProbeHolderToRobotBaseTransformActive:
            qt.QTimer.singleShot(0, self.updateProbeHolderToRobotBaseTransform)

    def onResetVolumeReconstructionButton(self):

        connectorNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLIGTLConnectorNode")
        if connectorNode:
            connectorNode.Stop()
        else:
            connectorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLIGTLConnectorNode")
            connectorNode.SetName("RobotUltrasoundConnector")
        connectorNode.SetTypeClient("localhost", 18944)
        connectorNode.Start()

        # Wait for the ultrasound image to be received
        import time
        for i in range(30):
            usImageNode = slicer.mrmlScene.GetFirstNodeByName("Image_Reference")
            if usImageNode:
                break
            slicer.app.processEvents()
            time.sleep(0.1)

        if not usImageNode:
            slicer.util.errorDisplay("Failed to receive ultrasound image")
            return

        liveUpdates = self._parameterNode.liveUpdates

        layoutManager = slicer.app.layoutManager()
        sliceWidget = layoutManager.sliceWidget("Red")

        sliceNode = sliceWidget.mrmlSliceNode()
        sliceLogic = sliceWidget.sliceLogic()

        if liveUpdates:
            sliceLogic.GetSliceCompositeNode().SetBackgroundVolumeID(usImageNode.GetID())
            sliceWidget.sliceController().setSliceVisible(True)
            sliceLogic.FitSliceToBackground()
        else:
            #sliceLogic.GetSliceCompositeNode().SetBackgroundVolumeID(None)
            slicer.util.setSliceViewerLayers(background=None)
            sliceWidget.sliceController().setSliceVisible(False)

        # Set up volume reslice driver.
        resliceLogic = slicer.modules.volumereslicedriver.logic()
        if resliceLogic:
            # Typically the image is zoomed in, therefore it is faster if the original resolution is used
            # on the 3D slice (and also we can show the full image and not the shape and size of the 2D view)
            sliceNode.SetSliceResolutionMode(slicer.vtkMRMLSliceNode.SliceResolutionMatchVolumes)
            resliceLogic.SetDriverForSlice(usImageNode.GetID(), sliceNode)
            resliceLogic.SetModeForSlice(6, sliceNode)  # Transverse mode, default for PLUS ultrasound.
            resliceLogic.SetFlipForSlice(True, sliceNode)
            resliceLogic.SetRotationForSlice(180, sliceNode)
            sliceLogic.FitSliceToAll()
        else:
            logging.warning('Logic not found for Volume Reslice Driver')

        imageToProbeHolderTransform = slicer.mrmlScene.GetFirstNodeByName("ImageToProbeHolder")
        if not imageToProbeHolderTransform:
            imageToProbeHolderTransform = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode", "ImageToProbeHolder")
        imageToProbeHolder = vtk.vtkTransform()
        imageToProbeHolder.RotateX(90)
        imageToProbeHolder.Scale(0.64, 0.64, 0.64)
        imageToProbeHolderTransform.SetMatrixTransformToParent(imageToProbeHolder.GetMatrix())

        probeHolderToRobotBaseTransform = slicer.mrmlScene.GetFirstNodeByName("ProbeHolderToRobotBase")
        if not probeHolderToRobotBaseTransform:
            slicer.util.errorDisplay("Robot position is not found. Connect to the robot first.")
            return
        
        usImageNode.SetAndObserveTransformNodeID(imageToProbeHolderTransform.GetID())
        imageToProbeHolderTransform.SetAndObserveTransformNodeID(probeHolderToRobotBaseTransform.GetID())

        # Set up volume reconstruction
        volumeReconstructionNode = slicer.mrmlScene.GetFirstNodeByName("VolumeReconstruction")
        if not volumeReconstructionNode:
            volumeReconstructionNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLVolumeReconstructionNode", "VolumeReconstruction")
        volumeReconstructionNode.SetLiveVolumeReconstruction(False)
        roiNode = slicer.mrmlScene.GetFirstNodeByName("VolumeReconstructionROI")
        if not roiNode:
            roiNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsROINode", "VolumeReconstructionROI")
            roiNode.CreateDefaultDisplayNodes()
            roiNode.SetDisplayVisibility(False)
        outputVolumeNode = slicer.mrmlScene.GetFirstNodeByName("Volume_Reference")
        if not outputVolumeNode:
            outputVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "Volume_Reference")
            outputVolumeNode.CreateDefaultDisplayNodes()

        volumeReconstructionNode.SetLiveVolumeReconstruction(True)
        volumeReconstructionNode.SetAndObserveInputVolumeNode(slicer.mrmlScene.GetFirstNodeByName("Image_Reference"))
        volumeReconstructionNode.SetAndObserveOutputVolumeNode(outputVolumeNode)
        volumeReconstructionNode.SetAndObserveInputROINode(roiNode)
        volumeReconstructionNode.SetFillHoles(True)
        volumeReconstructionNode.SetLiveUpdateIntervalSeconds(1 if liveUpdates else 1000)

        spacing = 1.0 if liveUpdates else 0.5
        volumeReconstructionNode.SetOutputSpacing(spacing, spacing, spacing)

        self.onStartButton(waitToArrive=True, speed=15)
        centerPosition = slicer.mc.angles_to_coords([0,0,0,0,0,0])

        roiSize = [80, 120, 60]
        roiOffset = [50, 50, 40]
        roiNode.SetXYZ(centerPosition[0] + roiOffset[0], centerPosition[1] + roiOffset[1], centerPosition[2] + roiOffset[2])
        roiNode.SetRadiusXYZ(roiSize[0]/2, roiSize[1]/2, roiSize[2]/2)

        slicer.modules.volumereconstruction.logic().ResetVolumeReconstruction(volumeReconstructionNode)

        volumeRenderingLogic = slicer.modules.volumerendering.logic()
        vrDisplayNode = volumeRenderingLogic.CreateDefaultVolumeRenderingNodes(outputVolumeNode)
        vrDisplayNode.SetVisibility(liveUpdates)
        vrDisplayNode.GetVolumePropertyNode().Copy(volumeRenderingLogic.GetPresetByName("MR-Default"))

        slicer.modules.volumereconstruction.logic().StartLiveVolumeReconstruction(volumeReconstructionNode)
  
    def onStartVolumeReconstructionButton(self):
        self.onEndButton()
        
    def onStopVolumeReconstructionButton(self):
        volumeReconstructionNode = slicer.mrmlScene.GetFirstNodeByName("VolumeReconstruction")
        slicer.modules.volumereconstruction.logic().StopLiveVolumeReconstruction(volumeReconstructionNode)
        liveUpdates = self._parameterNode.liveUpdates
        if not liveUpdates:
            outputVolumeNode = slicer.mrmlScene.GetFirstNodeByName("Volume_Reference")
            volumeRenderingLogic = slicer.modules.volumerendering.logic()
            vrDisplayNode = volumeRenderingLogic.GetFirstVolumeRenderingDisplayNode(outputVolumeNode)
            if vrDisplayNode:
                vrDisplayNode.SetVisibility(True)


        
#
# RobotUltrasoundLogic
#


class RobotUltrasoundLogic(ScriptedLoadableModuleLogic):
    """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self) -> None:
        """Called when the logic class is instantiated. Can be used for initializing member variables."""
        ScriptedLoadableModuleLogic.__init__(self)

    def getParameterNode(self):
        return RobotUltrasoundParameterNode(super().getParameterNode())



#
# RobotUltrasoundTest
#


class RobotUltrasoundTest(ScriptedLoadableModuleTest):
    """
    This is the test case for your scripted module.
    Uses ScriptedLoadableModuleTest base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def setUp(self):
        """Do whatever is needed to reset the state - typically a scene clear will be enough."""
        slicer.mrmlScene.Clear()

    def runTest(self):
        """Run as few or as many tests as needed here."""
        self.setUp()
        self.test_RobotUltrasound1()

    def test_RobotUltrasound1(self):
        """Ideally you should have several levels of tests.  At the lowest level
        tests should exercise the functionality of the logic with different inputs
        (both valid and invalid).  At higher levels your tests should emulate the
        way the user would interact with your code and confirm that it still works
        the way you intended.
        One of the most important features of the tests is that it should alert other
        developers when their changes will have an impact on the behavior of your
        module.  For example, if a developer removes a feature that you depend on,
        your test should break so they know that the feature is needed.
        """

        self.delayDisplay("Starting the test")

        self.delayDisplay("Test passed")
