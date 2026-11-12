import json
import os
import shutil

def read_jsoninfo():

    querys = []
    additional_requirements_room = "You need to infer the overall desktop based on the description of some objects on the desktop."
    additional_requirements_objects = []
    file_name_list = [] # Renamed to avoid conflict with the variable in the loop
    
    previously_processed_scene_ids = set() 
    
    
    print(f"Loaded {len(previously_processed_scene_ids)} previously processed scene IDs.")

    with open('/Users/luozhen/desktop/code/TableLLM/test_0512_split_raw.json', 'r') as f:
        inputs = json.load(f)

    # Process each input
    scenes_to_process_count = 0
    items_to_save = [] # New list to store items that are not skipped
    for idx, input_item in enumerate(inputs): 
        input_data = json.loads(input_item['input'])
        scene_id = input_item['scene_id'] 

        if scene_id in previously_processed_scene_ids: # Check if already processed in previous runs
            continue # Skip if already processed
        
        items_to_save.append(input_item) # Save the entire input_item if not skipped

        querys.append(input_data['Environment'])
        additional_requirements_objects.append("You must include the following objects, as well as any other objects that may appear in the scene: " + str(input_data["Objects cluster"]))
        file_name_list.append(scene_id) # Use scene_id as the file name identifier
        scenes_to_process_count +=1

    print(f"Found {scenes_to_process_count} new scene IDs to process in this run.")

    # Save the unskipped items to a new JSON file
    output_json_path = '/Users/luozhen/desktop/code/TableLLM/unskipped_input_items.json'
    with open(output_json_path, 'w') as outfile:
        json.dump(items_to_save, outfile, indent=4)
    print(f"Saved {len(items_to_save)} unskipped items to {output_json_path}")
    
    return querys, additional_requirements_room, additional_requirements_objects, file_name_list

def delete_folders_without_prefix(base_path, prefix):
    """
    Deletes folders in the base_path that do not start with the given prefix.
    Also, counts and lists folders that do start with the prefix.

    Args:
        base_path (str): The path to the directory to scan.
        prefix (str): The required prefix for folder names to be kept.
    """
    print(f"Scanning directory: {base_path}")
    print(f"Working with prefix: '{prefix}'")
    
    folders_to_delete_count = 0
    prefixed_folders_count = 0
    prefixed_folder_names_stripped = []

    print("\n--- Folders NOT starting with prefix (identified for potential deletion) ---")
    for item_name in os.listdir(base_path):
        item_path = os.path.join(base_path, item_name)
        if os.path.isdir(item_path):
            if not item_name.startswith(prefix):
                print(f"  - Would delete: {item_path}")
                folders_to_delete_count += 1
                # UNCOMMENT THE LINES BELOW TO ACTUALLY DELETE THE FOLDERS
                # try:
                #     shutil.rmtree(item_path)
                #     print(f"    - DELETED: {item_path}")
                # except OSError as e:
                #     print(f"    - ERROR deleting {item_path}: {e}")
            else:
                # This folder has the prefix
                prefixed_folders_count += 1
                prefixed_folder_names_stripped.append(item_name[len(prefix):])
        else:
            # This is a file, not a folder, so we ignore it.
            pass
            
    if folders_to_delete_count == 0:
        print("No folders found that DO NOT start with the prefix.")
    else:
        print(f"\nIdentified {folders_to_delete_count} folder(s) for potential deletion (those not starting with '{prefix}').")
        # The following line was: print("To actually delete them, you need to uncomment the 'shutil.rmtree(item_path)' line in the script.")
        # It is still relevant if uncommenting deletion logic.
        print("If deletion is enabled in the script, these would be removed.")

    print("\n--- Folders STARTING with prefix ---")
    print(f"Found {prefixed_folders_count} folder(s) that start with '{prefix}'.")
    if prefixed_folders_count > 0:
        print(f"Names of these folders (with '{prefix}' prefix removed):")
        for name in sorted(prefixed_folder_names_stripped): # Sort for consistent output
            print(f"  - {name}")
    
    # The original if __name__ == "__main__": block would still call this function.

if __name__ == "__main__":
    target_directory = "/Users/luozhen/Desktop/tabletop/task_test/"
    required_prefix = "scene_"
    
    # Confirmation before proceeding (even for printing)
    # confirm = input(f"This script will scan '{target_directory}' and identify folders "
    #                 f"that DO NOT start with '{required_prefix}' for potential deletion. "
    #                 "It will only PRINT what it would delete by default. "
    #                 "Are you sure you want to continue? (yes/no): ")
    # if confirm.lower() == 'yes':
    #     delete_folders_without_prefix(target_directory, required_prefix)
    # else:
    #     print("Operation cancelled by user.")

    # Simpler execution without interactive confirmation for now, relying on commented-out deletion
    delete_folders_without_prefix(target_directory, required_prefix)