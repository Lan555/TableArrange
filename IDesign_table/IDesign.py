from autogen import GroupChatManager
import json
import re
import networkx as nx

from agents import create_agents
from agents import is_termination_msg, gpt4_config
from corrector_agents import get_corrector_agents
from refiner_agents import get_refiner_agents

from chats import GroupChat, ChatWithEngineer, LayoutCorrectorGroupChat, ObjectDeletionGroupChat, LayoutRefinerGroupChat 

from utils import get_table_priors, extract_list_from_json
from utils import preprocess_scene_graph, build_graph, remove_unnecessary_edges, handle_under_prepositions, get_conflicts, get_size_conflicts, get_object_from_scene_graph
from utils import get_object_from_scene_graph, get_rotation, get_cluster_objects, clean_and_extract_edges
from utils import get_cluster_size
from utils import get_possible_positions, is_point_bbox, calculate_overlap, get_topological_ordering, place_object, get_depth, get_visualization

import time

class IDesign:
    def __init__(self, no_of_objects, user_input, table_dimensions):
        self.no_of_objects = no_of_objects
        self.user_input = user_input
        self.table_dimensions = table_dimensions
        self.table_priors = get_table_priors(self.table_dimensions)
        # Normalize table_priors to ensure 'name' key
        if isinstance(self.table_priors, list):
            for prior in self.table_priors:
                if isinstance(prior, dict):
                    if 'name' not in prior and prior.get('new_object_id'):
                        prior['name'] = prior['new_object_id']
        self.scene_graph = None

    def create_initial_design(self):
        # 设置重试次数和超时时间
        max_retries = 3
        retry_count = 0
        timeout_seconds = 60
        
        while retry_count < max_retries:
            try:
                user_proxy, json_schema_debugger, interior_designer, interior_architect, engineer = create_agents(self.no_of_objects)
                
                # 初始化空的场景图，确保即使后续步骤失败也有一个有效的结构
                self.scene_graph = {"objects_on_table": []}
                
                groupchat = GroupChat(
                    agents=[user_proxy, interior_designer, interior_architect],
                    messages=[],
                    max_round=3
                )

                chat_with_engineer = ChatWithEngineer(
                    agents=[user_proxy, engineer, json_schema_debugger],
                    messages=[],
                    max_round=15
                )

                # 设置超时时间
                start_time = time.time()
                
                manager = GroupChatManager(groupchat=groupchat, llm_config=gpt4_config, is_termination_msg=is_termination_msg)
                user_proxy.initiate_chat(
                    manager,
                    message=f"""
                    The table has the size {self.table_dimensions[0]}m x {self.table_dimensions[1]}m x {self.table_dimensions[2]}m
                    User Preference (in triple backquotes):
                    ```
                    {self.user_input}    
                    ```
                    Table layout elements on the table (in triple backquotes):
                    ```
                    ['north_edge', 'south_edge', 'west_edge', 'east_edge', 'middle_of_table']
                    ```
                    json
                    """,
                )

                # 检查是否超时
                if time.time() - start_time > timeout_seconds:
                    print(f"Warning: Initial design creation timed out after {timeout_seconds} seconds. Retrying...")
                    retry_count += 1
                    continue

                # 安全解析设计师和建筑师的响应
                try:
                    if len(groupchat.messages) < 2:
                        print("Warning: Not enough messages in groupchat. Retrying...")
                        retry_count += 1
                        continue
                        
                    designer_content = groupchat.messages[-2].get("content", "{}")
                    architect_content = groupchat.messages[-1].get("content", "{}")
                    
                    if not isinstance(designer_content, str) or not isinstance(architect_content, str):
                        print("Warning: Designer or architect response is not a string. Retrying...")
                        retry_count += 1
                        continue
                    
                    designer_response = json.loads(designer_content)
                    architect_response = json.loads(architect_content)
                except (json.JSONDecodeError, IndexError) as e:
                    print(f"Warning: Failed to parse designer or architect response: {e}. Retrying...")
                    retry_count += 1
                    continue

                blocks_designer, blocks_architect = extract_list_from_json(designer_response), extract_list_from_json(architect_response)
                
                # 检查是否获取到了有效的块
                if not blocks_designer or not blocks_architect:
                    print("Warning: Failed to extract valid blocks from designer or architect. Retrying...")
                    retry_count += 1
                    continue
                
                # 检查设计师和建筑师的块数是否一致，如果不一致，取较短的长度
                if len(blocks_designer) != len(blocks_architect):
                    print(f"Warning: The number of blocks from the designer ({len(blocks_designer)}) and architect ({len(blocks_architect)}) are different.")
                    min_blocks = min(len(blocks_designer), len(blocks_architect))
                    blocks_designer = blocks_designer[:min_blocks]
                    blocks_architect = blocks_architect[:min_blocks]
                
                json_data = {"objects_on_table": []}

                # 限制处理的块数，避免处理太多导致超时
                max_blocks = min(len(blocks_designer), 10)
                
                for i, (d_block, a_block) in enumerate(zip(blocks_designer[:max_blocks], blocks_architect[:max_blocks])):
                    # 检查是否超时
                    if time.time() - start_time > timeout_seconds:
                        print(f"Warning: Block processing timed out after {timeout_seconds} seconds. Using partial results.")
                        break
                        
                    try:
                        engineer.reset(), json_schema_debugger.reset()
                        prompt = str(d_block) + "\n" + str(a_block)

                        object_ids = [item.get("new_object_id", f"unknown_{idx}") for idx, item in enumerate(json_data.get("objects_on_table", []))]

                        block_manager = GroupChatManager(
                            groupchat=chat_with_engineer, 
                            llm_config=gpt4_config, 
                            human_input_mode="NEVER", 
                            is_termination_msg=is_termination_msg
                        )
                        
                        user_proxy.initiate_chat(
                            block_manager,
                            message=f"""
                            Table layout elements on the table (in triple backquotes):
                            ```
                            ['north_edge', 'south_edge', 'west_edge', 'east_edge', 'middle_of_table']
                            ```
                            Array of objects on the table (in triple backquotes):
                            ```
                            {object_ids}
                            ```
                            Objects to be placed on the table (in triple backquotes):
                            ```
                            {prompt}
                            ```
                            json
                            """,
                        )
                        
                        # 安全解析工程师的响应
                        if len(chat_with_engineer.messages) < 2:
                            print(f"Warning: Not enough messages in chat_with_engineer for block {i}. Skipping this block.")
                            continue
                            
                        engineer_content = chat_with_engineer.messages[-2].get("content", "{}")
                        
                        if not isinstance(engineer_content, str):
                            print(f"Warning: Engineer response for block {i} is not a string. Skipping this block.")
                            continue
                        
                        # 尝试多种方式解析JSON
                        try:
                            engineer_json = json.loads(engineer_content)
                        except json.JSONDecodeError:
                            # 尝试从响应中提取JSON块
                            pattern = r'```json\s*([^`]+)\s*```'
                            match = re.search(pattern, engineer_content, re.DOTALL)
                            if match:
                                try:
                                    engineer_json = json.loads(match.group(1))
                                except json.JSONDecodeError:
                                    print(f"Warning: Failed to parse JSON from engineer response for block {i}. Skipping this block.")
                                    continue
                            else:
                                print(f"Warning: No JSON block found in engineer response for block {i}. Skipping this block.")
                                continue
                        
                        # 合并对象
                        if isinstance(engineer_json, dict) and "objects_on_table" in engineer_json and isinstance(engineer_json["objects_on_table"], list):
                            json_data["objects_on_table"].extend(engineer_json["objects_on_table"])
                        else:
                            print(f"Warning: Invalid structure in engineer response for block {i}. Skipping this block.")
                            
                    except Exception as block_error:
                        print(f"Warning: Error processing block {i}: {block_error}. Skipping this block.")
                        continue
                
                # 确保scene_graph被正确初始化，即使生成的对象数量与预期不符
                self.scene_graph = json_data
                
                # 打印实际生成的对象数量
                actual_objects = len(self.scene_graph.get("objects_on_table", []))
                expected_objects = self.no_of_objects
                print(f"Expected {expected_objects} objects, actually generated {actual_objects} objects.")
                
                # 如果生成的对象数量为0，但重试次数未达到最大值，则重试
                if actual_objects == 0 and retry_count < max_retries - 1:
                    print("Warning: Generated 0 objects. Retrying...")
                    retry_count += 1
                    continue
                
                # 规范化对象，确保所有对象都有一个'name'键
                self._normalize_objects()
                
                # 成功完成，退出循环
                break
                
            except Exception as e:
                print(f"Error in create_initial_design: {e}")
                retry_count += 1
                print(f"Retrying... ({retry_count}/{max_retries})")
                
                # 确保即使出错也有一个有效的scene_graph
                self.scene_graph = {"objects_on_table": []}
                
                # 如果已经达到最大重试次数，则不再重试
                if retry_count >= max_retries:
                    print(f"Reached maximum retries ({max_retries}). Continuing with empty scene_graph.")
                    break

        # 将规范化对象的代码移到单独的方法中
        self._normalize_objects()

def _normalize_objects(self):
    """规范化对象，确保所有对象都有一个'name'键"""
    if self.scene_graph and isinstance(self.scene_graph.get("objects_on_table"), list):
        for obj_data in self.scene_graph["objects_on_table"]:
            if isinstance(obj_data, dict):
                # Try to establish 'name' from common ID keys in order of preference
                if 'name' not in obj_data:
                    if obj_data.get('new_object_id'):
                        obj_data['name'] = obj_data['new_object_id']
                    elif obj_data.get('name_id'): # from refiner schema
                        obj_data['name'] = obj_data['name_id']
                    elif obj_data.get('instance'): # from initial input file schema
                        obj_data['name'] = obj_data['instance']
                    elif obj_data.get('object_id'): # from some placement schemas
                        obj_data['name'] = obj_data['object_id']

    def correct_design(self, verbose=False, auto_prune=True):
        # 检查scene_graph是否已初始化
        if not self.scene_graph or not isinstance(self.scene_graph.get("objects_on_table"), list):
            print("Warning: scene_graph or objects_on_table is not properly initialized. Initializing empty scene_graph.")
            self.scene_graph = {"objects_on_table": []}
            return

        # Correct Spatial Conflicts
        try:
            scene_graph = preprocess_scene_graph(self.scene_graph["objects_on_table"])
            G = build_graph(scene_graph)
            G = remove_unnecessary_edges(G)
            G, scene_graph = handle_under_prepositions(G, scene_graph)

            conflicts = get_conflicts(G, scene_graph)
        except Exception as e:
            print(f"Error initializing graph or detecting conflicts: {e}")
            # 确保即使出错也有一个有效的scene_graph
            self.scene_graph["objects_on_table"] = []
            return

        if verbose:
            print("-------------------CONFLICTS-------------------")
            for conflict in conflicts:
                print(conflict)
                print("\n\n")

        user_proxy, spatial_corrector_agent, json_schema_debugger, object_deletion_agent = get_corrector_agents()

        # 更严格的限制
        max_conflict_loops = 5  # 进一步减少最大循环次数
        conflict_loops = 0
        consecutive_failures = 0  # 跟踪连续失败次数
        total_conflicts_processed = 0  # 跟踪总共处理的冲突数量

        # 添加时间限制
        start_time = time.time()
        time_limit = 300  # 5分钟时间限制

        while len(conflicts) > 0:
            conflict_loops += 1
            total_conflicts_processed += 1
            
            # 检查是否达到任何终止条件
            current_time = time.time()
            if (conflict_loops > max_conflict_loops or 
                consecutive_failures >= 3 or 
                total_conflicts_processed > 20 or  # 总冲突处理限制
                current_time - start_time > time_limit):  # 时间限制
                print("Warning: Reached termination condition in conflict correction. Breaking to avoid infinite loop.")
                print(f"- Loops: {conflict_loops}/{max_conflict_loops}")
                print(f"- Consecutive failures: {consecutive_failures}/3")
                print(f"- Total conflicts processed: {total_conflicts_processed}/20")
                print(f"- Time elapsed: {current_time - start_time:.1f}/{time_limit} seconds")
                break

            current_conflict_to_resolve = conflicts[0]

            # 如果冲突太复杂，直接跳过
            if len(str(current_conflict_to_resolve)) > 1000:
                print(f"Warning: Conflict is too complex (length: {len(str(current_conflict_to_resolve))}). Skipping.")
                conflicts.pop(0)
                continue

            try:
                spatial_corrector_agent.reset(), json_schema_debugger.reset()
                groupchat = LayoutCorrectorGroupChat(
                    agents=[user_proxy, spatial_corrector_agent, json_schema_debugger],
                    messages=[],
                    max_round=5  # 减少最大轮次
                )
                manager = GroupChatManager(groupchat=groupchat, llm_config=gpt4_config, is_termination_msg=is_termination_msg)
                user_proxy.initiate_chat(
                    manager,
                    message=f"""Please provide a correction for the following spatial conflict.
    The conflict is:
    {current_conflict_to_resolve}

    Your response MUST be a JSON object enclosed in triple backticks, starting with ```json and ending with ```.
    The JSON object should have a key "corrected_object" with the details of the correction. For example:
    ```json
    {{
    "corrected_object": {{
        "new_object_id": "object_id_to_correct",
        "is_on_the_table": true,
        "facing": "front",
        "placement": {{
        "objects_on_table": [
            {{
            "object_id": "another_object_id",
            "preposition": "left of",
            "is_adjacent": true
            }}
        ]
        }}
    }}
    }}
    ```"""
                )

                # Robustly parse the agent's response
                if len(groupchat.messages) < 2:
                    print(f"Error: Not enough messages in groupchat to get agent's correction. Skipping this conflict.")
                    conflicts.pop(0)
                    consecutive_failures += 1
                    continue

                correction_message_content = groupchat.messages[-2].get("content")
                if not isinstance(correction_message_content, str):
                    print(f"Error: Agent's correction message content is not a string. Skipping this conflict.")
                    conflicts.pop(0)
                    consecutive_failures += 1
                    continue

                # 尝试多种方式解析JSON
                json_string_from_agent = None
                pattern = r'```json\s*([^`]+)\s*```'
                match_obj = re.search(pattern, correction_message_content, re.DOTALL)

                if match_obj:
                    json_string_from_agent = match_obj.group(1)
                else:
                    # 尝试直接解析整个内容
                    try:
                        json.loads(correction_message_content)
                        json_string_from_agent = correction_message_content
                    except:
                        pass

                if not json_string_from_agent:
                    print(f"Error: Could not extract JSON from agent's response. Skipping this conflict.")
                    conflicts.pop(0)
                    consecutive_failures += 1
                    continue

                try:
                    correction_json = json.loads(json_string_from_agent)
                except json.JSONDecodeError:
                    print(f"Error: Invalid JSON in agent's response. Skipping this conflict.")
                    conflicts.pop(0)
                    consecutive_failures += 1
                    continue
                
                corrected_object_data = correction_json.get("corrected_object")
                if not isinstance(corrected_object_data, dict):
                    print(f"Error: 'corrected_object' key is missing or not a dictionary. Skipping this conflict.")
                    conflicts.pop(0)
                    consecutive_failures += 1
                    continue

                object_id_to_correct = corrected_object_data.get("new_object_id")
                if object_id_to_correct is None:
                    print(f"Error: 'new_object_id' is missing in 'corrected_object' data. Skipping this conflict.")
                    conflicts.pop(0)
                    consecutive_failures += 1
                    continue

                # 尝试查找对象，如果找不到就跳过
                corr_obj = get_object_from_scene_graph(object_id_to_correct, scene_graph)
                if corr_obj is None:
                    print(f"Warning: Object '{object_id_to_correct}' not found in scene_graph. Skipping this correction.")
                    conflicts.pop(0)
                    consecutive_failures += 1
                    continue

                # 安全应用修正，使用默认值
                if "is_on_the_table" in corrected_object_data:
                    corr_obj["is_on_the_table"] = corrected_object_data["is_on_the_table"]
                if "facing" in corrected_object_data:
                    corr_obj["facing"] = corrected_object_data["facing"]
                if "placement" in corrected_object_data:
                    corr_obj["placement"] = corrected_object_data["placement"]

                # 重建图并更新冲突
                try:
                    G = build_graph(scene_graph)
                    G = remove_unnecessary_edges(G)
                    G, scene_graph = handle_under_prepositions(G, scene_graph)
                    
                    # 检查是否解决了冲突
                    new_conflicts = get_conflicts(G, scene_graph)
                    
                    # 即使冲突没有减少，也移除当前冲突，避免死循环
                    conflicts.pop(0)
                    
                    # 只有当冲突明显减少时，才更新冲突列表
                    if len(new_conflicts) < len(conflicts) - 1:
                        conflicts = new_conflicts
                        consecutive_failures = 0  # 重置连续失败计数
                    else:
                        consecutive_failures += 1
                except Exception as e_graph:
                    print(f"Error rebuilding graph: {e_graph}. Skipping this conflict.")
                    conflicts.pop(0)
                    consecutive_failures += 1
                    continue
                    
            except Exception as e_apply:
                print(f"Error applying correction: {e_apply}. Skipping this conflict.")
                conflicts.pop(0)
                consecutive_failures += 1
                continue

        # 大幅简化尺寸冲突处理
        if auto_prune:
            try:
                size_conflicts = get_size_conflicts(G, scene_graph, self.user_input, self.table_priors, verbose)
                
                # 如果有太多尺寸冲突，只处理前几个
                if len(size_conflicts) > 5:
                    print(f"Warning: Too many size conflicts ({len(size_conflicts)}). Only processing the first 5.")
                    size_conflicts = size_conflicts[:5]
                    
                if verbose and size_conflicts:
                    print("-------------------SIZE CONFLICTS-------------------")
                    for conflict_item in size_conflicts:
                        print(conflict_item)
                        print("\n\n")

                # 更严格的限制
                max_size_conflict_loops = 2
                size_conflict_loops = 0
                
                # 添加时间限制
                size_start_time = time.time()
                size_time_limit = 120  # 2分钟时间限制

                while len(size_conflicts) > 0:
                    size_conflict_loops += 1
                    
                    # 检查是否达到任何终止条件
                    current_time = time.time()
                    if (size_conflict_loops > max_size_conflict_loops or 
                        current_time - size_start_time > size_time_limit):
                        print("Warning: Reached termination condition in size conflict resolution.")
                        break

                    # 简单地删除第一个冲突中提到的第一个对象
                    current_size_conflict = size_conflicts[0]
                    try:
                        # 从冲突描述中提取第一个对象ID
                        conflict_str = str(current_size_conflict)
                        object_match = re.search(r'([a-zA-Z0-9_]+)(?:\s+is|\s+and)', conflict_str)
                        
                        if object_match:
                            object_to_delete = object_match.group(1)
                            
                            # 检查对象是否存在于图中
                            if G.has_node(object_to_delete):
                                # 删除对象及其依赖
                                descendants = nx.descendants(G, object_to_delete)
                                objs_to_delete = descendants.union({object_to_delete})
                                
                                # 更新场景图和图结构
                                scene_graph = [x for x in scene_graph if isinstance(x, dict) and x.get("new_object_id") not in objs_to_delete]
                                
                                for obj_id_to_remove in objs_to_delete:
                                    if G.has_node(obj_id_to_remove):
                                        G.remove_node(obj_id_to_remove)
                                
                                # 重建图和冲突列表
                                G = build_graph(scene_graph)
                                G = remove_unnecessary_edges(G)
                                G, scene_graph = handle_under_prepositions(G, scene_graph)
                                size_conflicts = get_size_conflicts(G, scene_graph, self.user_input, self.table_priors, verbose)
                            else:
                                # 对象不在图中，跳过这个冲突
                                size_conflicts.pop(0)
                        else:
                            # 无法从冲突中提取对象ID，跳过这个冲突
                            size_conflicts.pop(0)
                    except Exception as e_size:
                        print(f"Error processing size conflict: {e_size}. Skipping.")
                        size_conflicts.pop(0)
            except Exception as e_size_outer:
                print(f"Error in size conflict handling: {e_size_outer}. Skipping size conflict resolution.")

        # 最终更新场景图
        if self.scene_graph is None:
            self.scene_graph = {"objects_on_table": []}
        self.scene_graph["objects_on_table"] = scene_graph

    def refine_design(self, verbose=False):
        cluster_dict = get_cluster_objects(self.scene_graph["objects_on_table"])

        inputs = []
        for key, value in cluster_dict.items():
            key = list(key)
            if len(key[0]) == 2:
                parent_id = key[0][0][1]
                prep = key[0][1][1]
            elif len(key[0]) == 3:
                parent_id = key[0][1][1]
                prep = key[0][2][1]
            objs = value

            inputs.append((parent_id, prep, objs))

        if verbose:
            if inputs == []:
                print("No clusters found")
            for parent_id, prep, objs in inputs:
                print(f"Parent Object : {parent_id}")
                print(f"Children Objects : {objs}")
                print(f"The children objects are '{prep}' the parent object")
                print("\n")

        for parent_id, prep, obj_names in inputs:
            # Ensure all obj_names exist in the scene_graph before proceeding
            objs_data = []
            valid_input_for_refiner = True
            for obj_name_iter in obj_names:
                obj_data = get_object_from_scene_graph(obj_name_iter, self.scene_graph["objects_on_table"])
                if obj_data is None:
                    print(f"Warning [refine_design]: Child object '{obj_name_iter}' not found in scene_graph for parent '{parent_id}'. Skipping this group for refinement.")
                    valid_input_for_refiner = False
                    break
                objs_data.append(obj_data)
            if not valid_input_for_refiner:
                continue
            
            # objs = [get_object_from_scene_graph(obj, self.scene_graph["objects_on_table"]) for obj in obj_names] # Replaced by loop above
            objs_rot = [get_rotation(obj, self.scene_graph["objects_on_table"]) for obj in objs_data] # Use objs_data

            parent_obj_data = get_object_from_scene_graph(parent_id, self.scene_graph["objects_on_table"])
            if parent_obj_data is None:
                parent_obj_data_list = [prior for prior in self.table_priors if prior.get("new_object_id") == parent_id]
                if not parent_obj_data_list:
                    print(f"Warning [refine_design]: Parent object '{parent_id}' not found as prior or in scene_graph. Skipping this group for refinement.")
                    continue
                parent_obj_data = parent_obj_data_list[0]
            
            parent_obj_rot = get_rotation(parent_obj_data, self.scene_graph["objects_on_table"]) # Use parent_obj_data

            rot_diffs = [obj_rot - parent_obj_rot for obj_rot in objs_rot]
            direction_check = lambda diff, prep_val: (diff % 180 == 0 and prep_val in ["left of", "right of"]) or \
                                                (diff % 180 != 0 and prep_val in ["in front", "behind"]) or \
                                                (diff % 180 != 0 and prep_val == "on")
            
            constraints_list = []
            for name, diff in zip(obj_names, rot_diffs):
                expected_prep = '`behind` or `in front`' if direction_check(diff, prep) else '`left of` or `right of`'
                constraints_list.append(f"\t- For object '{name}', its relative orientation to parent '{parent_id}' suggests it should be placed {expected_prep} of other children objects in this cluster.")
            possibilities_str = "Constraints for relative placement within the cluster (based on orientation to parent):\n" + '\n'.join(constraints_list)


            user_proxy, layout_refiner, json_schema_debugger = get_refiner_agents()

            layout_refiner.reset(), json_schema_debugger.reset()
            groupchat = LayoutRefinerGroupChat(
                agents=[user_proxy, layout_refiner, json_schema_debugger],
                messages=[],
                max_round=5
            )
            manager = GroupChatManager(groupchat=groupchat, llm_config=gpt4_config, is_termination_msg=is_termination_msg)
            
            # Enhanced prompt for layout_refiner
            refiner_prompt = f"""
Context: We are refining the placement of a cluster of objects relative to each other. These objects are all children of a parent object.
Parent Object ID: {parent_id}
Children Object IDs in this cluster: {obj_names}
The children objects are all positioned '{prep}' the parent object '{parent_id}'.

{possibilities_str}

Task: Define the spatial relationships (e.g., "left of", "right of", "in front of", "behind") BETWEEN the children objects listed above.
The goal is to arrange them neatly and logically within their shared space relative to the parent.

Output Format:
Your response MUST be a JSON object enclosed in triple backticks (```json ... ```).
The JSON object must have a single key "children_objects", which is a list.
Each item in the "children_objects" list must be a dictionary representing one of the children.
Each child dictionary must contain:
  - "name_id": (string) The ID of the child object itself (from the list: {obj_names}).
  - "placement": (dictionary) Describes placement relative to *other children in the same cluster*.
    - "children_objects": (list) A list of dictionaries, where each dictionary defines a relationship to another child in the cluster.
      - "name_id": (string) The ID of the *other* child object this one is being placed relative to.
      - "preposition": (string) The spatial preposition (e.g., "left of", "right of", "in front of", "behind").
      - "is_adjacent": (boolean) Whether the two objects are directly adjacent.

Example for two children "apple" and "banana" in a cluster:
```json
{{
  "children_objects": [
    {{
      "name_id": "apple",
      "placement": {{
        "children_objects": [
          {{
            "name_id": "banana",
            "preposition": "left of",
            "is_adjacent": true
          }}
        ]
      }}
    }}
    // Banana's relationships would implicitly be defined or could also be listed if needed.
    // Ensure relationships are consistent and cover the cluster.
  ]
}}
```
Please provide the refined relationships for the given children objects: {obj_names}.
"""
            user_proxy.initiate_chat(manager, message=refiner_prompt)

            if len(groupchat.messages) < 2:
                print(f"Error [refine_design]: Not enough messages from LayoutRefinerGroupChat for parent '{parent_id}'. Skipping refinement for this group.")
                continue
            
            refiner_response_content = groupchat.messages[-2].get("content")
            if not isinstance(refiner_response_content, str):
                print(f"Error [refine_design]: LayoutRefiner response content is not a string or is missing for parent '{parent_id}'. Content: {refiner_response_content}. Skipping refinement.")
                continue

            json_match = re.search(r'```json\s*([^`]+)\s*```', refiner_response_content, re.DOTALL)
            if not json_match:
                print(f"Error [refine_design]: LayoutRefiner response for parent '{parent_id}' did not contain the expected JSON block. Response: {refiner_response_content}. Skipping.")
                continue
            
            json_string_from_refiner = json_match.group(1)
            try:
                new_relationships = json.loads(json_string_from_refiner)
            except json.JSONDecodeError as e:
                print(f"Error [refine_design]: Failed to decode JSON from LayoutRefiner for parent '{parent_id}'. JSON string: '{json_string_from_refiner}'. Error: {e}. Skipping.")
                continue

            children_objects_list = new_relationships.get("children_objects")
            if isinstance(children_objects_list, dict) and "items" in children_objects_list: # Handle potential {"items": []} structure
                children_objects_list = children_objects_list.get("items")

            if not isinstance(children_objects_list, list):
                print(f"Warning [refine_design]: 'children_objects' in refiner response for parent '{parent_id}' is not a list or is missing. Response: {new_relationships}. Skipping refinement for this group.")
                continue
            
            valid_children_for_processing = []
            invalid_name_ids = [] # For the original orientation check

            for child_dict in children_objects_list:
                if not isinstance(child_dict, dict):
                    print(f"Warning [refine_design]: Item in 'children_objects' is not a dictionary for parent '{parent_id}'. Item: {child_dict}. Skipping this item.")
                    continue
                
                child_name_id = child_dict.get("name_id")
                if child_name_id is None or child_name_id not in obj_names:
                    print(f"Warning [refine_design]: 'name_id' is missing or invalid in child object from refiner for parent '{parent_id}'. Child dict: {child_dict}. Skipping this child.")
                    continue

                child_obj_for_rot_check = get_object_from_scene_graph(child_name_id, self.scene_graph["objects_on_table"])
                if not child_obj_for_rot_check: # Should have been caught by earlier check, but for safety
                    print(f"Warning [refine_design]: Child object '{child_name_id}' for rotation check not found. Skipping orientation check for this child.")
                    valid_children_for_processing.append(child_dict) # Add to process, but orientation check might be incomplete
                    continue

                child_placement = child_dict.get("placement")
                if not isinstance(child_placement, dict):
                    print(f"Warning [refine_design]: 'placement' is missing or not a dictionary for child '{child_name_id}' from refiner (parent '{parent_id}'). Child dict: {child_dict}. Skipping placement for this child.")
                    # This child might still be valid if it has no outgoing relationships defined by refiner
                    valid_children_for_processing.append({"name_id": child_name_id, "placement": {"children_objects": []}}) # Add with empty placement
                    continue

                placement_children_list = child_placement.get("children_objects")
                if not isinstance(placement_children_list, list):
                    print(f"Warning [refine_design]: 'children_objects' under 'placement' is not a list for child '{child_name_id}' (parent '{parent_id}'). Placement: {child_placement}. Assuming no refined relationships from this child.")
                    # This child is still valid, but its placement definitions are ignored
                    valid_children_for_processing.append({"name_id": child_name_id, "placement": {"children_objects": []}})
                    continue
                
                # Original orientation check (for `invalid_name_ids`)
                # This check might need to be re-evaluated if it causes issues, or moved/adapted
                # For now, let's ensure the data for it is valid before attempting
                child_actual_rotation = get_rotation(child_obj_for_rot_check, self.scene_graph["objects_on_table"])

                for other_child_relation in placement_children_list:
                    if not isinstance(other_child_relation, dict): continue
                    other_child_id_in_relation = other_child_relation.get("name_id")
                    other_child_preposition = other_child_relation.get("preposition")

                    if other_child_id_in_relation is None or other_child_preposition is None:
                        continue # Skip malformed relation

                    obj_for_other_child_rot = get_object_from_scene_graph(other_child_id_in_relation, self.scene_graph["objects_on_table"])
                    if not obj_for_other_child_rot: continue

                    other_child_actual_rotation = get_rotation(obj_for_other_child_rot, self.scene_graph["objects_on_table"])
                    
                    # The original logic for invalid_name_ids, now with safer access:
                    # This logic compares the orientation of other_child_id_in_relation relative to the parent object,
                    # with the preposition used between child_name_id and other_child_id_in_relation.
                    # This seems complex and might be a source of logical issues if not perfectly aligned with agent's understanding.
                    # For now, retain with safer access.
                    if direction_check(other_child_actual_rotation - parent_obj_rot, prep) and \
                       other_child_preposition not in ["in front", "behind"]:
                        invalid_name_ids.append(child_name_id)
                        break # Break from inner loop for this child_name_id
                    elif not direction_check(other_child_actual_rotation - parent_obj_rot, prep) and \
                         other_child_preposition not in ["left of", "right of"]:
                        invalid_name_ids.append(child_name_id)
                        break # Break from inner loop for this child_name_id
                
                if child_name_id not in invalid_name_ids: # Only add if not marked invalid by the orientation check above
                    valid_children_for_processing.append(child_dict)


            # Filter out children that were marked by the orientation check
            # The list `valid_children_for_processing` already implicitly handles this by only adding valid items
            # However, the original code used `invalid_name_ids` to filter `new_relationships["children_objects"]` later.
            # Let's rebuild `new_relationships` structure for `clean_and_extract_edges`
            
            processed_new_relationships = {"children_objects": [
                child for child in valid_children_for_processing if child.get("name_id") not in invalid_name_ids
            ]}


            if verbose:
                print("Original invalid name IDs (based on orientation to parent vs. inter-child preposition): ", list(set(invalid_name_ids))) # Use set for unique
                print("Children objects being passed to clean_and_extract_edges: ", processed_new_relationships["children_objects"])
            
            if not processed_new_relationships["children_objects"]: # Check if the list is empty
                print(f"Info [refine_design]: No valid children relationships to process after filtering for parent '{parent_id}'. Skipping edge processing.")
                continue

            # Ensure clean_and_extract_edges can handle the structure
            edges, edges_to_flip = clean_and_extract_edges(processed_new_relationships, parent_id, verbose=verbose)

            prep_correspondences ={
                "left of" : "right of",
                "right of" : "left of",
                "in front" : "behind",
                "behind" : "in front",
            }

            # Apply the relationships: This loop also needs very robust access
            for child_def in processed_new_relationships.get("children_objects", []):
                if not isinstance(child_def, dict): continue
                
                current_child_name_id = child_def.get("name_id")
                if current_child_name_id is None: continue

                child_placement_def = child_def.get("placement")
                if not isinstance(child_placement_def, dict): continue
                
                relations_list = child_placement_def.get("children_objects", [])
                if not isinstance(relations_list, list): continue

                for r_dict in relations_list:
                    if not isinstance(r_dict, dict): continue
                    
                    other_obj_name_id = r_dict.get("name_id")
                    preposition_val = r_dict.get("preposition")
                    is_adjacent_val = r_dict.get("is_adjacent") # Ensure this key is expected by your logic

                    if other_obj_name_id is None or preposition_val is None or is_adjacent_val is None:
                        print(f"Warning [refine_design]: Incomplete relation data for {current_child_name_id} -> {other_obj_name_id}. Skipping this relation.")
                        continue

                    if (current_child_name_id, other_obj_name_id) in edges:
                        to_flip = edges_to_flip.get((current_child_name_id, other_obj_name_id), False) # Default to False if somehow missing
                        
                        target_obj_for_update_id = other_obj_name_id if to_flip else current_child_name_id
                        source_obj_for_relation_id = current_child_name_id if to_flip else other_obj_name_id
                        final_preposition = prep_correspondences.get(preposition_val) if to_flip else preposition_val

                        if final_preposition is None: # Preposition not in correspondences and needs flipping
                             print(f"Warning [refine_design]: Preposition '{preposition_val}' not in correspondence map for flipping. Relation: {current_child_name_id} -> {other_obj_name_id}. Skipping.")
                             continue

                        corr_obj_to_update = get_object_from_scene_graph(target_obj_for_update_id, self.scene_graph["objects_on_table"])
                        if corr_obj_to_update:
                            if "placement" not in corr_obj_to_update or not isinstance(corr_obj_to_update.get("placement"), dict):
                                corr_obj_to_update["placement"] = {} # Initialize if missing or wrong type
                            if "objects_on_table" not in corr_obj_to_update["placement"] or not isinstance(corr_obj_to_update["placement"].get("objects_on_table"), list):
                                corr_obj_to_update["placement"]["objects_on_table"] = [] # Initialize if missing or wrong type
                            
                            corr_obj_to_update["placement"]["objects_on_table"].append({
                                "object_id": source_obj_for_relation_id, 
                                "preposition": final_preposition, 
                                "is_adjacent": is_adjacent_val
                            })
                        else:
                            print(f"Warning [refine_design]: Could not find object '{target_obj_for_update_id}' in scene_graph to update placement. Relation: {current_child_name_id} -> {other_obj_name_id}")
            # End of the main loop for parent_id, prep, obj_names

    def create_object_clusters(self, verbose=False):
        # Assign the rotations
        if not self.scene_graph or not isinstance(self.scene_graph.get("objects_on_table"), list):
            print("Warning [create_object_clusters]: scene_graph or objects_on_table is not properly initialized. Skipping.")
            return

        for obj in self.scene_graph["objects_on_table"]:
            if not isinstance(obj, dict): # Ensure obj is a dictionary
                print(f"Warning [create_object_clusters]: Encountered non-dict item in objects_on_table: {obj}. Skipping rotation assignment for this item.")
                continue
            rot = get_rotation(obj, self.scene_graph["objects_on_table"]) # obj is passed to get_rotation
            obj["rotation"] = {"z_angle" : rot}
        
        TABLE_LAYOUT_ELEMENTS = ["north_edge", "south_edge", "west_edge", "east_edge", "middle_of_table"]

        # Ensure self.scene_graph["objects_on_table"] is used for building graph if it's the primary source
        graph_build_input = self.scene_graph.get("objects_on_table", [])
        if not isinstance(graph_build_input, list): # Should be a list of dicts
            print(f"Warning [create_object_clusters]: Input for build_graph is not a list: {graph_build_input}. Using empty list.")
            graph_build_input = []

        G = build_graph(graph_build_input)
        nodes = list(G.nodes()) # Make a copy of nodes if G is modified in loop (though not directly here)

        # Create clusters
        for node in nodes:
            if node not in TABLE_LAYOUT_ELEMENTS:
                cluster_size, children_objs = get_cluster_size(node, G, self.scene_graph["objects_on_table"])
                if verbose:
                    print("Node: ", node)
                    print("Cluster size: ", cluster_size)
                    print("Children: ", children_objs)
                    print("\n")
                
                node_obj = get_object_from_scene_graph(node, self.scene_graph["objects_on_table"])
                if node_obj: # Check if node_obj was found
                    # Ensure cluster_size is a dictionary before using .get()
                    if not isinstance(cluster_size, dict):
                        print(f"Warning [create_object_clusters]: cluster_size for node '{node}' is not a dictionary: {cluster_size}. Skipping cluster assignment.")
                        continue

                    cluster_size_dict = {
                        "x_neg" : cluster_size.get("left of"), 
                        "x_pos" : cluster_size.get("right of"), 
                        "y_neg" : cluster_size.get("behind"), 
                        "y_pos" : cluster_size.get("in front")
                    }
                    node_obj["cluster"] = {"constraint_area" : cluster_size_dict}
                else:
                    print(f"Warning [create_object_clusters]: Node '{node}' (object ID) not found in scene_graph when trying to assign cluster.")

    def backtrack(self, verbose=False):
        # 检查scene_graph是否已初始化
        if not self.scene_graph or not isinstance(self.scene_graph.get("objects_on_table"), list):
            print("Warning [backtrack]: scene_graph or objects_on_table is not properly initialized. Initializing empty scene_graph.")
            self.scene_graph = {"objects_on_table": []}
            return

        # self.scene_graph is expected to be a dict like {"objects_on_table": [...]}
        # Get the list of objects, default to empty list if key missing or not a list
        objects_on_table = self.scene_graph.get("objects_on_table", [])
        if not isinstance(objects_on_table, list):
            if verbose:
                print(f"Warning [backtrack]: 'objects_on_table' in self.scene_graph was not a list (type: {type(objects_on_table)}). Using empty list.")
            objects_on_table = []

        # 确保table_priors是有效的列表
        if not isinstance(self.table_priors, list):
            print(f"Warning [backtrack]: self.table_priors is not a list (type: {type(self.table_priors)}). Initializing as empty list.")
            self.table_priors = []

        # working_scene_graph is the list of all objects (placed + priors) for this method's operations
        working_scene_graph = objects_on_table + self.table_priors
        
        prior_ids = ["north_edge", "south_edge", "west_edge", "east_edge", "middle_of_table"]
        
        # Initialize point_bbox for all valid new_object_ids in working_scene_graph
        valid_ids_for_point_bbox = [item["new_object_id"] for item in working_scene_graph if isinstance(item, dict) and "new_object_id" in item]
        point_bbox = dict.fromkeys(valid_ids_for_point_bbox, False)
        
        # Place objects with absolute positions
        for item in working_scene_graph:
            if not isinstance(item, dict) or "new_object_id" not in item:
                if verbose: print(f"Debug [backtrack]: Skipping item in absolute positioning due to malformed structure or missing 'new_object_id': {item}")
                continue
            
            item_id = item["new_object_id"]
            if item_id in prior_ids:
                continue

            # 'placement' is required for get_possible_positions
            if "placement" not in item or not isinstance(item.get("placement"), dict):
                if verbose: print(f"Info [backtrack]: Item '{item_id}' missing valid 'placement', cannot determine absolute position.")
                continue

            try:
                possible_pos = get_possible_positions(item_id, working_scene_graph, self.table_dimensions)
                
                overlap = None
                if possible_pos: # Ensure possible_pos is not empty
                    overlap = possible_pos[0]
                    for i in range(1, len(possible_pos)):
                        # Ensure calculate_overlap handles None for its first argument if needed, though here overlap starts non-None if possible_pos is non-empty.
                        overlap = calculate_overlap(overlap, possible_pos[i]) 
                
                if overlap is not None and is_point_bbox(overlap):
                    item["position"] = {"x" : overlap[0], "y" : overlap[2], "z" : overlap[4]}
                    if item_id in point_bbox: # Check if item_id is a key before assigning
                        point_bbox[item_id] = True
            except Exception as e:
                print(f"Warning [backtrack]: Error processing absolute position for {item_id}: {e}")
                continue
        
        # Filter out priors for backtracking layout logic
        scene_graph_wo_layout = [item for item in working_scene_graph if isinstance(item, dict) and item.get("new_object_id") not in prior_ids]
        
        if not scene_graph_wo_layout:
            if verbose:
                print("Backtrack: No non-prior objects to process. Finalizing scene graph.")
            self.scene_graph = {"objects_on_table": working_scene_graph} # Update instance member with properly structured dict
            return

        try:
            depth_scene_graph = get_depth(scene_graph_wo_layout)
            
            if not depth_scene_graph or not isinstance(depth_scene_graph, dict): 
                if verbose:
                    print(f"Backtrack: Depth graph is empty or invalid (type: {type(depth_scene_graph)}). Cannot determine max depth. Finalizing scene graph.")
                self.scene_graph = {"objects_on_table": working_scene_graph}
                return

            depth_values = [v for v in depth_scene_graph.values() if isinstance(v, (int, float))]
            if not depth_values:
                if verbose:
                    print("Backtrack: No valid depth values found in depth_scene_graph. Finalizing scene graph.")
                self.scene_graph = {"objects_on_table": working_scene_graph}
                return
                
            max_depth = max(depth_values)
            
            if verbose:
                print("Max depth: ", max_depth)
                print("Depth scene graph: ", depth_scene_graph)
                print("Point BBox: ", {key: value for key, value in point_bbox.items() if value})
                # get_visualization(working_scene_graph, self.table_priors) 
                for obj_vis in scene_graph_wo_layout: 
                    if isinstance(obj_vis, dict) and "position" in obj_vis: 
                        print(obj_vis.get("new_object_id", "Unknown Object"), obj_vis["position"])
            
            try:
                topological_order = get_topological_ordering(scene_graph_wo_layout)
                if not isinstance(topological_order, list):
                    if verbose:
                        print(f"Warning [backtrack]: topological_order is not a list (type: {type(topological_order)}). Using empty list.")
                    topological_order = []
                
                if verbose:
                    print("Topological order: ", topological_order)
                
                max_iterations = 50  # 防止无限循环
                iteration_count = 0
                d = 1
                while d <= max_depth and iteration_count < max_iterations:
                    iteration_count += 1
                    if verbose:
                        print("Depth: ", d)
                    error_flag = False
                    
                    nodes_at_current_depth = [node_id for node_id in topological_order if depth_scene_graph.get(node_id) == d]
                    if verbose:
                        print(f"Nodes at depth {d}:", nodes_at_current_depth)
                    
                    errors_in_pass = {} 
                    for node_id in nodes_at_current_depth:
                        if point_bbox.get(node_id, False): 
                            continue
                        
                        obj_to_place = next((item for item in scene_graph_wo_layout if isinstance(item, dict) and item.get("new_object_id") == node_id), None)
                        if obj_to_place is None:
                            if verbose: print(f"Warning [backtrack]: Object with id '{node_id}' not found in scene_graph_wo_layout during placement.")
                            continue

                        try:
                            errors_in_pass = place_object(obj_to_place, working_scene_graph, self.table_dimensions, errors={}, verbose=verbose)
                            if verbose:
                                print(f"Placement errors for {obj_to_place.get('new_object_id', 'Unknown Object')}:", errors_in_pass)
                        except Exception as place_error:
                            print(f"Error [backtrack]: Failed to place object {node_id}: {place_error}")
                            errors_in_pass = {"error": str(place_error)}  # 标记有错误发生

                        if errors_in_pass:
                            if d > 1:
                                d -= 1
                                if verbose:
                                    print("Reducing depth to: ", d)
                            
                            error_flag = True
                            for del_item in scene_graph_wo_layout: 
                                if not isinstance(del_item, dict): continue
                                del_item_id = del_item.get("new_object_id")
                                if del_item_id and depth_scene_graph.get(del_item_id, float('inf')) >= d: 
                                    if "position" in del_item and not point_bbox.get(del_item_id, False):
                                        if verbose:
                                            print("Deleting position for: ", del_item_id)
                                        del del_item["position"]
                            break 
                                
                    if not error_flag:
                        d += 1
            except Exception as topo_error:
                print(f"Error [backtrack]: Error in topological processing: {topo_error}")
                # 继续执行，不中断处理
                
        except Exception as depth_error:
            print(f"Error [backtrack]: Error in depth processing: {depth_error}")
            # 即使出错，也确保更新scene_graph
        
        if verbose:
            # get_visualization(working_scene_graph, self.table_priors)
            print("Backtracking complete.")
        
        # 确保最终结果是正确的格式
        self.scene_graph = {"objects_on_table": working_scene_graph}
    
    def to_json(self, filename="scene_graph.json"):
        # Save the scene graph to a json file
        with open(filename, "w") as file:
            json.dump(self.scene_graph, file, indent=4)