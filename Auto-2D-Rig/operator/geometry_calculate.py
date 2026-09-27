from mathutils import Vector
from typing import Tuple
from ..type import Geometry
import math

def get_world_vertices(objects):
    """Get all meshes' vertices in world coordinates."""
    points = []
    for obj in objects:
        matrix = obj.matrix_world
        for vertex in obj.data.vertices:
            points.append(matrix @ vertex.co)
    return points

# Basic geometry

def project_point(point, plane):
    """Project 3D point onto selected 2D plane."""
    if plane == 'XY':
        return Vector((point.x, point.y))
    if plane == 'XZ':
        return Vector((point.x, point.z))
    if plane == 'YZ':
        return Vector((point.y, point.z))
    return Vector((point.x, point.z))

def calculate_2d_centroid(points_2d):
    """
    Calculates the 2D centroid from a list of 2D vectors.
    Returns Vector((0.0, 0.0)) if the list is empty.
    """
    if not points_2d:
        return Vector((0.0, 0.0))
    return sum(points_2d, Vector((0.0, 0.0))) / len(points_2d)

def calculate_projection_range(points_2d, center_2d, direction, min_length=0.1, threshold=0.001):
    """
    Calculate the projection range and length of 2D points along a direction vector.
    Args:
        points_2d (list): List of 2D points (objects with .dot() or numpy arrays).
        center_2d: The 2D centroid point.
        direction: Normalized 2D direction vector.
        min_length (float): Fallback length if calculated length is below threshold.
        threshold (float): Minimum acceptable length threshold.
    Returns:
        tuple: (min_proj, max_proj, length)
    """
    projections = [(p - center_2d).dot(direction) for p in points_2d]

    min_proj = min(projections)
    max_proj = max(projections)

    length = max_proj - min_proj
    if length < threshold:
        length = min_length

    return min_proj, max_proj, length

def calculate_average_depth(points_3d, plane):
    """Calculate the average depth value perpendicular to the projection plane.
    Args:
        points_3d (list): List of 3D point objects with x, y, z attributes.
        plane (str): The projection plane ('XY', 'XZ', or 'YZ').
    Returns:
        float: The average depth coordinate value.
    """
    if not points_3d:
        return 0.0

    plane_axis_map = {
        'XY': lambda p: p.z,
        'XZ': lambda p: p.y,
        'YZ': lambda p: p.x,
    }

    if plane not in plane_axis_map:
        raise ValueError(f"Invalid plane string: {plane}")

    get_coordinate = plane_axis_map[plane]
    total_depth = sum(get_coordinate(p) for p in points_3d)

    return total_depth / len(points_3d)

def point_from_2d(point2d, plane, depth) -> Vector:
    """Convert 2D point back into 3D."""
    if plane == 'XY':
        return Vector((point2d.x, point2d.y, depth))
    if plane == 'XZ':
        return Vector((point2d.x, depth, point2d.y))
    if plane == 'YZ':
        return Vector((depth, point2d.x, point2d.y))
    return Vector((point2d.x, depth, point2d.y))

# PCA

def compute_covariance_matrix_2d(points, sample = True) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    n = len(points)
    if n == 0:
        return ((0.0, 0.0), (0.0, 0.0))

    if sample and n < 2:
        return ((0.0, 0.0), (0.0, 0.0))

    mean_x, mean_y = calculate_2d_centroid(points)

    xx = 0.0
    xy = 0.0
    yy = 0.0

    for p in points:
        dx = p.x - mean_x
        dy = p.y - mean_y
        xx += dx * dx
        xy += dx * dy
        yy += dy * dy

    divisor = (n - 1) if sample else n

    cov_xx = xx / divisor
    cov_xy = xy / divisor
    cov_yy = yy / divisor

    return ((cov_xx, cov_xy), (cov_xy, cov_yy))

def compute_pca_2d(points_2d: list, sample: bool = True) -> Tuple[float, Vector]:
    """Computes 2D PCA parameters using the existing compute_covariance_matrix_2d function.

    Returns a tuple containing (eigenvalue, direction_vector).
    """
    cov_matrix = compute_covariance_matrix_2d(points_2d, sample=sample)
    (xx, xy), (_, yy) = cov_matrix

    trace = xx + yy
    diff = xx - yy

    discriminant = math.sqrt(max(0.0, diff * diff + 4.0 * xy * xy))
    eigenvalue = (trace + discriminant) * 0.5

    if abs(xy) > 1e-8:
        direction = Vector((eigenvalue - yy, xy))
    elif xx >= yy:
        direction = Vector((1.0, 0.0))
    else:
        direction = Vector((0.0, 1.0))

    if direction.length < 1e-8:
        direction = Vector((1.0, 0.0))

    direction.normalize()

    return eigenvalue, direction

# Component geometry calculation

def calculate_component_geometry(objects, plane):
    """
    Calculate component geometry.
    """

    points_3d = get_world_vertices(objects)

    if not points_3d:
        return None

    # Project point to 2D plan
    points_2d = [project_point(p, plane) for p in points_3d]
    # All meshes' center
    center_2d = calculate_2d_centroid(points_2d)
    # Principal direction
    _, direction = compute_pca_2d(points_2d)

    # Projection range
    min_proj, max_proj, length = calculate_projection_range(points_2d, center_2d, direction)
    # Depth
    depth = calculate_average_depth(points_3d, plane)
    # Component endpoints
    head_2d = center_2d + direction * min_proj
    tail_2d = center_2d + direction * max_proj
    head = point_from_2d(head_2d, plane, depth)
    tail = point_from_2d(tail_2d, plane, depth)
    
    # Bounding box
    min_x = min(p.x for p in points_2d)
    max_x = max(p.x for p in points_2d)
    min_y = min(p.y for p in points_2d)
    max_y = max(p.y for p in points_2d)

    geometry = Geometry(
        plane=plane,
        centroid_2d=center_2d,
        center=point_from_2d(center_2d, plane, depth),
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