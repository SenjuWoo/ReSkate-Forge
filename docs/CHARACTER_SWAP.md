# Full-body character swap (verified pipeline)

Turns a rigged FBX character, here an Illusion/HS2 export, into a skate. full-body costume that replaces the whole skater. Everything up to the `.fbproject` runs headless.

```powershell
python -m reskateforge character-swap workspaces\Kitana_MK1\source\swap_config.json          # all stages
python -m reskateforge character-swap workspaces\Kitana_MK1\source\swap_config.json --stage glb
```

## Stages (`tools/character_swap/`)

| Stage | Script | What it does |
| --- | --- | --- |
| dump | `blender_dump.py` (Blender, background) | Rest-pose meshes, UVs, sparse weights and source bone heads, plus decimated LODs. `lod0_ratio` trims dense meshes. |
| tex | `textures.py` | Bakes albedo (HS2 skin/hair/eye colour comes from shader parameters, not MainTex) and normals into one atlas per native section. |
| glb | `fbx_bind.py`, `fit_reskin.py`, `glb_writer.py` | Reads the true cluster bind matrices, re-poses the source onto the game rig, remaps weights and writes the GLB. |
| import | Studio `reskate_cli.exe cosmetic-mesh-import` | Writes the costume into a `.fbproject` (item `Own_<item_name>`). |

The glb stage in detail:

- Re-posing works by anchor deltas plus the source's own linear blend skinning.
- Weights are remapped by rig profile and spread over the RM_ twist joints. Breasts bind to PS_*Shoulder_Sec_03 and glutes half to PS_*UpLeg_Sec_04, the joints the physics plugin moves.
- The GLB is written with the game render skeleton's exact bind pose (row-vector LinearTransforms → glTF).

`blender_preview.py` renders front, side and back previews of the GLB in rest pose or a bent pose.

## Verified contracts (bundled CLI, this game build)

- `cosmetic-mesh-import <game> <donor-item> <model.glb|fbx> <out.fbproject|.fbmod>` (hidden command, found in the unpacked CLI strings). It writes `<out>.readback.glb`.
- Mesh nodes must be named `RS_LOD<n>_SECTION<k>_<anything>`, one node per section per LOD. Missing LODs are filled from LOD0.
- The bind pose must equal the costume rig's render skeleton (`characters/maincharacters/common/animbase/animbase_default_renderskeleton`). Animation-export FBX rigs are rejected ("bind pose differs at AITrajectory").
- Each section is limited to ≤65535 vertices (16-bit indices).
- Crash test dummy donor: 5 sections (Bottom, Footwear, Handwear, Headwear, Top), 4 influences per vertex, and `FullBodyCostume_hide_everything` (hides head and body).
- `ReSkate Studio.exe` takes no project-path argument; its only options are `--game`, `--workspace` and the `--ui-*` capture flags. Open the project from File > Open.
- The CLI import does not take textures; the project gets neutral appearances. Studio GUI **Model → Import mesh...** with the same GLB adds embedded textures automatically ("Matching textures are added automatically").
- Donors: Isaac Clarke and Mocap Suit are paid store bundles, so avoid them. Crash test dummy, Sumo and Ghost Skater are used by published working mods.
- Runtime animation skeleton (395 joints): hips 7, Spine3 45, head 103, PS_LeftShoulder_Sec_03 332, PS_RightShoulder_Sec_03 337, PS_LeftUpLeg_Sec 370 / _04 371, PS_RightUpLeg_Sec 37 / _04 41.

## Textures and build (Studio GUI, then CLI)

1. Studio → Cosmetics → New Cosmetic → pick the donor → **Mesh** tab → **Import mesh...** → the built GLB. Studio replaces the matching texture slots from the GLB's materials. Do not re-import onto a CLI-created item: that fails with "Rig dependency partition is unavailable".
2. Name it → **Create cosmetic** → Project → **Save** → **Export .fbmod**.
3. `reskate_cli compile-mod <game> <staging> <mod.fbmod>` then `reskate_cli deploy-mod <game> <staging> <Owner-Name>`.
4. Add `manifest.json`, `icon.png`, `README.md` and any plugin files, run `reskateforge adopt-studio <ws> --from <staging>\Patch`, copy `initfs_win32`, then validate and package.

## Illusion/HS2 specifics

- Blender's armature rest is the BindPose (height slider ~1.11x larger), not the cluster bind. Use `fbx_bind.read_bind` TransformLinks. Accessories on `ca_slot`/`N_move` empties need the same rest→bind affine.
- Alpha-cut clothing (lace) needs `alpha_cut` in the config, because native costume shaders are opaque.
