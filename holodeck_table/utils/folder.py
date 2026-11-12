import shutil
import os

# 源文件夹路径
src_folder = '/Volumes/新加卷/objaverse/objaverse_holodeck/09_23_combine_scale/processed_2023_09_23_combine_scale/34cf668cb2c1478c9de5d7cb5f4d0e56'
# 目标文件夹路径
dest_folder = '/Users/luozhen/Desktop/tabletop/data/obj/34cf668cb2c1478c9de5d7cb5f4d0e56'

if not os.path.exists(dest_folder):
    os.makedirs(dest_folder)

src_files = os.listdir(src_folder)
for file_name in src_files:
    full_file_name = os.path.join(src_folder, file_name)
    if os.path.isfile(full_file_name):
        shutil.copy(full_file_name, dest_folder)
