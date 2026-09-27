from ..type import Component
from typing import List


def collect_components(root_collection) -> List[Component]:
    """
    Collect components from a root collection.

    Component rules
    ---------------
    1. A Mesh object directly inside ROOT
       -> one independent component.

    2. A direct child Collection of ROOT
       -> one component.

    3. All Mesh objects recursively contained inside
       that child Collection belong to the same component.

    Example
    -------
    Root
    ├── Body.mesh
    ├── Head.mesh
    │
    ├── Arm
    │   ├── UpperArm.mesh
    │   ├── LowerArm.mesh
    │   └── Hand
    │       └── Hand.mesh
    │
    └── Leg
        ├── UpperLeg.mesh
        └── LowerLeg.mesh

    Components
    -----------
    Body.mesh
    Head.mesh
    Arm
        -> UpperArm.mesh
        -> LowerArm.mesh
        -> Hand.mesh
    Leg
        -> UpperLeg.mesh
        -> LowerLeg.mesh
    """

    components = []

    if root_collection is None:
        return components

    # ---------------------------------------------------------
    # 1. Direct Mesh objects inside ROOT
    # ---------------------------------------------------------

    for obj in root_collection.objects:

        if obj.type != 'MESH':
            continue

        components.append(
            Component(
                name=obj.name,
                collection=None,
                objects=[obj],
            )
        )

    # ---------------------------------------------------------
    # 2. Direct child Collections
    # ---------------------------------------------------------

    for child_collection in root_collection.children:

        objects = get_component_objects(child_collection)

        if not objects:
            continue

        components.append(
            Component(
                name=child_collection.name,
                collection=child_collection,
                objects=objects,
            )
        )

    # ---------------------------------------------------------
    # Debug information
    # ---------------------------------------------------------

    print("\n" + "=" * 60)
    print(f"COMPONENT DISCOVERY: {root_collection.name}")
    print("=" * 60)

    for index, component in enumerate(components):

        print(f"\nComponent {index}: {component.name}")

        if component.collection is None:
            print("  Type: Direct Mesh")
        else:
            print("  Type: Collection")
            print(f"  Collection: {component.collection.name}")

        print("  Objects:")

        for obj in component.objects:
            print(f"    - {obj.name}")

    print("\n" + "=" * 60)
    print(f"Total Components: {len(components)}")
    print("=" * 60 + "\n")

    return components


def get_component_objects(collection) -> List:
    """
    Recursively collect all Mesh objects inside a collection.

    The collection itself and all nested child collections
    are treated as ONE component.

    Example
    -------
    Arm
    ├── UpperArm.mesh
    ├── LowerArm.mesh
    └── Hand
        ├── Palm.mesh
        └── Finger
            └── Finger.mesh

    Result:
        [
            UpperArm.mesh,
            LowerArm.mesh,
            Palm.mesh,
            Finger.mesh
        ]
    """

    objects = []

    def recursive_collect(current_collection):

        # Collect Mesh objects directly inside this collection
        for obj in current_collection.objects:

            if obj.type == 'MESH':
                objects.append(obj)

        # Recursively process child collections
        for child_collection in current_collection.children:

            recursive_collect(child_collection)

    recursive_collect(collection)

    return objects
