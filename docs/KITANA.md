# Kitana model swap — current evaluation

## What the supplied file contains

`20261108223847_McM_Kitana_Mask_-_MK1.zip` is **not** a compiled ReSkate mod. It contains one 13,150,896-byte binary **FBX 7.4** and **76 PNG textures**, about 114 MB uncompressed. The archive is structurally sound and contains no ZIP path anomalies.

Our read-only FBX metadata parser found approximately:

| Metric | Result |
| --- | ---: |
| FBX Model nodes | 922 |
| Bone-like Model nodes | 903 |
| Geometry nodes | 148 |
| Deformer nodes | 532 |
| FBX coordinate/mesh array `Vertices` entries | 733,608 |
| Polygon vertex indices | 669,483 |
| External PNG textures | 76 |

These are low-level FBX node/array counts, **not** 922 distinct render meshes or 733,608 unique skater vertices. The source is complex and contains a large `cf_J_...` rig hierarchy and many facial/body shape keys. Those naming conventions clearly do **not** establish compatibility with skate.'s donor skeleton. The face, hair, costume and some detailed body submeshes will likely need selective export and cleanup.

**Feasibility:** real material/mesh import into ReSkate Studio is documented, so a cosmetic/costume or multiple custom items are realistic. A whole-body animated skater replacement is a harder second phase. The forge must compare the target donor skeleton, bind transforms, scale, weights and animation output; otherwise a naïve swap may deform badly, clip or fail to load.

## Suggested Windows workflow

1. `reskateforge new Kitana_Skater --kind cosmetic --owner YourTeam --description "A custom Kitana skater set"`.
2. In the **private Forge ZIP** Kitana is already staged at `workspaces/Kitana_Skater/source/Kitana/20261108223847_McM_Kitana_Mask_-_MK1/McM_Kitana_Mask_-_MK1.fbx` with its 76 textures and metadata JSON. No extraction step is necessary.
3. Use `tools/blender_preflight.py` with Blender `--background` on the extracted FBX. Examine rig count, total render triangles, missing images and shape keys. You can export a GLB for Studio after cleanup.
4. Open **ReSkate Studio**, choose a **free** clothing/costume donor (never an in-game paid-store item), and export its mesh as the basis for bone/fit comparison.
5. In Blender, compare donor and Kitana rigs. Use the donor's working skeleton, match scale/orientation and origin, transfer mesh weights, prune irrelevant nodes, set material maps and mask covered body areas; animate/test deformations.
6. In Studio: import the prepared FBX/GLB as the donor cosmetic's **Model**, import textures as its **Look**, configure **Fit** and any hidden body parts. Make an original item name/card, not a copy of the paid item.
7. Use Studio's **Fit Check**, then **Test in game** and inspect locomotion, ollies, grinds, bails, footwear, fingers, facial animation and visual glitches.
8. Once Studio builds the mod, `reskateforge adopt-studio ...` and `reskateforge validate ...`, then package with release checks.

## What remains before an actual Kitana mod

- A free skate. donor model exported from the user's installed game, ideally a full outfit item with suitable slots.
- Blender and ReSkate Studio running on the user's Windows PC.
- A practical choice of *full-body replacement* versus *original wearable costume*; Studio documentation specifically supports **cosmetic meshes**, not a guaranteed all-in-one complete skater avatar swap.
- Rig/weight, materials and silhouette fit evaluation and a real in-game test.
- Explicit permission to redistribute the supplied character mesh/texture source publicly, if a public release is intended.

No fabricated patch is supplied. The model source is staged inside **this private handoff ZIP** to let an AI begin Blender prep immediately. It is excluded from normal public-oriented Forge ZIPs unless `tools/build_distribution.py --include-private-sources` is explicitly specified. Never include `source/` when packaging a Thunderstore mod.
