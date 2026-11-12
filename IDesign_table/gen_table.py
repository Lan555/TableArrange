import json
import os
import time
import sys
import traceback
from IDesign import IDesign

# --- 1. Data Loading and Preprocessing ---

print("Loading and preprocessing data...")
design_tasks = []
processed_scene_ids = set()
try:
    with open('/ssd1/zhen/tablellm/test_0512_split_raw.json', 'r') as f:
        raw_inputs = json.load(f)
except FileNotFoundError:
    print("Error: Input file '/ssd1/zhen/tablellm/test_0512_split_raw.json' not found.")
    exit()
except json.JSONDecodeError:
    print("Error: Could not decode JSON from the input file.")
    exit()

# 定义合理的表格尺寸范围（单位：米）
MIN_TABLE_DIMENSION = 0.3  # 最小30厘米
MAX_TABLE_DIMENSION = 3.0  # 最大3米

for idx, item in enumerate(raw_inputs):
    try:
        # Parse necessary parts - handle potential missing keys or invalid JSON strings
        input_data_str = item.get('input')
        output_data_str = item.get('output')
        scene_id_str = item.get('scene_id') # Assuming scene_id is also a string needing parsing

        if not all([input_data_str, output_data_str, scene_id_str]):
             print(f"Warning: Skipping item {idx} due to missing 'input', 'output', or 'scene_id'.")
             continue

        input_data = json.loads(input_data_str)
        output_data = json.loads(output_data_str)
        scene_id = scene_id_str # Parse scene_id if it's a JSON string like "123"

        # Check for duplicate scene_id
        if scene_id in processed_scene_ids:
            print(f"Skipping duplicate scene_id: {scene_id} at index {idx}")
            continue
        processed_scene_ids.add(scene_id)

        # Extract data needed for IDesign
        # Use .get() for safer dictionary access within parsed data
        objects_list = output_data.get('objects')
        item_placement_zone = output_data.get('item_placement_zone')
        user_environment = input_data.get('Environment')

        if objects_list is None or item_placement_zone is None or user_environment is None:
             print(f"Warning: Skipping item {idx} (scene_id: {scene_id}) due to missing 'objects', 'item_placement_zone', or 'Environment' in parsed data.")
             continue

        no_of_objects = len(objects_list)
        # Check if item_placement_zone has enough elements
        if len(item_placement_zone) < 4:
            print(f"Warning: Skipping item {idx} (scene_id: {scene_id}) due to invalid 'item_placement_zone' length.")
            continue
            
        # 提取原始尺寸
        raw_width = item_placement_zone[1]/100
        raw_length = item_placement_zone[3]/100
        
        # 确保尺寸为正数
        width = abs(raw_width)
        length = abs(raw_length)
        
        # 检查尺寸是否在合理范围内
        if width < MIN_TABLE_DIMENSION or length < MIN_TABLE_DIMENSION:
            print(f"Warning: Table dimensions too small for scene_id={scene_id}: {width}m x {length}m")
            print(f"Adjusting to minimum size: {MIN_TABLE_DIMENSION}m x {MIN_TABLE_DIMENSION}m")
            width = max(width, MIN_TABLE_DIMENSION)
            length = max(length, MIN_TABLE_DIMENSION)
        
        if width > MAX_TABLE_DIMENSION or length > MAX_TABLE_DIMENSION:
            print(f"Warning: Table dimensions too large for scene_id={scene_id}: {width}m x {length}m")
            print(f"Adjusting to maximum size: {MAX_TABLE_DIMENSION}m x {MAX_TABLE_DIMENSION}m")
            width = min(width, MAX_TABLE_DIMENSION)
            length = min(length, MAX_TABLE_DIMENSION)
            
        table_dimensions = [width, length, 0.75]
        
        # 记录调整信息
        if width != raw_width or length != raw_length:
            print(f"Table dimensions adjusted for scene_id={scene_id}: {raw_width}m x {raw_length}m -> {width}m x {length}m")

        # Store the prepared task data
        design_tasks.append({
            'idx': idx, # Keep original index for output filename consistency
            'scene_id': scene_id,
            'no_of_objects': no_of_objects,
            'user_input': user_environment,
            'table_dimensions': table_dimensions
        })

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON string for item {idx}: {e}. Skipping.")
    except KeyError as e:
        print(f"Missing key for item {idx}: {e}. Skipping.")
    except Exception as e: # Catch other potential errors during preprocessing
        print(f"Unexpected error preprocessing item {idx}: {e}. Skipping.")
    

print(f"Preprocessing complete. Found {len(design_tasks)} unique tasks.")

# --- Worker function for processing a single design task ---
def process_single_task(task, base_output_dir):
    """
    Processes a single design task.
    """
    idx = task['idx']
    scene_id = task['scene_id']
    print(f"\nProcessing task original_idx={idx}, scene_id={scene_id}")

    output_filename = f"{scene_id}.json"
    output_filepath = os.path.join(base_output_dir, output_filename)

    run_idesign_for_this_task = False # Default to False

    if not os.path.exists(output_filepath):
        print(f"Output file {output_filepath} does not exist. Proceeding with IDesign for task idx={idx}, scene_id={scene_id}.")
        run_idesign_for_this_task = True
    else: # File exists
        try:
            file_size = os.path.getsize(output_filepath)
            if file_size == 0:
                print(f"Output file {output_filepath} exists and is 0-byte empty. Proceeding with IDesign for task idx={idx}, scene_id={scene_id}.")
                run_idesign_for_this_task = True
            else:
                # File exists and is not 0-byte. Check if it's "semantically empty" (contains only {}).
                try:
                    with open(output_filepath, 'r', encoding='utf-8') as f:
                        content = json.load(f)
                    # Check if content is an empty dictionary
                    if isinstance(content, dict) and not content:
                        print(f"Output file {output_filepath} exists and contains only '{{}}' (size: {file_size} bytes). Proceeding with IDesign for task idx={idx}, scene_id={scene_id}.")
                        run_idesign_for_this_task = True
                    else:
                        print(f"Output file {output_filepath} exists, is not 0-byte, and content is not '{{}}' (size: {file_size} bytes). Skipping IDesign for task idx={idx}, scene_id={scene_id}.")
                        # run_idesign_for_this_task remains False
                except json.JSONDecodeError:
                    # File exists, not 0-byte, but is not valid JSON.
                    # Treat as non-empty to avoid overwriting potentially important, though malformed, data.
                    print(f"Output file {output_filepath} exists, is not 0-byte, but is not valid JSON (size: {file_size} bytes). Skipping IDesign for task idx={idx}, scene_id={scene_id}.")
                    # run_idesign_for_this_task remains False
                except Exception as e_read: # Other errors during reading the file content
                    print(f"Error reading content of existing file {output_filepath} (size: {file_size} bytes) for task idx={idx}, scene_id={scene_id}: {e_read}. Skipping IDesign.")
                    # run_idesign_for_this_task remains False
        except OSError as e_stat: # Error with os.path.getsize itself
            print(f"Error checking size of {output_filepath} for task idx={idx}, scene_id={scene_id}: {e_stat}. Skipping IDesign.")
            # run_idesign_for_this_task remains False

    if run_idesign_for_this_task:
        # 设置超时时间（秒）
        TIMEOUT = 30  # 5分钟
        start_time = time.time()
        
        try:
            # 创建IDesign实例
            i_design = IDesign(no_of_objects=task['no_of_objects'],
                               user_input=task['user_input'],
                               table_dimensions=task['table_dimensions'])

            # 创建初始设计（设置超时）
            create_design_timeout = min(180, TIMEOUT * 0.6)  # 最多用总超时的60%时间
            create_start_time = time.time()
            i_design.create_initial_design()
            
            # 检查是否超时
            if time.time() - start_time > TIMEOUT:
                print(f"Task timed out during create_initial_design for scene_id={scene_id}")
                with open(output_filepath, 'w') as f:
                    json.dump({}, f)
                return f"Timeout during create_initial_design: {scene_id}"
            
            # 检查对象数量是否与预期一致，如果不一致，打印警告但继续执行
            if i_design.scene_graph and isinstance(i_design.scene_graph.get("objects_on_table"), list):
                actual_objects = len(i_design.scene_graph["objects_on_table"])
                if actual_objects != task['no_of_objects']:
                    print(f"Warning: Expected {task['no_of_objects']} objects but got {actual_objects} for scene_id={scene_id}. Continuing anyway.")
                    
                # 如果没有生成任何对象，直接保存空结果并返回
                if actual_objects == 0:
                    print(f"Warning: No objects generated for scene_id={scene_id}. Saving empty result.")
                    i_design.to_json(output_filepath)
                    return f"Warning: No objects generated: {scene_id}"
            
            # 继续执行后续步骤，即使对象数量不匹配
            # 每个步骤都检查超时
            if time.time() - start_time <= TIMEOUT:
                i_design.correct_design()
            else:
                print(f"Task timed out before correct_design for scene_id={scene_id}")
                i_design.to_json(output_filepath)
                return f"Partial completion (timed out before correct_design): {scene_id}"
                
            if time.time() - start_time <= TIMEOUT:
                i_design.refine_design()
            else:
                print(f"Task timed out before refine_design for scene_id={scene_id}")
                i_design.to_json(output_filepath)
                return f"Partial completion (timed out before refine_design): {scene_id}"
                
            if time.time() - start_time <= TIMEOUT:
                i_design.create_object_clusters(verbose=False)
            else:
                print(f"Task timed out before create_object_clusters for scene_id={scene_id}")
                i_design.to_json(output_filepath)
                return f"Partial completion (timed out before create_object_clusters): {scene_id}"
                
            if time.time() - start_time <= TIMEOUT:
                i_design.backtrack(verbose=False)
            else:
                print(f"Task timed out before backtrack for scene_id={scene_id}")
                i_design.to_json(output_filepath)
                return f"Partial completion (timed out before backtrack): {scene_id}"

            # 保存结果
            i_design.to_json(output_filepath)
            total_time = time.time() - start_time
            print(f"Successfully saved result to {output_filepath} for task idx={idx}, scene_id={scene_id} in {total_time:.1f} seconds")
            return f"Success: {scene_id} ({total_time:.1f}s)"
        except Exception as e:
            print(f"Error processing task original_idx={idx}, scene_id={scene_id}: {e}")
            traceback.print_exc()  # 打印详细的错误堆栈
            try:
                with open(output_filepath, 'w') as f:
                    json.dump({}, f) # Save an empty JSON object on error
                print(f"Saved empty JSON '{{}}' to {output_filepath} due to error for task idx={idx}, scene_id={scene_id}.")
                return f"Error (saved empty '{{}}'): {scene_id} - {str(e)}"
            except IOError as io_e:
                print(f"Failed to save empty JSON for error case (idx={idx}, scene_id={scene_id}): {io_e}")
                return f"Error (failed to save empty '{{}}'): {scene_id} - {str(io_e)}"
    else:
        # Task was skipped because file existed and was non-empty, or an error occurred during check
        return f"Skipped: {scene_id} (file exists and is non-empty or check error)"


# --- 2. IDesign Execution (Serial Processing) ---
print("\nStarting IDesign processing in serial mode...")
output_dir = "/ssd1/zhen/tablellm/test_results"
os.makedirs(output_dir, exist_ok=True) # Ensure output directory exists

# 保存任务列表到文件，以便在程序中断后可以恢复
task_list_file = os.path.join(output_dir, "task_list.json")
with open(task_list_file, 'w') as f:
    json.dump(design_tasks, f)
print(f"Task list saved to {task_list_file}")

# 记录已完成的任务
completed_tasks_file = os.path.join(output_dir, "completed_tasks.txt")
completed_tasks = set()
if os.path.exists(completed_tasks_file):
    with open(completed_tasks_file, 'r') as f:
        completed_tasks = set(line.strip() for line in f)
    print(f"Loaded {len(completed_tasks)} completed tasks from {completed_tasks_file}")

results = []
total_tasks = len(design_tasks)
for task_idx, task in enumerate(design_tasks):
    scene_id = task['scene_id']
    
    # 检查任务是否已完成
    if scene_id in completed_tasks:
        print(f"Task {task_idx+1}/{total_tasks} (scene_id={scene_id}) already completed. Skipping.")
        results.append(f"Skipped (already completed): {scene_id}")
        continue
    
    print(f"\nProcessing task {task_idx+1}/{total_tasks} (scene_id={scene_id})...")
    
    try:
        # 设置每个任务的全局超时
        task_start_time = time.time()
        task_timeout = 600  # 10分钟
        
        # 处理任务
        result = process_single_task(task, output_dir)
        results.append(result)
        
        # 记录已完成的任务
        with open(completed_tasks_file, 'a') as f:
            f.write(f"{scene_id}\n")
        
        # 打印进度
        elapsed_time = time.time() - task_start_time
        print(f"Task {task_idx+1}/{total_tasks} completed in {elapsed_time:.1f} seconds. Result: {result}")
        
    except Exception as e:
        error_msg = f"Critical error processing task {task_idx+1}/{total_tasks} (scene_id={scene_id}): {e}"
        print(error_msg)
        traceback.print_exc()
        results.append(f"Critical error: {scene_id} - {str(e)}")
        
        # 保存空结果
        output_filepath = os.path.join(output_dir, f"{scene_id}.json")
        try:
            with open(output_filepath, 'w') as f:
                json.dump({}, f)
            print(f"Saved empty JSON '{{}}' to {output_filepath} due to critical error")
        except Exception as save_e:
            print(f"Failed to save empty JSON after critical error: {save_e}")

print("\n--- All tasks processing completed ---")
print(f"Number of results/exceptions collected: {len(results)}")

# 保存结果摘要
results_summary_file = os.path.join(output_dir, "results_summary.txt")
with open(results_summary_file, 'w') as f:
    for result in results:
        f.write(f"{result}\n")
print(f"Results summary saved to {results_summary_file}")

print("\nAll tasks have been processed or attempted.")