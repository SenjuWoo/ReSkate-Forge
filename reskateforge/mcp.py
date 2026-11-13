"""Small MCP stdio server: JSON-RPC 2.0 newline-delimited messages, no dependencies."""

from __future__ import annotations

import json
import sys
from argparse import Namespace

from .cli import run
from .studio import default_owner


def tool(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {"name": name, "description": description,
            "inputSchema": {"type": "object", "properties": properties, "required": required or [], "additionalProperties": False}}


S = lambda desc: {"type": "string", "description": desc}
TOOLS = [
    tool("forge_doctor", "Detect bundled Studio, compiler, Blender and game paths", {}),
    tool("forge_studio_launch", "Launch the bundled ReSkate Studio GUI on Windows", {}),
    tool("forge_studio_probe", "Discover the actual bundled Studio compiler help output", {}),
    tool("forge_build_map", "Execute the verified Studio CLI compile-map; deploy only with deploy=true", {
        "source": S("Existing .blend path"), "output": S("Fresh map package directory"),
        "game": S("Local game directory"), "deploy": {"type": "boolean"},
        "dry_run": {"type": "boolean"}}, ["source", "output"]),
    tool("forge_blender_preflight", "Use Blender to audit model meshes, rigs and texture paths", {
        "source": S("Existing model file"), "output": S("Fresh JSON report"),
        "blender": S("Path to blender.exe"), "dry_run": {"type": "boolean"}}, ["source", "output"]),
    tool("forge_map_import", "Import FBX/GLB/GLTF/OBJ into a new Blender map scene", {
        "source": S("Source mesh scene"), "output": S("New .blend file"),
        "blender": S("Path to blender.exe"), "dry_run": {"type": "boolean"}}, ["source", "output"]),
    tool("forge_map_convert", "Run bundled Studio map handshake converter in Blender", {
        "source": S("Existing .blend or .fbx"), "output": S("New map handshake folder"),
        "blender": S("Path to blender.exe"), "dry_run": {"type": "boolean"}}, ["source", "output"]),
    tool("forge_install_blender_addon", "Install bundled Skate Map add-on into Blender", {
        "output": S("Fresh installer report JSON"), "blender": S("Path to blender.exe"),
        "dry_run": {"type": "boolean"}}, ["output"]),
    tool("forge_plan", "Plan a model swap, custom map, park or Luau plugin from a user request", {"request": S("Natural language goal")}, ["request"]),
    tool("forge_inspect_model", "Inspect a private source model ZIP without extracting", {"archive": S("Absolute ZIP path")}, ["archive"]),
    tool("forge_inspect_archive", "Inspect split example mod ZIP in sequential order without extracting", {"parts": {"type": "array", "items": S("Path to part"), "minItems": 1}}, ["parts"]),
    tool("forge_stage_model", "Stage private source model files into a fresh workbench folder", {
        "archive": S("ZIP containing FBX and textures"), "destination": S("New private destination folder")}, ["archive", "destination"]),
    tool("forge_new", "Create an isolated new mod project", {"name": S("Underscore package name"), "kind": {"type": "string", "enum": ["plugin", "park", "map", "cosmetic"]}, "description": S("1-250 chars"), "owner": S("Thunderstore owner"), "root": S("Parent directory"), "version": S("SemVer x.y.z")}, ["name", "kind", "description"]),
    tool("forge_validate", "Validate existing project structure and current publication rules", {"project": S("Path to forge project")}, ["project"]),
    tool("forge_adopt_studio", "Copy genuine built ReSkate Studio output, refusing existing file overwrite", {"project": S("Path to project"), "from_dir": S("Studio built mod directory")}, ["project", "from_dir"]),
    tool("forge_package", "Validate and build Thunderstore zip (never upload)", {
        "project": S("Path to project"), "overwrite": {"type": "boolean"}}, ["project"]),
    tool("forge_release_prep", "Produce a practical release gate checklist and JSON report", {"project": S("Path to project")}, ["project"]),
    tool("forge_install", "Preview or explicitly install a mod in an existing Mods folder", {
        "project": S("Forge project"), "mods_dir": S("Existing Mods directory"),
        "apply": {"type": "boolean"}}, ["project", "mods_dir"]),
]


def dispatch(name: str, args: dict) -> object:
    fields = {"forge_doctor": "doctor", "forge_studio_launch": "launch-studio", "forge_studio_probe": "studio-probe",
              "forge_build_map": "build-map", "forge_blender_preflight": "blender-preflight", "forge_map_import": "map-import",
              "forge_map_convert": "map-convert", "forge_install_blender_addon": "install-blender-addon",
              "forge_stage_model": "stage-model", "forge_install": "install", "forge_plan": "plan",
              "forge_inspect_model": "inspect-model", "forge_inspect_archive": "inspect-archive",
              "forge_new": "new", "forge_validate": "validate", "forge_adopt_studio": "adopt-studio",
              "forge_package": "package", "forge_release_prep": "release-prep"}
    if name not in fields:
        raise ValueError(f"Unknown forge tool: {name}")
    allowed = next(x for x in TOOLS if x["name"] == name)["inputSchema"]
    if any(key not in allowed["properties"] for key in args):
        raise ValueError("Unexpected tool parameter")
    if any(key not in args for key in allowed["required"]):
        raise ValueError("Missing required tool parameter")
    defaults = {"root": "workspaces", "owner": default_owner(), "version": "0.1.0", "verbose": False,
                "output": None, "overwrite": False, "apply": False, "deploy": False, "dry_run": False,
                "blender": None, "game": None, "source": None}
    defaults.update(args)
    defaults["action"] = fields[name]
    return run(Namespace(**defaults))


def serve() -> None:
    # Do not print ordinary logging to stdout: stdout is the JSON-RPC wire protocol.
    for line in sys.stdin:
        try:
            request = json.loads(line)
            method = request.get("method")
            rid = request.get("id")
            if method == "initialize":
                client_version = request.get("params", {}).get("protocolVersion", "2025-06-18")
                result = {"protocolVersion": client_version, "capabilities": {"tools": {"listChanged": False}},
                          "serverInfo": {"name": "ReSkateForge", "version": "0.2.0"}}
            elif method == "tools/list": result = {"tools": TOOLS}
            elif method == "tools/call":
                params = request.get("params", {})
                try:
                    value = dispatch(params.get("name", ""), params.get("arguments", {}))
                    result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, default=str)}],
                              "isError": isinstance(value, dict) and value.get("success") is False}
                except Exception as exc:
                    result = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
            elif method == "ping": result = {}
            elif method and method.startswith("notifications/"): continue
            else:
                if rid is None: continue
                response = {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
                print(json.dumps(response, separators=(",", ":")), flush=True)
                continue
            if rid is not None:
                print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}, separators=(",", ":")), flush=True)
        except Exception as exc:
            print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(exc)}}, separators=(",", ":")), flush=True)
