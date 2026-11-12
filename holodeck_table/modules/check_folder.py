import os
import json

def find_missing_scene_folders():
    """
    Identifies scene_ids from a JSON file that do not have a corresponding folder
    (with a 'scene_' prefix) in the specified base_path.
    Also prints the total number of folders in base_path and the count of missing folders.
    """
    base_path = '/Users/luozhen/desktop/tabletop/task_test/'
    json_file_path = '/Users/luozhen/desktop/code/TableLLM/test_0512_split_raw.json'
    folder_prefix = "scene_"

    # 1. Read unique scene_ids from the JSON file
    scene_ids_from_json = set()
    try:
        with open(json_file_path, 'r') as f:
            inputs = json.load(f)
        for item in inputs:
            # Assuming the scene_id is directly available as item['scene_id']
            # and input_data is a string that needs to be loaded if scene_id is nested
            # Based on previous context: scene_id = input_item['scene_id']
            if 'scene_id' in item:
                scene_ids_from_json.add(item['scene_id'])
            # If scene_id is inside a nested JSON string 'input'
            elif 'input' in item:
                try:
                    input_data = json.loads(item['input'])
                    if 'scene_id' in input_data:
                         scene_ids_from_json.add(input_data['scene_id'])
                except json.JSONDecodeError:
                    print(f"Warning: Could not decode 'input' field for an item: {item}")

    except FileNotFoundError:
        print(f"Error: JSON file not found at {json_file_path}")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {json_file_path}")
        return
    
    if not scene_ids_from_json:
        print("No scene_ids found in the JSON file.")
        # Still might want to count folders, so don't return immediately
        # unless base_path itself is an issue.

    # 2. Get existing folder names from base_path, count all folders, and strip prefix for relevant ones
    processed_existing_folders = set()
    total_folders_in_base_path = 0
    try:
        for item_name in os.listdir(base_path):
            item_path = os.path.join(base_path, item_name)
            if os.path.isdir(item_path):
                total_folders_in_base_path += 1 # Count all actual folders
                if item_name.startswith(folder_prefix):
                    processed_existing_folders.add(item_name[len(folder_prefix):])
    except FileNotFoundError:
        print(f"Error: Base path not found at {base_path}")
        return

    print(f"Total number of folders found in {base_path}: {total_folders_in_base_path}")
    
    if not scene_ids_from_json: # if json was empty or unreadable, but base_path was fine.
        return

    # 3. Find and print missing scene_id folders
    missing_folders = scene_ids_from_json - processed_existing_folders

    if missing_folders:
        print(f"Number of missing scene_id folders: {len(missing_folders)}")
        print(f"Scene_ids from JSON not found as folders (with '{folder_prefix}' prefix) in base_path:")
        for scene_id in sorted(list(missing_folders)): # Sort for consistent output
            print(scene_id)
    else:
        print("All scene_ids from the JSON file have corresponding folders (with '{folder_prefix}' prefix) in the base_path.")
        print("Number of missing scene_id folders: 0")

if __name__ == '__main__':
    find_missing_scene_folders()
