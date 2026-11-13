"""Verified Windows bridges to the user-bundled ReSkate Studio and Blender tools.

The map compiler argument contract comes from the bundled ``Build Skate Map.bat``;
Blender's command arguments come from the bundled scripts themselves. This module
does not guess undocumented EBX/cosmetic compilation commands.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .artifacts import json_write


ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "ReSkate Studio"
STUDIO_EXE = STUDIO / "ReSkate Studio.exe"
STUDIO_CLI = STUDIO / "reskate_cli.exe"
BLENDER_TOOLS = STUDIO / "Native" / "Blender"
MAP_CONVERTER = BLENDER_TOOLS / "studio_map_import.py"
ADDON_INSTALLER = BLENDER_TOOLS / "install_studio_addon.py"
SKATE_ADDON = BLENDER_TOOLS / "sk8_map_export.py"


def default_owner() -> str:
    """The Thunderstore team name new projects are created under.

    It is yours, so it is not written into the source: set RESKATE_OWNER, or put
    the name on the first line of local-config/owner.txt (that folder is private
    and never committed). Without either, projects get a placeholder to replace.
    """
    name = os.environ.get("RESKATE_OWNER", "").strip()
    if name:
        return name
    try:
        lines = (ROOT / "local-config" / "owner.txt").read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        lines = []
    return next((line.strip() for line in lines if line.strip()), "YourTeam")


def _first_file(paths: list[Path | None]) -> Path | None:
    for candidate in paths:
        if candidate and candidate.is_file():
            return candidate.resolve()
    return None


def find_blender(override: str | None = None) -> Path | None:
    paths: list[Path | None] = []
    if override:
        return _first_file([Path(override)])
    env = os.environ.get("RESKATE_BLENDER")
    if env:
        paths.append(Path(env))
    from_path = shutil.which("blender")
    if from_path:
        paths.append(Path(from_path))
    for key in ("ProgramFiles", "ProgramFiles(x86)"):
        prefix = os.environ.get(key)
        if not prefix:
            continue
        base = Path(prefix)
        paths.append(base / "Steam" / "steamapps" / "common" / "Blender" / "blender.exe")
        paths += sorted((base / "Blender Foundation").glob("Blender */blender.exe"), reverse=True)
    return _first_file(paths)


def find_game(override: str | None = None) -> Path | None:
    if override:
        game = Path(override)
        return game.resolve() if game.is_dir() else None
    env = os.environ.get("RESKATE_GAME")
    candidates = ([Path(env)] if env else [])
    # This is only a fallback because the user's installed Studio displayed it.
    if sys.platform == "win32":
        candidates.append(Path(r"C:\Games\ReSkate"))
    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    return None


def diagnostics(blender: str | None = None, game: str | None = None) -> dict:
    found_blender = find_blender(blender)
    found_game = find_game(game)
    essentials = {
        "studio_executable": STUDIO_EXE.is_file(),
        "studio_cli": STUDIO_CLI.is_file(),
        "native_libraries": (STUDIO / "Native" / "dxcompiler.dll").is_file(),
        "map_converter": MAP_CONVERTER.is_file(),
        "blender_addon": SKATE_ADDON.is_file(),
        "blender_addon_installer": ADDON_INSTALLER.is_file(),
    }
    return {
        "platform": sys.platform,
        "bundled_studio_directory": str(STUDIO),
        "bundled_tool_presence": essentials,
        "bundled_toolkit_complete": all(essentials.values()),
        "blender_executable": str(found_blender) if found_blender else None,
        "game_directory": str(found_game) if found_game else None,
        "windows_build_ready": sys.platform == "win32" and all(essentials.values()) and bool(found_blender and found_game),
        "supported_automation": ["map-import", "map-convert", "build-map", "blender-preflight", "install-blender-addon", "launch-studio"],
        "limitation": "Cosmetic donor fitting/building uses ReSkate Studio's UI; no unattended cosmetic compiler contract has been verified.",
    }


def _windows(command: str) -> None:
    if sys.platform != "win32":
        raise OSError(f"{command} requires Windows; this runtime is {sys.platform}. Run inside the Forge on your PC.")


def _existing_file(path: Path, suffixes: tuple[str, ...] | None = None) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"Missing source file: {path}")
    if suffixes and path.suffix.lower() not in suffixes:
        raise ValueError(f"{path.name} must be one of {', '.join(suffixes)}")
    return path.resolve()


def _run_logged(command: list[str], report: Path, *, cwd: Path, timeout_seconds: int = 3600) -> dict:
    """Run a confirmed argument vector, collecting the full console output in a log."""
    if report.exists():
        raise FileExistsError(f"Refusing to overwrite an existing build log: {report}")
    report.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    with report.open("x", encoding="utf-8") as log:
        try:
            outcome = subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, timeout=timeout_seconds, check=False)
            rc = outcome.returncode
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"Command timed out after {timeout_seconds}s; inspect {report}") from exc
    # Read the tail without loading arbitrarily large compiler logs into memory.
    with report.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        stream.seek(max(0, stream.tell() - 24000))
        tail = stream.read().decode("utf-8", errors="replace")[-8000:]
    return {"returncode": rc, "success": rc == 0, "log": str(report),
            "command": command, "started_utc": started, "output_tail": tail}


def launch_studio() -> dict:
    _windows("launch-studio")
    executable = _existing_file(STUDIO_EXE)
    process = subprocess.Popen([str(executable)], cwd=STUDIO, stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"started": True, "pid": process.pid, "executable": str(executable)}


def probe_compiler() -> dict:
    _windows("studio-probe")
    executable = _existing_file(STUDIO_CLI)
    result = subprocess.run([str(executable), "--help"], cwd=STUDIO, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=25, check=False)
    return {"command": [str(executable), "--help"], "returncode": result.returncode,
            "stdout": result.stdout[-16000:], "stderr": result.stderr[-8000:],
            "note": "A nonzero status may mean the compiler uses a different help interface; map command is confirmed by bundled BAT."}


def build_map(source: Path, package: Path, *, game: str | None = None, deploy: bool = False,
              dry_run: bool = False, log: Path | None = None) -> dict:
    """Execute the *exact* compile-map command documented in Build Skate Map.bat."""
    blend = _existing_file(source, (".blend",))
    game_dir = find_game(game)
    if not game_dir:
        raise FileNotFoundError("No game folder found; pass --game or set RESKATE_GAME (Studio shows C:\\Games\\ReSkate on your PC)")
    cli = _existing_file(STUDIO_CLI)
    package = package.resolve()
    if package.exists():
        raise FileExistsError(f"Refusing to overwrite an existing map build: {package}")
    if package == game_dir or package.is_relative_to(game_dir):
        raise ValueError("Build output must not be inside the game directory")
    command = [str(cli), "compile-map", str(game_dir), str(blend), str(package)]
    if deploy:
        command.append("--deploy")
    result = {"command": command, "deploy": deploy, "package": str(package), "dry_run": dry_run}
    if dry_run:
        return result
    _windows("build-map")
    target_log = log or package.parent / (package.name + ".compile.log")
    result.update(_run_logged(command, target_log.resolve(), cwd=STUDIO))
    result["built_package_exists"] = package.exists()
    result["success"] = result["success"] and result["built_package_exists"]
    if not result["built_package_exists"]:
        result["output_warning"] = "Compiler did not create the requested package directory; review the log"
    return result


def blender_job(kind: str, source: Path | None = None, *, output: Path,
                blender: str | None = None, log: Path | None = None, dry_run: bool = False) -> dict:
    blender_path = find_blender(blender)
    if not blender_path:
        raise FileNotFoundError("Blender executable unavailable; pass --blender or set RESKATE_BLENDER")
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {output}")
    python_script: Path
    flags: list[str] = []
    if kind == "blender-preflight":
        if source is None:
            raise ValueError("blender-preflight requires a source")
        source = _existing_file(source, (".fbx", ".glb", ".gltf", ".obj", ".blend"))
        python_script = ROOT / "tools" / "blender_preflight.py"
        flags = ["--input", str(source), "--report", str(output)]
    elif kind == "map-import":
        if source is None:
            raise ValueError("map-import requires a source")
        source = _existing_file(source, (".fbx", ".glb", ".gltf", ".obj"))
        if output.suffix.lower() != ".blend":
            raise ValueError("map-import output must end in .blend")
        python_script = ROOT / "tools" / "blender_map_ingest.py"
        flags = ["--input", str(source), "--output", str(output)]
    elif kind == "map-convert":
        if source is None:
            raise ValueError("map-convert requires a source")
        source = _existing_file(source, (".fbx", ".blend"))
        python_script = _existing_file(MAP_CONVERTER)
        flags = ["--input", str(source), "--output", str(output)]
    elif kind == "install-blender-addon":
        python_script = _existing_file(ADDON_INSTALLER)
        flags = ["--addon", str(_existing_file(SKATE_ADDON)), "--result", str(output)]
    else:
        raise ValueError(f"Unsupported Blender job: {kind}")
    script = _existing_file(python_script)
    command = [str(blender_path), "--background", "--python", str(script), "--", *flags]
    result = {"command": command, "output": str(output), "dry_run": dry_run}
    if dry_run:
        return result
    _windows(kind)
    target_log = log or output.parent / (output.name + ".blender.log")
    result.update(_run_logged(command, target_log.resolve(), cwd=ROOT))
    result["output_exists"] = output.exists()
    if kind == "map-convert":
        result["map_json_exists"] = (output / "map.json").is_file()
        result["success"] = result["success"] and result["map_json_exists"]
    else:
        result["success"] = result["success"] and result["output_exists"]
    if not result["success"] and result["returncode"] == 0:
        result["output_warning"] = "Process exited zero but expected output was missing; inspect the log"
    return result
