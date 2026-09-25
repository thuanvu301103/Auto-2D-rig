from ..type import Component
from typing import List

def collect_components(root_collection) -> List[Component]:
    """
    Component rules:
    - Direct Mesh inside ROOT -> one component
    - Direct child Collection -> one component
    - All meshes inside that child Collection -> same component
    """

    components = []

    # Direct mesh
    for obj in root_collection.objects:
        if obj.type == 'MESH':
            components.append(
                Component(
                    name=obj.name,
                    collection=None,
                    objects=[obj],
                ))

    # Child collections - All the meshes that are inside child collection
    for child in root_collection.children:
        objects = get_component_objects(child)
        if not objects:
            continue
        components.append(
            Component(
                name=child.name,
                collection=child,
                objects=objects,
            ))

    for comp in components:
        print(comp)
        print("-" * 40)

    return components


def get_component_objects(collection):
    """
    Get all **MESH** objects recursively inside a collection.
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