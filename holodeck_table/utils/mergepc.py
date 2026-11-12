import open3d as o3d
import numpy as np
import os

def translate_point_cloud(point_cloud, position):
    # 将点云平移到指定位置
    points = np.asarray(point_cloud.points)
    translation = np.array(position)
    points += translation  # 平移点云
    point_cloud.points = o3d.utility.Vector3dVector(points)  # 更新点云的 points 属性
    return point_cloud

def merge_point_clouds(pc1, pc2, position1=(0, 0, 0), position2=(0, 0, 0)):
    # 将每个点云平移到指定位置
    pc1 = translate_point_cloud(pc1, position1)
    pc2 = translate_point_cloud(pc2, position2)
    
    # 合并点云
    merged_pc = pc1 + pc2
    return merged_pc

path = '/Users/luozhen/Desktop/tabletop/data/obj'
path1 = os.path.join(path, "34cf668cb2c1478c9de5d7cb5f4d0e56/raw_model.ply").replace('\\', '/')
path2 = os.path.join(path, "6c1dd565e5e349e7867f82e18fa15f7e/raw_model.ply").replace('\\', '/')
# 加载两个点云
pc1 = o3d.io.read_point_cloud(path1)
pc2 = o3d.io.read_point_cloud(path2)

# 为每个点云指定位置并合并
position1 = (0, 0, 0)
position2 = (1, 1, 1)  # 示例位置
merged_pc = merge_point_clouds(pc1, pc2, position1, position2)

# # 可视化合并后的点云
# o3d.visualization.draw_geometries([merged_pc])

# 保存合并后的点云
o3d.io.write_point_cloud("/Users/luozhen/Desktop/tabletop/data/obj/merged_point_cloud.ply", merged_pc)
