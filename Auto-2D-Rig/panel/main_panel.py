import bpy

class MainPanel(bpy.types.Panel):
    bl_label = "2D Component Auto Rig"
    bl_idname = "AUTORIG_MainPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = '2D AutoRig'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Configuration box
        box = layout.box()
        box.label(text="Configuration:", icon='ARMATURE_DATA')
        box.prop(scene, "target_collection", text="Target")
        box.prop(scene, "projection_plane", text="Projection")
        box.prop(scene, "overlap_factor", text="Connection")

        # Explanation box
        info = layout.box()
        header = info.row()
        header.label(text="Rules & Structure", icon='INFO')
        col = info.column(align=True)
        sub = col.column(align=True)
        sub.scale_y = 0.9
        sub.label(text="• 1 Component = 1 Bone")
        sub.label(text="• Child Collection = Component")
        sub.label(text="• Direct Mesh = Component")
        sub.label(text="• Bones connect at overlap")

        # Generate button
        layout.separator()
        row = layout.row()
        row.scale_y = 1.5
        row.operator(   # Assign operator
            "autorig.process",
            text="Generate Collection Rig",
            icon='ADD'
        )