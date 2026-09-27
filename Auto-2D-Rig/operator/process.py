import bpy

from .component_discovery import collect_components
from .geometry_calculate import (
    calculate_component_geometry,
    point_from_2d,
)
from .hierarchy import (
    calculate_hierarchy,
    calculate_connection_point,
    bind_component_to_bone,
)

from mathutils import Vector


# ============================================================
# CONSTANTS
# ============================================================

EPSILON = 0.001
MIN_BONE_LENGTH = 0.05


# ============================================================
# OPERATOR
# ============================================================

class Process(bpy.types.Operator):

    bl_idname = "autorig.process"
    bl_label = "Generate 2D Component Rig"

    bl_options = {
        'REGISTER',
        'UNDO'
    }

    # ========================================================
    # EXECUTE
    # ========================================================

    def execute(self, context):

        # ----------------------------------------------------
        # 1. Get settings
        # ----------------------------------------------------

        scene = context.scene

        root_collection = scene.target_collection
        plane = scene.projection_plane
        overlap_factor = scene.overlap_factor

        # ----------------------------------------------------
        # 2. Validate collection
        # ----------------------------------------------------

        if not root_collection:

            self.report(
                {'ERROR'},
                "Please select a Target Collection."
            )

            return {'CANCELLED'}

        # ----------------------------------------------------
        # 3. Collect components
        # ----------------------------------------------------

        components = collect_components(
            root_collection
        )

        if not components:

            self.report(
                {'ERROR'},
                "No Mesh components found."
            )

            return {'CANCELLED'}

        # ----------------------------------------------------
        # 4. Calculate component geometry
        # ----------------------------------------------------

        valid_components = []

        for comp in components:

            geometry = calculate_component_geometry(
                comp.get_objects(),
                plane
            )

            if geometry is None:
                continue

            valid_components.append({
                "component": comp,
                "geometry": geometry,
            })

        components = valid_components

        if not components:

            self.report(
                {'ERROR'},
                "No valid component geometry."
            )

            return {'CANCELLED'}

        # ----------------------------------------------------
        # 5. Calculate hierarchy
        # ----------------------------------------------------

        calculate_hierarchy(
            components
        )

        # ----------------------------------------------------
        # 6. Create armature
        # ----------------------------------------------------

        armature_name = (
            f"{root_collection.name}_Rig"
        )

        armature_data = bpy.data.armatures.new(
            f"{armature_name}_Data"
        )

        armature_obj = bpy.data.objects.new(
            armature_name,
            armature_data
        )

        root_collection.objects.link(
            armature_obj
        )

        # ----------------------------------------------------
        # 7. Activate armature
        # ----------------------------------------------------

        bpy.ops.object.select_all(
            action='DESELECT'
        )

        armature_obj.select_set(True)

        context.view_layer.objects.active = (
            armature_obj
        )

        # ====================================================
        # EDIT MODE
        # ====================================================

        bpy.ops.object.mode_set(
            mode='EDIT'
        )

        edit_bones = armature_data.edit_bones

        # ----------------------------------------------------
        # 8. First pass
        #
        # Create one basic bone for every component.
        #
        # At this stage:
        #
        #     bone.head = geometry.head
        #     bone.tail = geometry.tail
        #
        # No hierarchy yet.
        # ----------------------------------------------------

        for comp in components:

            geometry = comp["geometry"]

            bone = edit_bones.new(
                comp["component"].name
            )

            bone.head = geometry.head
            bone.tail = geometry.tail

            # ------------------------------------------------
            # Safety for degenerate component
            # ------------------------------------------------

            if (
                bone.tail -
                bone.head
            ).length < EPSILON:

                direction_3d = (
                    geometry.tail -
                    geometry.head
                )

                if direction_3d.length < EPSILON:

                    direction_3d = Vector(
                        (0.0, 0.1, 0.0)
                    )

                else:

                    direction_3d.normalize()
                    direction_3d *= 0.1

                bone.tail = (
                    bone.head +
                    direction_3d
                )

            comp["bone_name"] = bone.name

        # ====================================================
        # 9. Second pass
        #
        # Parent / Child relationships
        # ====================================================

        for index, comp in enumerate(components):

            parent_index = comp[
                "parent_index"
            ]

            # ------------------------------------------------
            # Root component
            # ------------------------------------------------

            if parent_index is None:
                continue

            # ------------------------------------------------
            # Get parent / child
            # ------------------------------------------------

            parent_comp = components[
                parent_index
            ]

            parent_geometry = parent_comp[
                "geometry"
            ]

            child_geometry = comp[
                "geometry"
            ]

            parent_bone = edit_bones.get(
                parent_comp["bone_name"]
            )

            child_bone = edit_bones.get(
                comp["bone_name"]
            )

            if not parent_bone or not child_bone:
                continue

            # =================================================
            # Calculate connection
            # =================================================

            result = calculate_connection_point(
                parent_geometry,
                child_geometry,
                overlap_factor
            )

            (
                connection_2d,
                has_overlap,
                parent_connection_2d,
                child_connection_2d
            ) = result

            # ------------------------------------------------
            # Convert connection to 3D
            #
            # Use child depth so the child bone remains
            # on the child's visual plane.
            # ------------------------------------------------

            connection_3d = point_from_2d(
                connection_2d,
                plane,
                child_geometry.depth
            )

            # =================================================
            # CHILD BONE ORIENTATION
            # =================================================

            direction_3d = (
                child_geometry.tail -
                child_geometry.head
            )

            if direction_3d.length < EPSILON:

                direction_3d = Vector(
                    (0.0, 0.1, 0.0)
                )

            else:

                direction_3d.normalize()

            # =================================================
            # Determine child bone length
            # =================================================

            bone_length = calculate_bone_length(
                child_geometry,
                connection_2d
            )

            bone_length = max(
                bone_length,
                MIN_BONE_LENGTH
            )

            # =================================================
            # Set child bone
            # =================================================

            child_bone.head = (
                connection_3d
            )

            child_bone.tail = (
                connection_3d +
                direction_3d *
                bone_length
            )

            # =================================================
            # Parent relationship
            # =================================================

            child_bone.parent = (
                parent_bone
            )

            # ------------------------------------------------
            # IMPORTANT
            #
            # Do NOT use_connect here.
            #
            # A parent can have multiple children, and every
            # child can have a different connection point.
            # ------------------------------------------------

            child_bone.use_connect = False

            # Store connection information for debugging
            comp["connection_2d"] = connection_2d
            comp["connection_3d"] = connection_3d
            comp["has_overlap"] = has_overlap

            comp[
                "parent_connection_2d"
            ] = parent_connection_2d

            comp[
                "child_connection_2d"
            ] = child_connection_2d

            comp[
                "bone_length"
            ] = bone_length

        # ====================================================
        # OBJECT MODE
        # ====================================================

        bpy.ops.object.mode_set(
            mode='OBJECT'
        )

        # ----------------------------------------------------
        # Display
        # ----------------------------------------------------

        armature_obj.show_in_front = True

        # ====================================================
        # 10. Bind components
        # ====================================================

        for comp in components:

            bone_name = comp[
                "bone_name"
            ]

            for obj in comp[
                "component"
            ].get_objects():

                bind_component_to_bone(
                    obj,
                    armature_obj,
                    bone_name
                )

        # ====================================================
        # 11. Select armature
        # ====================================================

        bpy.ops.object.select_all(
            action='DESELECT'
        )

        armature_obj.select_set(
            True
        )

        context.view_layer.objects.active = (
            armature_obj
        )

        # ====================================================
        # 12. Result
        # ====================================================

        self.report(
            {'INFO'},
            (
                f"Generated "
                f"{len(components)} "
                f"components / bones."
            )
        )

        return {'FINISHED'}


# ============================================================
# BONE LENGTH
# ============================================================

def calculate_bone_length(
    geometry,
    connection_2d
):
    """
    Calculate the actual bone length from the connection
    point to the farther component endpoint.

    This replaces the old arbitrary formula:

        original_length * (1 - overlap_factor * 0.5)

    The bone length is now derived directly from geometry.
    """

    center = geometry.centroid_2d
    direction = geometry.direction.copy()

    # --------------------------------------------------------
    # Safety
    # --------------------------------------------------------

    if direction.length < EPSILON:

        direction = Vector(
            (1.0, 0.0)
        )

    else:

        direction.normalize()

    # --------------------------------------------------------
    # Component endpoints
    # --------------------------------------------------------

    head_2d = (
        center +
        direction *
        geometry.min_proj
    )

    tail_2d = (
        center +
        direction *
        geometry.max_proj
    )

    # --------------------------------------------------------
    # Distance from connection to endpoints
    # --------------------------------------------------------

    distance_to_head = (
        head_2d -
        connection_2d
    ).length

    distance_to_tail = (
        tail_2d -
        connection_2d
    ).length

    # --------------------------------------------------------
    # We use the farther endpoint.
    #
    # This ensures that the bone represents the component
    # instead of being arbitrarily shortened.
    # --------------------------------------------------------

    return max(
        distance_to_head,
        distance_to_tail
    )


# ============================================================
# DEBUG / UTILITY
# ============================================================

def calculate_projection_interval(
    geometry,
    axis
):
    """
    Return the component interval on a selected axis.

    This helper is kept for future geometry / overlap
    extensions.
    """

    if axis == "direction":

        return (
            geometry.min_proj,
            geometry.max_proj
        )

    if axis == "x":

        values = [
            point.x
            for point in geometry.points_2d
        ]

        if not values:
            return 0.0, 0.0

        return (
            min(values),
            max(values)
        )

    if axis == "y":

        values = [
            point.y
            for point in geometry.points_2d
        ]

        if not values:
            return 0.0, 0.0

        return (
            min(values),
            max(values)
        )

    return (
        geometry.min_proj,
        geometry.max_proj
    )