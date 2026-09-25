from dataclasses import dataclass
from typing import List, Optional
from mathutils import Vector
import bpy

@dataclass
class Geometry:
    centroid_2d: Vector