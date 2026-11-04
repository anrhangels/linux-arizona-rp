import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import arizona


class FontRepairTests(unittest.TestCase):
    def fixture(self, root):
        client = root / 'client'
        client.mkdir()
        for name in ['font.ttf', 'font.ttf:Zone.Identifier', 'samp.dll',
                     'samp.dll:Zone.Identifier', 'missing.ttf:Zone.Identifier']:
            (client / name).write_text(name)
        return client

    def test_preview_does_not_modify_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client = self.fixture(root)
            before = sorted(p.name for p in client.iterdir())
            arizona.fix_fonts(client)
            self.assertEqual(before, sorted(p.name for p in client.iterdir()))
            self.assertEqual([p.name for p in arizona.font_sidecars(client)], ['font.ttf:Zone.Identifier'])

    def test_apply_restore_and_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client = self.fixture(root)
            with patch.object(arizona.lab, 'STATE', root / 'state'), patch.object(arizona, 'require_closed'):
                arizona.fix_fonts(client, True)
                self.assertTrue((client / 'font.ttf').is_file())
                self.assertTrue((client / 'samp.dll:Zone.Identifier').is_file())
                self.assertFalse((client / 'font.ttf:Zone.Identifier').exists())
                arizona.fix_fonts(client, True)
                manifest, = (root / 'state/backups').glob('*/restore.json')
                arizona.restore_fonts(manifest)
                arizona.restore_fonts(manifest)
                self.assertEqual((client / 'font.ttf:Zone.Identifier').read_text(), 'font.ttf:Zone.Identifier')

    def test_restore_does_not_overwrite_new_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client = self.fixture(root)
            with patch.object(arizona.lab, 'STATE', root / 'state'), patch.object(arizona, 'require_closed'):
                arizona.fix_fonts(client, True)
                (client / 'font.ttf:Zone.Identifier').write_text('new')
                manifest, = (root / 'state/backups').glob('*/restore.json')
                with self.assertRaises(ValueError):
                    arizona.restore_fonts(manifest)
                self.assertEqual((client / 'font.ttf:Zone.Identifier').read_text(), 'new')

    def test_symlink_escape_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client = self.fixture(root)
            outside = root / 'outside'
            outside.mkdir()
            (outside / 'other.ttf').write_text('font')
            (outside / 'other.ttf:Zone.Identifier').write_text('sidecar')
            (client / 'linked').symlink_to(outside, target_is_directory=True)
            (client / 'alias.ttf:Zone.Identifier').symlink_to(outside / 'other.ttf:Zone.Identifier')
            (client / 'alias.ttf').write_text('font')
            self.assertEqual([p.name for p in arizona.font_sidecars(client)], ['font.ttf:Zone.Identifier'])

    def test_busy_guard_prevents_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = self.fixture(Path(tmp))
            with patch.object(arizona, 'require_closed', side_effect=ValueError('busy')):
                with self.assertRaises(ValueError):
                    arizona.fix_fonts(client, True)
            self.assertTrue((client / 'font.ttf:Zone.Identifier').exists())


if __name__ == '__main__':
    unittest.main()
