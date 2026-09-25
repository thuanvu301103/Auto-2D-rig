from dataclasses import dataclass
from typing import List, Optional
import bpy

@dataclass
class Component:
    name: str
    collection: Optional[bpy.types.Collection]
    objects: List[bpy.types.Object]

    def __str__(self) -> str:
        coll_name = self.collection.name if self.collection else "None (Direct Mesh)"
        obj_names = ", ".join([obj.name for obj in self.objects])
        return f"Component(name='{self.name}', collection='{coll_name}', objects=[{obj_names}])"

    def get_objects(self) -> List[bpy.types.Object]:
        return self.objects