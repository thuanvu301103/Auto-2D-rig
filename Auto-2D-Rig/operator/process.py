import bpy
from .component_discovery import collect_components
from .geometry_calculate import calculate_component_geometry, point_from_2d
from .hierarchy import calculate_hierarchy, calculate_connection_point, bind_component_to_bone
from ..type import Geometry
import math
from mathutils import Vector

class Process(bpy.types.Operator):

    bl_idname = "autorig.process"
    bl_label = "Generate 2D Component Rig"
    bl_options = {
        'REGISTER',
        'UNDO'
    }

    def execute(self, context):

        # Get context
        scene = context.scene
        root_collection = scene.target_collection
        plane = scene.projection_plane
        overlap_factor = scene.overlap_factor

        # Validate
        if not root_collection:
            self.report(
                {'ERROR'},
                "Please select a Target Collection."
            )
            return {'CANCELLED'}

        # Collect components
        components = collect_components(root_collection)
        if not components:
            self.report(
                {'ERROR'},
                "No Mesh components found."
            )
            return {'CANCELLED'}

        # Geometry
        valid_components = []
        for comp in components:
            geometry = calculate_component_geometry(comp.get_objects(), plane)
            if geometry is None:
                continue
            valid_comp = {
                "component": comp,
                "geometry": geometry 
            }
            valid_components.append(valid_comp)
        components = valid_components
        if not components:
            self.report({'ERROR'}, "No valid component geometry.")
            return {'CANCELLED'}

        # Hierarchy
        calculate_hierarchy(components)

        # Create armature
        armature_name = f"{root_collection.name}_Rig"
        armature_data = bpy.data.armatures.new(f"{armature_name}_Data")
        armature_obj = bpy.data.objects.new(armature_name, armature_data)
        root_collection.objects.link(armature_obj)

        # Active armature
        bpy.ops.object.select_all(action='DESELECT')
        armature_obj.select_set(True)
        context.view_layer.objects.active = (armature_obj)

        # ----------------------------------------------------

        # Edit mode
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = armature_data.edit_bones
        
        # First pass: Create basic bones
        for comp in components:
            geometry = comp["geometry"]
            bone = edit_bones.new(comp["component"].name)
            bone.head = geometry.head
            bone.tail = geometry.tail
            if (bone.tail -bone.head).length < 0.001:
                bone.tail = bone.head + Vector((0.0, 0.1, 0.0))
            comp["bone_name"] = bone.name

        # Second pass: Parent / child connection
        for index, comp in enumerate(components):
            parent_index = comp["parent_index"]
            if parent_index is None:
                continue
            parent_comp = components[parent_index]
            child_geometry = comp["geometry"]
            parent_geometry = parent_comp["geometry"]

            # Calculate connection
            connection_2d, has_overlap = calculate_connection_point(parent_geometry, child_geometry, overlap_factor)

            # Use child's depth so the bone sits on the child's visual plane.
            connection_3d = point_from_2d(connection_2d, plane, child_geometry.depth)

            parent_bone = edit_bones.get(parent_comp["bone_name"])
            child_bone = edit_bones.get(comp["bone_name"])
            if not parent_bone or not child_bone:
                continue

            # Parent bone tail = connection
            parent_bone.tail = connection_3d
            # Child bone head = same connection
            child_bone.head = connection_3d

            # Preserve child direction
            direction_3d = child_geometry.tail - child_geometry.head
            if direction_3d.length < 0.001:
                direction_3d = Vector((0.0,0.1,0.0))
            direction_3d.normalize()

            # Determine child bone length
            original_length = child_geometry.length

            # Bone is shorter than the complete component when overlap exists.
            if has_overlap:
                bone_length = original_length * max(0.05, min(1.0, 1.0 - overlap_factor * 0.5))
            else:
                bone_length = original_length * 0.75
            bone_length = max(bone_length, 0.05)

            child_bone.tail = connection_3d + direction_3d * bone_length

            # Parent relationship
            child_bone.parent = parent_bone
            child_bone.use_connect = True

        # ----------------------------------------------------
        
        # Object mode
        bpy.ops.object.mode_set(mode='OBJECT')
        # Display
        armature_obj.show_in_front = True
        # Bind
        for comp in components:
            bone_name = comp["bone_name"]
            for obj in comp["component"].get_objects():
                bind_component_to_bone(obj, armature_obj, bone_name)

        # Select armature
        bpy.ops.object.select_all(action='DESELECT')
        armature_obj.select_set(True)
        context.view_layer.objects.active = (armature_obj)

        # ----------------------------------------------------

        # Result
        self.report(
            {'INFO'},
            (
                f"Generated {len(components)} "
                f"components / bones."
            )
        )
        return {'FINISHED'}


# ============================================================
# 5. OVERLAP DETECTION
# ============================================================

def calculate_projection_interval(
    geometry,
    axis
):
    """
    Return component interval on a selected axis.
    """

    direction = geometry["direction"]

    # Component's principal direction.
    if axis == "direction":
        return (
            geometry["min_proj"],
            geometry["max_proj"]
        )

    if axis == "x":

        values = [
            p.x
            for p in geometry["points_2d"]
        ]

        return (
            min(values),
            max(values)
        )

    if axis == "y":

        values = [
            p.y
            for p in geometry["points_2d"]
        ]

        return (
            min(values),
            max(values)
        )

    return (
        geometry["min_proj"],
        geometry["max_proj"]
    )
