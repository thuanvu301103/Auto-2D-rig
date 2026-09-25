from mathutils import Vector
from typing import Tuple

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