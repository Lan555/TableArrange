# TableArrange

This repository contains tabletop scene generation baselines implemented for two research works:

- **[MesaTask](https://arxiv.org/abs/2509.22281)** — *Towards Task-Driven Tabletop Scene Generation via 3D Spatial Reasoning* (NeurIPS 2025).
- **[STABLE](https://arxiv.org/abs/2605.16137)** — *Simulation-Ready Tabletop Layout Generation via a Semantics–Physics Dual System* (ICML 2026).

The repository adapts two existing 3D indoor scene generation methods to **task-driven tabletop scene generation**.

## Implemented Baselines

| Method | Description | Documentation |
| --- | --- | --- |
| **I-Design-Table** | Adapted from [I-Design](https://github.com/atcelen/IDesign). Extends its LLM-based scene graph generation and backtracking placement pipeline from indoor furniture arrangement to task-driven tabletop object layouts. | [Setup and Usage](IDesign_table/README.md) |
| **Holodeck-Table** | Adapted from [Holodeck](https://github.com/allenai/Holodeck). Extends its language-guided scene generation, asset retrieval, and spatial constraint-based placement pipeline to tabletop environments. | [Setup and Usage](holodeck_table/README.md) |

## Setup

The two baselines require separate Python environments due to differences in dependencies, input formats, coordinate conventions, and asset requirements. Please refer to their respective documentation for installation and evaluation instructions.

## License

This repository is licensed under the [Apache License 2.0](LICENSE).
