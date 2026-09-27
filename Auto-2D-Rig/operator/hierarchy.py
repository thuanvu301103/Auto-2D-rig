from mathutils import Vector

def calculate_hierarchy(components):
    """
    Creates a geometric hierarchy.
    The component closest to the overall center becomes the root.
    Other components are attached to the nearest connected component.
    """

    count = len(components)
    for comp in components:
        comp["parent_index"] = None

    if count <= 1:
        return

    # Global center
    global_center = Vector((0.0, 0.0, 0.0))

    # Calculate all components' center
    for comp in components:
        global_center += comp["geometry"].center
    global_center /= count

    # Root - The component closest to the overall center becomes the root.
    root_index = 0
    best_distance = float("inf")
    for i, comp in enumerate(components):
        distance = (comp["geometry"].center - global_center).length
        if distance < best_distance:
            best_distance = distance
            root_index = i

    # Initial state
    connected = {root_index}
    remaining = set(range(count))
    remaining.remove(root_index)

    # Build tree
    while remaining:
        best_child = None
        best_parent = None
        best_distance = float("inf")

        for child_index in remaining:
            child_center = components[child_index]["geometry"].center
            for parent_index in connected:
                parent_center = components[parent_index]["geometry"].center
                distance = (child_center - parent_center).length

                if distance < best_distance:
                    best_distance = distance
                    best_child = child_index
                    best_parent = parent_index

        if best_child is None:
            break
        components[best_child]["parent_index"] = best_parent
        connected.add(best_child)
        remaining.remove(best_child)


def get_overlap_along_direction(parent_geometry, child_geometry):
    """
    Detect overlap along parent's main direction.
    Returns:
        overlap_length
        parent interval
        child interval
    """

    direction = parent_geometry.direction
    parent_center = parent_geometry.centroid_2d

    parent_values = []
    for p in parent_geometry.points_2d:
        value = (p - parent_center).dot(direction)
        parent_values.append(value)
    
    child_values = []
    for p in child_geometry.points_2d:
        value = (p - parent_center).dot(direction)
        child_values.append(value)

    p_min = min(parent_values)
    p_max = max(parent_values)

    c_min = min(child_values)
    c_max = max(child_values)

    overlap_min = max(p_min, c_min)
    overlap_max = min(p_max, c_max)
    overlap_length = (overlap_max - overlap_min)
    return overlap_length, p_min, p_max, c_min, c_max, overlap_min, overlap_max


def calculate_connection_point(parent_geometry, child_geometry, overlap_factor):
    """
    Calculate connection point between parent and child.
    Strategy:
    1. Detect overlap along parent direction.
    2. If overlap exists: use overlap center / adjustable position.
    3. Otherwise: find closest point between centers.
    """

    parent_center = parent_geometry.centroid_2d
    parent_direction = parent_geometry.direction

    (
        overlap_length,
        p_min,
        p_max,
        c_min,
        c_max,
        overlap_min,
        overlap_max
    ) = get_overlap_along_direction(parent_geometry, child_geometry)

    # --------------------------------------------------------
    
    # CASE 1: Actual overlap
    if overlap_length > 0.0001:
        # Position inside overlap.
        connection_value = overlap_min + (overlap_max - overlap_min) * overlap_factor
        connection_2d = parent_center + parent_direction * connection_value
        # Find child position along its own direction
        child_direction = child_geometry.direction
        child_center = child_geometry.centroid_2d
        # Project connection to child axis.
        child_value = (connection_2d - child_center).dot(child_direction)
        connection_2d = child_center + child_direction * child_value
        return connection_2d, True

    # CASE 2: No overlap
    parent_point = parent_center
    child_point = child_geometry.centroid_2d
    # Project child center onto parent direction.
    parent_value = (child_point - parent_center).dot(parent_direction)
    parent_value = max(p_min, min(p_max, parent_value))
    connection_2d = parent_center + parent_direction * parent_value

    return connection_2d, False


def bind_component_to_bone(obj, armature_obj, bone_name):
    """
    Bind entire mesh to exactly one bone. Every vertex receives weight 1.0.
    """

    # Remove old group
    old_group = obj.vertex_groups.get(bone_name)
    if old_group:
        obj.vertex_groups.remove(old_group)

    # Create group
    group = obj.vertex_groups.new(name=bone_name)
    vertex_indices = [v.index for v in obj.data.vertices]
    if vertex_indices:
        group.add(vertex_indices, 1.0, 'REPLACE')

    # Armature modifier
    modifier = None
    for mod in obj.modifiers:
        if mod.type == 'ARMATURE':
            modifier = mod
            break
    if modifier is None:
        modifier = obj.modifiers.new(name="2D AutoRig", type='ARMATURE')

    modifier.object = armature_obj