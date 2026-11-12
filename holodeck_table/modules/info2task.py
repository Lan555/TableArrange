import json
import os

def read_jsoninfo():
    root = "/Users/luozhen/desktop/code/TableLLM/direct_test_output_multiple_sft"

    querys = []
    additional_requirements_room = "You need to infer the overall desktop based on the description of some objects on the desktop."
    additional_requirements_objects = []
    file_name = []
    
    count = 0
    for name in os.listdir(root):
        if count >= 10:  # 只处理前10个场景
            break
            
        scene_dir = os.path.join(root, name)
        if os.path.isdir(scene_dir) and name.startswith("scene_"):
            json_file = os.path.join(scene_dir, "prompt_and_response.json")
            file_name.append(name)
            with open(json_file, "r") as f:
                data = json.load(f)

            querys.append(data["input_task_description"]["Environment"])
            additional_requirements_objects.append("You must include the following objects, as well as any other objects that may appear in the scene: " + str(data["input_task_description"]["Objects cluster"]))
            count += 1

    return querys, additional_requirements_room, additional_requirements_objects, file_name

