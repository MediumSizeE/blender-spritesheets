import os
import sys
import bpy
import math
import shutil
import platform
import subprocess
import json
from properties.SpriteSheetPropertyGroup import SpriteSheetPropertyGroup
from properties.ProgressPropertyGroup import ProgressPropertyGroup
from properties.CameraPropertyGroup import CameraPropertyGroup
from helpers.cameraSettings import CameraSettingsFactory
from copy import deepcopy

platform = platform.system()
if platform == "Windows":
    ASSEMBLER_FILENAME = "assembler.exe"
elif platform == "Linux":
    ASSEMBLER_FILENAME = "assembler_linux"
else:
    ASSEMBLER_FILENAME = "assembler_mac"

class RenderSpriteSheet(bpy.types.Operator):
    """Operator used to render sprite sheets for an object"""
    bl_idname = "spritesheets.render"
    bl_label = "Render Sprite Sheets"
    bl_description = "Renders all actions to a single sprite sheet"

    def execute(self, context):
        scene = bpy.context.scene
        props = scene.SpriteSheetPropertyGroup
        progressProps = scene.ProgressPropertyGroup
        progressProps.rendering = True
        progressProps.success = False
        progressProps.actionTotal = len(bpy.data.actions)
        actions = [strip.action for item in bpy.context.object.animation_data.nla_tracks.values() for strip in item.strips.values()]
        print("Actions: ")
        print(actions)

        cameraProps = scene.CameraPropertyGroup

        animation_descs = []
        frame_start = 0

        objectToRender = props.target

        # rust assembler combines in alphabetical order
        anim_dir_order = deepcopy(CameraSettingsFactory.anim_suffix)
        anim_dir_order.sort()
        # actions_sorted = [action for action in bpy.data.actions]
        # actions_sorted = [action for action in bpy.data.actions]
        actions.sort(key=lambda action: action.name)

        for index, action in enumerate(actions):
            progressProps.actionName = action.name
            progressProps.actionIndex = index
            objectToRender.animation_data.action = action

            for dir_num in range(8):
                count, _, _ = frame_count(action.frame_range)
                animation_descs.append({
                    "name": action.name + anim_dir_order[dir_num],
                    "start": frame_start,
                    "count": count,
                })
                frame_start += count

            self.processAction(action, scene, props,
                               progressProps, cameraProps, objectToRender)

        assemblerPath = os.path.normpath(
            os.path.join(
                props.binPath,
                ASSEMBLER_FILENAME,
            )
        )
        
        # Assemble the rendered tiles from the temp folder
        print("Assembler path: ", assemblerPath)
        subprocess.run([assemblerPath, "--root", bpy.path.abspath(props.outputPath), "--out", objectToRender.name + ".png"])

        json_info = {
            "name": objectToRender.name,
            "tileWidth": props.tileSize[0],
            "tileHeight": props.tileSize[1],
            "frameRate": props.fps,
            "animations": animation_descs,
        }

        with open(bpy.path.abspath(os.path.join(props.outputPath, objectToRender.name + ".bss")), "w") as f:
            json.dump(json_info, f, indent='\t')

        progressProps.rendering = False
        progressProps.success = True
        shutil.rmtree(bpy.path.abspath(os.path.join(props.outputPath, "temp")))
        return {'FINISHED'}


    def processAction(self, action, scene, props, progressProps, cameraProps, objectToRender):
        """Processes a single action by iterating through each frame and rendering tiles to a temp folder"""
        frameRange = action.frame_range
        frameCount, frameMin, frameMax = frame_count(frameRange)
        progressProps.tileTotal = frameCount  
        actionPoseMarkers = action.pose_markers        
        
        cameras = CameraSettingsFactory(18., 12., 45.).getCameraSettingsList(CameraSettingsFactory.OBJECT_ROTATE)
        print([camera.suffix for camera in cameras])
        for camera in cameras:
            camera.setRenderSettings(scene)
            camera.setObjectSettings(props)
            cameraProps.angleName = camera.suffix

            if props.onlyRenderMarkedFrames is True and actionPoseMarkers is not None and len(actionPoseMarkers.keys()) > 0:
                for marker in actionPoseMarkers.values():
                    progressProps.tileIndex = marker.frame
                    scene.frame_set(marker.frame)
                    # TODO: Unfortunately Blender's rendering happens on the same thread as the UI and freezes it while running,
                    # eventually they may fix this and then we can leverage some of the progress information we track
                    bpy.ops.spritesheets.render_tile('EXEC_DEFAULT')
            else:
                for index in range(frameMin, frameMax + 1):
                    progressProps.tileIndex = index
                    scene.frame_set(index)
                    # TODO: Unfortunately Blender's rendering happens on the same thread as the UI and freezes it while running,
                    # eventually they may fix this and then we can leverage some of the progress information we track
                    bpy.ops.spritesheets.render_tile('EXEC_DEFAULT')


def frame_count(frame_range):
    frameMin = math.floor(frame_range[0])
    frameMax = math.ceil(frame_range[1])
    return (frameMax + 1 - frameMin, frameMin, frameMax)