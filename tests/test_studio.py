"""Exercise argument contracts against isolated fake tools, never the user's game."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reskateforge import studio
from reskateforge.mcp import TOOLS, dispatch


class StudioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.game = self.root / "Game"
        self.game.mkdir()
        self.scene = self.root / "World.blend"
        self.scene.write_bytes(b"BLENDER")
        self.fbx = self.root / "World.fbx"
        self.fbx.write_bytes(b"FBX")
        self.fake_cli = self.root / "reskate_cli.exe"
        self.fake_cli.write_bytes(b"fake exe")
        self.fake_blender = self.root / "blender.exe"
        self.fake_blender.write_bytes(b"fake exe")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_bundled_studio_present(self) -> None:
        info = studio.diagnostics()
        self.assertTrue(info["bundled_toolkit_complete"], info)
        self.assertTrue(studio.STUDIO_CLI.is_file())

    def test_map_build_matches_actual_bundled_bat(self) -> None:
        bat = (studio.STUDIO / "Build Skate Map.bat").read_text(encoding="utf-8")
        self.assertIn('compile-map "%GAME%" "%BLEND%" "%PACKAGE%" --deploy', bat)
        with patch.object(studio, "STUDIO_CLI", self.fake_cli):
            command = studio.build_map(self.scene, self.root / "Package", game=str(self.game),
                                       deploy=True, dry_run=True)["command"]
        self.assertEqual(command[1:], ["compile-map", str(self.game), str(self.scene),
                                       str(self.root / "Package"), "--deploy"])

    def test_map_build_no_overwrite_or_input_destruction(self) -> None:
        with patch.object(studio, "STUDIO_CLI", self.fake_cli):
            target = self.root / "Package"
            target.mkdir()
            with self.assertRaises(FileExistsError):
                studio.build_map(self.scene, target, game=str(self.game), dry_run=True)
            with self.assertRaises(ValueError):
                studio.build_map(self.scene, self.game / "Inside", game=str(self.game), dry_run=True)
            self.assertEqual(self.scene.read_bytes(), b"BLENDER")

    def test_blender_job_uses_real_bundled_flags(self) -> None:
        preview = studio.blender_job("blender-preflight", self.fbx, output=self.root / "preflight.json",
                                     blender=str(self.fake_blender), dry_run=True)
        self.assertEqual(preview["command"][-4:], ["--input", str(self.fbx),
                                                  "--report", str(self.root / "preflight.json")])
        imported = studio.blender_job("map-import", self.fbx, output=self.root / "import.blend",
                                      blender=str(self.fake_blender), dry_run=True)
        self.assertIn("blender_map_ingest.py", imported["command"][3])
        conversion = studio.blender_job("map-convert", self.scene, output=self.root / "handshake",
                                        blender=str(self.fake_blender), dry_run=True)
        self.assertEqual(conversion["command"][-4:], ["--input", str(self.scene),
                                                     "--output", str(self.root / "handshake")])
        addon = studio.blender_job("install-blender-addon", output=self.root / "addon.json",
                                   blender=str(self.fake_blender), dry_run=True)
        self.assertIn("--addon", addon["command"])

    def test_external_process_exit_and_outputs_are_checked(self) -> None:
        with patch.object(studio, "STUDIO_CLI", self.fake_cli), patch.object(studio.sys, "platform", "win32"):
            with patch.object(studio.subprocess, "run", return_value=type("Result", (), {"returncode": 0})()):
                result = studio.build_map(self.scene, self.root / "ExpectedBuild", game=str(self.game))
        self.assertFalse(result["success"])
        self.assertFalse(result["built_package_exists"])
        self.assertTrue(Path(result["log"]).exists())

    def test_mcp_exposes_verified_bridge_and_sane_defaults(self) -> None:
        tool_names = {t["name"] for t in TOOLS}
        self.assertTrue({"forge_studio_launch", "forge_build_map", "forge_map_import",
                         "forge_map_convert", "forge_install_blender_addon", "forge_install"} <= tool_names)
        with patch.object(studio, "STUDIO_CLI", self.fake_cli):
            result = dispatch("forge_build_map", {"source": str(self.scene), "output": str(self.root / "Map"),
                                                  "game": str(self.game), "dry_run": True})
        self.assertNotIn("--deploy", result["command"])
        self.assertEqual(result["dry_run"], True)
        self.assertTrue(json.dumps(result))


if __name__ == "__main__":
    unittest.main()
