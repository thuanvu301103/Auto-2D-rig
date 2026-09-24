import bpy
import math
from mathutils import Vector


# ============================================================
# 1. METADATA
# ============================================================

bl_info = {
    "name": "2D Component Auto Rigger",
    "author": "Vu Ngoc Thuan",
    "version": (2, 1, 0),
    "blender": (5, 1, 0),
    "location": "View3D > N-Panel > 2D AutoRig",
    "description": (
        "Creates one bone per 2D component, "
        "automatically detects component overlap, "
        "connects bones and binds components."
    ),
    "category": "Rigging",
}


# ============================================================
# 2. BASIC GEOMETRY
# ============================================================

def project_point(point, plane):
    """Project 3D point onto selected 2D plane."""

    if plane == 'XY':
        return Vector((point.x, point.y))

    if plane == 'XZ':
        return Vector((point.x, point.z))

    if plane == 'YZ':
        return Vector((point.y, point.z))

    return Vector((point.x, point.z))


def point_from_2d(point2d, plane, depth):
    """Convert 2D point back into 3D."""

    if plane == 'XY':
        return Vector((point2d.x, point2d.y, depth))

    if plane == 'XZ':
        return Vector((point2d.x, depth, point2d.y))

    if plane == 'YZ':
        return Vector((depth, point2d.x, point2d.y))

    return Vector((point2d.x, depth, point2d.y))


def get_component_objects(collection):
    """
    Get all mesh objects recursively inside a collection.
    """

    objects = []

    def recursive_collect(coll):

        for obj in coll.objects:

            if obj.type == 'MESH':
                objects.append(obj)

        for child in coll.children:
            recursive_collect(child)

    recursive_collect(collection)

    return objects


def get_world_vertices(objects):
    """Get all mesh vertices in world coordinates."""

    points = []

    for obj in objects:

        matrix = obj.matrix_world

        for vertex in obj.data.vertices:

            points.append(
                matrix @ vertex.co
            )

    return points


# ============================================================
# 3. COMPONENT DISCOVERY
# ============================================================

def collect_components(root_collection):
    """
    Component rules:

    Direct Mesh inside ROOT
        -> one component

    Direct child Collection
        -> one component

    All meshes inside that child Collection
        -> same component
    """

    components = []

    # --------------------------------------------------------
    # Direct mesh
    # --------------------------------------------------------

    for obj in root_collection.objects:

        if obj.type == 'MESH':

            components.append({
                "name": obj.name,
                "collection": None,
                "objects": [obj],
            })

    # --------------------------------------------------------
    # Child collections
    # --------------------------------------------------------

    for child in root_collection.children:

        objects = get_component_objects(
            child
        )

        if not objects:
            continue

        components.append({
            "name": child.name,
            "collection": child,
            "objects": objects,
        })

    return components


# ============================================================
# 4. PCA COMPONENT GEOMETRY
# ============================================================

def calculate_component_geometry(
    objects,
    plane
):
    """
    Calculate component geometry.

    Returns:

        center
        head
        tail
        direction
        length
        projected points
        min/max projection
        bounding box
    """

    points_3d = get_world_vertices(
        objects
    )

    if not points_3d:
        return None

    points_2d = [
        project_point(p, plane)
        for p in points_3d
    ]

    # --------------------------------------------------------
    # Center
    # --------------------------------------------------------

    center_2d = Vector((0.0, 0.0))

    for p in points_2d:
        center_2d += p

    center_2d /= len(points_2d)

    # --------------------------------------------------------
    # Covariance matrix
    # --------------------------------------------------------

    xx = 0.0
    xy = 0.0
    yy = 0.0

    for p in points_2d:

        dx = p.x - center_2d.x
        dy = p.y - center_2d.y

        xx += dx * dx
        xy += dx * dy
        yy += dy * dy

    count = max(1, len(points_2d))

    xx /= count
    xy /= count
    yy /= count

    # --------------------------------------------------------
    # Principal direction
    # --------------------------------------------------------

    trace = xx + yy
    diff = xx - yy

    discriminant = math.sqrt(
        max(
            0.0,
            diff * diff +
            4.0 * xy * xy
        )
    )

    eigenvalue = (
        trace +
        discriminant
    ) * 0.5

    if abs(xy) > 1e-8:

        direction = Vector((
            eigenvalue - yy,
            xy
        ))

    elif xx >= yy:

        direction = Vector((
            1.0,
            0.0
        ))

    else:

        direction = Vector((
            0.0,
            1.0
        ))

    if direction.length < 1e-8:

        direction = Vector((
            1.0,
            0.0
        ))

    direction.normalize()

    # --------------------------------------------------------
    # Projection range
    # --------------------------------------------------------

    projections = []

    for p in points_2d:

        relative = p - center_2d

        projections.append(
            relative.dot(direction)
        )

    min_proj = min(projections)
    max_proj = max(projections)

    length = max_proj - min_proj

    if length < 0.001:
        length = 0.1

    # --------------------------------------------------------
    # Depth
    # --------------------------------------------------------

    depth = 0.0

    for p in points_3d:

        if plane == 'XY':
            depth += p.z

        elif plane == 'XZ':
            depth += p.y

        elif plane == 'YZ':
            depth += p.x

    depth /= len(points_3d)

    # --------------------------------------------------------
    # Component endpoints
    # --------------------------------------------------------

    head_2d = (
        center_2d +
        direction * min_proj
    )

    tail_2d = (
        center_2d +
        direction * max_proj
    )

    head = point_from_2d(
        head_2d,
        plane,
        depth
    )

    tail = point_from_2d(
        tail_2d,
        plane,
        depth
    )

    # --------------------------------------------------------
    # Bounding box
    # --------------------------------------------------------

    min_x = min(p.x for p in points_2d)
    max_x = max(p.x for p in points_2d)

    min_y = min(p.y for p in points_2d)
    max_y = max(p.y for p in points_2d)

    return {
        "center": point_from_2d(
            center_2d,
            plane,
            depth
        ),

        "center_2d": center_2d,

        "head": head,

        "tail": tail,

        "direction": direction,

        "length": length,

        "points_2d": points_2d,

        "min_proj": min_proj,

        "max_proj": max_proj,

        "min_x": min_x,

        "max_x": max_x,

        "min_y": min_y,

        "max_y": max_y,

        "depth": depth,
    }


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


def get_overlap_along_direction(
    parent_geometry,
    child_geometry
):
    """
    Detect overlap along parent's main direction.

    Returns:

        overlap_length
        parent interval
        child interval
    """

    direction = (
        parent_geometry["direction"]
    )

    parent_center = (
        parent_geometry["center_2d"]
    )

    parent_values = []

    for p in parent_geometry["points_2d"]:

        value = (
            p - parent_center
        ).dot(direction)

        parent_values.append(value)

    child_values = []

    # Use parent's coordinate system
    for p in child_geometry["points_2d"]:

        value = (
            p - parent_center
        ).dot(direction)

        child_values.append(value)

    p_min = min(parent_values)
    p_max = max(parent_values)

    c_min = min(child_values)
    c_max = max(child_values)

    overlap_min = max(
        p_min,
        c_min
    )

    overlap_max = min(
        p_max,
        c_max
    )

    overlap_length = (
        overlap_max -
        overlap_min
    )

    return (
        overlap_length,
        p_min,
        p_max,
        c_min,
        c_max,
        overlap_min,
        overlap_max
    )


# ============================================================
# 6. FIND CONNECTION POINT
# ============================================================

def calculate_connection_point(
    parent_geometry,
    child_geometry,
    overlap_factor
):
    """
    Calculate connection point between parent and child.

    Strategy:

    1. Detect overlap along parent direction.
    2. If overlap exists:
         use overlap center / adjustable position.
    3. Otherwise:
         find closest point between centers.
    """

    parent_center = (
        parent_geometry["center_2d"]
    )

    parent_direction = (
        parent_geometry["direction"]
    )

    (
        overlap_length,
        p_min,
        p_max,
        c_min,
        c_max,
        overlap_min,
        overlap_max
    ) = get_overlap_along_direction(
        parent_geometry,
        child_geometry
    )

    # --------------------------------------------------------
    # CASE 1:
    # Actual overlap
    # --------------------------------------------------------

    if overlap_length > 0.0001:

        # Position inside overlap.
        connection_value = (
            overlap_min +
            (
                overlap_max -
                overlap_min
            ) * overlap_factor
        )

        connection_2d = (
            parent_center +
            parent_direction *
            connection_value
        )

        # Find child position along its own direction
        child_direction = (
            child_geometry["direction"]
        )

        child_center = (
            child_geometry["center_2d"]
        )

        # Project connection to child axis.
        child_value = (
            connection_2d -
            child_center
        ).dot(
            child_direction
        )

        connection_2d = (
            child_center +
            child_direction *
            child_value
        )

        return connection_2d, True

    # --------------------------------------------------------
    # CASE 2:
    # No overlap
    # --------------------------------------------------------

    parent_point = (
        parent_center
    )

    child_point = (
        child_geometry["center_2d"]
    )

    # Project child center onto parent direction.
    parent_value = (
        child_point -
        parent_center
    ).dot(
        parent_direction
    )

    parent_value = max(
        p_min,
        min(
            p_max,
            parent_value
        )
    )

    connection_2d = (
        parent_center +
        parent_direction *
        parent_value
    )

    return connection_2d, False


# ============================================================
# 7. AUTOMATIC HIERARCHY
# ============================================================

def calculate_hierarchy(
    components
):
    """
    Creates a geometric hierarchy.

    The component closest to the overall center
    becomes the root.

    Other components are attached to the
    nearest connected component.
    """

    count = len(components)

    if count <= 1:

        for comp in components:
            comp["parent_index"] = None

        return

    # --------------------------------------------------------
    # Global center
    # --------------------------------------------------------

    global_center = Vector((
        0.0,
        0.0,
        0.0
    ))

    for comp in components:

        global_center += (
            comp["geometry"]["center"]
        )

    global_center /= count

    # --------------------------------------------------------
    # Root
    # --------------------------------------------------------

    root_index = 0

    best_distance = float("inf")

    for i, comp in enumerate(
        components
    ):

        distance = (
            comp["geometry"]["center"] -
            global_center
        ).length

        if distance < best_distance:

            best_distance = distance

            root_index = i

    # --------------------------------------------------------
    # Initial state
    # --------------------------------------------------------

    for comp in components:

        comp["parent_index"] = None

    connected = {
        root_index
    }

    remaining = set(
        range(count)
    )

    remaining.remove(
        root_index
    )

    # --------------------------------------------------------
    # Build tree
    # --------------------------------------------------------

    while remaining:

        best_child = None
        best_parent = None
        best_distance = float("inf")

        for child_index in remaining:

            child_center = (
                components[
                    child_index
                ]["geometry"]["center"]
            )

            for parent_index in connected:

                parent_center = (
                    components[
                        parent_index
                    ]["geometry"]["center"]
                )

                distance = (
                    child_center -
                    parent_center
                ).length

                if distance < best_distance:

                    best_distance = distance

                    best_child = child_index

                    best_parent = parent_index

        if best_child is None:
            break

        components[
            best_child
        ]["parent_index"] = best_parent

        connected.add(
            best_child
        )

        remaining.remove(
            best_child
        )


# ============================================================
# 8. BIND COMPONENT
# ============================================================

def bind_component_to_bone(
    obj,
    armature_obj,
    bone_name
):
    """
    Bind entire mesh to exactly one bone.

    Every vertex receives weight 1.0.
    """

    # --------------------------------------------------------
    # Remove old group
    # --------------------------------------------------------

    old_group = (
        obj.vertex_groups.get(
            bone_name
        )
    )

    if old_group:

        obj.vertex_groups.remove(
            old_group
        )

    # --------------------------------------------------------
    # Create group
    # --------------------------------------------------------

    group = (
        obj.vertex_groups.new(
            name=bone_name
        )
    )

    vertex_indices = [
        v.index
        for v in obj.data.vertices
    ]

    if vertex_indices:

        group.add(
            vertex_indices,
            1.0,
            'REPLACE'
        )

    # --------------------------------------------------------
    # Armature modifier
    # --------------------------------------------------------

    modifier = None

    for mod in obj.modifiers:

        if mod.type == 'ARMATURE':

            modifier = mod

            break

    if modifier is None:

        modifier = obj.modifiers.new(
            name="2D AutoRig",
            type='ARMATURE'
        )

    modifier.object = armature_obj


# ============================================================
# 9. OPERATOR
# ============================================================

class AUTORIG_OT_ProcessCollection(
    bpy.types.Operator
):

    bl_idname = (
        "autorig.process_collection"
    )

    bl_label = (
        "Generate 2D Component Rig"
    )

    bl_options = {
        'REGISTER',
        'UNDO'
    }

    def execute(
        self,
        context
    ):

        scene = context.scene

        root_collection = (
            scene.autorig_collection
        )

        plane = (
            scene.autorig_projection_plane
        )

        overlap_factor = (
            scene.autorig_overlap_factor
        )

        # ----------------------------------------------------
        # Validate
        # ----------------------------------------------------

        if not root_collection:

            self.report(
                {'ERROR'},
                "Please select a Target Collection."
            )

            return {'CANCELLED'}

        # ----------------------------------------------------
        # Collect components
        # ----------------------------------------------------

        components = (
            collect_components(
                root_collection
            )
        )

        if not components:

            self.report(
                {'ERROR'},
                "No Mesh components found."
            )

            return {'CANCELLED'}

        # ----------------------------------------------------
        # Geometry
        # ----------------------------------------------------

        valid_components = []

        for comp in components:

            geometry = (
                calculate_component_geometry(
                    comp["objects"],
                    plane
                )
            )

            if geometry is None:
                continue

            comp["geometry"] = geometry

            valid_components.append(
                comp
            )

        components = valid_components

        if not components:

            self.report(
                {'ERROR'},
                "No valid component geometry."
            )

            return {'CANCELLED'}

        # ----------------------------------------------------
        # Hierarchy
        # ----------------------------------------------------

        calculate_hierarchy(
            components
        )

        # ----------------------------------------------------
        # Create armature
        # ----------------------------------------------------

        armature_name = (
            f"{root_collection.name}_Rig"
        )

        armature_data = (
            bpy.data.armatures.new(
                f"{armature_name}_Data"
            )
        )

        armature_obj = (
            bpy.data.objects.new(
                armature_name,
                armature_data
            )
        )

        root_collection.objects.link(
            armature_obj
        )

        # ----------------------------------------------------
        # Active armature
        # ----------------------------------------------------

        bpy.ops.object.select_all(
            action='DESELECT'
        )

        armature_obj.select_set(
            True
        )

        context.view_layer.objects.active = (
            armature_obj
        )

        # ----------------------------------------------------
        # Edit mode
        # ----------------------------------------------------

        bpy.ops.object.mode_set(
            mode='EDIT'
        )

        edit_bones = (
            armature_data.edit_bones
        )

        # ----------------------------------------------------
        # First pass:
        # Create basic bones
        # ----------------------------------------------------

        for comp in components:

            geometry = comp["geometry"]

            bone = edit_bones.new(
                comp["name"]
            )

            bone.head = geometry["head"]

            bone.tail = geometry["tail"]

            if (
                bone.tail -
                bone.head
            ).length < 0.001:

                bone.tail = (
                    bone.head +
                    Vector((0.0, 0.1, 0.0))
                )

            comp["bone_name"] = (
                bone.name
            )

        # ----------------------------------------------------
        # Second pass:
        # Parent / child connection
        # ----------------------------------------------------

        for index, comp in enumerate(
            components
        ):

            parent_index = (
                comp["parent_index"]
            )

            if parent_index is None:
                continue

            parent_comp = (
                components[parent_index]
            )

            child_geometry = (
                comp["geometry"]
            )

            parent_geometry = (
                parent_comp["geometry"]
            )

            # -----------------------------------------------
            # Calculate connection
            # -----------------------------------------------

            connection_2d, has_overlap = (
                calculate_connection_point(
                    parent_geometry,
                    child_geometry,
                    overlap_factor
                )
            )

            # -----------------------------------------------
            # Depth
            #
            # Use child's depth so the bone sits
            # on the child's visual plane.
            # -----------------------------------------------

            connection_3d = point_from_2d(
                connection_2d,
                plane,
                child_geometry["depth"]
            )

            parent_bone = (
                edit_bones.get(
                    parent_comp["bone_name"]
                )
            )

            child_bone = (
                edit_bones.get(
                    comp["bone_name"]
                )
            )

            if not parent_bone or not child_bone:
                continue

            # -----------------------------------------------
            # Parent bone tail = connection
            # -----------------------------------------------

            parent_bone.tail = (
                connection_3d
            )

            # -----------------------------------------------
            # Child bone head = same connection
            # -----------------------------------------------

            child_bone.head = (
                connection_3d
            )

            # -----------------------------------------------
            # Preserve child direction
            # -----------------------------------------------

            direction_3d = (
                child_geometry["tail"] -
                child_geometry["head"]
            )

            if direction_3d.length < 0.001:

                direction_3d = Vector((
                    0.0,
                    0.1,
                    0.0
                ))

            direction_3d.normalize()

            # -----------------------------------------------
            # Determine child bone length
            # -----------------------------------------------

            original_length = (
                child_geometry["length"]
            )

            # Bone is shorter than the complete
            # component when overlap exists.
            if has_overlap:

                bone_length = (
                    original_length *
                    max(
                        0.05,
                        min(
                            1.0,
                            1.0 -
                            overlap_factor * 0.5
                        )
                    )
                )

            else:

                bone_length = (
                    original_length * 0.75
                )

            bone_length = max(
                bone_length,
                0.05
            )

            child_bone.tail = (
                connection_3d +
                direction_3d *
                bone_length
            )

            # -----------------------------------------------
            # Parent relationship
            # -----------------------------------------------

            child_bone.parent = (
                parent_bone
            )

            # -----------------------------------------------
            # TRUE CONNECT
            # -----------------------------------------------

            child_bone.use_connect = True

        # ----------------------------------------------------
        # Object mode
        # ----------------------------------------------------

        bpy.ops.object.mode_set(
            mode='OBJECT'
        )

        # ----------------------------------------------------
        # Display
        # ----------------------------------------------------

        armature_obj.show_in_front = True

        # ----------------------------------------------------
        # Bind
        # ----------------------------------------------------

        for comp in components:

            bone_name = (
                comp["bone_name"]
            )

            for obj in comp["objects"]:

                bind_component_to_bone(
                    obj,
                    armature_obj,
                    bone_name
                )

        # ----------------------------------------------------
        # Select armature
        # ----------------------------------------------------

        bpy.ops.object.select_all(
            action='DESELECT'
        )

        armature_obj.select_set(
            True
        )

        context.view_layer.objects.active = (
            armature_obj
        )

        # ----------------------------------------------------
        # Result
        # ----------------------------------------------------

        self.report(
            {'INFO'},
            (
                f"Generated {len(components)} "
                f"components / bones."
            )
        )

        return {'FINISHED'}


# ============================================================
# 10. PANEL
# ============================================================

class AUTORIG_PT_MainPanel(
    bpy.types.Panel
):

    bl_label = (
        "2D Component Auto Rig"
    )

    bl_idname = (
        "AUTORIG_PT_MainPanel"
    )

    bl_space_type = 'VIEW_3D'

    bl_region_type = 'UI'

    bl_category = '2D AutoRig'

    def draw(
        self,
        context
    ):

        layout = self.layout

        scene = context.scene

        # ----------------------------------------------------
        # Configuration
        # ----------------------------------------------------

        box = layout.box()

        box.label(
            text="Rig Configuration:",
            icon='ARMATURE_DATA'
        )

        box.prop(
            scene,
            "autorig_collection",
            text="Target"
        )

        box.prop(
            scene,
            "autorig_projection_plane",
            text="Projection"
        )

        box.prop(
            scene,
            "autorig_overlap_factor",
            text="Connection"
        )

        # ----------------------------------------------------
        # Explanation
        # ----------------------------------------------------

        info = layout.box()

        info.label(
            text="1 Component = 1 Bone",
            icon='INFO'
        )

        info.label(
            text="Child Collection = Component"
        )

        info.label(
            text="Direct Mesh = Component"
        )

        info.label(
            text="Bones connect at overlap"
        )

        # ----------------------------------------------------
        # Generate
        # ----------------------------------------------------

        layout.separator()

        row = layout.row()

        row.scale_y = 1.5

        row.operator(
            "autorig.process_collection",
            text="Generate Component Rig",
            icon='ARMATURE_DATA'
        )


# ============================================================
# 11. REGISTER
# ============================================================

classes = (
    AUTORIG_OT_ProcessCollection,
    AUTORIG_PT_MainPanel,
)


def register():

    for cls in classes:

        try:
            bpy.utils.register_class(
                cls
            )
        except Exception:
            pass

    bpy.types.Scene.autorig_collection = (
        bpy.props.PointerProperty(
            name="Target Collection",
            type=bpy.types.Collection,
            description=(
                "Root collection containing "
                "2D components"
            )
        )
    )

    bpy.types.Scene.autorig_projection_plane = (
        bpy.props.EnumProperty(
            name="Projection Plane",

            items=[
                (
                    'XY',
                    "XY Plane",
                    "Use X/Y coordinates"
                ),
                (
                    'XZ',
                    "XZ Plane",
                    "Use X/Z coordinates"
                ),
                (
                    'YZ',
                    "YZ Plane",
                    "Use Y/Z coordinates"
                ),
            ],

            default='XZ'
        )
    )

    bpy.types.Scene.autorig_overlap_factor = (
        bpy.props.FloatProperty(
            name="Connection Overlap",
            description=(
                "Position of the connection "
                "inside the overlap region"
            ),
            default=0.5,
            min=0.0,
            max=1.0,
            subtype='FACTOR'
        )
    )


def unregister():

    if hasattr(
        bpy.types.Scene,
        "autorig_collection"
    ):

        del bpy.types.Scene.autorig_collection

    if hasattr(
        bpy.types.Scene,
        "autorig_projection_plane"
    ):

        del bpy.types.Scene.autorig_projection_plane

    if hasattr(
        bpy.types.Scene,
        "autorig_overlap_factor"
    ):

        del bpy.types.Scene.autorig_overlap_factor

    for cls in reversed(classes):

        try:
            bpy.utils.unregister_class(
                cls
            )
        except Exception:
            pass


# ============================================================
# 12. RUN
# ============================================================

if __name__ == "__main__":

    try:
        unregister()
    except Exception:
        pass

    register()