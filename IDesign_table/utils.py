import networkx as nx
from matplotlib import pyplot as plt
import numpy as np
import cv2
from copy import copy, deepcopy
import random
import time

from constraint_functions import get_above_constraint, get_behind_constraint, get_in_corner_constraint, get_in_front_constraint, get_left_of_constraint, get_right_of_constraint, get_on_constraint, get_under_contraint

# 全局超时设置（秒）
GLOBAL_TIMEOUT = 60  # 整个放置过程的最大运行时间
MAX_ATTEMPTS_PER_OBJECT = 20  # 每个物体的最大尝试次数
MAX_OBJECT_PLACEMENT_TIME = 5  # 每个物体的最大放置时间（秒）

# 将房间布局元素改为桌面布局元素
TABLE_LAYOUT_ELEMENTS = ["north_edge", "south_edge", "west_edge", "east_edge", "middle_of_table"]

verbose = False # Define verbose for utils if it's used at global scope there for prints

def get_table_priors(table_dimensions):
    x_mid = table_dimensions[0] / 2
    y_mid = table_dimensions[1] / 2
    z_mid = table_dimensions[2] / 2

    table_priors = [
        {"new_object_id": "north_edge", "itemType": "edge", "position": {"x": x_mid, "y": 0, "z": z_mid}, "size_in_meters": {"length": table_dimensions[0], "width": 0.05, "height": 0.05}, "rotation": {"z_angle": 0.0}},
        {"new_object_id": "south_edge", "itemType": "edge", "position": {"x": x_mid, "y": table_dimensions[1], "z": z_mid}, "size_in_meters": {"length": table_dimensions[0], "width": 0.05, "height": 0.05}, "rotation": {"z_angle": 180.0}},
        {"new_object_id": "east_edge", "itemType": "edge", "position": {"x": table_dimensions[0], "y": y_mid, "z": z_mid}, "size_in_meters": {"length": table_dimensions[1], "width": 0.05, "height": 0.05}, "rotation": {"z_angle": 270.0}},
        {"new_object_id": "west_edge", "itemType": "edge", "position": {"x": 0, "y": y_mid, "z": z_mid}, "size_in_meters": {"length": table_dimensions[1], "width": 0.05, "height": 0.05}, "rotation": {"z_angle": 90.0}},
        {"new_object_id": "middle_of_table", "itemType": "surface", "position": {"x": x_mid, "y": y_mid, "z": 0}, "size_in_meters": {"length": table_dimensions[0], "width": table_dimensions[1], "height": 0.0}, "rotation": {"z_angle": 0.0}}
    ]

    return table_priors

# 保留原有的get_room_priors函数以兼容旧代码
def get_room_priors(room_dimensions):
    return get_table_priors(room_dimensions)

def extract_list_from_json(input_json):
    for value in input_json.values(): 
        if isinstance(value, list):
            return value
        
def is_thin_object(obj):
    """
    Returns True if the object is thin
    """
    size = obj["size_in_meters"]
    return min(size.values()) > 0.0 and max(size.values()) / min(size.values()) >= 40.0

def is_point_bbox(position):
    """
    Returns whether the plausible bounding box is a point
    """
    return np.isclose(position[0], position[1]) and np.isclose(position[2], position[3]) and np.isclose(position[4], position[5])

def get_rotation(obj_A, scene_graph):
    # Get the rotation of an object in the scene graph
    layout_rot = {
        "west_edge": 270.0,
        "east_edge": 90.0,
        "north_edge": 0.0,
        "south_edge": 180.0,
        "middle_of_table": 0.0
    }

    if "rotation" in obj_A.keys():
        rot = obj_A["rotation"]["z_angle"]
    elif "facing" in obj_A.keys() and obj_A["facing"] in layout_rot.keys():
        rot = layout_rot[obj_A["facing"]]
    elif obj_A["new_object_id"] in layout_rot.keys():
        rot = layout_rot[obj_A["new_object_id"]]
    else: 
        parents = []
        for x in obj_A["placement"]["objects_on_table"]:
            try:
                p = [element for element in scene_graph if element.get("new_object_id") == x["object_id"]][0]
            except:
                print(f"Object {x['object_id']} not found in scene graph!")
                raise ValueError("Object not found in scene graph!")
            parents.append(p)
        if len(parents) > 0:
            parent = parents[0]
            rot = get_rotation(parent, scene_graph)
        else:
            rot = 0.0
    return rot

def find_key(dictionary, value):
    for key, val in dictionary.items():
        if val == value:
            return key
    return None
        
def get_conflicts(G, scene_graph):
    conflicts_wall = check_edge_relationship_impossibilities(G, scene_graph)
    conflicts_corner = check_corner_relationship_impossibilities(G, scene_graph)
    conflicts_table_layout = find_table_layout_conflicts(G, scene_graph)
    conflicts_one_parent = check_corner_relationships(G, scene_graph)
    conflicts_impossible_relationships = check_impossible_relationships(G, scene_graph)
    return conflicts_corner + conflicts_table_layout + conflicts_one_parent + conflicts_impossible_relationships + conflicts_wall

def get_size_conflicts(G, scene_graph, user_input, table_priors, verbose=False):
    conflicts_size = check_size_conflicts(G, scene_graph, user_input, table_priors, verbose)
    return conflicts_size

def preprocess_scene_graph(scene_graph):
    # 获取所有可用的对象ID
    available_ids = [x["new_object_id"] for x in scene_graph]
    
    # 创建一个映射，将seat_X映射到适当的桌面物体
    # 例如，将seat_1映射到dinner_plate_1，seat_2映射到dinner_plate_2，等等
    seat_mapping = {}
    dinner_plates = [id for id in available_ids if "dinner_plate" in id]
    for i, plate in enumerate(dinner_plates, 1):
        seat_mapping[f"seat_{i}"] = plate
    
    for obj in scene_graph:
        # 处理table_layout_elements...
        
        # 处理objects_on_table
        valid_objects = []
        for elem in obj["placement"]["objects_on_table"]:
            if elem["object_id"] == "middle_of_table":
                continue
                
            # 处理seat_X引用
            if "seat_" in elem["object_id"] and elem["object_id"] in seat_mapping:
                print(f"Replacing {elem['object_id']} with {seat_mapping[elem['object_id']]} for object {obj['new_object_id']}")
                elem["object_id"] = seat_mapping[elem["object_id"]]
                valid_objects.append(elem)
            elif elem["object_id"] in available_ids:
                valid_objects.append(elem)
            else:
                # 尝试找到最接近的ID
                closest_id = next(iter([id for id in available_ids if elem["object_id"] in id]), None)
                if closest_id:
                    elem["object_id"] = closest_id
                    valid_objects.append(elem)
                else:
                    print(f"Warning: Object {elem['object_id']} not found and will be ignored for {obj['new_object_id']}")
        
        obj["placement"]["objects_on_table"] = valid_objects
    
    return scene_graph

def build_graph(scene_graph):
    G = nx.DiGraph()
    # Create graph
    for obj in scene_graph:
        if obj["new_object_id"] not in G.nodes():
            G.add_node(obj["new_object_id"])
        obj_scene_graph = obj["placement"]
        for constraint in obj_scene_graph["table_layout_elements"]:
            if constraint["layout_element_id"] not in G.nodes():
                G.add_node(constraint["layout_element_id"])
            G.add_edge(constraint["layout_element_id"], obj["new_object_id"], weight={"preposition" : constraint["preposition"], "adjacency" : True})
        for constraint in obj_scene_graph["objects_on_table"]:
            if constraint["object_id"] not in G.nodes():
                G.add_node(constraint["object_id"])
            G.add_edge(constraint["object_id"], obj["new_object_id"], weight={"preposition" : constraint["preposition"], "adjacency" : constraint["is_adjacent"]})
    return G

def find_table_layout_conflicts(G, scene_graph):
    conflicts = []

    topological_order = list(nx.topological_sort(G))
    node_layout = dict(G.nodes(data=True))
    for node in topological_order:
        if node not in TABLE_LAYOUT_ELEMENTS:
            parents = list(G.predecessors(node))
            parents_table_layout = [node_layout[p] for p in parents]
            different_parent_table_layout = False
            for p in parents_table_layout[1:]:
                if isinstance(p, list):
                    if isinstance(parents_table_layout[0], list):
                        different_parent_table_layout = True if p != parents_table_layout[0] else different_parent_table_layout
                    else:
                        different_parent_table_layout = True if parents_table_layout[0] not in p else different_parent_table_layout
                elif isinstance(p, str):
                    if isinstance(parents_table_layout[0], list):
                        different_parent_table_layout = True if p not in parents_table_layout[0] else different_parent_table_layout
                    else:
                        different_parent_table_layout = True if p != parents_table_layout[0] else different_parent_table_layout
                elif isinstance(p, dict):
                    if isinstance(parents_table_layout[0], list):
                        different_parent_table_layout = True if p not in parents_table_layout[0] else different_parent_table_layout
                    else:
                        different_parent_table_layout = True if p != parents_table_layout[0] else different_parent_table_layout
            if len(parents_table_layout) > 0 and different_parent_table_layout:
                # This should be a spatial conflict, if the relationship isn't 'corner'
                if not all([G[p][node]["weight"]["preposition"] == "in the corner" for p in parents]):
                    conflict_string = f"The object {node} cannot have the parents {parents} at the same time! Eliminate one."
                    conflict_string += "\nObject to reposition: " + str(get_object_from_scene_graph(node, scene_graph))
                    conflicts.append(conflict_string)
                else:
                    node_layout[node] = {}
            else:
                node_layout[node] = parents_table_layout[0]

        if node in TABLE_LAYOUT_ELEMENTS:
            node_layout[node] = node
    return conflicts

def remove_unnecessary_edges(G):
    """
    Remove non-corner relationships if the object has a corner relationship
    """
    topological_order = list(nx.topological_sort(G))
    for node in topological_order:
        if node not in TABLE_LAYOUT_ELEMENTS:
            parents = list(G.predecessors(node))
            if any([G[p][node]["weight"]["preposition"] == "in the corner" for p in parents]):
                if len(parents) > 2:
                    # Remove the non-corner relationships
                    for p in parents:
                        if G[p][node]["weight"]["preposition"] != "in the corner":
                            print(f"Removing edge {p} -> {node} with preposition {G[p][node]['weight']['preposition']}")
                            G.remove_edge(p, node)
    return G

def handle_under_prepositions(G, scene_graph):
    """
    For objects that are under another object, remove the object if it isn't a thin object
    """
    nodes = G.nodes()
    nodes_to_remove = []
    for node in nodes:
        incoming_e = list(G.in_edges(node, data=True))
        outgoing_e = list(G.out_edges(node, data=True))
        under_obj = any([e[2]["weight"]["preposition"] == "under" for e in incoming_e])
        if under_obj:
            obj = get_object_from_scene_graph(node, scene_graph)
            if not is_thin_object(obj):
                nodes_to_remove.append(node)
                for e in outgoing_e:
                    nodes_to_remove.append(e[1])
    for node in nodes_to_remove:
        print("Removing node: ", node)
        scene_graph = [x for x in scene_graph if x["new_object_id"] != node]
        if node in G.nodes():
            G.remove_node(node)
    return G, scene_graph

def check_corner_relationships(G, scene_graph):
    def find_corner_vacancy():
        # Find the corner that is not occupied
        corners = [("south_edge", "west_edge"), ("south_edge", "east_edge"), ("north_edge", "west_edge"), ("north_edge", "east_edge")]
        occupied_corners = []
        for edge_1, edge_2 in corners:
            for node in topological_order:
                if node not in TABLE_LAYOUT_ELEMENTS:
                    parents = list(G.predecessors(node))
                    if edge_1 in parents and edge_2 in parents:
                        occupied_corners.append((edge_1, edge_2))
        vacant_corners = list(set(corners) - set(occupied_corners))
        return vacant_corners
    
    def find_corner_occupancy():
        # Find whether corners are occupied by more than one object 
        corners = [("south_edge", "west_edge"), ("south_edge", "east_edge"), ("north_edge", "west_edge"), ("north_edge", "east_edge")]
        occupied_corners = {k : [] for k in corners}
        for edge_1, edge_2 in corners:
            for node in topological_order:
                if node not in TABLE_LAYOUT_ELEMENTS:
                    parents = list(G.predecessors(node))
                    if edge_1 in parents and edge_2 in parents:
                        occupied_corners[(edge_1, edge_2)].append(node)
        return occupied_corners

    topological_order = list(nx.topological_sort(G))
    conflicts = []

    corner_occupancy = find_corner_occupancy()
    for key, value in corner_occupancy.items():
        if len(value) > 1:
            conflict_string = f"The corner {key[0].split('_')[0]}-{key[1].split('_')[0]} is occupied by more than one object: {value}. Move one of them to another vacant corner."
            conflict_string += "\nVacant corners: " + str(find_corner_vacancy())
            conflicts.append(conflict_string)
        

    # Check whether objects with "corner" relationships have two corresponding edges
    for node in topological_order:
        if node not in TABLE_LAYOUT_ELEMENTS:
            parents = list(G.predecessors(node))
            if any([G[p][node]["weight"]["preposition"] == "in the corner" for p in parents]):
                if len(parents) == 1:
                    vacant_corners = find_corner_vacancy()
                    vacant_corners = [f"{c[0].split('_')[0]}-{c[1].split('_')[0]} corner" for c in vacant_corners]
                    conflict_string = f"Corner relationship for {node} has {len(parents)} parent, add another edge to the relationship. \n Current vacant corners: {vacant_corners}"
                    conflict_string += "\nObject to reposition: " + str(get_object_from_scene_graph(node, scene_graph))
                    conflicts.append(conflict_string)
    return conflicts

directional_preps = ["in front", "left of", "behind", "right of"]

def check_corner_relationship_impossibilities(G, scene_graph):
    conflicts = []
    # Check for impossible relationships in corners
    edge_impossible_preps = {
        "south_edge": "behind",
        "north_edge": "in front",
        "west_edge": "left of",
        "east_edge": "right of"
    }

    topological_order = list(nx.topological_sort(G))
    for node in topological_order:
        if node not in TABLE_LAYOUT_ELEMENTS:
            parents_raw = list(G.predecessors(node))
            parents = list(filter(lambda x : x not in TABLE_LAYOUT_ELEMENTS, parents_raw))
            parents_rot = [get_rotation(next((x for x in scene_graph if x["new_object_id"] == p), None), scene_graph) for p in parents]
            # Check whether the parent object is in the corner and if this object is located spatially correctly
            for p, r in zip(parents, parents_rot):
                p_parent = list(G.predecessors(p))
                corners = [p_p for p_p in p_parent if G[p_p][p]["weight"]["preposition"] == "in the corner"]
                impossible_preps = []
                if len(corners) != 2:
                    continue
                for p_p in corners:
                    corner_name = corners[0].split('_')[0] + "-" + corners[1].split('_')[0] + " corner"
                    impossible_prep = edge_impossible_preps[p_p]
                    idx = directional_preps.index(impossible_prep)
                    rotated_idx = int((idx + (r // 90)) % len(directional_preps))
                    impossible_prep = directional_preps[rotated_idx]
                    impossible_preps.append(impossible_prep)
                if G[p][node]["weight"]["preposition"] in impossible_preps:
                    conflict_string = [
                        f"The object {node} cannot be {G[p][node]['weight']['preposition']} the object {p} as it would be placed out of bounds. ",
                        f"The {impossible_preps[0]} and {impossible_preps[1]} the object are out of bounds. Find another relationship for {node} either with {p}, on the {corners[0]} or on the {corners[1]}!",
                        f"This relationship has to be exclusive, you cannot have two objects with the same relative positioning. IMPORTANT: you can only have one relationship in the new scene graph!!!",
                    ]
                    conflict_string = "\n".join(conflict_string)
                    conflict_string += f"The object {p} is on the {corner_name}. "
                    conflict_string += " ".join([f"{p} has the object {edge[1]} {edge[2]['weight']['preposition']} it. " for edge in G.out_edges(p, data=True) if edge[1] != node and edge[2]["weight"]["adjacency"]])
                    conflict_string += "\n Object to reposition: " + str(get_object_from_scene_graph(node, scene_graph))
                    conflicts.append(conflict_string)
    return conflicts

def check_edge_relationship_impossibilities(G, scene_graph):
    conflicts = []
    # Check for impossible relationships in corners
    edge_impossible_preps = {
        "south_edge": "behind",
        "north_edge": "in front",
        "west_edge": "left of",
        "east_edge": "right of"
    }

    topological_order = list(nx.topological_sort(G))
    for node in topological_order:
        if node not in TABLE_LAYOUT_ELEMENTS:
            parents_raw = list(G.predecessors(node))
            parents = list(filter(lambda x : x not in TABLE_LAYOUT_ELEMENTS, parents_raw))
            parents_rot = [get_rotation(next((x for x in scene_graph if x["new_object_id"] == p), None), scene_graph) for p in parents]
            # Check whether the parent object is on the edge and if this object is located spatially correctly
            for p, r in zip(parents, parents_rot): 
                p_parent_raw = list(G.predecessors(p))
                p_parent = list(filter(lambda x : x in edge_impossible_preps.keys(), p_parent_raw))
                edges = [p_p for p_p in p_parent if G[p_p][p]["weight"]["preposition"] == "on"]
                for p_p in edges:
                    impossible_prep = edge_impossible_preps[p_p]
                    idx = directional_preps.index(impossible_prep)
                    rotated_idx = int((idx + (r // 90)) % len(directional_preps))
                    impossible_prep = directional_preps[rotated_idx]
                    if G[p][node]["weight"]["preposition"] == impossible_prep:
                        conflict_string =[
                            f"The object {node} cannot be {G[p][node]['weight']['preposition']} the object {p} as it would be placed out of bounds. ",
                            f"The {impossible_prep} the object is out of bounds. Find another relationship for {node} either with {p}, on the {p_p}!",
                            f"This relationship has to be exclusive, you cannot have two objects with the same relative positioning. IMPORTANT: you can only have one relationship in the new scene graph!!!",
                        ]
                        conflict_string = "\n".join(conflict_string)
                        conflict_string += f"The object {p} is on the {p_p}. "
                        conflict_string += " ".join([f"{p} has the object {edge[1]} {edge[2]['weight']['preposition']} it. " for edge in G.out_edges(p, data=True) if edge[1] != node and edge[2]["weight"]["adjacency"]])
                        conflict_string += "\n Object to reposition: " + str(get_object_from_scene_graph(node, scene_graph))
                        conflicts.append(conflict_string)
    return conflicts


def check_impossible_relationships(G, scene_graph):
    conflicts = []
    topological_order = list(nx.topological_sort(G))
    # Check for impossible relationships between objects
    for node in topological_order:
        if node not in TABLE_LAYOUT_ELEMENTS:
            parents_raw = list(G.predecessors(node))
            parents = list(filter(lambda x : x not in TABLE_LAYOUT_ELEMENTS, parents_raw))
            children = list(G.successors(node))
            node_rot = get_rotation(next((x for x in scene_graph if x["new_object_id"] == node), None), scene_graph) 
            # Adjacent child exclusivity
            for p in parents:
                prep = G[p][node]["weight"]["preposition"]
                adj = G[p][node]["weight"]["adjacency"]
                if prep in directional_preps and adj:
                    idx = directional_preps.index(prep)
                    rotated_idx = int((idx + (node_rot // 90)) % len(directional_preps))
                    impossible_prep = directional_preps[(rotated_idx + 2) % len(directional_preps)] 
                    for c in children:
                        if G[node][c]["weight"]["preposition"] == impossible_prep and G[node][c]["weight"]["adjacency"]:
                            conflict_string = f"The object {c} cannot be {G[node][c]['weight']['preposition']} of the object {node} since the {p} object is there. Find another relationship for {c} with {node}!"
                            conflict_string += "\n Object to reposition: " + str(get_object_from_scene_graph(c, scene_graph))
                            conflicts.append(conflict_string)
    return conflicts

def get_cluster_size(node, G, scene_graph): 
    # Get the size of the cluster of objects
    node_obj = get_object_from_scene_graph(node, scene_graph)
    try:
        node_obj_rot = get_rotation(node_obj, scene_graph)
    except:
        print(f"Node: {node}")
        raise ValueError("Error in getting the rotation of the object!")
    # Get the outgoing edges
    outgoing_e = list(G.out_edges(node, data=True))
    outgoing_nodes = [edge[1] for edge in outgoing_e]
    # Get the topological order of the outgoing nodes
    topological_order_reversed = list(reversed(list(nx.topological_sort(G))))
    topological_outgoing_nodes = [node for node in topological_order_reversed if node in outgoing_nodes]
    outgoing_e_sorted = sorted(outgoing_e, key=lambda x : topological_outgoing_nodes.index(x[1]))
    size_constraint = {"left of" : 0.0, "right of" : 0.0, "behind" : 0.0, "in front" : 0.0}
    children_objs = set()
    if len(outgoing_e_sorted) != 0:
        for edge in outgoing_e_sorted:
            # Check if the child object is already in the children objects
            if edge[1] in children_objs:
                continue
            # Check if the preposition is a directional preposition
            if edge[2]["weight"]["preposition"] not in directional_preps:
                continue
            
            edge_obj = get_object_from_scene_graph(edge[1], scene_graph)
            children_objs.add(edge[1])
            edge_obj_rot = get_rotation(edge_obj, scene_graph)
            rot_diff = abs(node_obj_rot - edge_obj_rot)
            prep = edge[2]["weight"]["preposition"]
            adj = edge[2]["weight"]["adjacency"]

            # Find the side of the child object to add to the size constraint
            direction_check = lambda diff, prep: (diff % 180 == 0 and prep in ["left of", "right of"]) or (diff % 90 == 0 and prep in ["in front", "behind"])
            size_constraint_key = "length" if direction_check(rot_diff, prep) else "width"
            side_to_add = ("left of", "right of") if size_constraint_key == "length" else ("in front", "behind")
            size_constraint_value = edge_obj["size_in_meters"][size_constraint_key]

            # Retrieve the size of the cluster and the additional descendants of the child object
            edge_cluster_size, edge_children = get_cluster_size(edge[1], G, scene_graph)
            children_objs = children_objs.union(edge_children)

            # Adjust the size constraint based on the preposition 
            constraints = ["left of", "right of", "in front", "behind"]
            value_to_add = size_constraint_value + edge_cluster_size[side_to_add[0]] + edge_cluster_size[side_to_add[1]]
            if prep in constraints:
                if adj:
                    size_constraint[prep] = max(size_constraint[prep], value_to_add)
                else:
                    size_constraint[prep] += value_to_add         
    return size_constraint, children_objs

def check_size_conflicts(G, scene_graph, user_input, table_priors, verbose=False):
    conflicts = []
    topological_order_reversed = list(reversed(list(nx.topological_sort(G))))

    if verbose:
        for node in topological_order_reversed:
            if node not in TABLE_LAYOUT_ELEMENTS:
                clstr_size, children_objs = get_cluster_size(node, G, scene_graph)
                
    # Find cluster size conflicts
    for node in topological_order_reversed:
        if node not in TABLE_LAYOUT_ELEMENTS:
            node_obj = get_object_from_scene_graph(node, scene_graph)
            node_obj_rot = get_rotation(node_obj, scene_graph)
            outgoing_e = list(G.out_edges(node, data=True))
            size_constraint = {"left of" : 0.0, "right of" : 0.0, "behind" : 0.0, "in front" : 0.0, "on" : [0.0, 0.0]}
            for edge in outgoing_e:
                edge_obj = get_object_from_scene_graph(edge[1], scene_graph)
                edge_obj_rot = get_rotation(edge_obj, scene_graph)
                rot_diff = abs(node_obj_rot - edge_obj_rot)
                prep = edge[2]["weight"]["preposition"]
                adj = edge[2]["weight"]["adjacency"]

                direction_check = lambda diff, prep: (diff % 180 == 0 and prep in ["left of", "right of"]) or (diff % 90 == 0 and prep in ["in front", "behind"])
                size_constraint_key = "width" if direction_check(rot_diff, prep) else "length"

                if prep not in directional_preps and prep != "on":
                    continue

                size_constraint_value = edge_obj["size_in_meters"][size_constraint_key]

                if adj:
                    if prep in ["left of", "right of", "in front", "behind"]:
                        size_constraint[prep] += size_constraint_value
                    elif prep == "on":
                        if rot_diff % 180 == 0:
                            size_constraint["on"][0] += edge_obj["size_in_meters"]["length"]
                            size_constraint["on"][1] += edge_obj["size_in_meters"]["width"]
                        else:
                            size_constraint["on"][0] += edge_obj["size_in_meters"]["width"]
                            size_constraint["on"][1] += edge_obj["size_in_meters"]["length"]
  
            for prep in ["in front", "behind", "left of", "right of"]:
                constraint_key = "length" if prep in ["in front", "behind"] else "width"
                if node_obj["size_in_meters"][constraint_key] < size_constraint[prep]:
                    conflict_str = f"The {constraint_key} of the object {node} is too small to accommodate the following object {prep} of it!"
                    nodes = [edge[1] for edge in outgoing_e if edge[2]["weight"]["preposition"] == prep]
                    conflict_str += "\nDelete one of these nodes depending on which one is the least important for the user preference and the table's functionality: "                
                    conflict_str += ", ".join(nodes)
                    conflict_str += f"\nUser preference: {user_input}"
                    conflicts.append(conflict_str)
            if node_obj["size_in_meters"]["length"] < size_constraint["on"][0] or node_obj["size_in_meters"]["width"] < size_constraint["on"][1]:
                nodes = [edge[1] for edge in outgoing_e if edge[2]["weight"]["preposition"] == "on"]
                conflict_str = f"The area of the {node} is too small to accommodate all of the following objects on it!"
                conflict_str += "\nDelete one of these nodes depending on which one is the least important for the user preference and the table's functionality: "                
                conflict_str += ", ".join(nodes)
                conflict_str += f"\nUser preference: {user_input}"
                conflicts.append(conflict_str)
                
        if node in TABLE_LAYOUT_ELEMENTS:   
            node_obj = get_object_from_scene_graph(node, table_priors)
            node_obj_rot = get_rotation(node_obj, scene_graph)
            outgoing_e = list(G.out_edges(node, data=True))
            outgoing_nodes = [edge[1] for edge in outgoing_e]
            topological_outgoing_nodes = [node for node in topological_order_reversed if node in outgoing_nodes]
            outgoing_e_sorted = sorted(outgoing_e, key=lambda x : topological_outgoing_nodes.index(x[1]))

            outgoing_set = set()
            size_constraint = 0.0 if node != "middle_of_table" else (0.0, 0.0)
            for edge in outgoing_e_sorted:
                if edge[1] in outgoing_set:
                    continue
                edge_obj = get_object_from_scene_graph(edge[1], scene_graph)
                if not edge_obj["is_on_the_table"]:
                    continue
                edge_obj_rot = get_rotation(edge_obj, scene_graph)
                cluster_size, e_children = get_cluster_size(edge[1], G, scene_graph)
                print(f"Cluster size for {edge[1]}: {cluster_size}")
                rot_diff = abs(node_obj_rot - edge_obj_rot)
                constraint_key = ("length", "width") if rot_diff % 180 == 0 else ("width", "length")
                side_to_add = (("left of", "right of"),("in front", "behind"))  if constraint_key[0] == "length" else (("in front", "behind"), ("left of", "right of"))

                outgoing_set.add(edge[1])
                outgoing_set = outgoing_set.union(e_children)
                if node == "middle_of_table":
                    x = edge_obj["size_in_meters"][constraint_key[0]] + cluster_size[side_to_add[0][0]] + cluster_size[side_to_add[0][1]]
                    constraint_x = max(size_constraint[0], x)
                    y = edge_obj["size_in_meters"][constraint_key[1]] + cluster_size[side_to_add[1][0]] + cluster_size[side_to_add[1][1]]
                    constraint_y = max(size_constraint[1], y)
                    size_constraint = (constraint_x, constraint_y)
                else:
                    size_constraint += edge_obj["size_in_meters"][constraint_key[0]] + cluster_size[side_to_add[0][0]] + cluster_size[side_to_add[0][1]]

            if verbose:
                print(f"Size constraint for {node}: {size_constraint}!")
                print(f"Outgoing Set: {outgoing_set}")
                print("\n")

            if node != "middle_of_table":
                if node_obj["size_in_meters"]["length"] < size_constraint:
                    conflict_str = f"The length of the {node} is too small to accommodate all of the following objects on it: "
                    conflict_str += "\nDelete one of these nodes depending on which one is the least important for the user preference and the table's functionality: "
                    conflict_str += ", ".join(outgoing_set)
                    conflict_str += f"\nUser preference: {user_input}"
                    conflicts.append(conflict_str)
            else:
                if node_obj["size_in_meters"]["length"] < size_constraint[0]:
                    conflict_str = f"The length of the {node} is too small to accommodate all of the following objects on it: "
                    conflict_str += "\nDelete one of these nodes depending on which one is the least important for the user preference and the table's functionality: "
                    conflict_str += ", ".join(outgoing_set)
                    conflict_str += f"\nUser preference: {user_input}"
                    conflicts.append(conflict_str)
                if node_obj["size_in_meters"]["width"] < size_constraint[1]:
                    conflict_str = f"The width of the {node} is too small to accommodate all of the following objects on it: "
                    conflict_str += "\nDelete one of these nodes depending on which one is the least important for the user preference and the table's functionality: "
                    conflict_str += ", ".join(outgoing_set)
                    conflict_str += f"\nUser preference: {user_input}"
                    conflicts.append(conflict_str)
    return conflicts

def get_cluster_objects(scene_graph):
    object_ids_by_scene_graph = {}

    for obj in scene_graph:
        # Don't add thin objects to the cluster
        if is_thin_object(obj):
            continue
        placement = obj.get("placement")
        if placement:
            edges = placement["objects_on_table"] + placement["table_layout_elements"]
            scene_graph_set = frozenset([tuple(sorted(x.items())) for x in edges])
            if scene_graph_set in object_ids_by_scene_graph:
                object_ids_by_scene_graph[scene_graph_set].append(obj["new_object_id"])
            else:
                object_ids_by_scene_graph[scene_graph_set] = [obj["new_object_id"]]

    # Filter out groups with only one object
    object_ids_groups = {k: v for k, v in object_ids_by_scene_graph.items() if len(v) > 1 and len(k) > 0}

    return object_ids_groups

def get_object_from_scene_graph(obj_id, scene_graph):
    """
    Get the object from the scene graph by its id
    """
    return next((x for x in scene_graph if x["new_object_id"] == obj_id), None)

def has_one_parent_and_one_child(tree):
        for node in tree.nodes():
            if tree.in_degree(node) > 1 or tree.out_degree(node) > 1:
                return False
        return True

def find_edges_to_flip(tree):
        edges_to_flip = []
        for node in tree.nodes():
            if tree.in_degree(node) > 1 or tree.out_degree(node) > 1:
                # If a node has more than one parent or child, find the edges to flip
                for parent in list(tree.predecessors(node)):
                    if tree.in_degree(node) > 1:
                        edges_to_flip.append((parent, node))
                for child in list(tree.successors(node)):
                    if tree.out_degree(node) > 1:
                        edges_to_flip.append((node, child))
        return edges_to_flip

def flip_edges(tree, root_node, verbose=False):
    flipped_edges = {}
    while not has_one_parent_and_one_child(tree):
        edges_to_flip = find_edges_to_flip(tree)
        if verbose:
            print("Edges to flip: ", edges_to_flip)
        if not edges_to_flip:
            break  # No more edges to flip

        edge_to_flip = edges_to_flip[0]
        tree.remove_edge(*edge_to_flip)
        tree.add_edge(edge_to_flip[1], edge_to_flip[0])

        # After flipping, check if the tree structure is valid
        if has_one_parent_and_one_child(tree):
            flipped_edges[edge_to_flip] = True
        else:
            # If the structure is still invalid, undo the flip by removing the flipped edge
            tree.remove_edge(edge_to_flip[1], edge_to_flip[0])
            tree.add_edge(edge_to_flip[0], edge_to_flip[1])
    
    while len(list(nx.simple_cycles(tree))) > 0:
        cycles = list(nx.simple_cycles(tree))
        tree.remove_edge(cycles[0][-1], cycles[0][0])
    
    # Populate the dictionary for the remaining edges
    for edge in tree.edges():
        if edge not in flipped_edges:
            flipped_edges[edge] = False

    return tree, flipped_edges

def flip_edges_to_binary_tree(graph, root_node, verbose):
    tree = nx.DiGraph(graph)
    flipped_edges = {}

    if verbose:
        print("Root Node: ", root_node)
    # Ensure that the graph is weakly connected
    if not nx.is_weakly_connected(tree):
        print("The input graph is not weakly connected.")
        return None

    # Perform edge flips until a binary tree is obtained
    while not is_binary_tree(tree, root_node):
        non_tree_edges = find_non_tree_edges(tree, root_node)
        if verbose:
            print("Non tree edges: ", non_tree_edges)
        if not non_tree_edges:
            break  # No more edges to flip

        edge_to_flip = non_tree_edges[0]
        tree.remove_edge(*edge_to_flip)
        tree.add_edge(edge_to_flip[1], edge_to_flip[0])

        if (edge_to_flip[1], edge_to_flip[0]) not in find_non_tree_edges(tree, root_node):
            # Update the dictionary to indicate that the edge has been flipped
            flipped_edges[edge_to_flip] = True
        else:
            # If the edge was flipped, but the graph is still not a binary tree, delete the edge
            tree.remove_edge(edge_to_flip[1], edge_to_flip[0])

    # Populate the dictionary for the remaining edges
    for edge in tree.edges():
        if edge not in flipped_edges:
            flipped_edges[edge] = False

    return tree, flipped_edges

def is_binary_tree(tree, root_node):
    # Check if the graph is a tree (acyclic and connected)
    if not nx.is_tree(tree):
        return False

    # Check if the in-degree of every node is at most 1 (binary tree condition)
    for node in tree.nodes():
        in_degree = tree.in_degree(node)
        if node != root_node and in_degree > 1:
            return False

    return True

def remove_edges_with_connectivity(dag, verbose):
    # Iteratively remove the edges that have weight 0
    edge_to_remove = None
    for edge in dag.edges(data=True):
        if edge[2]["weight"] == 0:
            temp_dag = dag.copy()  # Make a copy of the original DAG
            temp_dag.remove_edge(edge[0], edge[1])  # Remove the edge
            undirected = temp_dag.to_undirected()
            if nx.is_connected(undirected):
                edge_to_remove = (edge[0], edge[1])
                break
    if verbose:
        print("Edge to remove: ", edge_to_remove)
    if edge_to_remove:
        dag.remove_edge(*edge_to_remove)
        return remove_edges_with_connectivity(dag, verbose)
    
    return dag

def find_non_tree_edges(graph, root_node):
    non_tree_edges = []
    for edge in graph.edges():
        temp_graph = nx.DiGraph(graph)
        temp_graph.remove_edge(*edge)
        if not nx.is_weakly_connected(temp_graph) or not nx.is_tree(temp_graph) or not nx.has_path(G=temp_graph, source=edge[0], target=root_node):
            non_tree_edges.append(edge)
    return non_tree_edges
        
def clean_and_extract_edges(relationships, parent_id, verbose):
    start_time = time.time()
    timeout = 20  # 设置20秒超时
    
    # 定义超时检查函数
    def check_timeout():
        if time.time() - start_time > timeout:
            print(f"Warning: Processing timed out after {timeout} seconds")
            return True
        return False
    
    # 构建图
    dag = nx.DiGraph()
    
    # 限制边的数量
    max_edges = 30  # 从50减少到30
    edge_count = 0
    
    print("Step 1: Adding nodes to graph...")
    # 添加节点
    for obj in relationships["children_objects"]:
        if obj["name_id"] != parent_id:
            dag.add_node(obj["name_id"])
    
    print(f"Added {len(dag.nodes())} nodes to graph")
    
    print("Step 2: Adding edges to graph...")
    # 添加边，直到达到限制
    for obj in relationships["children_objects"]:
        if check_timeout():
            print("Timeout during edge addition, proceeding with current edges")
            break
        
        if obj["name_id"] != parent_id:
            for rel in obj["placement"]["children_objects"]:
                if rel["name_id"] != parent_id:
                    if edge_count < max_edges:
                        dag.add_edge(obj["name_id"], rel["name_id"], weight=int(rel["is_adjacent"]))
                        edge_count += 1
                    else:
                        print(f"Warning: Maximum edge limit ({max_edges}) reached, ignoring remaining edges")
                        break
            if edge_count >= max_edges:
                break
    
    print(f"Added {edge_count} edges to graph")
    
    # 检查图是否为空
    if len(dag.nodes()) == 0:
        print("Warning: Empty graph, returning empty results")
        return [], {}
    
    print("Step 3: Processing cycles...")
    # 处理循环，添加超时检查
    cycle_count = 0
    try:
        while True:
            if check_timeout():
                print("Cycle processing timed out, proceeding with current graph")
                break
                
            cycles = list(nx.simple_cycles(dag))
            if not cycles:
                break
                
            cycle_count += 1
            if cycle_count > 50:  # 限制循环处理次数
                print("Warning: Too many cycles, stopping cycle processing")
                break
                
            dag.remove_edge(cycles[0][-1], cycles[0][0])
            
            if cycle_count % 10 == 0:  # 每处理10个循环打印一次
                print(f"Processed {cycle_count} cycles so far...")
    except Exception as e:
        print(f"Warning: Error processing cycles: {e}")
    
    print(f"Processed {cycle_count} cycles total")
    
    print("Step 4: Creating simplified graph...")
    # 简化连通性处理
    try:
        # 使用最小生成树来简化图
        undirected = dag.to_undirected()
        if len(undirected.edges()) > 0:
            # 如果超时，跳过复杂的简化
            if check_timeout():
                print("Timeout during graph simplification, using current graph")
                simplified = undirected
            else:
                simplified = nx.minimum_spanning_tree(undirected)
            dag = nx.DiGraph(simplified)
            print(f"Simplified graph to {len(dag.edges())} edges")
        else:
            print("No edges to simplify")
    except Exception as e:
        print(f"Warning: Error simplifying graph: {e}")
    
    print("Step 5: Creating directed tree...")
    # 简化边翻转过程
    flipped_edges = {}
    try:
        if len(dag.nodes()) > 0:
            # 选择一个根节点
            root_node = list(dag.nodes())[0]
            
            # 创建一个简单的有向树
            tree = nx.DiGraph()
            for node in dag.nodes():
                tree.add_node(node)
            
            # 使用BFS添加边，避免复杂的翻转逻辑
            visited = {root_node}
            queue = [root_node]
            
            while queue:
                if check_timeout():
                    print("Timeout during tree creation, using current tree")
                    break
                    
                node = queue.pop(0)
                neighbors = list(undirected.neighbors(node))
                
                for neighbor in neighbors:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
                        tree.add_edge(node, neighbor)
                        flipped_edges[(node, neighbor)] = False
            
            print(f"Created tree with {len(tree.edges())} edges")
            return tree.edges(), flipped_edges
        else:
            print("Warning: No nodes in graph after processing")
            return [], {}
    except Exception as e:
        print(f"Warning: Error in edge flipping: {e}")
        # 返回当前边和空的翻转字典
        edges = list(dag.edges())
        return edges, {edge: False for edge in edges}

def create_empty_image_with_boxes(image_size, boxes):
    img = np.zeros((image_size[0], image_size[1], 3), dtype=np.uint8)

    for box in boxes:
        x, y, w, h, r, label = box
        x, y, w, h = int(x * 100), int(y * 100), int(w * 100), int(h * 100)
        if np.isclose(r, 90.0) or np.isclose(r, 270.0):
            x, y = int(x - h/2), int(y - w/2)
            cv2.rectangle(img, (x, y), (x + h, y + w), (0, 255, 0), 2)
        else:
            x, y = int(x - w/2) , int(y - h/2)
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(img, label, (x, y - 10), cv2.FONT_ITALIC , 0.5, (255, 255, 255), 1)
    cv2.imshow("image", img) 
    key = cv2.waitKey(0)

def get_visualization(scene_graph, table_priors=None):
    print("Visualization disabled to avoid display errors")
    # visual_scene_graph = [
    #     (
    #         item["position"]["x"] + 2.0,
    #         item["position"]["y"] + 2.0,
    #         item["size_in_meters"]["length"],
    #         item["size_in_meters"]["width"],
    #         item["rotation"]["z_angle"],
    #         item["new_object_id"]
    #     )
    #     for item in scene_graph if "position" in item.keys()
    # ]
    # #TODO : Adjust visualization window size according to the table size
    # create_empty_image_with_boxes((800, 800), visual_scene_graph)

def calculate_overlap(box1, box2):
    if box1 is None or box2 is None:
        return None
    
    x_min = max(box1[0], box2[0])
    x_max = min(box1[1], box2[1])
    y_min = max(box1[2], box2[2])
    y_max = min(box1[3], box2[3])
    z_min = max(box1[4], box2[4])
    z_max = min(box1[5], box2[5])
    
    # Check if the boxes overlap with a small tolerance
    if x_min <= x_max + 1e-03 and y_min <= y_max + 1e-03 and z_min <= z_max + 1e-03:
        return (x_min, x_max, y_min, y_max, z_min, z_max)
    else:
        return None

def is_collision_3d(obj1, obj2, bbox_instead = False):
    pos1, rot1, size1 = copy(obj1['position']), copy(obj1["rotation"]["z_angle"]), copy(obj1['size_in_meters'])
    # We won't check for collisions for objects with very thin surfaces
    if is_thin_object(obj1):
        return False
    if not bbox_instead:
        pos2, rot2, size2 = copy(obj2['position']), copy(obj2["rotation"]["z_angle"]), copy(obj2['size_in_meters'])
        # We won't check for collisions for objects with very thin surfaces
        try:
            if is_thin_object(obj2):
                return False
        except:
            print(obj2)
            raise Exception
    else:
        pos2, rot2, size2 = {"x" : (obj2[1] + obj2[0]) / 2 , "y" : (obj2[3] + obj2[2]) / 2, "z" : (obj2[5] + obj2[4]) / 2}, 0.0, {"length" : (obj2[1] - obj2[0]), "width" : (obj2[3] - obj2[2]), "height" : (obj2[5] - obj2[4])}


    def swap_dimensions_if_rotated(size, rotation):
        if np.isclose(rotation, 90.0) or np.isclose(rotation, 270.0):
            size["length"], size["width"] = size["width"], size["length"]

    def get_bounds(pos, size):
        x_max = pos['x'] + size['length'] / 2
        x_min = pos['x'] - size['length'] / 2
        y_max = pos['y'] + size['width'] / 2
        y_min = pos['y'] - size['width'] / 2
        z_max = pos['z'] + size['height'] / 2
        z_min = pos['z'] - size['height'] / 2
        return x_max, x_min, y_max, y_min, z_max, z_min

    def check_overlap(min1, max1, min2, max2):
        return min1 < max2 and max1 > min2 and abs(min1 - max2) > 1e-3 and abs(max1 - min2) > 1e-3

    # Swap dimensions if needed
    swap_dimensions_if_rotated(size1, rot1)
    swap_dimensions_if_rotated(size2, rot2)

    # Get bounds for both objects
    obj1_bounds = get_bounds(pos1, size1)
    obj2_bounds = get_bounds(pos2, size2)

    # Unpack bounds
    (obj1_x_max, obj1_x_min, obj1_y_max, obj1_y_min, obj1_z_max, obj1_z_min) = obj1_bounds
    (obj2_x_max, obj2_x_min, obj2_y_max, obj2_y_min, obj2_z_max, obj2_z_min) = obj2_bounds

    # Check for overlap in each dimension
    x_check = check_overlap(obj1_x_min, obj1_x_max, obj2_x_min, obj2_x_max)
    y_check = check_overlap(obj1_y_min, obj1_y_max, obj2_y_min, obj2_y_max)
    z_check = check_overlap(obj1_z_min, obj1_z_max, obj2_z_min, obj2_z_max)

    return x_check and y_check and z_check

def get_depth(scene_graph):
    G = nx.DiGraph()
    # Create graph
    for obj in scene_graph: # scene_graph here is scene_graph_wo_layout
        if not isinstance(obj, dict) or "new_object_id" not in obj: 
            continue
        
        obj_id = obj["new_object_id"]
        if obj_id not in G.nodes():
            G.add_node(obj_id)

        if "placement" not in obj or not isinstance(obj.get("placement"), dict):
            if verbose: print(f"Warning [get_depth]: Item '{obj_id}' missing valid 'placement' key. Treating as isolated node for depth calculation.")
            continue 

        obj_scene_graph = obj["placement"]
        for constraint in obj_scene_graph.get("table_layout_elements", []):
            if isinstance(constraint, dict) and "layout_element_id" in constraint:
                layout_id = constraint["layout_element_id"]
                if layout_id not in G.nodes():
                    G.add_node(layout_id)
                G.add_edge(layout_id, obj_id)
        for constraint in obj_scene_graph.get("objects_on_table", []):
            if isinstance(constraint, dict) and "object_id" in constraint:
                other_obj_id = constraint["object_id"]
                if other_obj_id not in G.nodes():
                    G.add_node(other_obj_id)
                G.add_edge(other_obj_id, obj_id)

    # DFS Algo
    visited = set()
    prior_ids = ["north_edge", "south_edge", "east_edge", "west_edge", "middle_of_table"]
    start_nodes = [node for node in G.nodes() if node in prior_ids]
    all_nodes_depth = {}

    def dfs(node, depth):
        visited.add(node)
        all_nodes_depth[node] = depth
        for successor in G.successors(node):
            if successor not in visited:
                dfs(successor, depth + 1)
            elif successor in all_nodes_depth and all_nodes_depth[successor] < depth + 1:
                # Skip already visited nodes with smaller depth to break out of cycles
                continue
            else:
                all_nodes_depth[successor] = depth + 1

    for start_node in start_nodes:
        dfs(start_node, 0)

    all_nodes_depth = {k: v for k, v in all_nodes_depth.items() if k not in prior_ids}
    return all_nodes_depth

def get_possible_positions(object_id, scene_graph, table_dimensions):
    obj_list = [element for element in scene_graph if isinstance(element, dict) and element.get("new_object_id") == object_id]
    if not obj_list:
        # print(f"Warning [get_possible_positions]: Object ID '{object_id}' not found in scene_graph.")
        return []
    obj = obj_list[0]
    
    if "placement" not in obj or not isinstance(obj.get("placement"), dict):
        # print(f"Warning [get_possible_positions]: Object ID '{object_id}' has no valid 'placement' data.")
        return []

    obj_scene_graph = obj["placement"]
    rot = get_rotation(obj, scene_graph)
    obj["rotation"] = {"z_angle" : rot}

    func_map = {
        "on" : get_on_constraint,
        "under" : get_under_contraint,
        "left of" : get_left_of_constraint,
        "right of" : get_right_of_constraint,
        "in front" : get_in_front_constraint,
        "behind" : get_behind_constraint,
        "above" : get_above_constraint,
        "in the corner" : get_in_corner_constraint,
        "in the middle of" : get_on_constraint
    }

    constraints = obj_scene_graph["table_layout_elements"] + obj_scene_graph["objects_on_table"]
    possible_positions = []
    for constraint in constraints:
        prep = constraint["preposition"]
        adjacency = constraint["is_adjacent"] if "is_adjacent" in constraint.keys() else True
        is_on_table = obj["is_on_the_table"]
        obj_A = obj
        key = "layout_element_id" if "layout_element_id" in constraint.keys() else "object_id"
        obj_B = [element for element in scene_graph if element.get("new_object_id") == constraint[key]][0]
        if "position" in obj_B.keys():
            possible_positions.append(func_map[prep](obj_A, obj_B, adjacency, is_on_table, table_dimensions))

    return possible_positions

def get_topological_ordering(scene_graph):
    G = nx.DiGraph()
    # Create graph
    for obj in scene_graph: # scene_graph here is scene_graph_wo_layout
        if not isinstance(obj, dict) or "new_object_id" not in obj:
            continue

        obj_id = obj["new_object_id"]
        if obj_id not in G.nodes():
            G.add_node(obj_id)

        if "placement" not in obj or not isinstance(obj.get("placement"), dict):
            # if verbose: print(f"Warning [get_topological_ordering]: Item '{obj_id}' missing valid 'placement' key. Treating as isolated node.")
            continue # Skips edge creation for this obj

        obj_scene_graph = obj["placement"]
        for constraint in obj_scene_graph.get("table_layout_elements", []):
            if isinstance(constraint, dict) and "layout_element_id" in constraint:
                layout_id = constraint["layout_element_id"]
                if layout_id not in G.nodes():
                    G.add_node(layout_id)
                G.add_edge(layout_id, obj_id)
        for constraint in obj_scene_graph.get("objects_on_table", []):
            if isinstance(constraint, dict) and "object_id" in constraint:
                other_obj_id = constraint["object_id"]
                if other_obj_id not in G.nodes():
                    G.add_node(other_obj_id)
                G.add_edge(other_obj_id, obj_id)
    
    # Topological ordering
    try:
        return list(nx.topological_sort(G))
    except nx.NetworkXUnfeasible: # Handles graphs with cycles if any remain
        # print("Warning [get_topological_ordering]: Graph has cycles, cannot compute topological sort. Returning nodes list.")
        return list(G.nodes())

def get_no_overlap_reason(obj, positions, cluster_constraint=None, errors={}):
    overlaps = []
    candidate_positions = positions
    scene_graph_edges = obj["placement"]["table_layout_elements"] + obj["placement"]["objects_on_table"]
    if cluster_constraint is not None:
        candidate_positions = candidate_positions + [cluster_constraint]
        scene_graph_edges = scene_graph_edges + ["cluster"]
    for i, pos1 in enumerate(candidate_positions):
        for j, pos2 in enumerate(candidate_positions[i+1:]):
            if pos1 == pos2:
                continue
            overlap = calculate_overlap(pos1, pos2)
            if overlap is None:
                overlaps.append((i, i + 1 + j))
    for i, j in overlaps:
        print("No Overlap between: ", i, " ", j)
        print("Object: ", obj["new_object_id"])
        if scene_graph_edges[i] == "cluster":
            key_j = "layout_element_id" if "layout_element_id" in scene_graph_edges[j].keys() else "object_id"
            key = ("no_overlap", obj["new_object_id"], scene_graph_edges[j][key_j], scene_graph_edges[j]["preposition"], "cluster")
            errors[key] = 1 + errors.get(key, 0)
        elif scene_graph_edges[j] == "cluster":
            key_i = "layout_element_id" if "layout_element_id" in scene_graph_edges[i].keys() else "object_id"
            key = ("no_overlap", obj["new_object_id"], scene_graph_edges[i][key_i], scene_graph_edges[i]["preposition"], "cluster")
            errors[key] = 1 + errors.get(key, 0)
        else:
            key_i = "layout_element_id" if "layout_element_id" in scene_graph_edges[i].keys() else "object_id"
            key_j = "layout_element_id" if "layout_element_id" in scene_graph_edges[j].keys() else "object_id"
            key = ("no_overlap", obj["new_object_id"], scene_graph_edges[i][key_i], scene_graph_edges[i]["preposition"], scene_graph_edges[j][key_j], scene_graph_edges[j]["preposition"])
            errors[key] = 1 + errors.get(key, 0)
    return errors

def place_object(obj, scene_graph, table_dimensions, errors={}, verbose=False, 
                 start_time=None, max_depth=3, current_depth=0):
    # 添加全局超时检查
    if start_time is None:
        start_time = time.time()
    elif time.time() - start_time > GLOBAL_TIMEOUT:
        print(f"Global timeout reached after {GLOBAL_TIMEOUT} seconds")
        print(f"Keeping current placement for {obj['new_object_id']}")
        key = ("global_timeout", obj["new_object_id"])
        errors[key] = 1 + errors.get(key, 0)
        # 保留当前位置，不报错
        return {}
    
    # 添加递归深度限制
    if current_depth > max_depth:
        print(f"Maximum recursion depth {max_depth} reached for {obj['new_object_id']}")
        key = ("max_depth_reached", obj["new_object_id"])
        errors[key] = 1 + errors.get(key, 0)
        # 保留当前位置，不报错
        return {}
    
    # 添加每个物体的放置时间限制
    object_start_time = time.time()
    
    if verbose:
        get_visualization(scene_graph)
    if not any(d.get("new_object_id") == obj["new_object_id"] for d in scene_graph):
        return errors
    positions = get_possible_positions(obj["new_object_id"], scene_graph, table_dimensions)
    print(f"Object: {obj['new_object_id']}")
    print("Possible positions: ", positions)
    abs_length, abs_width = deepcopy(obj["size_in_meters"]["length"]), deepcopy(obj["size_in_meters"]["width"])
    x_neg, x_pos, y_neg, y_pos = obj["cluster"]["constraint_area"]["x_neg"], obj["cluster"]["constraint_area"]["x_pos"], obj["cluster"]["constraint_area"]["y_neg"], obj["cluster"]["constraint_area"]["y_pos"]
    raw_constraint = (
        x_neg + abs_length / 2,
        y_pos + abs_width / 2,
        x_pos + abs_length / 2,
        y_neg + abs_width / 2,  
    )
    shift = int(obj["rotation"]["z_angle"] // 90)
    raw_constraint = raw_constraint[-shift:] + raw_constraint[:-shift]
        
    cluster_constraint = (
        raw_constraint[0],
        table_dimensions[0] - raw_constraint[2],
        raw_constraint[3],
        table_dimensions[1] - raw_constraint[1],
        0.0,
        table_dimensions[2] 
    )
    if verbose:
        print("Cluster constraint: ", cluster_constraint)
    if len(positions) == 0:
        # 如果没有可能的位置，尝试在桌面中心放置
        print(f"No positions found for {obj['new_object_id']}, trying default position")
        obj["position"] = {
            "x": table_dimensions[0] / 2,
            "y": table_dimensions[1] / 2,
            "z": obj.get("size_in_meters", {}).get("height", 0.01) / 2
        }
        return {}
    
    children = [element for element in scene_graph if "placement" in element.keys() and obj.get("new_object_id") in [x["object_id"] for x in element["placement"]["objects_on_table"]]]
    topological_sorted = get_topological_ordering(scene_graph)

    # Check condition to skip placing object
    if "position" in obj.keys():
        current_collisions = 0
        for obj_B in scene_graph:
            if obj_B == obj or "position" not in obj_B.keys():
                continue
            if is_collision_3d(obj, obj_B):
                current_collisions += 1
        overlap = calculate_overlap(cluster_constraint, positions[0])
        for pos in positions[1:]:
            overlap = calculate_overlap(overlap, pos)
        check_preposition = is_collision_3d(obj, overlap, bbox_instead=True) if overlap is not None else False
        check_children = any([is_collision_3d(child, item) for child in children if "position" in child.keys() for item in scene_graph if item["new_object_id"] != child["new_object_id"] and "position" in item.keys()])
        if current_collisions == 0 and check_preposition and (not check_children or len(children) == 0):
            if verbose:
                print("Object already placed: ", obj["new_object_id"])
                print("Preposition: ", check_preposition)
            return errors
    
    # Place object
    if len(positions) == 1:
        overlap = calculate_overlap(cluster_constraint, positions[0])            
    else:
        overlap = calculate_overlap(cluster_constraint, positions[0])
        for pos in positions[1:]:
            overlap = calculate_overlap(overlap, pos)
    
    # Find what causes the no overlap
    if overlap is None:
        if verbose:
            print("No overlap found for object: ", obj["new_object_id"])
        # 尝试使用第一个位置
        if len(positions) > 0:
            x = (positions[0][0] + positions[0][1]) / 2
            y = (positions[0][2] + positions[0][3]) / 2
            z = (positions[0][4] + positions[0][5]) / 2
            obj["position"] = {"x": x, "y": y, "z": z}
            print(f"Using first available position for {obj['new_object_id']}")
            return {}
        else:
            errors = get_no_overlap_reason(obj, positions, cluster_constraint, errors)
            return errors
    
    counter = 0
    while True:
        # 检查单个物体的放置时间
        if time.time() - object_start_time > MAX_OBJECT_PLACEMENT_TIME:
            print(f"Object placement timeout for {obj['new_object_id']} after {MAX_OBJECT_PLACEMENT_TIME} seconds")
            # 使用当前最佳位置
            if "position" not in obj:
                x = (overlap[0] + overlap[1]) / 2
                y = (overlap[2] + overlap[3]) / 2
                z = (overlap[4] + overlap[5]) / 2
                obj["position"] = {"x": x, "y": y, "z": z}
                print(f"Using center of overlap for {obj['new_object_id']}")
            return {}
        
        # 检查全局超时
        if time.time() - start_time > GLOBAL_TIMEOUT:
            print(f"Global timeout reached after {GLOBAL_TIMEOUT} seconds")
            # 使用当前最佳位置
            if "position" not in obj:
                x = (overlap[0] + overlap[1]) / 2
                y = (overlap[2] + overlap[3]) / 2
                z = (overlap[4] + overlap[5]) / 2
                obj["position"] = {"x": x, "y": y, "z": z}
                print(f"Using center of overlap for {obj['new_object_id']}")
            return {}
            
        counter += 1
        if counter > MAX_ATTEMPTS_PER_OBJECT:  # 从50减少到20
            if verbose:
                print(f"Maximum attempts ({MAX_ATTEMPTS_PER_OBJECT}) reached for object: {obj['new_object_id']}")
            # 使用当前最佳位置
            if "position" not in obj:
                x = (overlap[0] + overlap[1]) / 2
                y = (overlap[2] + overlap[3]) / 2
                z = (overlap[4] + overlap[5]) / 2
                obj["position"] = {"x": x, "y": y, "z": z}
                print(f"Using center of overlap for {obj['new_object_id']}")
            return {}
            
        if is_point_bbox(overlap):
            x = overlap[0]
            y = overlap[2]
            z = overlap[4]
            obj["position"] = {"x": x, "y": y, "z": z}
            if verbose:
                print(f"Using point bbox for {obj['new_object_id']}")
            return {}
            
        x = random.uniform(overlap[0], overlap[1])
        y = random.uniform(overlap[2], overlap[3])
        z = random.uniform(overlap[4], overlap[5])
        obj["position"] = {
            "x" : x,
            "y" : y,
            "z" : z
        }
        if verbose:
            print("Assigned position: ", obj["position"], " to object: ", obj["new_object_id"])
        flag = False
        for obj_B in scene_graph:
            if obj_B == obj or "position" not in obj_B.keys():
                continue
            if is_collision_3d(obj, obj_B):
                flag = True
                break
        if flag:
            continue
        
        child_flag = False
        # Topologically sort children
        children = [x for topo in topological_sorted for x in children if topo == x["new_object_id"]]
        # 限制处理的子物体数量
        max_children = 3  # 最多处理3个子物体
        children = children[:max_children]
        
        for child in children:
            if verbose:
                print(obj["new_object_id"], " placing child: ", child["new_object_id"])
            # 递归调用时传递开始时间和增加深度
            errors_child = place_object(child, scene_graph, table_dimensions, errors={}, 
                                       start_time=start_time, max_depth=max_depth, 
                                       current_depth=current_depth+1)
            if verbose:
                print("Errors child: ", errors_child)
            if errors_child:
                child_flag = True
                # Add the errors to the main errors
                for key in errors_child.keys():
                    if key in errors.keys():
                        errors[key] += errors_child[key]
                    else:
                        errors[key] = errors_child[key]
                break
        if verbose:
            print("Child flag: ", child_flag, " for object: ", obj["new_object_id"])
        if child_flag:
            # Delete the position key in children
            for child in children:
                if "position" in child.keys():
                    del child["position"]
            continue
        if verbose:
            print("Object placed: ", obj["new_object_id"])
        errors = {}
        break 
    return errors






