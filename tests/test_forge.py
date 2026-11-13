import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from reskateforge.artifacts import json_write
from reskateforge.inspect import SegmentedReader, inspect_mod_archive, safe_zip_name, zip_security_checks
from reskateforge.validate import validate_mod
from reskateforge.workflow import create_project, package_project, release_prep, task_plan


class ForgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def make_plugin(self):
        return create_project(self.base, "Test_HUD", "plugin", "GennyWoo", "A practical passive HUD", "1.0.0")

    def test_plugin_package_and_reproducible_zip(self):
        p = self.make_plugin()
        report = validate_mod(p / "mod", "GennyWoo", ["Mods", "Plugins"])
        self.assertTrue(report["ready"], report)
        first = package_project(p)
        package = Path(first["package"])
        digest = hashlib.sha256(package.read_bytes()).hexdigest()
        second = package_project(p, overwrite=True)
        self.assertEqual(digest, hashlib.sha256(package.read_bytes()).hexdigest())
        self.assertEqual(first["bytes"], second["bytes"])
        with zipfile.ZipFile(package) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual([], zip_security_checks(z))
            self.assertEqual(json.loads(z.read("reskate-plugin.json"))["api"], 1)
            self.assertIn("gw hud", z.read("plugin/main.lua").decode("utf-8"))
        report = release_prep(p)
        self.assertTrue((p / "RELEASE_CHECKLIST.md").exists())
        self.assertTrue(report["validation"]["ready"])

    def test_plugin_rejects_windows_program(self):
        p = self.make_plugin()
        (p / "mod" / "evil.js").write_text("not okay", encoding="utf-8")
        result = validate_mod(p / "mod", "GennyWoo", ["Mods", "Plugins"])
        self.assertFalse(result["ready"])
        self.assertIn("plugin-program", [x["code"] for x in result["issues"]])
        with self.assertRaises(ValueError): package_project(p)

    def test_category_gate(self):
        p = self.make_plugin()
        result = validate_mod(p / "mod", "GennyWoo", ["Mods"])
        self.assertFalse(result["ready"])
        self.assertIn("plugin-category", [x["code"] for x in result["issues"]])

    def test_game_data_needs_real_stamp(self):
        p = create_project(self.base, "Mesh", "cosmetic", "GennyWoo", "New wearable mesh")
        (p / "mod" / "layout.toc").write_bytes(b"placeholder")
        result = validate_mod(p / "mod", "GennyWoo", ["Mods", "Cosmetics"])
        self.assertFalse(result["ready"])
        self.assertIn("studio-stamp", [x["code"] for x in result["issues"]])

    def test_park_schema_and_bad_quaternion(self):
        p = create_project(self.base, "Skate_Park", "park", "GennyWoo", "A rail park")
        self.assertTrue(validate_mod(p / "mod", "GennyWoo", ["Mods"])["ready"])
        path = p / "mod" / "parks" / "bam.park.json"
        data = json.loads(path.read_text())
        data["maps"]["bam"][0]["rotation"] = [0, 0, 0, 0]
        json_write(path, data)
        result = validate_mod(p / "mod", "GennyWoo", ["Mods"])
        self.assertFalse(result["ready"])
        self.assertIn("park-rotation", [x["code"] for x in result["issues"]])

    def test_map_strict_schema(self):
        p = create_project(self.base, "My_Map", "map", "GennyWoo", "An imported skate map")
        json_write(p / "mod" / "reskate-levels.json", {"schema": 1, "levels": [
            {"asset": "levels/game/test/test", "displayName": "Test", "startPoints": ["spawn"]}]})
        result = validate_mod(p / "mod", "GennyWoo", ["Mods", "Maps"])
        self.assertFalse(result["ready"], result)
        self.assertIn("map-no-build", [x["code"] for x in result["issues"]])
        data = json.loads((p / "mod" / "reskate-levels.json").read_text())
        data["levels"][0]["arbitrary"] = True
        json_write(p / "mod" / "reskate-levels.json", data)
        invalid = validate_mod(p / "mod", "GennyWoo", ["Mods", "Maps"])
        self.assertFalse(invalid["ready"])
        self.assertIn("map-entry", [x["code"] for x in invalid["issues"]])

    def test_safe_zip_paths(self):
        for name in ("../evil", "/absolute", "safe//bad", "x\\bad", "C:/drive", "./dot"):
            self.assertFalse(safe_zip_name(name), name)
        self.assertTrue(safe_zip_name("Patch/Win32/map.cas"))

    def test_split_archive_without_concatenation(self):
        entire = self.base / "test.zip"
        with zipfile.ZipFile(entire, "w") as z:
            z.writestr("Mods/Alpha-Plugin/manifest.json", json.dumps({"name": "Plugin", "version_number": "1.0.0"}))
            z.writestr("Mods/Alpha-Plugin/reskate-plugin.json", '{"api":1,"entry":"plugin/main.lua"}')
            z.writestr("Mods/Alpha-Plugin/plugin/main.lua", 'reskate.log("hi")')
        binary = entire.read_bytes()
        splits = [self.base / "first.001", self.base / "middle.002", self.base / "final.003"]
        cuts = [binary[:17], binary[17:114], binary[114:]]
        for path, part in zip(splits, cuts): path.write_bytes(part)
        with SegmentedReader(splits) as stream:
            with zipfile.ZipFile(stream) as z:
                self.assertIn("Mods/Alpha-Plugin/manifest.json", z.namelist())
        result = inspect_mod_archive(splits)
        self.assertEqual(result["mod_count"], 1)
        self.assertIn("plugin", result["mods"][0]["kinds"])

    def test_natural_language_routing(self):
        self.assertEqual(task_plan("Swap skater with Kitana model")["classification"], "cosmetic")
        self.assertEqual(task_plan("Import a Skater XL map")["classification"], "map")

    def test_mcp_protocol(self):
        wire = "\n".join([
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
            json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "forge_plan", "arguments": {"request": "Make a skate map"}}}),
        ]) + "\n"
        proc = subprocess.run([sys.executable, "-m", "reskateforge", "mcp"], input=wire, text=True, capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        replies = [json.loads(s) for s in proc.stdout.splitlines()]
        self.assertEqual(replies[0]["result"]["serverInfo"]["name"], "ReSkateForge")
        self.assertTrue(any(t["name"] == "forge_package" for t in replies[1]["result"]["tools"]))
        self.assertEqual(json.loads(replies[2]["result"]["content"][0]["text"])["classification"], "map")


class OwnerDefaultTests(unittest.TestCase):
    def test_owner_comes_from_the_environment_then_a_private_file_then_a_placeholder(self):
        import os
        import tempfile
        from pathlib import Path
        from unittest import mock

        from reskateforge import studio

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch.object(studio, "ROOT", root), mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("RESKATE_OWNER", None)
                self.assertEqual(studio.default_owner(), "YourTeam")
                (root / "local-config").mkdir()
                (root / "local-config" / "owner.txt").write_text("\n  TeamFromFile  \n", encoding="utf-8")
                self.assertEqual(studio.default_owner(), "TeamFromFile")
                os.environ["RESKATE_OWNER"] = "TeamFromEnv"
                self.assertEqual(studio.default_owner(), "TeamFromEnv")

    def test_no_personal_name_is_a_source_default(self):
        from pathlib import Path

        package = Path(__file__).resolve().parents[1] / "reskateforge"
        for path in package.glob("*.py"):
            self.assertNotIn('default="GennyWoo"', path.read_text(encoding="utf-8"), path.name)


if __name__ == "__main__":
    unittest.main()
