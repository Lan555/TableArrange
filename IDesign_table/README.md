# IDesign Table

A tabletop adaptation of [I-Design: Personalized LLM Interior Designer](https://atcelen.github.io/I-Design/). This directory contains the modified research implementation used to generate object layouts on tables. It is a derivative implementation, rather than the official upstream repository.

The pipeline uses LLM agents to propose objects and spatial relationships, correct and refine the scene graph, form object clusters, and assign coordinates through backtracking. Table layout references include the four edges and `middle_of_table`.

## Setup

Run commands from this directory. Use a separate environment from `holodeck_table`, since the two implementations use different generations of the OpenAI client dependencies.

```bash
conda create -n idesign-table python=3.9
conda activate idesign-table
pip install -r requirements.txt
```

The core layout pipeline does not require Blender, Objaverse assets, or OpenShape. Those dependencies belong to the optional asset retrieval and rendering scripts. The requirements retain the research version pins; a complete fresh-environment installation and end-to-end generation have not been validated as part of this documentation update.

## LLM configuration

Set credentials in the shell before running Python:

```bash
export OPENAI_API_KEY="YOUR_API_KEY"
export OPENAI_MODEL="gpt-4.1-mini-2025-04-14"
# Optional: use the endpoint supplied by your provider.
# export OPENAI_BASE_URL="https://your-provider.example/v1"
```

Replace the placeholder with your own key. `llm_config.py` reads these environment variables. `OPENAI_API_KEY` takes precedence over the local JSON configuration; `OPENAI_MODEL` and `OPENAI_BASE_URL` override those fields when supplied. Choose a model supported by your endpoint and the legacy `pyautogen==0.2.0` client, including the JSON response format used by the agents. The model name above is the existing research default, not a guarantee of provider availability.

Alternatively, copy the configuration template and fill in the local file:

```bash
cp OAI_CONFIG_LIST.example.json OAI_CONFIG_LIST.json
```

`OAI_CONFIG_LIST.json` is ignored by Git. A `.env` file is not loaded automatically; export its variables yourself if you use one. Keep real credentials out of the example file, source code, and commits.

## Generate one tabletop layout

Run this example from `IDesign_table/`:

```python
from IDesign import IDesign

design = IDesign(
    no_of_objects=5,
    user_input="A study desk with a laptop, notebook, pen, mug, and desk lamp",
    table_dimensions=[1.2, 0.8, 0.75],
)
design.create_initial_design()
design.correct_design()
design.refine_design()
design.create_object_clusters(verbose=False)
design.backtrack(verbose=False)
design.to_json("my_table.json")
```

Dimensions and generated positions are in meters; rotations use `rotation.z_angle` in degrees. The current generator writes a JSON object with an `objects_on_table` list. Object records can contain `new_object_id`, `size_in_meters`, placement relationships, `position`, and `rotation`. Generation can produce incomplete layouts, so inspect the output before downstream use. The checked-in scene JSON files are older list-format examples.

## Batch generation

`gen_table.py` processes a JSON list of benchmark records. Each record has:

| Field | Type | Required content |
| --- | --- | --- |
| `scene_id` | Non-empty string | Unique output identifier |
| `input` | JSON-encoded string | An object with `Environment` |
| `output` | JSON-encoded string | An object with `objects` and `item_placement_zone` |

The driver uses the length of `objects` as the requested object count and `Environment` as the prompt. It does not pass the full `objects` list to the design constructor. Width and length are read from `item_placement_zone[1]` and `[3]`, divided by 100, made positive, and clamped to 0.3–3.0 meters. Table height is set to 0.75 meters.

Before running, update the hardcoded input file and `output_dir` in `gen_table.py` to your own paths:

```bash
python gen_table.py
```

The script writes `<scene_id>.json`, a task list, completion IDs, and a results summary. It skips existing non-empty results and attempts to write `{}` on failures. Time limits are checked between stages and do not interrupt a blocked API call. Failed attempts can also be written to `completed_tasks.txt`; inspect both that file and the results before retrying.

## Files and optional tools

| File | Purpose |
| --- | --- |
| `IDesign.py` | Tabletop generation, correction, refinement, clustering, and backtracking |
| `agents.py`, `corrector_agents.py`, `refiner_agents.py`, `chats.py` | LLM agents and conversation flow |
| `schemas.py`, `constraint_functions.py`, `utils.py` | JSON schemas, spatial constraints, and geometry |
| `llm_config.py`, `OAI_CONFIG_LIST.example.json` | Credential loading and public configuration template |
| `gen_table.py` | Benchmark batch driver |
| `retrieve.py` | Experimental OpenShape/Objaverse asset retrieval |
| `place_in_blender.py` | Legacy Blender asset placement script |
| `process_json.py` | Convert results in place to a downstream object-list format |
| `gpt_v_as_evaluator.py` | Legacy image evaluation helper; reads `OPENAI_API_KEY` |

`retrieve.py` requires a separate OpenShape/PyTorch/CUDA environment, embeddings, and Objaverse dependencies. It currently uses server-specific cache paths, assumes CUDA at startup, and reads a list-format `scene_graph.json`. `place_in_blender.py` also expects a list and matching assets in `Assets/`, and retains room-specific filters and geometry. Adapt the schema and paths before using these scripts with the current generator output. Asset downloads and a complete rendering pipeline are not bundled here.

`test.py` retains the upstream `room_dimensions` argument and is not a valid tabletop quickstart; use the example above. The processing helpers retain hardcoded paths. `process_json.py` overwrites JSON files, and `process.py` enables deletion in its main block, so review these utilities before running them on results.

## Attribution and release notes

Credit the original I-Design work when using this adaptation. This directory currently has no standalone `LICENSE` file; the sibling Holodeck license does not establish licensing for this implementation.

Local credentials and caches are ignored. This release starts from a fresh source snapshot and excludes the previous credential-bearing Git history. Keys found during the release audit still need to be revoked or rotated; removing history does not invalidate credentials.
