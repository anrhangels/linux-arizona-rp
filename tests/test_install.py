import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import install as setup

ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def test_proton_user_alias_is_one_launcher_but_distinct_installs_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix=Path(tmp);users=prefix/'drive_c/users'
            exe=users/'steamuser/AppData/Local/Programs/Arizona Games Launcher/Arizona Games Launcher.exe'
            exe.parent.mkdir(parents=True);exe.write_bytes(b'MZ')
            (users/'hostuser').symlink_to('steamuser',target_is_directory=True)
            self.assertEqual(setup.launcher_in(prefix),exe)
            second=users/'other/AppData/Local/Programs/Arizona Games Launcher/Arizona Games Launcher.exe'
            second.parent.mkdir(parents=True);second.write_bytes(b'MZ')
            with self.assertRaises(ValueError):setup.launcher_in(prefix)

    def test_plan_never_creates_files_or_calls_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch.object(setup, 'HOME', home), patch.object(setup, 'urlopen', side_effect=AssertionError('network')), \
                 patch.object(sys, 'argv', ['install.py', '--plan', '--prefix', str(home / 'game')]):
                self.assertEqual(setup.main(), 0)
            self.assertEqual(list(home.iterdir()), [])

    def test_shell_plan_has_no_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = subprocess.run(['bash', str(ROOT/'install.sh'), '--plan'],
                               env={**os.environ, 'HOME': tmp}, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_invalid_shell_option_stops_before_package_manager(self):
        r = subprocess.run(['bash', str(ROOT/'install.sh'), '--not-an-option', '--yes'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn('Неизвестный параметр', r.stderr)

    def test_digest_validates_sha256_and_git_blob(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'font';p.write_bytes(b'test font')
            sha = hashlib.sha256(b'test font').hexdigest()
            self.assertTrue(setup.digest_matches(p, {'sha256': sha}))
            git = hashlib.sha1(b'blob 9\0test font').hexdigest()
            self.assertTrue(setup.digest_matches(p, {'git_sha1': git, 'size': 9}))
            p.write_bytes(b'corrupted')
            self.assertFalse(setup.digest_matches(p, {'sha256': sha}))

    def test_bad_download_does_not_replace_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'asset';p.write_bytes(b'keep original')
            response = io.BytesIO(b'bad download');response.url='https://example.com/a'
            with patch.object(setup, 'urlopen', return_value=response):
                with self.assertRaises(ValueError):
                    setup.fetch({'url': 'https://example.com/a', 'sha256': '0'*64}, p)
            self.assertEqual(p.read_bytes(), b'keep original')
            self.assertFalse(p.with_name('asset.part').exists())

    def test_verified_cache_needs_no_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'asset';p.write_bytes(b'valid')
            with patch.object(setup, 'urlopen', side_effect=AssertionError('network')):
                self.assertEqual(setup.fetch({'sha256': hashlib.sha256(b'valid').hexdigest()}, p), p)

    def test_insecure_download_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(setup, 'urlopen', side_effect=AssertionError('network')):
                with self.assertRaises(ValueError):
                    setup.fetch({'url': 'http://example.com/file', 'sha256':'0'*64}, Path(tmp)/'x')

    def test_snapshot_restore_original_and_remove_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);old=root/'old';new=root/'new';old.write_text('original');old.chmod(0o755)
            with patch.object(setup,'STATE',root/'state'),patch.object(setup,'HOME',root),patch.object(setup,'require_closed'):
                snap=setup.Snapshot();snap.write(old,'changed');snap.write(new,'created')
                setup.restore(snap.root/'restore.json')
                self.assertEqual(old.read_text(),'original');self.assertFalse(new.exists())
                self.assertTrue(old.stat().st_mode & 0o100)

    def test_snapshot_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);original=root/'original';original.write_text('keep');link=root/'link';link.symlink_to(original)
            with patch.object(setup,'STATE',root/'state'):
                snap=setup.Snapshot()
                with self.assertRaises(ValueError):snap.write(link,'bad')
            self.assertEqual(original.read_text(),'keep')

    def test_restore_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);home=root/'home';backup=home/'state/backups/one';backup.mkdir(parents=True)
            outside=root/'outside';outside.write_text('keep')
            manifest=backup/'restore.json';manifest.write_text(json.dumps([{'path':str(home/'../outside'),'backup':None}]))
            with patch.object(setup,'HOME',home),patch.object(setup,'STATE',home/'state'),patch.object(setup,'require_closed'):
                with self.assertRaises(ValueError):setup.restore(manifest)
            self.assertEqual(outside.read_text(),'keep')

    def test_localized_download_folder_and_explicit_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config=root/'.config';config.mkdir();downloads=root/'Мои загрузки';downloads.mkdir()
            (config/'user-dirs.dirs').write_text('XDG_DOWNLOAD_DIR="$HOME/Мои загрузки"\n')
            exe=downloads/'Arizona-Games-Launcher.exe';exe.write_bytes(b'MZfixture')
            with patch.object(setup,'HOME',root),patch.dict(os.environ,{'XDG_CONFIG_HOME':str(config)}):
                self.assertIn(downloads,setup.download_directories())
                self.assertEqual(setup.local_installer(Path('Arizona-Games-Launcher.exe')),exe)
                self.assertEqual(setup.local_installer(Path('auto')),exe)

    def test_download_configuration_is_not_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config=root/'config';config.mkdir();sentinel=root/'executed'
            (config/'user-dirs.dirs').write_text('XDG_DOWNLOAD_DIR="$(touch '+str(sentinel)+')"\n')
            with patch.object(setup,'HOME',root),patch.dict(os.environ,{'XDG_CONFIG_HOME':str(config)}):
                setup.download_directories()
            self.assertFalse(sentinel.exists())

    def test_verified_faugus_umu_reused_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'faugus/umu-run';source.parent.mkdir();source.write_bytes(b'known pinned UMU')
            downloads={**setup.DOWNLOADS,'umu':{'url':'https://example.test/umu','sha256':hashlib.sha256(source.read_bytes()).hexdigest()}}
            with patch.object(setup,'DATA',root/'data'),patch.object(setup,'FAUGUS',source.parent),patch.object(setup,'DOWNLOADS',downloads),patch.object(setup,'urlopen',side_effect=AssertionError('network')):
                target=setup.ensure_umu();self.assertEqual(target.read_bytes(),source.read_bytes());self.assertTrue(target.stat().st_mode & 0o100)

    def test_wrong_faugus_umu_not_trusted_or_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'faugus/umu-run';source.parent.mkdir();source.write_bytes(b'wrong version')
            def fetch(spec,target):
                target.parent.mkdir();target.write_bytes(b'pinned download');return target
            with patch.object(setup,'DATA',root/'data'),patch.object(setup,'FAUGUS',source.parent),patch.object(setup,'fetch',side_effect=fetch) as network:
                target=setup.ensure_umu();network.assert_called_once();self.assertEqual(target.read_bytes(),b'pinned download')
            self.assertEqual(source.read_bytes(),b'wrong version')

    def test_dejavu_from_runtime_when_host_font_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);font=root/'runtime/files/share/fonts/dejavu/DejaVuSans.ttf';font.parent.mkdir(parents=True);font.write_bytes(b'font')
            def call(args,**kwargs):
                if args[0]=='fc-match':return Mock(stdout=str(root/'OtherFont.otf'))
                return Mock(stdout='org.gnome.Platform/x86_64/51' if '--show-runtime' in args else str(root/'runtime'))
            with patch.object(setup,'call',side_effect=call):self.assertEqual(setup.dejavu_font(),font)

    def test_current_launcher_is_resolved_dynamically(self):
        release={'tag_name':'v9.9.9','assets':[{'name':'Arizona-Games-Launcher.exe',
                 'browser_download_url':'https://github.com/dogoran-el/arizona-launcher/releases/download/v9.9.9/Arizona-Games-Launcher.exe',
                 'digest':'sha256:'+'a'*64}]}
        with patch.object(setup,'urlopen',return_value=io.BytesIO(json.dumps(release).encode())):
            spec,tag=setup.latest_launcher()
        self.assertEqual(tag,'v9.9.9');self.assertEqual(spec['sha256'],'a'*64)

    def test_changed_upstream_and_missing_digest_fail_closed(self):
        for url,digest in [('https://evil.example/setup.exe','sha256:'+'a'*64),
                           ('https://github.com/dogoran-el/arizona-launcher/releases/download/v1/a.exe',None)]:
            release={'tag_name':'v1','assets':[{'name':'Arizona-Games-Launcher.exe','browser_download_url':url,'digest':digest}]}
            with patch.object(setup,'urlopen',return_value=io.BytesIO(json.dumps(release).encode())):
                with self.assertRaises(ValueError):setup.latest_launcher()

    def test_register_preserves_other_games_and_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data=root/'faugus';data.mkdir();prefix=root/'prefix';prefix.mkdir();runner=root/'runner'
            other={'gameid':'another','path':'other.exe','launch_arguments':'KEEP=yes'}
            own={'gameid':setup.GAMEID,'prefix':str(prefix),'launch_arguments':'OTHER=keep','playtime':42}
            games=data/'games.json';games.write_text(json.dumps([other,own]));umu=root/'data/umu-run';umu.parent.mkdir();umu.write_bytes(b'umu')
            with patch.object(setup,'FAUGUS',data),patch.object(setup,'STATE',root/'state'),patch.object(setup,'DATA',umu.parent):
                snap=setup.Snapshot();setup.register(prefix/'Arizona Games Launcher.exe',prefix,runner,snap)
            result=json.loads(games.read_text());self.assertEqual(result[0],other)
            self.assertEqual(result[1]['launch_arguments'],'OTHER=keep');self.assertEqual(result[1]['playtime'],42)
            self.assertEqual(result[1]['runner'],str(runner))
            self.assertEqual(json.loads((snap.root/'0').read_text()),[other,own])

    def test_register_does_not_retarget_existing_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data=root/'faugus';data.mkdir();games=data/'games.json'
            original=json.dumps([{'gameid':setup.GAMEID,'prefix':str(root/'old')}]);games.write_text(original)
            with patch.object(setup,'FAUGUS',data),patch.object(setup,'STATE',root/'state'):
                with self.assertRaises(ValueError):setup.register(root/'new/a.exe',root/'new',root/'runner',setup.Snapshot())
            self.assertEqual(games.read_text(),original)

    def test_launcher_search_rejects_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);prefix=root/'prefix';user=prefix/'drive_c/users/steamuser';user.mkdir(parents=True)
            outside=root/'outside/Programs/Arizona Games Launcher';outside.mkdir(parents=True)
            (outside/'Arizona Games Launcher.exe').write_bytes(b'MZ')
            (user/'AppData').symlink_to(root/'outside',target_is_directory=True)
            self.assertIsNone(setup.launcher_in(prefix))

    def test_runner_extract_does_not_write_outside_root(self):
        if not hasattr(tarfile,'data_filter'):self.skipTest('requires patched tarfile')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive=root/'evil.tar'
            with tarfile.open(archive,'w') as tf:
                member=tarfile.TarInfo('../../escaped');member.size=4;tf.addfile(member,io.BytesIO(b'evil'))
            with patch.object(setup,'DATA',root/'data'),patch.object(setup,'CACHE',root/'cache'),patch.object(setup,'fetch',return_value=archive):
                with self.assertRaises(tarfile.TarError):setup.ensure_runner()
            self.assertFalse((root/'escaped').exists())

    def test_original_segoe_removes_only_our_old_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);prefix=root/'prefix';prefix.mkdir();source=root/'segoeui.ttf';source.write_bytes(b'font')
            calls=[]
            def query(args, **kw):
                name=args[-1]
                value={'Segoe UI':'DejaVu Sans', 'Segoe UI Semibold':'My Custom Font', 'Segoe UI Emoji':'Noto Color Emoji'}[name]
                return Mock(returncode=0, stdout=name+'    REG_MULTI_SZ    '+value+'\n')
            with patch.object(setup,'HOME',root),patch.object(setup,'STATE',root/'state'), \
                 patch.dict(os.environ,{'XDG_DATA_HOME':str(root/'share')}), \
                 patch.object(setup,'font_plan',return_value=[(source,'segoeui.ttf','Segoe UI (TrueType)')]), \
                 patch.object(setup,'run_logged',side_effect=lambda args,path:calls.append(args)), \
                 patch.object(setup.subprocess,'run',side_effect=query),patch.object(setup,'call'):
                setup.install_fonts(prefix,root/'runner',root,setup.Snapshot())
            deleted=[c for c in calls if 'delete' in c]
            self.assertEqual(len(deleted),1);self.assertIn('Segoe UI',deleted[0])
            self.assertFalse(any('add' in c and 'My Custom Font' in c for c in calls))
            self.assertEqual((prefix/'drive_c/windows/Fonts/segoeui.ttf').read_bytes(),b'font')

    def test_windows_font_signature_and_known_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);emoji=root/'NotoColorEmoji.ttf';emoji.write_bytes(b'font')
            dj=root/'DejaVuSans.ttf';dj.write_bytes(b'font');win=root/'windows';win.mkdir()
            original=win/'SegoeUIEmoji.ttf';original.write_bytes(b'\x00\x01\x00\x00fixture')
            (win/'not-a-font.txt').write_text('ignore')
            with patch.object(setup,'fetch',return_value=emoji),patch.object(setup,'call',return_value=Mock(stdout=str(dj))):
                plan=setup.font_plan(win)
                self.assertEqual(plan[-1][1],'seguiemj.ttf');self.assertEqual(len(plan),3)
                original.write_bytes(b'<html>')
                with self.assertRaises(ValueError):setup.font_plan(win)


if __name__=='__main__':unittest.main()
