import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["TRANSFORMERS_CACHE"] = "/ssd1/zhen/hf_cache"
os.environ["HF_HOME"] = "/ssd1/zhen/hf_cache"


import openshape
from huggingface_hub import hf_hub_download
import torch
import json
import numpy as np
import transformers
import threading
import multiprocessing
import sys, os, shutil
import objaverse
from torch.nn import functional as F
import re
#Print device
print("Device: ", torch.cuda.get_device_name(0))

# Load the Pointcloud Encoder
pc_encoder = openshape.load_pc_encoder('openshape-pointbert-vitg14-rgb')

# Get the pre-computed embeddings
meta = json.load(
    open(hf_hub_download("OpenShape/openshape-objaverse-embeddings", "objaverse_meta.json", repo_type='dataset', local_dir = "OpenShape-Embeddings"))
)

meta = {x['u']: x for x in meta['entries']}
deser = torch.load(
    hf_hub_download("OpenShape/openshape-objaverse-embeddings", "objaverse.pt", repo_type='dataset', local_dir = "OpenShape-Embeddings"), map_location='cpu'
)
us = deser['us']
feats = deser['feats']

def move_files(file_dict, destination_folder, id):
    os.makedirs(destination_folder, exist_ok=True)
    for item_id, file_path in file_dict.items():
        destination_path = f"{destination_folder}{id}.glb"

        shutil.move(file_path, destination_path)
        print(f"File {item_id} moved from {file_path} to {destination_path}")


def load_openclip():
    print("Locking...")
    sys.clip_move_lock = threading.Lock()
    print("Locked.")
    clip_model, clip_prep = transformers.CLIPModel.from_pretrained(
        "laion/CLIP-ViT-bigG-14-laion2B-39B-b160k",
         torch_dtype=half,
    ), transformers.CLIPProcessor.from_pretrained("laion/CLIP-ViT-bigG-14-laion2B-39B-b160k")
    if torch.cuda.is_available():
        with sys.clip_move_lock:
            clip_model.cuda()
    return clip_model, clip_prep

def retrieve(embedding, top, sim_th=0.0, filter_fn=None):
    sims = []
    embedding = F.normalize(embedding.detach().cpu(), dim=-1).squeeze()
    for chunk in torch.split(feats, 10240):
        sims.append(embedding @ F.normalize(chunk.float(), dim=-1).T)
    sims = torch.cat(sims)
    sims, idx = torch.sort(sims, descending=True)
    sim_mask = sims > sim_th
    sims = sims[sim_mask]
    idx = idx[sim_mask]
    results = []
    for i, sim in zip(idx, sims):
        if us[i] in meta:
            if filter_fn is None or filter_fn(meta[us[i]]):
                results.append(dict(meta[us[i]], sim=sim))
                if len(results) >= top:
                    break
    return results

def get_filter_fn():
    face_min = 0
    face_max = 34985808
    anim_min = 0
    anim_max = 563
    anim_n = not (anim_min > 0 or anim_max < 563)
    face_n = not (face_min > 0 or face_max < 34985808)
    filter_fn = lambda x: (
        (anim_n or anim_min <= x['anims'] <= anim_max)
        and (face_n or face_min <= x['faces'] <= face_max)
    )
    return filter_fn

def preprocess(input_string):
    wo_numericals = re.sub(r'\d', '', input_string)
    output = wo_numericals.replace("_", " ")
    return output

f32 = np.float32
half = torch.float16 if torch.cuda.is_available() else torch.bfloat16
clip_model, clip_prep = load_openclip()
torch.set_grad_enabled(False)

file_path = "scene_graph.json"

# Load the original JSON data
with open(file_path, "r") as file:
    objects_in_room = json.load(file)

# Iterate through the objects and add the retrieved UID
for obj_in_room in objects_in_room:
    # Skip objects that are not actual items to be placed (like edges, middle_of_table)
    # You might need to adjust this condition based on how you identify non-retrievable items
    if "itemType" in obj_in_room and obj_in_room["itemType"] in ["edge", "surface"]:
        obj_in_room["uid"] = None # Assign None or skip adding the key for these items
        continue

    # Ensure style and material exist, otherwise skip retrieval for this object
    if "style" in obj_in_room and "material" in obj_in_room:
        style, material = obj_in_room['style'], obj_in_room["material"]
    else:
        print(f"Skipping retrieval for object {obj_in_room.get('new_object_id', 'N/A')} due to missing style/material.")
        obj_in_room["uid"] = None # Assign None or skip
        continue

    # Construct the text query
    # Use get() with a default for safer access in case 'new_object_id' is missing
    object_id_str = obj_in_room.get('new_object_id', 'object')
    text = preprocess(f"A high-poly {object_id_str}") + f" with {material} material and in {style} style, high quality"

    # Prepare CLIP input
    device = clip_model.device
    tn = clip_prep(
        text=[text], return_tensors='pt', truncation=True, max_length=76
    ).to(device)

    # Get CLIP features
    enc = clip_model.get_text_features(**tn).float().cpu()

    # Retrieve the object UID
    # Handle potential retrieval failures (e.g., retrieve returns empty list or None)
    try:
        retrieved_results = retrieve(enc, top=1, sim_th=0.1, filter_fn=get_filter_fn())
        if retrieved_results:
            retrieved_obj = retrieved_results[0]
            retrieved_uid = retrieved_obj["u"]
            print(f"Retrieved object UID: {retrieved_uid} for {object_id_str}")
            # Add the retrieved UID to the original object dictionary
            obj_in_room["uid"] = retrieved_uid
        else:
            print(f"No object retrieved for {object_id_str} with similarity > 0.1")
            obj_in_room["uid"] = None # Indicate retrieval failure
    except Exception as e:
        print(f"Error during retrieval for {object_id_str}: {e}")
        obj_in_room["uid"] = None # Indicate retrieval error


# After the loop, save the modified list back to the JSON file
# Overwriting the original file_path, change if needed
output_file_path = file_path # Or specify a new file like "scene_graph_with_uids.json"
with open(output_file_path, "w") as file:
    json.dump(objects_in_room, file, indent=4) # Use indent for readability

print(f"Updated scene graph with UIDs saved to {output_file_path}")

# ... (rest of your script, like the objaverse download part, might need adjustment
# as you now have the UIDs *before* needing to download them one by one inside the loop)