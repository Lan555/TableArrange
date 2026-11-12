# TableArrange

Research implementations of two tabletop scene arrangement methods:

| Method | Description | Documentation |
| --- | --- | --- |
| IDesign Table | LLM agents build and refine a scene graph, then assign object positions with backtracking. | [Setup and usage](IDesign_table/README.md) |
| Holodeck Table | Text-guided table generation, Objaverse asset retrieval, and spatial constraint placement. | [Setup and usage](holodeck_table/README.md) |

Use separate Python environments for the two methods. Their dependencies, input formats, coordinate conventions, and external asset requirements differ; consult each method's README before running it.

Credentials are supplied through environment variables or an ignored local configuration file. Real API keys, `.env` files, caches, and previous Git histories are excluded from this source snapshot. Previously used credentials still need to be revoked or rotated.

Holodeck's upstream license is preserved in [holodeck_table/LICENSE](holodeck_table/LICENSE). The IDesign adaptation currently has no standalone license file; licensing for the two directories should be considered separately.
