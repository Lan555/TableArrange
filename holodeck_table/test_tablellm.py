import ast
import json
import os
from tqdm import tqdm
from argparse import ArgumentParser
from modules.holodeck import Holodeck
from modules.info2task_test import read_jsoninfo

def generate_single_scene(args):
    folder_name = args.query.replace(" ", "_").replace("'", "")
    # try:
    #     if args.original_scene is not None:
    #         scene = json.load(open(args.original_scene, "r"))
    #         print(f"Loading exist scene from {args.original_scene}.")
    #     else:
    #         scene = json.load(open(f"data/scenes/{folder_name}/{folder_name}.json", "r"))
    #         print(f"Loading exist scene from data/scenes/{folder_name}/{folder_name}.json.")
    # except:
    args.model = Holodeck(args.objaverse_version, args.asset_dir)
    scene = args.model.get_empty_scene()
    print("Generating from an empty scene.")

    args.model.generate_scene(
        scene=scene,
        query=args.query,
        save_dir=args.save_dir,
        used_assets=args.used_assets,
        generate_image=ast.literal_eval(args.generate_image),
        generate_video=ast.literal_eval(args.generate_video),
        add_ceiling=ast.literal_eval(args.add_ceiling),
        add_time=ast.literal_eval(args.add_time),
        use_constraint=ast.literal_eval(args.use_constraint),
        use_milp=ast.literal_eval(args.use_milp),
        random_selection=ast.literal_eval(args.random_selection)
    )


def generate_multi_scenes(args):
    with open(args.query_file, "r") as f:
        queries = f.readlines()
        queries = [query.strip() for query in queries]
    
    for query in tqdm(queries):
        args.query = query
        generate_single_scene(args)

def generate_multi_task2scenes(args):
    querys, additional_requirements_room, additional_requirements_objects, file_names = read_jsoninfo()

    processed_ids_file_path = '/Users/luozhen/desktop/tabletop/task_test/processed_scene_ids.txt'
    # Ensure the directory for the processed IDs file exists
    os.makedirs(os.path.dirname(processed_ids_file_path), exist_ok=True)

    for query, additional_requirements_object, file_name in zip(querys, additional_requirements_objects, file_names):
        try:
            # file_name here is the scene_id from read_jsoninfo
            args.model = Holodeck(args.objaverse_version, args.asset_dir, additional_requirements_room, additional_requirements_object, f"scene_{file_name}") # Use file_name (scene_id) for Holodeck scene name for clarity
            scene = args.model.get_empty_scene()
            print(f"Generating scene for ID: {file_name}")

            args.model.generate_scene(
                scene=scene,
                query=query,
                save_dir=args.save_dir,
                used_assets=args.used_assets,
                generate_image=ast.literal_eval(args.generate_image),
                generate_video=ast.literal_eval(args.generate_video),
                add_ceiling=ast.literal_eval(args.add_ceiling),
                add_time=ast.literal_eval(args.add_time),
                use_constraint=ast.literal_eval(args.use_constraint),
                use_milp=ast.literal_eval(args.use_milp),
                random_selection=ast.literal_eval(args.random_selection)
            )

            # If generate_scene was successful, record the scene_id
            with open(processed_ids_file_path, 'a') as f_ids:
                f_ids.write(f"{file_name}\n")
            print(f"Successfully processed and recorded scene ID: {file_name}")

        except Exception as e:
            print(f"Error generating scene for file_name {file_name}: {e}")
            error_dir_path = os.path.join(args.save_dir, str(file_name))
            os.makedirs(error_dir_path, exist_ok=True)
            error_file_path = os.path.join(error_dir_path, "table.json")
            with open(error_file_path, 'w') as f:
                json.dump({}, f)
            print(f"Saved empty table.json at {error_file_path} due to error.")

def generate_variants(args):
    try: original_scene = json.load(open(args.original_scene, "r"))
    except: raise Exception(f"Could not load original scene from {args.original_scene}.")
    try:
        args.model.generate_variants(
            query=args.query,
            original_scene=original_scene,
            save_dir=args.save_dir,
            number_of_variants=int(args.number_of_variants),
            used_assets=args.used_assets,
        )
    except:
        print(f"Could not generate variants from {args.query}.")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--mode", help = "Mode to run in (generate_single_table, generate_multi_tables or generate_variants).", default = "generate_multi_task2scenes")
    parser.add_argument("--query", help = "Query to generate scene from.", default = "a dining table")
    parser.add_argument("--query_file", help = "File to load queries from.", default = "/Volumes/新加卷/objaverse/queries.txt")
    parser.add_argument("--number_of_variants", help = "Number of variants to generate.", default = 5)
    parser.add_argument("--original_scene", help = "Original scene to generate variants from.", default = None)
    parser.add_argument("--objaverse_version", help = "Version of objaverse to use.", default = "09_23_combine_scale")
    parser.add_argument(
        "--asset_dir",
        help="Directory to load assets from.",
        default="/Volumes/新加卷/objaverse/objaverse_holodeck/09_23_combine_scale/processed_2023_09_23_combine_scale",
    )
    parser.add_argument(
        "--save_dir", help="Directory to save scene to.", default="/Users/luozhen/Desktop/tabletop/task_test"
    )
    parser.add_argument("--generate_image", help = "Whether to generate an image of the scene.", default = "True")
    parser.add_argument("--generate_video", help = "Whether to generate a video of the scene.", default = "False")
    parser.add_argument("--add_ceiling", help = "Whether to add a ceiling to the scene.", default = "False")
    parser.add_argument("--add_time", help = "Whether to add the time to the scene name.", default = "True")
    parser.add_argument("--use_constraint", help = "Whether to use constraints.", default = "True")
    parser.add_argument("--use_milp", help = "Whether to use mixed integer linear programming for the constraint satisfaction solver.", default = "False")
    parser.add_argument("--random_selection", help = "Whether to more random object selection, set to False will be more precise, True will be more diverse", default = "False")
    parser.add_argument("--used_assets", help = "a list of assets which we want to exclude from the scene", default = [])
    args = parser.parse_args()

    if args.used_assets != [] and args.used_assets.endswith(".txt"):
        with open(args.used_assets, "r") as f:
            args.used_assets = f.readlines()
            args.used_assets = [asset.strip() for asset in args.used_assets]
    else:
        args.used_assets = []
    
    if args.mode == "generate_single_table":
        generate_single_scene(args)
    
    elif args.mode == "generate_multi_tables":
        generate_multi_scenes(args)
    
    elif args.mode == "generate_variants":
        generate_variants(args)
    elif args.mode == "generate_multi_task2scenes":
        generate_multi_task2scenes(args)
