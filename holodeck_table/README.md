# Holodeck Table

A tabletop adaptation of Holodeck for generating table surfaces, selecting Objaverse objects, and placing them under spatial constraints. This directory contains the modified research implementation for table arrangement.

The pipeline generates a table plan from text, retrieves assets with CLIP and sentence embeddings, asks an LLM for spatial constraints, and searches for object placements. The output keeps Holodeck's scene structure: table surfaces are stored under `rooms`, and placed items under `objects` and `floor_objects`.

## Setup

Run commands from this directory. Use an environment separate from `IDesign_table` because this implementation retains legacy OpenAI, LangChain, and PyTorch versions.

```bash
conda create -n holodeck-table python=3.9
conda activate holodeck-table
pip install -r requirements.txt
pip install matplotlib tqdm ai2thor
```

The extra packages are imported by the generation modules but are not explicitly listed in `requirements.txt`. Requirements include `openai==0.27.6`, `langchain==0.0.171`, and `torch==1.13.1`; platform support and compatibility need to be checked in your environment. The dependency list is a research snapshot, rather than a validated lockfile. Optional visualization and conversion helpers may require additional packages such as Blender, Open3D, and trimesh.

## LLM configuration

```bash
export OPENAI_API_KEY="YOUR_API_KEY"
export OPENAI_MODEL="gpt-4-1106-preview"
# Optional: use the endpoint supplied by your provider.
# export OPENAI_BASE_URL="https://your-provider.example/v1"
```

Replace the key placeholder. `modules/holodeck.py` reads credentials from the environment and uses `https://api.openai.com/v1` if no base URL is supplied. A `.env` file is not loaded automatically.

This research version calls `langchain.llms.OpenAI`, which uses the legacy completions interface. Select an endpoint and model compatible with that interface. The existing model default reflects the original deployment and may require a compatible gateway or an update to the LLM wrapper for your provider. Do not paste credentials into Python source files.

## Prepare asset data

Generation requires an external Objaverse/Holodeck database and precomputed embeddings; they are not included in this directory. In `modules/objaverse_retriever.py`, replace the original `/Volumes/...` paths with your own asset-data directory. For the selected version, provide:

```text
<asset-data>/<version>/
  objaverse_holodeck_database.json
  objaverse_holodeck_features_clip_3.p
  objaverse_holodeck_description_features_sbert.p
```

The database's asset order must match the embedding rows. The CLIP features are expected to contain three feature vectors per asset. The implementation loads CLIP `ViT-L-14` with `laion2b_s32b_b82k` weights and SentenceTransformer `all-mpnet-base-v2`; these model weights must also be available or downloaded.

`--asset_dir` points to the processed 3D asset directory used by rendering. It does not replace the separate hardcoded database and embedding paths in `ObjaverseRetriever`.

## Generate one table

After configuring the endpoint and asset paths:

```bash
python main.py \
  --mode generate_single_table \
  --query "a study desk with a laptop, notebook, pen, mug, and desk lamp" \
  --objaverse_version 09_23_combine_scale \
  --asset_dir /path/to/processed_assets \
  --save_dir ./outputs/study_desk \
  --generate_image False \
  --generate_video False \
  --use_constraint True \
  --use_milp False
```

This single-table mode writes `./outputs/study_desk/table.json`. Although query names and timestamps are computed, the current implementation uses `Holodeck.file_name` as the output subdirectory. That value is empty in single-table mode, so use a different `--save_dir` for each run to keep results.

For explicit output naming through Python:

```python
from modules.holodeck import Holodeck

model = Holodeck(
    objaverse_version="09_23_combine_scale",
    objaverse_asset_dir="/path/to/processed_assets",
    additional_requirements_object="Include a laptop, notebook, and mug.",
    file_name="study_desk",
)
model.generate_scene(
    scene=model.get_empty_scene(),
    query="a study desk",
    save_dir="./outputs",
    generate_image=False,
    generate_video=False,
    use_constraint=True,
    use_milp=False,
)
```

This writes `outputs/study_desk/table.json`. Output objects include asset IDs, positions, rotations, and table associations. Placement search operates on a centimeter grid; serialized position fields use meters with `y` as the vertical axis. Geometry and placement conventions therefore differ from `IDesign_table`.

## Task-conditioned batch generation

`main.py` defaults to `generate_multi_task2scenes`. This mode calls `modules/info2task.py`, whose dataset root must be changed to your own directory:

```text
task_inputs/
  scene_001/
    prompt_and_response.json
  scene_002/
    prompt_and_response.json
```

Each file must include:

```json
{
  "input_task_description": {
    "Environment": "A study desk",
    "Objects cluster": ["laptop", "notebook", "mug"]
  }
}
```

The loader currently processes at most ten matching scene directories, in filesystem order. Run `python main.py --mode generate_multi_task2scenes` with the same asset and output arguments as above. Results are saved as `<save_dir>/<scene_directory>/table.json`.

`test_tablellm.py` is a separate benchmark runner. Its loader in `modules/info2task_test.py` expects a JSON list with `scene_id` and a JSON-encoded `input` field containing `Environment` and `Objects cluster`. Update the input path and both copies of `processed_scene_ids.txt` paths in the runner and loader. The runner records completed IDs and writes `{}` on scene-generation errors; those empty outputs are failure markers.

## Files and current limitations

| File | Purpose |
| --- | --- |
| `main.py` | Single-table and task-conditioned generation entry point |
| `modules/holodeck.py` | Pipeline orchestration and environment-based LLM configuration |
| `modules/desktops.py`, `modules/table_prompts.py` | Table surface generation and prompts |
| `modules/object_selector.py`, `modules/objaverse_retriever.py` | Object selection and asset retrieval |
| `modules/floor_objects.py`, `modules/milp_utils.py` | Constraint parsing and placement search |
| `modules/info2task*.py`, `test_tablellm.py` | Dataset loaders and benchmark runner |
| `modules/utils.py`, `utils/` | Rendering and conversion helpers |

- Image and video generation blocks are currently commented out; the corresponding flags do not produce media.
- Keep `--use_constraint True`: the current placement function does not define a result for the unconstrained branch.
- `--use_milp` is passed through, but the current `get_solution()` implementation executes the DFS search without switching to a MILP solver.
- `generate_multi_tables` reuses an empty output name and can overwrite earlier results. Use task-conditioned generation or assign unique `file_name` values through Python.
- `generate_variants` in the CLI needs model initialization and output naming fixes before use.
- The full pipeline requires external assets, model weights, and LLM access. End-to-end generation has not been validated as part of this documentation update.

## Attribution and credentials

This adaptation retains the upstream Holodeck [Apache 2.0 license](LICENSE), including the Allen Institute for Artificial Intelligence copyright notice. Preserve the original notices when redistributing the code; external assets have their own attribution and terms.

Credentials are read from environment variables, and local `.env` files and caches are ignored. This release starts from a fresh source snapshot without the previous credential-bearing Git history. Keys found during the release audit still need to be revoked or rotated; removing history does not invalidate credentials.
