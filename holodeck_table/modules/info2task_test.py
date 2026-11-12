import json
import os

def read_jsoninfo():

    querys = []
    additional_requirements_room = "You need to infer the overall desktop based on the description of some objects on the desktop."
    additional_requirements_objects = []
    file_name_list = [] # Renamed to avoid conflict with the variable in the loop
    
    processed_ids_file_path = '/Users/luozhen/desktop/tabletop/task_test/processed_scene_ids.txt'
    previously_processed_scene_ids = set() 

    # Load previously processed scene IDs
    if os.path.exists(processed_ids_file_path):
        with open(processed_ids_file_path, 'r') as f_ids:
            previously_processed_scene_ids = set(line.strip() for line in f_ids)
    
    print(f"Loaded {len(previously_processed_scene_ids)} previously processed scene IDs.")

    with open('/Users/luozhen/desktop/code/TableLLM/test_0512_split_raw.json', 'r') as f:
        inputs = json.load(f)

    # Process each input
    scenes_to_process_count = 0
    for idx, input_item in enumerate(inputs): 
        input_data = json.loads(input_item['input'])
        scene_id = input_item['scene_id'] 

        if scene_id in previously_processed_scene_ids: # Check if already processed in previous runs
            continue # Skip if already processed
        
        querys.append(input_data['Environment'])
        additional_requirements_objects.append("You must include the following objects, as well as any other objects that may appear in the scene: " + str(input_data["Objects cluster"]))
        file_name_list.append(scene_id) # Use scene_id as the file name identifier
        scenes_to_process_count +=1

    print(f"Found {scenes_to_process_count} new scene IDs to process in this run.")
    
    return querys, additional_requirements_room, additional_requirements_objects, file_name_list