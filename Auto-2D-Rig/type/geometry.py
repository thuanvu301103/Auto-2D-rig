from dataclasses import dataclass
from typing import List, Optional, Any
from mathutils import Vector
import bpy

@dataclass
class Geometry:
    plane: str
    centroid_2d: Vector
    center: Vector
    head: Vector
    tail: Vector
    direction: Vector
    length: float
    points_2d: List[Any]
    min_proj: Any
    max_proj: Any
    min_x: Any
    max_x: Any
    min_y: Any
    max_y: Any
    depth: float