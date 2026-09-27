from mathutils import Vector


# ============================================================
# UTILITY
# ============================================================

EPSILON = 1e-5


def clamp(value, minimum=0.0, maximum=1.0):
    """
    Clamp a value into [minimum, maximum].
    """
    return max(
        minimum,
        min(maximum, value)
    )


# ============================================================
# HIERARCHY
# ============================================================

def calculate_hierarchy(components):
    """
    Build a geometric component hierarchy.

    Strategy
    --------
    1. Find the component closest to the global center.
       This becomes the root.

    2. Starting from the root, attach the remaining
       components to the closest already-connected component.

    This produces a tree structure without cycles.

    Result
    ------
    Each component receives:

        component["parent_index"]

    Root:

        parent_index = None
    """

    count = len(components)

    # --------------------------------------------------------
    # Reset hierarchy
    # --------------------------------------------------------

    for comp in components:
        comp["parent_index"] = None

    if count <= 1:
        return

    # --------------------------------------------------------
    # Calculate global center
    # --------------------------------------------------------

    global_center = Vector((0.0, 0.0, 0.0))

    for comp in components:
        global_center += comp["geometry"].center

    global_center /= count

    # --------------------------------------------------------
    # Find root
    # --------------------------------------------------------

    root_index = 0
    best_distance = float("inf")

    for index, comp in enumerate(components):

        distance = (
            comp["geometry"].center -
            global_center
        ).length

        if distance < best_distance:

            best_distance = distance
            root_index = index

    # --------------------------------------------------------
    # Build tree
    # --------------------------------------------------------

    connected = {root_index}

    remaining = set(
        range(count)
    )

    remaining.remove(root_index)

    while remaining:

        best_child = None
        best_parent = None
        best_distance = float("inf")

        # ----------------------------------------------------
        # Find closest child-parent pair
        # ----------------------------------------------------

        for child_index in remaining:

            child_center = (
                components[child_index]
                ["geometry"]
                .center
            )

            for parent_index in connected:

                parent_center = (
                    components[parent_index]
                    ["geometry"]
                    .center
                )

                distance = (
                    child_center -
                    parent_center
                ).length

                if distance < best_distance:

                    best_distance = distance
                    best_child = child_index
                    best_parent = parent_index

        # ----------------------------------------------------
        # Safety
        # ----------------------------------------------------

        if best_child is None:
            break

        # ----------------------------------------------------
        # Assign hierarchy
        # ----------------------------------------------------

        components[best_child][
            "parent_index"
        ] = best_parent

        connected.add(
            best_child
        )

        remaining.remove(
            best_child
        )


# ============================================================
# PROJECTION INTERVAL
# ============================================================

def get_projection_interval(
    geometry,
    origin,
    direction
):
    """
    Project all component points onto a given axis.

    Parameters
    ----------
    geometry:
        Component geometry.

    origin:
        Origin of projection axis.

    direction:
        Normalized 2D direction.

    Returns
    -------
    min_value, max_value
    """

    values = [
        (point - origin).dot(direction)
        for point in geometry.points_2d
    ]

    if not values:
        return 0.0, 0.0

    return (
        min(values),
        max(values)
    )


# ============================================================
# OVERLAP DETECTION
# ============================================================

def get_overlap_along_direction(
    parent_geometry,
    child_geometry
):
    """
    Detect the overlap of parent and child when both
    are projected onto the parent's principal direction.

    Returns
    -------
    overlap_length

    parent_min
    parent_max

    child_min
    child_max

    overlap_min
    overlap_max
    """

    direction = (
        parent_geometry.direction.copy()
    )

    if direction.length < EPSILON:
        direction = Vector((1.0, 0.0))
    else:
        direction.normalize()

    parent_center = (
        parent_geometry.centroid_2d
    )

    # --------------------------------------------------------
    # Parent interval
    # --------------------------------------------------------

    parent_min, parent_max = (
        get_projection_interval(
            parent_geometry,
            parent_center,
            direction
        )
    )

    # --------------------------------------------------------
    # Child interval
    #
    # IMPORTANT:
    # Both parent and child are projected onto
    # the SAME axis.
    # --------------------------------------------------------

    child_min, child_max = (
        get_projection_interval(
            child_geometry,
            parent_center,
            direction
        )
    )

    # --------------------------------------------------------
    # Intersection
    # --------------------------------------------------------

    overlap_min = max(
        parent_min,
        child_min
    )

    overlap_max = min(
        parent_max,
        child_max
    )

    overlap_length = max(
        0.0,
        overlap_max - overlap_min
    )

    return (
        overlap_length,
        parent_min,
        parent_max,
        child_min,
        child_max,
        overlap_min,
        overlap_max
    )


# ============================================================
# CLOSEST POINT BETWEEN TWO LINE SEGMENTS
# ============================================================

def closest_points_on_segments_2d(
    p1,
    p2,
    q1,
    q2
):
    """
    Find the closest points between two 2D line segments.

    Returns
    -------
    point_on_parent,
    point_on_child,
    distance
    """

    u = p2 - p1
    v = q2 - q1
    w = p1 - q1

    a = u.dot(u)
    b = u.dot(v)
    c = v.dot(v)
    d = u.dot(w)
    e = v.dot(w)

    denominator = (
        a * c -
        b * b
    )

    # --------------------------------------------------------
    # Degenerate parent / child segment
    # --------------------------------------------------------

    if a < EPSILON and c < EPSILON:

        return (
            p1,
            q1,
            (p1 - q1).length
        )

    # Parent is a point
    if a < EPSILON:

        t = 0.0

        if c > EPSILON:
            t = clamp(
                e / c
            )

        point_q = q1 + v * t

        return (
            p1,
            point_q,
            (p1 - point_q).length
        )

    # Child is a point
    if c < EPSILON:

        s = clamp(
            -d / a
        )

        point_p = p1 + u * s

        return (
            point_p,
            q1,
            (point_p - q1).length
        )

    # --------------------------------------------------------
    # Non-parallel case
    # --------------------------------------------------------

    if abs(denominator) > EPSILON:

        s = (
            b * e -
            c * d
        ) / denominator

        t = (
            a * e -
            b * d
        ) / denominator

        s = clamp(s)
        t = clamp(t)

    else:

        # Parallel segments.
        s = 0.0

        t = clamp(
            e / c
        )

    point_p = p1 + u * s
    point_q = q1 + v * t

    return (
        point_p,
        point_q,
        (point_p - point_q).length
    )


# ============================================================
# CONNECTION POINT
# ============================================================

def calculate_connection_point(
    parent_geometry,
    child_geometry,
    overlap_factor=0.5
):
    """
    Calculate the connection point between parent and child.

    Strategy
    --------
    CASE 1
        Parent and child overlap along the parent axis.

        The connection point is selected inside the overlap
        region using overlap_factor.

    CASE 2
        No overlap.

        The closest points between the two component
        principal segments are used.

    Returns
    -------
    connection_2d
        Final connection point in 2D.

    has_overlap
        True if an actual projection overlap exists.

    connection_parent_2d
        Point on parent axis.

    connection_child_2d
        Point on child axis.
    """

    overlap_factor = clamp(
        overlap_factor
    )

    parent_center = (
        parent_geometry.centroid_2d
    )

    parent_direction = (
        parent_geometry.direction.copy()
    )

    child_center = (
        child_geometry.centroid_2d
    )

    child_direction = (
        child_geometry.direction.copy()
    )

    # --------------------------------------------------------
    # Normalize directions
    # --------------------------------------------------------

    if parent_direction.length < EPSILON:
        parent_direction = Vector((1.0, 0.0))
    else:
        parent_direction.normalize()

    if child_direction.length < EPSILON:
        child_direction = Vector((1.0, 0.0))
    else:
        child_direction.normalize()

    # --------------------------------------------------------
    # Parent principal segment
    # --------------------------------------------------------

    parent_head = (
        parent_center +
        parent_direction *
        parent_geometry.min_proj
    )

    parent_tail = (
        parent_center +
        parent_direction *
        parent_geometry.max_proj
    )

    # --------------------------------------------------------
    # Child principal segment
    # --------------------------------------------------------

    child_head = (
        child_center +
        child_direction *
        child_geometry.min_proj
    )

    child_tail = (
        child_center +
        child_direction *
        child_geometry.max_proj
    )

    # ========================================================
    # CASE 1: OVERLAP
    # ========================================================

    (
        overlap_length,
        parent_min,
        parent_max,
        child_min,
        child_max,
        overlap_min,
        overlap_max
    ) = get_overlap_along_direction(
        parent_geometry,
        child_geometry
    )

    if overlap_length > EPSILON:

        # ----------------------------------------------------
        # Choose a point inside overlap.
        # ----------------------------------------------------

        connection_value = (
            overlap_min +
            (
                overlap_max -
                overlap_min
            ) * overlap_factor
        )

        parent_connection = (
            parent_center +
            parent_direction *
            connection_value
        )

        # ----------------------------------------------------
        # Find the corresponding point on child axis.
        #
        # Instead of returning the projected child point
        # directly, calculate both points first.
        # ----------------------------------------------------

        child_value = (
            parent_connection -
            child_center
        ).dot(
            child_direction
        )

        child_value = clamp_projection_to_segment(
            child_value,
            child_geometry.min_proj,
            child_geometry.max_proj
        )

        child_connection = (
            child_center +
            child_direction *
            child_value
        )

        # ----------------------------------------------------
        # Final connection.
        #
        # Use the midpoint between the two axis points.
        #
        # This avoids biasing the connection toward either
        # parent or child when their principal axes differ.
        # ----------------------------------------------------

        connection = (
            parent_connection +
            child_connection
        ) * 0.5

        return (
            connection,
            True,
            parent_connection,
            child_connection
        )

    # ========================================================
    # CASE 2: NO OVERLAP
    # ========================================================

    (
        parent_point,
        child_point,
        distance
    ) = closest_points_on_segments_2d(
        parent_head,
        parent_tail,
        child_head,
        child_tail
    )

    connection = (
        parent_point +
        child_point
    ) * 0.5

    return (
        connection,
        False,
        parent_point,
        child_point
    )


# ============================================================
# CLAMP PROJECTION
# ============================================================

def clamp_projection_to_segment(
    value,
    min_value,
    max_value
):
    """
    Clamp a projection value to a component segment.
    """

    return max(
        min_value,
        min(
            max_value,
            value
        )
    )


# ============================================================
# BIND COMPONENT TO BONE
# ============================================================

def bind_component_to_bone(
    obj,
    armature_obj,
    bone_name
):
    """
    Bind an entire mesh object to exactly one bone.

    Every vertex receives weight 1.0.
    """

    # --------------------------------------------------------
    # Remove existing vertex group with same name
    # --------------------------------------------------------

    old_group = obj.vertex_groups.get(
        bone_name
    )

    if old_group:
        obj.vertex_groups.remove(
            old_group
        )

    # --------------------------------------------------------
    # Create vertex group
    # --------------------------------------------------------

    group = obj.vertex_groups.new(
        name=bone_name
    )

    vertex_indices = [
        vertex.index
        for vertex in obj.data.vertices
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
