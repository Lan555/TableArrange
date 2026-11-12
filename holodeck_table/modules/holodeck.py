import os
import json
import datetime
import open_clip
from tqdm import tqdm
from langchain.llms import OpenAI
from sentence_transformers import SentenceTransformer
from modules.desktops import FloorPlanGenerator
from modules.object_selector import ObjectSelector
from modules.floor_objects import FloorObjectGenerator
from modules.objaverse_retriever import ObjaverseRetriever
from modules.lights import generate_lights
from modules.layers import table2layer
from modules.utils import get_top_down_frame


class Holodeck():
    def __init__(self, objaverse_version, objaverse_asset_dir, additional_requirements_room="N/A", additional_requirements_object="N/A", file_name=""):
        openai_api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not openai_api_key or openai_api_key == "YOUR_API_KEY":
            raise ValueError("Set OPENAI_API_KEY before generating a scene.")
        custom_api_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

        # initialize llm
        self.llm = OpenAI(
            model_name=os.environ.get("OPENAI_MODEL", "gpt-4-1106-preview"),
            max_tokens=2048,
            openai_api_key=openai_api_key,
            openai_api_base=custom_api_url,
        )

        # initialize CLIP
        self.clip_model, _, self.clip_preprocess = open_clip.create_model_and_transforms('ViT-L-14', pretrained='laion2b_s32b_b82k')
        self.clip_tokenizer = open_clip.get_tokenizer('ViT-L-14')

        # initialize sentence transformer
        self.sbert_model = SentenceTransformer('all-mpnet-base-v2', device="cpu")

        # objaverse version and asset dir
        self.objaverse_version = objaverse_version
        self.objaverse_asset_dir = objaverse_asset_dir
        
        # initialize modules
        self.retrieval_threshold = 28
        self.object_retriever = ObjaverseRetriever(self.clip_model, self.clip_preprocess, self.clip_tokenizer, self.sbert_model, self.objaverse_version, self.retrieval_threshold)
        self.floor_generator = FloorPlanGenerator(self.clip_model, self.clip_preprocess, self.clip_tokenizer, self.llm)
        self.object_selector = ObjectSelector(self.object_retriever, self.llm)
        self.floor_object_generator = FloorObjectGenerator(self.llm, self.object_retriever)

        # additional requirements
        self.additional_requirements_room = additional_requirements_room
        # self.additional_requirements_object = "N/A"
        self.additional_requirements_object = additional_requirements_object
        self.file_name = file_name
    

    def get_empty_scene(self):
        with open("./modules/empty_scene.json", "r") as f:
            scene = json.load(f)
        return scene


    def empty_table(self, scene):
        scene["rooms"] = []
        scene["objects"] = []
        return scene


    def generate_table(self, scene, additional_requirements_room, used_assets=[]):
        self.floor_generator.used_assets = used_assets
        tables = self.floor_generator.generate_desktop(scene, additional_requirements_room)
        scene["rooms"] = tables
        return scene
    

    def select_objects(self, scene, additional_requirements_object, used_assets=[]):
        self.object_selector.used_assets = used_assets
        object_selection_plan, selected_objects = self.object_selector.select_objects(scene, additional_requirements_object)
        scene["object_selection_plan"] = object_selection_plan
        scene["selected_objects"] = selected_objects
        return scene

    def generate_scene(self, scene, query, save_dir, used_assets=[], add_ceiling=False, generate_image=True, generate_video=False, add_time=True, use_constraint=True, random_selection=False, use_milp=False):
        # initialize scene
        query = query.replace("_", " ")
        scene["query"] = query

        # empty table
        scene = self.empty_table(scene)

        # generate table
        scene = self.generate_table(scene, additional_requirements_room=self.additional_requirements_room, used_assets=used_assets)

        # select objects
        # objects names
        self.object_selector.random_selection = random_selection
        scene = self.select_objects(scene, additional_requirements_object=self.additional_requirements_object, used_assets=used_assets)

        # generate floor objects
        self.floor_object_generator.use_milp = use_milp
        scene["floor_objects"] = self.floor_object_generator.generate_objects(scene, use_constraint=use_constraint)
        scene["objects"] = scene["floor_objects"]

        # generate small objects
        # scene = self.generate_small_objects(scene, used_assets=used_assets)
        # scene["objects"] += scene["small_objects"]

        # generate lights
        lights = generate_lights(scene)
        scene["proceduralParameters"]["lights"] = lights

        # assign layers
        scene = table2layer(scene)

        # assign skybox
        # scene = getSkybox(scene)

        # create folder
        query_name = query.replace(" ", "_").replace("'", "")[:30]
        create_time = str(datetime.datetime.now()).replace(" ", "-").replace(":", "-").replace(".", "-")
        
        # if add_time: folder_name = f"{query_name}-{create_time}" # query name + time
        # else: folder_name = query_name # query name only
        folder_name = self.file_name

        os.makedirs(f"{save_dir}/{folder_name}", exist_ok=True)
        # with open(f"{save_dir}/{folder_name}/{query_name}.json", "w") as f:
        with open(f"{save_dir}/{folder_name}/table.json", "w") as f:
            json.dump(scene, f, indent=4)

        # save top down image
        # if generate_image:
        #     top_image = get_top_down_frame(scene, self.objaverse_asset_dir, 1024, 1024)
        #     top_image.show()
        #     top_image.save(f"{save_dir}/{folder_name}/{query_name}.png")

        # # save video
        # if generate_video:
        #     scene["objects"] = scene["floor_objects"]
        #     final_video = room_video(scene, self.objaverse_asset_dir, 1024, 1024)
        #     final_video.write_videofile(f"{save_dir}/{folder_name}/{query_name}.mp4", fps=30)

        return scene


    def generate_variants(self, query, original_scene, save_dir="data/scenes", number_of_variants=5, used_assets=[]):
        self.object_selector.reuse_selection = False # force the selector to retrieve different assets

        # create the list of used assets
        used_assets += [obj["assetId"] for obj in original_scene["objects"]]
        used_assets = list(set(used_assets))

        variant_scenes = []
        for i in tqdm(range(number_of_variants)):
            variant_scene = self.generate_scene(original_scene.copy(), query, save_dir, used_assets, generate_image=True, generate_video=False, add_time=True)
            variant_scenes.append(variant_scene)
            used_assets += [obj["assetId"] for obj in variant_scene["objects"]]
            used_assets = list(set(used_assets))
        return variant_scenes 