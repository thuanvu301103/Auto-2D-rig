from mathutils import Vector
from typing import Tuple
from ..type import Geometry
import math


# ============================================================
# WORLD GEOMETRY
# ============================================================

def get_world_vertices(objects):
    """
    Get all mesh vertices in WORLD coordinates.

    Every object can have its own location / rotation / scale.
    The object matrix_world is therefore applied to every vertex.
    """

    points = []

    for obj in objects:

        if obj.type != 'MESH':
            continue

        matrix = obj.matrix_world

        for vertex in obj.data.vertices:
            points.append(matrix @ vertex.co)

    return points


# ============================================================
# 2D PROJECTION
# ============================================================

def project_point(point, plane):
    """
    Project a 3D point onto the selected 2D projection plane.

    XY -> (X, Y)
    XZ -> (X, Z)
    YZ -> (Y, Z)
    """

    if plane == 'XY':
        return Vector((point.x, point.y))

    if plane == 'XZ':
        return Vector((point.x, point.z))

    if plane == 'YZ':
        return Vector((point.y, point.z))

    raise ValueError(
        f"Invalid projection plane: {plane}"
    )


def calculate_2d_centroid(points_2d):
    """
    Calculate the arithmetic centroid of 2D points.
    """

    if not points_2d:
        return Vector((0.0, 0.0))

    total = sum(
        points_2d,
        Vector((0.0, 0.0))
    )

    return total / len(points_2d)


# ============================================================
# PROJECTION RANGE
# ============================================================

def calculate_projection_range(
    points_2d,
    center_2d,
    direction,
    min_length=0.1,
    threshold=0.001
):
    """
    Calculate the projection interval of a component
    along its principal direction.

    Returns
    -------
    min_proj
        Minimum projection value.

    max_proj
        Maximum projection value.

    length
        max_proj - min_proj.

    Notes
    -----
    If the component is extremely small, the interval is
    expanded around the centroid so that head and tail
    remain different points.
    """

    if not points_2d:
        return (
            -min_length * 0.5,
            min_length * 0.5,
            min_length
        )

    # Make sure direction is normalized.
    direction = direction.copy()

    if direction.length < 1e-8:
        direction = Vector((1.0, 0.0))
    else:
        direction.normalize()

    # --------------------------------------------------------
    # Project every point onto the principal axis.
    # --------------------------------------------------------

    projections = [
        (point - center_2d).dot(direction)
        for point in points_2d
    ]

    min_proj = min(projections)
    max_proj = max(projections)

    length = max_proj - min_proj

    # --------------------------------------------------------
    # Degenerate / extremely small component.
    # --------------------------------------------------------

    if length < threshold:

        length = max(
            min_length,
            threshold
        )

        # IMPORTANT:
        # Expand the actual projection interval too.
        #
        # Previously only `length` was changed while
        # min_proj/max_proj remained equal.
        #
        # That could create:
        #
        #     head == tail
        #
        # even though length == 0.1.
        #
        half_length = length * 0.5

        min_proj = -half_length
        max_proj = half_length

    return (
        min_proj,
        max_proj,
        length
    )


# ============================================================
# DEPTH
# ============================================================

def calculate_average_depth(points_3d, plane):
    """
    Calculate the average depth coordinate perpendicular
    to the selected projection plane.

    XY -> Z
    XZ -> Y
    YZ -> X
    """

    if not points_3d:
        return 0.0

    if plane == 'XY':
        return sum(p.z for p in points_3d) / len(points_3d)

    if plane == 'XZ':
        return sum(p.y for p in points_3d) / len(points_3d)

    if plane == 'YZ':
        return sum(p.x for p in points_3d) / len(points_3d)

    raise ValueError(
        f"Invalid projection plane: {plane}"
    )


# ============================================================
# 2D -> 3D
# ============================================================

def point_from_2d(point2d, plane, depth):
    """
    Convert a 2D point back into 3D world coordinates.

    XY -> (X, Y, depth)
    XZ -> (X, depth, Z)
    YZ -> (depth, X, Y)
    """

    if plane == 'XY':
        return Vector((
            point2d.x,
            point2d.y,
            depth
        ))

    if plane == 'XZ':
        return Vector((
            point2d.x,
            depth,
            point2d.y
        ))

    if plane == 'YZ':
        return Vector((
            depth,
            point2d.x,
            point2d.y
        ))

    raise ValueError(
        f"Invalid projection plane: {plane}"
    )


# ============================================================
# PCA
# ============================================================

def compute_covariance_matrix_2d(
    points,
    sample=True
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """
    Calculate the 2D covariance matrix.

    Returns
    -------
    (
        (cov_xx, cov_xy),
        (cov_xy, cov_yy)
    )
    """

    n = len(points)

    if n == 0:
        return (
            (0.0, 0.0),
            (0.0, 0.0)
        )

    if sample and n < 2:
        return (
            (0.0, 0.0),
            (0.0, 0.0)
        )

    mean = calculate_2d_centroid(points)

    xx = 0.0
    xy = 0.0
    yy = 0.0

    for point in points:

        dx = point.x - mean.x
        dy = point.y - mean.y

        xx += dx * dx
        xy += dx * dy
        yy += dy * dy

    divisor = (n - 1) if sample else n

    cov_xx = xx / divisor
    cov_xy = xy / divisor
    cov_yy = yy / divisor

    return (
        (cov_xx, cov_xy),
        (cov_xy, cov_yy)
    )


def compute_pca_2d(
    points_2d,
    sample=True
) -> Tuple[float, Vector]:
    """
    Calculate the dominant PCA direction of 2D points.

    Returns
    -------
    eigenvalue
        Largest eigenvalue.

    direction
        Normalized principal direction.
    """

    if not points_2d:
        return (
            0.0,
            Vector((1.0, 0.0))
        )

    cov_matrix = compute_covariance_matrix_2d(
        points_2d,
        sample=sample
    )

    (xx, xy), (_, yy) = cov_matrix

    # --------------------------------------------------------
    # Largest eigenvalue of 2x2 covariance matrix.
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
        trace + discriminant
    ) * 0.5

    # --------------------------------------------------------
    # Corresponding eigenvector.
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Safety fallback.
    # --------------------------------------------------------

    if direction.length < 1e-8:

        direction = Vector((
            1.0,
            0.0
        ))

    direction.normalize()

    return (
        eigenvalue,
        direction
    )


# ============================================================
# COMPONENT GEOMETRY
# ============================================================

def calculate_component_geometry(objects, plane):
    """
    Calculate the complete geometric representation
    of one component.

    A component may contain multiple mesh objects.

    The geometry is calculated from ALL mesh vertices
    belonging to that component.
    """

    # --------------------------------------------------------
    # 1. World-space vertices
    # --------------------------------------------------------

    points_3d = get_world_vertices(objects)

    if not points_3d:
        return None

    # --------------------------------------------------------
    # 2. Project to 2D
    # --------------------------------------------------------

    points_2d = [
        project_point(point, plane)
        for point in points_3d
    ]

    if not points_2d:
        return None

    # --------------------------------------------------------
    # 3. Component centroid
    # --------------------------------------------------------

    center_2d = calculate_2d_centroid(
        points_2d
    )

    # --------------------------------------------------------
    # 4. Principal direction
    # --------------------------------------------------------

    _, direction = compute_pca_2d(
        points_2d
    )

    # --------------------------------------------------------
    # 5. Projection interval
    # --------------------------------------------------------

    (
        min_proj,
        max_proj,
        length
    ) = calculate_projection_range(
        points_2d,
        center_2d,
        direction
    )

    # --------------------------------------------------------
    # 6. Average depth
    # --------------------------------------------------------

    depth = calculate_average_depth(
        points_3d,
        plane
    )

    # --------------------------------------------------------
    # 7. Component endpoints in 2D
    # --------------------------------------------------------

    head_2d = (
        center_2d +
        direction * min_proj
    )

    tail_2d = (
        center_2d +
        direction * max_proj
    )

    # --------------------------------------------------------
    # 8. Convert endpoints to 3D
    # --------------------------------------------------------

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
    # 9. Bounding box
    # --------------------------------------------------------

    min_x = min(
        point.x
        for point in points_2d
    )

    max_x = max(
        point.x
        for point in points_2d
    )

    min_y = min(
        point.y
        for point in points_2d
    )

    max_y = max(
        point.y
        for point in points_2d
    )

    # --------------------------------------------------------
    # 10. 3D center
    # --------------------------------------------------------

    center = point_from_2d(
        center_2d,
        plane,
        depth
    )

    # --------------------------------------------------------
    # 11. Build Geometry object
    # --------------------------------------------------------

    geometry = Geometry(
        plane=plane,

        centroid_2d=center_2d,

        center=center,

        head=head,

        tail=tail,

        direction=direction,

        length=length,

        points_2d=points_2d,

        min_proj=min_proj,

        max_proj=max_proj,

        min_x=min_x,

        max_x=max_x,

        min_y=min_y,

        max_y=max_y,

        depth=depth,
    )

    return geometry
