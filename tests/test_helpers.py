import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("helpers", Path(__file__).parents[1] / "scripts/samp_linux.py")
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)


class ConfigurationTests(unittest.TestCase):
    def test_unknown_game_is_rejected(self):
        with self.assertRaises(ValueError):
            helpers.select_game([{"gameid": "known"}], "unknown")

    def test_missing_runtime_leaves_config_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            games = Path(tmp) / "games.json"
            original = '[{"gameid":"example"}]'
            games.write_text(original)
            with patch.object(helpers, "GAMES", games), patch.object(
                helpers, "layer_runtime", side_effect=ValueError("missing")):
                with self.assertRaises(ValueError):
                    helpers.configure_hud("example")
            self.assertEqual(games.read_text(), original)

    def test_scoped_launch_grants_prefix_and_read_only_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);prefix=root/"префикс с пробелом";runner=root/"runner";runner.mkdir()
            (prefix/"drive_c").mkdir(parents=True);(runner/"proton").write_text("fixture")
            hud=root/"data/linux-arizona-rp/example";hud.mkdir(parents=True)
            with patch.object(helpers,"DATA",root/"data"):
                args=helpers.flatpak_launch_command({"gameid":"example","prefix":str(prefix),"runner":str(runner)})
            self.assertIn("--filesystem="+str(prefix),args)
            self.assertIn("--filesystem="+str(runner)+":ro",args)
            self.assertIn("--filesystem="+str(hud)+":ro",args)
            self.assertEqual(args[-4:],[helpers.APP,"--game","example","--logs"])
            self.assertNotIn("--filesystem=home",args)

    def test_reconfigure_preserves_options_and_backups(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            games = root / "games.json"
            original = [{"gameid": "example", "runner": "TestProton",
                         "launch_arguments": "OTHER=value DXVK_HUD=fps",
                         "path": "unchanged.exe", "prefix": "unchanged-prefix"}]
            games.write_text(json.dumps(original))
            runtime = root / "runtime"
            for arch, abi in [("x86_64", "x86_64-linux-gnu"), ("x86", "i386-linux-gnu")]:
                library = runtime / "lib" / abi / "libMangoHud.so"
                library.parent.mkdir(parents=True)
                library.write_bytes(b"test fixture")
                manifest = runtime / "share/vulkan/implicit_layer.d" / f"MangoHud.{arch}.json"
                manifest.parent.mkdir(parents=True, exist_ok=True)
                manifest.write_text(json.dumps({"layer": {"library_path": "old"}}))
            with patch.object(helpers, "GAMES", games), patch.object(helpers, "DATA", root / "data"), \
                 patch.object(helpers, "STATE", root / "state"), \
                 patch.object(helpers, "layer_runtime", return_value=runtime):
                helpers.configure_hud("example")
                helpers.configure_hud("example")
            result = json.loads(games.read_text())[0]
            self.assertIn("OTHER=value", result["launch_arguments"])
            self.assertEqual(result["launch_arguments"].count("MANGOHUD_CONFIGFILE="), 1)
            self.assertEqual(result["prefix"], "unchanged-prefix")
            self.assertEqual(result["path"], "unchanged.exe")
            self.assertEqual(len(list((root / "state/backups").glob("*/games.json"))), 2)


if __name__ == "__main__":
    unittest.main()
