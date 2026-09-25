import bpy
from .panel import MainPanel
from .operator import Process

# Meta information for Blender Add-on

bl_info = {
    "name": "2D Component Auto Rigger",
    "author": "Vu Ngoc Thuan",
    "version": (2, 1, 0),
    "blender": (5, 1, 0),
    "location": "View3D > N-Panel > 2D AutoRig",
    "description": (
        "Creates one bone per 2D component, "
        "automatically detects component overlap, "
        "connects bones and binds components."
    ),
    "category": "Rigging",
}

# Register / Unregister
classes = ( # Panel and Operator
    Process,
    MainPanel,
)

def register():
    # Register classes
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except Exception:
            pass
    
    # Register properties in bpy.types.Scene
    ## PointerProperty for Collection
    bpy.types.Scene.target_collection = (
        bpy.props.PointerProperty(  # PointerProperty is used to reference a Collection
            name="Target Collection",
            type=bpy.types.Collection,
            description="Root collection containin 2D components"
        )
    )
    ## EnumProperty for Projection Plane
    bpy.types.Scene.projection_plane = (
        bpy.props.EnumProperty(
            name="Projection Plane",
            items=[
                (
                    'XY',
                    "XY Plane",
                    "Use X/Y coordinates"
                ),
                (
                    'XZ',
                    "XZ Plane",
                    "Use X/Z coordinates"
                ),
                (
                    'YZ',
                    "YZ Plane",
                    "Use Y/Z coordinates"
                ),
            ],
            default='XZ'
        )
    )
    ## FloatProperty for Overlap Factor
    bpy.types.Scene.overlap_factor = (
        bpy.props.FloatProperty(
            name="Connection Overlap",
            description="Position of the connection inside the overlap region",
            default=0.5,
            min=0.0,
            max=1.0,
            subtype='FACTOR'
        )
    )


def unregister():
    if hasattr(bpy.types.Scene, "target_collection"):
        del bpy.types.Scene.target_collection
    if hasattr(bpy.types.Scene, "projection_plane"):
        del bpy.types.Scene.projection_plane
    if hasattr(bpy.types.Scene, "overlap_factor"):
        del bpy.types.Scene.overlap_factor
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass


# Main entry point for script execution - Add-on
if __name__ == "__main__":

    try:
        unregister()
    except Exception:
        pass

    register()