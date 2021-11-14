import bpy
from mathutils import Vector
import functools

# ======== OSL shaders ========

shadow_thing_shader = """
point lerp3(point a, point b, float t) {
    return (1 - t) * a + t * b;
}

shader shadow_thing(
    point light_pos = vector(0.0, 0.0, 0.0),
    point __dummy_uv = vector(0.0, 0.0, 0.0),
    output closure color BSDF = 0
) {
    string myname;
    getattribute("geom:name", myname);
    if(myname == "shadowcaster") {
        BSDF = transparent();
    }
    else{
        if(trace(P, normalize(light_pos - P))) {
            point trace_P;
            point trace_uv;
            string trace_name;
            getmessage("trace", "P", trace_P);
            getmessage("trace", "geom:uv", trace_uv);
            getmessage("trace", "geom:name", trace_name);
            if(trace_name == "shadowcaster") {
                BSDF = emission() * color(trace_uv.x, trace_uv.y, 0);
            } else {
                BSDF = emission() * color(0, 0, 1);
            }
        } else {
            BSDF = emission() * color(0, 0, 1);
        }
    }
}
"""

imageuv_shader = """
shader imageuv (
    point __dummy_uv = 0,
    output closure color BSDF = 0
) {
    string myname;
    getattribute("geom:name", myname);
    if(myname == "shadowcaster") {
        point uv;
        getattribute("geom:uv", uv);
        BSDF = emission() * color(uv.x, uv.y, 0);
    } else {
        BSDF = emission() * color(0, 0, 1);
    }
}
"""

# ======== ========

def add_osl_script_node(node_tree, *, shader_path=None, shader_text=None, text_name='osl_shader.osl'):
    scriptnode = node_tree.nodes.new('ShaderNodeScript')
    if shader_path is not None:
        scriptnode.mode = 'EXTERNAL'
        scriptnode.filepath = shader_path
    elif shader_text is not None:
        scriptnode.mode = 'INTERNAL'
        txt = bpy.data.texts.new(text_name)
        txt.from_string(shader_text)
        scriptnode.script = txt
    return scriptnode

def __new_nodetree(typ, output_node_type, *, name):
    tree_container = getattr(bpy.data, typ).new(name)
    tree_container.use_nodes = True
    tree_container.node_tree.nodes.clear()  # remove default nodes
    output_node = tree_container.node_tree.nodes.new(output_node_type)
    return tree_container, output_node
def new_material(*, name='mat'):
    return __new_nodetree('materials', 'ShaderNodeOutputMaterial', name=name)
def new_world(*, name='world'):
    return __new_nodetree('worlds', 'ShaderNodeOutputWorld', name=name)

def driver_copyval(from_target, from_prop, to_target, to_prop):
    curve_or_curves = from_target.driver_add(from_prop)
    if isinstance(curve_or_curves, bpy.types.FCurve):
        var = curve_or_curves.driver.variables.new()
        var.targets[0].id = to_target
        var.targets[0].data_path = to_prop
        var.name = 'n'
        curve_or_curves.expression = 'n'
    else:
        for idx, curve in enumerate(curve_or_curves):
            var = curve.driver.variables.new()
            var.targets[0].id = to_target
            var.targets[0].data_path = f'{to_prop}[{idx}]'
            var.name = 'n'
            curve.driver.expression = 'n'

def link_nodes(node_tree, from_node, from_socket, to_node, to_socket, reposition_from=False, reposition_to=False):
    node_tree.links.new(from_node.outputs[from_socket], to_node.inputs[to_socket])
    if reposition_to:
        to_node.location = from_node.location + Vector((from_node.width + 40, 0))
    if reposition_from:
        from_node.location = to_node.location - Vector((from_node.width + 40, 0))

# ======== ========

def shadowthing_mat_setup():
    mat, out = new_material()
    script = add_osl_script_node(mat.node_tree, shader_text=shadow_thing_shader)
    tex_coord = mat.node_tree.nodes.new('ShaderNodeTexCoord')
    link_nodes(mat.node_tree, script, 'BSDF', out, 'Surface', reposition_from=True)
    link_nodes(mat.node_tree, tex_coord, 'UV', script, '__dummy_uv', reposition_from=True)
    script.inputs['light_pos'].default_value = bpy.data.objects['shadow_light'].location
    driver_copyval(from_target=script.inputs['light_pos'], from_prop='default_value', to_target=bpy.data.objects['shadow_light'], to_prop='location')
    return mat

def shadowthing_world_setup():
    world, out = new_world()
    bg = world.node_tree.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = (0, 0, 1, 1)
    world.node_tree.links.new(bg.outputs['Background'], out.inputs['Surface'])
    return world

def imagemap_mat_setup():
    mat, out = new_material()
    script = add_osl_script_node(mat.node_tree, shader_text=imageuv_shader);
    tex_coord = mat.node_tree.nodes.new('ShaderNodeTexCoord')
    link_nodes(mat.node_tree, script, 'BSDF', out, 'Surface', reposition_from=True)
    link_nodes(mat.node_tree, tex_coord, 'UV', script, '__dummy_uv', reposition_from=True)
    return mat

# ======== scenes setup ========

main_scene = bpy.context.scene
main_scene.use_fake_user = True
main_view_layer_name = bpy.context.view_layer.name
def setup_secondary_scene(name):
    scene = main_scene.copy()
    scene.use_fake_user = True
    scene.name = name
    return scene, scene.view_layers[main_view_layer_name]

def shadowthing_scene_setup():
    scene, viewlayer = setup_secondary_scene('Shadow Map')
    scene.cycles.device = 'CPU'  # OSL shaders only support CPU compute
    scene.cycles.samples = 1
    scene.cycles.preview_samples = 1
    scene.view_settings.view_transform = 'Raw'
    shadowthing_mat = shadowthing_mat_setup()
    viewlayer.material_override = shadowthing_mat
    scene.world = shadowthing_world_setup()
    return scene, viewlayer
shadowthing_scene, shadowthing_viewlayer = shadowthing_scene_setup()

def imagemap_scene_setup():
    scene, viewlayer = setup_secondary_scene('Image Map')
    scene.cycles.device = 'CPU'  # OSL shaders only support CPU compute
    scene.cycles.samples = 1
    scene.cycles.preview_samples = 1
    scene.view_settings.view_transform = 'Raw'
    viewlayer.material_override = imagemap_mat_setup()
    scene.world = shadowthing_scene.world
    return scene, viewlayer
imagemap_scene, imagemap_viewlayer = imagemap_scene_setup()

def noshadow_scene_setup():
    scene, viewlayer = setup_secondary_scene('No Shadow')
    return scene, viewlayer
noshadow_scene, noshadow_viewlayer = noshadow_scene_setup()

# ======== compositor setup ========

def make_render_layer_node(node_tree, *, scene, layer_name):
    rlayer = node_tree.nodes.new('CompositorNodeRLayers')
    rlayer.scene = scene
    rlayer.layer = layer_name
    return rlayer

main_scene.use_nodes = True
main_scene.node_tree.nodes.clear()

rlayer_main = make_render_layer_node(main_scene.node_tree, scene=main_scene, layer_name=main_view_layer_name)
rlayer_noshadow = make_render_layer_node(main_scene.node_tree, scene=noshadow_scene, layer_name=noshadow_viewlayer.name)
rlayer_shadowthing = make_render_layer_node(main_scene.node_tree, scene=shadowthing_scene, layer_name=shadowthing_viewlayer.name)
rlayer_imagemap = make_render_layer_node(main_scene.node_tree, scene=imagemap_scene, layer_name=imagemap_viewlayer.name)

compositor_output = main_scene.node_tree.nodes.new('CompositorNodeComposite')
link_nodes(main_scene.node_tree, rlayer_main, 'Image', compositor_output, 'Image', reposition_from=True)

def make_compositor_outputfile_slot(file_slots, name):
    socket = file_slots.new(name)
    slot = file_slots[name]
    slot.use_node_format = False
    slot.format.color_mode = 'RGBA'
    slot.format.file_format = 'PNG'
    slot.format.color_depth = '8'
    slot.format.compression = 100

fileoutput_node = main_scene.node_tree.nodes.new('CompositorNodeOutputFile')
fileoutput_node.file_slots.clear()
for slotname, rlayer in [
    ( 'light', rlayer_noshadow ),
    ( 'dark', rlayer_main ),
    ( 'imageuv', rlayer_imagemap ),
    ( 'shadowuv', rlayer_shadowthing ),
]:
    make_compositor_outputfile_slot(fileoutput_node.file_slots, name=slotname)
    link_nodes(main_scene.node_tree, rlayer, 'Image', fileoutput_node, slotname)

# ======== render ========

# bpy.ops.render.render('INVOKE_DEFAULT', animation=False, write_still=False, use_viewport=True, layer=main_view_layer_name, scene=main_scene.name)
