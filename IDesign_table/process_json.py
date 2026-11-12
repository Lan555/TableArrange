import json
import os
import re
import glob

base_path = "/ssd1/zhen/tablellm/test_results"

count = 0

def process_json_file(file_path):
    global count
    try:
        # 读取JSON文件
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        if "objects_on_table" in data:
            objects = data["objects_on_table"]
        
            # 检查数据格式
        elif isinstance(data, list):
                # 如果直接是对象列表
            objects = data
        else:
            print(f"Warning: Unsupported JSON format in {file_path}, skipping.")
            return False
        
        processed_objects = []
        # 处理每个对象
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            
            # 检查是否在桌子上 - 过滤掉边缘和表面元素
            if "is_on_the_table" not in obj:
                continue
                
            new_obj = {}  # 创建新对象，只包含需要的字段
            # print(obj)
            # 如果已有description，直接提取需要的字段
            if "description" in obj:
                # 只复制需要的四个字段
                if "new_object_id" in obj:
                    new_obj["instance"] = obj["new_object_id"]
                if "position" in obj and isinstance(obj["position"], list):
                    new_obj["position"] = obj["position"]
                if "size" in obj and isinstance(obj["size"], list):
                    new_obj["size"] = obj["size"]
                if "rotation" in obj and isinstance(obj["rotation"], dict) and "z_angle" in obj["rotation"]:
                    new_obj["z_rotation"] = obj["rotation"]["z_angle"]
                new_obj["description"] = obj["description"]
                # print(new_obj)
                # 检查必要字段是否都存在
                if all(key in new_obj for key in ["instance", "position", "z_rotation", "description"]):
                    processed_objects.append(new_obj)
                continue  # 跳过后续处理
            
            # 处理position
            if "position" in obj:
                pos = obj["position"]
                if isinstance(pos, dict):
                    new_obj["position"] = [
                        int(pos.get("x", 0) * 100),
                        int(pos.get("y", 0) * 100),
                        int(pos.get("z", 0) * 100)
                    ]
            else:
                continue  # 如果没有position，跳过
            
            # 处理rotation -> z_rotation
            if "rotation" in obj and isinstance(obj["rotation"], dict) and "z_angle" in obj["rotation"]:
                new_obj["z_rotation"] = obj["rotation"]["z_angle"]
            else:
                continue  # 如果没有z_rotation，跳过
            
            # 添加instance键和description
            if "new_object_id" in obj:
                new_obj["instance"] = obj["new_object_id"]
                
                # 添加description
                base_name = re.sub(r'_\d+$', '', obj["new_object_id"])
                base_name = re.sub(r'\d+$', '', base_name)
                
                # 构建description
                description = f"This is a {base_name}"
    
                if "style" in obj and obj["style"]:
                    description += f" with {obj['style']} style"
                
                if "material" in obj and obj["material"]:
                    description += f", made of {obj['material']}"
                
                new_obj["description"] = description
            else:
                continue  # 如果没有new_object_id，跳过
            
            # 检查所有必要字段是否都存在
            if all(key in new_obj for key in ["instance", "position", "z_rotation", "description"]):
                processed_objects.append(new_obj)
        
        # 打印处理结果
        # print(f"File: {file_path}, Objects found: {len(objects)}, Objects processed: {len(processed_objects)}")
        if len(processed_objects) == 0:
            count += 1
            print(f"No objects found in {file_path}")
        # 保存修改后的JSON
        with open(file_path, 'w') as f:
            json.dump(processed_objects, f, indent=4)
        
        return True
    
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    # 获取所有JSON文件
    json_files = glob.glob(os.path.join(base_path, "**/*.json"), recursive=True)
    
    print(f"Found {len(json_files)} JSON files to process")
    
    success_count = 0
    for file_path in json_files:
        if process_json_file(file_path):
            success_count += 1
            if success_count % 100 == 0:
                print(f"Processed {success_count} files")
    
    print(f"Successfully processed {success_count} out of {len(json_files)} JSON files")
    print(f"Skipped {count} files")
if __name__ == "__main__":
    main()