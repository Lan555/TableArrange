import bpy
import numpy as np
import os

def load_pickled_3d_asset(file_path, export_path):
    import gzip
    import pickle
    # Open the compressed pickled file
    with gzip.open(file_path, 'rb') as f:
        # Load the pickled object
        loaded_object_data = pickle.load(f)

    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.object.select_by_type(type='MESH')
    bpy.ops.object.delete()

    # Create a new mesh object in Blender
    mesh = bpy.data.meshes.new(name='LoadedMesh')
    obj = bpy.data.objects.new('LoadedObject', mesh)

    # Link the object to the scene
    bpy.context.scene.collection.objects.link(obj)

    # Set the mesh data for the object
    obj.data = mesh

    # Update the mesh with the loaded data
    # print(loaded_object_data.keys())
    # print(loaded_object_data['triangles'])
    # triangles = [vertex_index for face in loaded_object_data['triangles'] for vertex_index in face]
    triangles = np.array(loaded_object_data['triangles']).reshape(-1,3)
    vertices = []

    for v in loaded_object_data['vertices']:
        vertices.append([v['x'],v['z'],v['y']])

    mesh.from_pydata(vertices, [], triangles)

    uvs = []
    for uv in loaded_object_data['uvs']:
        uvs.append([uv['x'],uv['y']]) 

    mesh.update()

    # Ensure UV coordinates are stored
    if not mesh.uv_layers:
        mesh.uv_layers.new(name="UVMap")

    uv_layer = mesh.uv_layers["UVMap"]
    for poly in mesh.polygons:
        for loop_index in poly.loop_indices:
            vertex_index = mesh.loops[loop_index].vertex_index
            uv_layer.data[loop_index].uv = uvs[vertex_index]
    

    material = bpy.data.materials.new(name="AlbedoMaterial")
    obj.data.materials.append(material)

    # Assign albedo color to the material
    material.use_nodes = True
    nodes = material.node_tree.nodes
    principled_bsdf = nodes.get("Principled BSDF")

    texture_node = nodes.new(type='ShaderNodeTexImage')

    image_path = f"{'/'.join(file_path.split('/')[:-1])}/albedo.jpg"  # Replace with your image file path

    image = bpy.data.images.load(image_path)

    # Assign the image to the texture node
    texture_node.image = image

    # Connect the texture node to the albedo color
    material.node_tree.links.new(
        texture_node.outputs["Color"],
        principled_bsdf.inputs["Base Color"]
    )

    # normal
    image_path = f"{'/'.join(file_path.split('/')[:-1])}/normal.jpg"
    img_normal = bpy.data.images.load(image_path)
    image_texture_node_normal = material.node_tree.nodes.new(type='ShaderNodeTexImage')
    image_texture_node_normal.image = img_normal    
    image_texture_node_normal.image.colorspace_settings.name = 'Non-Color'

    normal_map_node = material.node_tree.nodes.new(type='ShaderNodeNormalMap')

    material.node_tree.links.new(normal_map_node.outputs["Normal"], principled_bsdf.inputs["Normal"])
    material.node_tree.links.new(image_texture_node_normal.outputs["Color"], normal_map_node.inputs["Color"])

    # Assign the material to the object
    obj.data.materials[0] = material
    #obj.data.materials.append(material)

    # Update mesh to apply UV changes
    mesh.update()

    #export_path = 'C:\\Users\\Administrator\Desktop\\000a0c5cdc3146ea87485993fbaf5352\\color_mesh.GLB'
    bpy.ops.wm.obj_export(filepath = export_path)
    #bpy.ops.export_scene.gltf(filepath=export_path, use_selection = True, export_format='GLB', export_materials = 'EXPORT')
    return obj

#path = '/Volumes/新加卷/objaverse/objaverse_holodeck/09_23_combine_scale/processed_2023_09_23_combine_scale/.pkl.gz'
#export_path = 'D:\\3d-dataset\\TableArrange\\test\\796f8add5d0043cb8e560ec7b7ebe7e7\\color_mesh.obj'
#obj = load_pickled_3d_asset(path)

path = '/Users/luozhen/Desktop/tabletop/data/obj'

obj_names = os.listdir(path)

for obj_name in obj_names:
    if obj_name=='.DS_Store':
        continue
    full_path = os.path.join(path, obj_name, obj_name+".pkl.gz").replace('\\', '/')
    full_export = os.path.join(path, obj_name, "raw_model.obj").replace('\\', '/')
    print(full_path)
    load_pickled_3d_asset(full_path, full_export)
    print(full_path)