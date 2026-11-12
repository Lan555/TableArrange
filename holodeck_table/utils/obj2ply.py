import trimesh
import open3d as o3d
import os

import os
import numpy as np
import open3d as o3d
from PIL import Image

def load_textures_from_mtl(file_path, obj_path):
    # 从 .mtl 文件中获取漫反射和凹凸贴图的路径
    mtl_path = obj_path.replace('.obj', '.mtl')
    diffuse_map = None
    bump_map = None

    with open(mtl_path, 'r') as file:
        for line in file:
            if line.startswith('map_Kd'):  # 漫反射贴图
                diffuse_map = os.path.join(file_path, line.split()[1])
            elif line.startswith('map_Bump') or line.startswith('bump'):  # 凹凸贴图
                bump_map = os.path.join(file_path, line.split()[1])

    return diffuse_map, bump_map

def apply_texture_to_vertices(mesh, texture_image):
    if not mesh.has_triangle_uvs():
        raise ValueError("Mesh does not have texture coordinates.")

    # 获取顶点和 UV 坐标
    vertices = np.asarray(mesh.vertices)
    triangles = np.asarray(mesh.triangles)
    uvs = np.asarray(mesh.triangle_uvs)

    # 转换 UV 坐标为图像像素坐标
    uvs[:, 0] *= texture_image.width
    uvs[:, 1] = (1 - uvs[:, 1]) * texture_image.height
    uvs = np.clip(uvs, 0, np.array([texture_image.width - 1, texture_image.height - 1])).astype(np.int32)

    # 创建顶点颜色数组
    vertex_colors = np.zeros((len(vertices), 3))

    for triangle_id, triangle in enumerate(triangles):
        for i, vertex_id in enumerate(triangle):
            uv_id = triangle_id * 3 + i
            uv = uvs[uv_id]
            color = texture_image.getpixel((uv[0], uv[1]))

            # 处理颜色通道
            if len(color) == 1:
                color = [color[0]] * 3
            elif len(color) == 4:
                color = color[:3]
            vertex_colors[vertex_id] = np.array(color[:3]) / 255.0

    return vertex_colors

def mesh2pc(file_path, save_file):
    if os.path.exists(save_file):
        return

    mesh = o3d.io.read_triangle_mesh(os.path.join(file_path, "raw_model.obj"))

    # 从 MTL 文件加载漫反射贴图和凹凸贴图
    diffuse_map, _ = load_textures_from_mtl(file_path, os.path.join(file_path, "raw_model.mtl"))

    if diffuse_map is None:
        print("No diffuse texture found in MTL.")
        return

    # 读取漫反射贴图
    texture_image = Image.open(diffuse_map)
    vertex_colors = apply_texture_to_vertices(mesh, texture_image)

    # 将颜色赋给 mesh
    mesh.vertex_colors = o3d.utility.Vector3dVector(vertex_colors)
    mesh.compute_vertex_normals()

    # 采样点云
    point_cloud = mesh.sample_points_poisson_disk(number_of_points=8192)

    # 保存点云
    o3d.io.write_point_cloud(save_file, point_cloud)



path = '/Users/luozhen/Desktop/tabletop/data/obj'

obj_names = os.listdir(path)

for obj_name in obj_names:
    if obj_name=='.DS_Store':
        continue
    # full_path = os.path.join(path, obj_name, "raw_model.obj").replace('\\', '/')
    full_path = os.path.join(path, obj_name).replace('\\', '/')
    full_export = os.path.join(path, obj_name, "raw_model.ply").replace('\\', '/')
    
    mesh2pc(full_path, full_export)
