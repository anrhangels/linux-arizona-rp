#!/usr/bin/env python3
"""Arizona RP: воспроизводимая установка в отдельный префикс, без системного Wine."""
import argparse
from contextlib import contextmanager
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
APP = 'io.github.Faugus.faugus-launcher'
GAMEID = 'arizona-launcher'
DATA = Path(os.environ.get('XDG_DATA_HOME', HOME / '.local/share')) / 'linux-arizona-rp'
STATE = Path(os.environ.get('XDG_STATE_HOME', HOME / '.local/state')) / 'linux-arizona-rp'
CACHE = Path(os.environ.get('XDG_CACHE_HOME', HOME / '.cache')) / 'linux-arizona-rp'
FAUGUS = HOME / '.var/app' / APP / 'data/faugus-launcher'
LOCKFILE = STATE / 'operation.lock'
DOWNLOADS = json.loads((ROOT / 'configs/downloads.json').read_text())
FONT_KEYS = [r'Software\Microsoft\Windows NT\CurrentVersion\Fonts',
             r'Software\Microsoft\Windows\CurrentVersion\Fonts']


def call(args, **kw):
    return subprocess.run([str(x) for x in args], check=True, **kw)


def digest_matches(path, spec):
    if not path.is_file():
        return False
    h = hashlib.sha256() if 'sha256' in spec else hashlib.sha1()
    if 'git_sha1' in spec:
        if path.stat().st_size != spec['size']:
            return False
        h.update(b'blob ' + str(path.stat().st_size).encode() + b'\0')
    with path.open('rb') as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest() == spec.get('sha256', spec.get('git_sha1'))


def fetch(spec, dest):
    """Pinned upstream file: no partial output and no unverified cache reuse."""
    if digest_matches(dest, spec):
        return dest
    if urlsplit(spec['url']).scheme != 'https':
        raise ValueError('Требуется HTTPS')
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + '.part')
    print('Скачивание: ' + dest.name, flush=True)
    try:
        with urlopen(Request(spec['url'], headers={'User-Agent': 'linux-arizona-rp/1.0'}), timeout=60) as src:
            if urlsplit(src.url).scheme != 'https':
                raise ValueError('Небезопасное перенаправление')
            with tmp.open('wb') as output:
                shutil.copyfileobj(src, output, 1024 * 1024)
        if not digest_matches(tmp, spec):
            raise ValueError('Не совпала контрольная сумма: ' + dest.name)
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)
    return dest


def latest_launcher():
    """Resolve the official current release instead of freezing its EXE address."""
    with urlopen(Request(DOWNLOADS['launcher']['release_api'],
                         headers={'User-Agent': 'linux-arizona-rp/1.0',
                                  'Accept': 'application/vnd.github+json'}), timeout=45) as response:
        release = json.load(response)
    matches = [a for a in release.get('assets', []) if a.get('name') == DOWNLOADS['launcher']['asset']]
    if len(matches) != 1:
        raise ValueError('В текущем официальном выпуске не найден установщик; используйте --installer с файлом с arizona-rp.com')
    asset = matches[0]
    url, digest = asset.get('browser_download_url', ''), asset.get('digest', '')
    if not url.startswith('https://github.com/dogoran-el/arizona-launcher/releases/download/'):
        raise ValueError('Изменился официальный адрес установщика; требуется проверка источника')
    if not digest or not digest.startswith('sha256:') or len(digest.split(':', 1)[1]) != 64:
        raise ValueError('Для нового установщика не опубликована SHA-256; скачайте с сайта и используйте --installer')
    version = str(release.get('tag_name', ''))
    import re
    if not re.fullmatch(r'[A-Za-z0-9._-]+', version):
        raise ValueError('Неожиданный номер официального выпуска')
    print('Найден актуальный официальный лаунчер Arizona.', flush=True)
    return {'url': url, 'sha256': digest.split(':', 1)[1]}, version


def download_directories():
    """XDG is parsed as data; never source a user-controlled shell file."""
    roots = []
    config = Path(os.environ.get('XDG_CONFIG_HOME', HOME / '.config')) / 'user-dirs.dirs'
    if config.is_file():
        for row in config.read_text().splitlines():
            if row.startswith('XDG_DOWNLOAD_DIR='):
                value = row.split('=', 1)[1].strip().strip('"').replace('${HOME}', str(HOME)).replace('$HOME', str(HOME))
                path = Path(value).expanduser()
                if path.is_absolute():
                    roots.append(path)
    roots += [HOME / 'Downloads', HOME / 'Загрузки']
    return list(dict.fromkeys(roots))


def local_installer(value):
    """An explicit path, a filename in Downloads, or 'auto' selects a local EXE."""
    if str(value) != 'auto':
        path = value.expanduser()
        if path.is_file():
            return path.resolve()
        if path.name == str(path):
            for root in download_directories():
                if (root / path).is_file():
                    return (root / path).resolve()
        raise ValueError('Установщик не найден: ' + str(value))
    found = []
    for root in download_directories():
        if root.is_dir():
            for candidate in root.iterdir():
                if (candidate.is_file() and 'arizona' in candidate.name.lower()
                        and candidate.suffix.lower() == '.exe'):
                    found.append(candidate)
    if not found:
        raise ValueError('В папках загрузок не найден Arizona EXE; передайте --installer /полный/путь.exe')
    return max(found, key=lambda p: p.stat().st_mtime).resolve()


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('wb', dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        stream.write(data if isinstance(data, bytes) else data.encode())
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


class Snapshot:
    """Write-ahead backup; files created during setup are removed on restore."""
    def __init__(self):
        self.root = STATE / 'backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        self.root.mkdir(parents=True, mode=0o700)
        self.entries = []

    def save(self, path):
        path = path.absolute()
        if any(e['path'] == str(path) for e in self.entries):
            return
        if path.is_symlink():
            raise ValueError('Не заменяем символическую ссылку: ' + str(path))
        copy = self.root / str(len(self.entries))
        existed = path.exists()
        if existed:
            if not path.is_file():
                raise ValueError('Ожидался обычный файл: ' + str(path))
            shutil.copy2(path, copy)
        self.entries.append({'path': str(path), 'backup': copy.name if existed else None})
        atomic(self.root / 'restore.json', json.dumps(self.entries, ensure_ascii=False, indent=2) + '\n')

    def write(self, path, text):
        self.save(path)
        atomic(path, text)


def restore(manifest):
    require_closed()
    manifest = manifest.expanduser().resolve()
    if not manifest.is_relative_to((STATE / 'backups').resolve()) or manifest.name != 'restore.json':
        raise ValueError('Нужен restore.json из каталога резервных копий этого проекта')
    plan = json.loads(manifest.read_text())
    checked = []
    for item in plan:
        dest = Path(item['path'])
        if not dest.is_absolute() or not dest.resolve().is_relative_to(HOME.resolve()) or dest.is_symlink():
            raise ValueError('Недопустимая цель восстановления')
        source = manifest.parent / item['backup'] if item['backup'] else None
        if source and (not source.resolve().is_relative_to(manifest.parent) or not source.is_file()):
            raise ValueError('Резервный файл не найден')
        checked.append((source, dest))
    for source, dest in checked:
        if source:
            atomic(dest, source.read_bytes())
            shutil.copymode(source, dest)
        else:
            dest.unlink(missing_ok=True)
    print('Файлы восстановлены. Игра, Flatpak и системные пакеты не удалены.')


def require_closed():
    # Keep imported checked guard, including Wine applications in other prefixes.
    import arizona
    arizona.require_closed()


@contextmanager
def operation_lock():
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with LOCKFILE.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Установка или запуск Arizona уже выполняется')
        yield


def setup_flatpak():
    call(['flatpak', 'remote-add', '--user', '--if-not-exists', 'flathub',
          'https://dl.flathub.org/repo/flathub.flatpakrepo'])
    if subprocess.run(['flatpak', 'info', APP], stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL).returncode:
        call(['flatpak', 'install', '--user', '-y', 'flathub', APP])


def ensure_runner():
    runner = DATA / 'runners' / DOWNLOADS['proton']['directory']
    if (runner / 'proton').is_file():
        return runner
    if runner.exists():
        raise ValueError('Неполный каталог Proton, проверьте его: ' + str(runner))
    archive = fetch(DOWNLOADS['proton'], CACHE / 'GE-Proton11-11-x86_64.tar.gz')
    runner.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='extract-', dir=runner.parent) as tmp:
        with tarfile.open(archive) as tf:
            if not hasattr(tarfile, 'data_filter'):
                raise ValueError('Обновите Python: необходим безопасный tarfile.data_filter (3.12+ или исправленный 3.10/3.11)')
            tf.extractall(tmp, filter='data')
        candidates = list(Path(tmp).glob('*/proton'))
        if len(candidates) != 1:
            raise ValueError('Неожиданная структура архива Proton')
        shutil.move(str(candidates[0].parent), runner)
    return runner


def ensure_umu():
    """Reuse only the exact pinned UMU; another game's copy is never overwritten."""
    target = DATA / 'umu-run'
    spec = DOWNLOADS['umu']
    if not digest_matches(target, spec):
        source = FAUGUS / 'umu-run'
        contents = source.read_bytes() if source.is_file() else None
        if contents is not None and hashlib.sha256(contents).hexdigest() == spec['sha256']:
            atomic(target, contents)
            print('Используется установленный UMU: SHA-256 совпала.', flush=True)
        else:
            fetch(spec, target)
    target.chmod(0o755)
    return target


def dejavu_font(bold=False):
    filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    pattern = "DejaVu Sans:style=Bold" if bold else "DejaVu Sans"
    selected = call(['fc-match', '-f', '%{file}', pattern],
                    capture_output=True, text=True).stdout.strip()
    font = Path(selected)
    if font.is_file() and font.name.lower() == filename.lower():
        return font
    # Faugus' installed runtime may provide the font even if the host does not.
    runtime = call(['flatpak', 'info', '--show-runtime', APP],
                   capture_output=True, text=True).stdout.strip()
    location = call(['flatpak', 'info', '--show-location', runtime],
                    capture_output=True, text=True).stdout.strip()
    font = Path(location) / 'files/share/fonts/dejavu' / filename
    if font.is_file():
        print('DejaVu Sans найден в установленном runtime Faugus.', flush=True)
        return font
    raise ValueError('Не найден ' + filename + '; установите пакет DejaVu для вашего дистрибутива')


def command(prefix, runner, exe, logs, extra=()):
    umu = DATA / 'umu-run'
    args = ['flatpak', 'run', '--env=LANG=ru_RU.UTF-8',
            '--env=LC_ALL=ru_RU.UTF-8', '--command=env', '--filesystem=' + str(DATA),
            '--filesystem=' + str(prefix), '--filesystem=' + str(logs),
            '--filesystem=' + str(CACHE) + ':ro']
    if isinstance(exe, Path):
        args.append('--filesystem=' + str(exe.parent) + ':ro')
    args += [APP]
    for key in ['WINEDLLOVERRIDES', 'PROTON_ENABLE_WAYLAND', 'PROTON_USE_WINED3D',
                'PROTON_USE_WOW64', 'MANGOHUD', 'VK_ADD_IMPLICIT_LAYER_PATH']:
        args += ['-u', key]
    args += ['WINEPREFIX=' + str(prefix), 'PROTONPATH=' + str(runner), 'GAMEID=0',
             'UMU_USE_STEAM=1', 'UMU_CONTAINER_NSENTER=1', 'MANGOHUD=0',
             'WINEDEBUG=-all,err+all', str(umu), str(exe)]
    return args + list(extra)


def run_logged(args, logfile):
    print('Журнал: ' + str(logfile), flush=True)
    with logfile.open('w') as out:
        call(args, stdout=out, stderr=subprocess.STDOUT)


def launcher_in(prefix):
    root = prefix / 'drive_c/users'
    found = list(root.glob('*/AppData/Local/Programs/Arizona Games Launcher/Arizona Games Launcher.exe'))
    # Proton can alias the host username to steamuser: compare actual files.
    found = list(dict.fromkeys(p.resolve() for p in found
                              if p.is_file() and p.resolve().is_relative_to(prefix.resolve())))
    if len(found) > 1:
        raise ValueError('Найдено несколько лаунчеров; выберите префикс с одной установкой')
    return found[0] if found else None


def font_plan(windows=None):
    # Use the pinned CBDT font across distros (Fedora's packaged font is COLRv1).
    emoji = fetch(DOWNLOADS['emoji'], CACHE / 'NotoColorEmoji.ttf')
    dejavu = dejavu_font()
    result = [(emoji, 'NotoColorEmoji.ttf', 'Noto Color Emoji (TrueType)'),
              (dejavu, 'DejaVuSans.ttf', 'DejaVu Sans (TrueType)')]
    if windows:
        wanted = {'segoeui.ttf': 'Segoe UI (TrueType)', 'seguisb.ttf': 'Segoe UI Semibold (TrueType)',
                  'seguiemj.ttf': 'Segoe UI Emoji (TrueType)', 'segoeuiemoji.ttf': 'Segoe UI Emoji (TrueType)'}
        imported = set()
        for f in sorted(windows.expanduser().iterdir()):
            key = f.name.lower()
            if f.is_file() and key in wanted and wanted[key] not in imported:
                name = 'seguiemj.ttf' if key == 'segoeuiemoji.ttf' else key
                with f.open('rb') as font_file:
                    signature = font_file.read(4)
                if signature not in (b'\x00\x01\x00\x00', b'OTTO', b'ttcf'):
                    raise ValueError('Некорректный файл шрифта: ' + str(f))
                result.append((f, name, wanted[key])); imported.add(wanted[key])
        if not imported:
            raise ValueError('В папке нет Segoe UI / Semibold / Emoji; см. docs/fonts.md')
    return result


def install_azrtc_font_files(prefix, snapshot):
    """AZRTC reads exact file names; Wine family replacements cannot supply them."""
    folder = prefix / 'drive_c/windows/Fonts'
    for name, bold in [('segoeui.ttf', False), ('seguisb.ttf', True)]:
        target = folder / name
        # Preserve original Microsoft fonts and any user-provided alternative.
        if target.exists():
            continue
        if target.is_symlink():
            raise ValueError('Повреждённая ссылка шрифта: ' + str(target))
        source = dejavu_font(bold=bold)
        snapshot.write(target, source.read_bytes())
        print('AZRTC: ' + name + ' → ' + source.name, flush=True)


def install_fonts(prefix, runner, logs, snapshot, windows=None):
    fonts = font_plan(windows)
    # Back up registry before invoking Wine, which changes registry files as a whole.
    for name in ['user.reg', 'system.reg', 'userdef.reg']:
        snapshot.save(prefix / name)
    for source, name, family in fonts:
        target = prefix / 'drive_c/windows/Fonts' / name
        if not target.is_file() or source.read_bytes() != target.read_bytes():
            snapshot.write(target, source.read_bytes())
        for hive in ['HKLM', 'HKCU']:
            for key in FONT_KEYS:
                run_logged(command(prefix, runner, 'reg.exe', logs,
                           ['add', hive + '\\' + key, '/v', family, '/t', 'REG_SZ', '/d', name, '/f']),
                           logs / ('font-' + name + '-' + hive + '-' + str(FONT_KEYS.index(key)) + '.log'))
    install_azrtc_font_files(prefix, snapshot)
    # Add fallback family mappings only when original Segoe wasn't supplied.
    families = {family for _, _, family in fonts}
    for missing, fallback in [('Segoe UI', 'DejaVu Sans'), ('Segoe UI Semibold', 'DejaVu Sans'),
                              ('Segoe UI Emoji', 'Noto Color Emoji')]:
        key = r'HKCU\Software\Wine\Fonts\Replacements'
        query = subprocess.run(command(prefix, runner, 'reg.exe', logs,
                               ['query', key, '/v', missing]), capture_output=True, text=True, errors='replace')
        import re
        own = bool(re.search(r'REG_MULTI_SZ\s+' + re.escape(fallback) + r'\s*$', query.stdout, re.M))
        if missing + ' (TrueType)' in families:
            if own:
                run_logged(command(prefix, runner, 'reg.exe', logs, ['delete', key, '/v', missing, '/f']),
                           logs / ('remove-fallback-' + missing.replace(' ', '-') + '.log'))
        elif query.returncode != 0 or own:
            run_logged(command(prefix, runner, 'reg.exe', logs,
                       ['add', key, '/v', missing, '/t', 'REG_MULTI_SZ', '/d', fallback, '/f']),
                       logs / ('fallback-' + missing.replace(' ', '-') + '.log'))
    # Host + sandboxed CEF fallback use fontconfig. Preserve existing user rules.
    host_fonts = Path(os.environ.get('XDG_DATA_HOME', HOME / '.local/share')) / 'fonts/linux-arizona-rp'
    for source, name, _ in fonts:
        snapshot.write(host_fonts / name, source.read_bytes())
    call(['fc-cache', '-f', str(host_fonts)])


def register(exe, prefix, runner, snapshot):
    target = FAUGUS / 'games.json'
    original = target.read_bytes() if target.exists() else b'[]'
    games = json.loads(original)
    if not isinstance(games, list) or any(not isinstance(g, dict) for g in games):
        raise ValueError('Неожиданный формат списка игр Faugus')
    matching = [g for g in games if g.get('gameid') == GAMEID]
    if len(matching) > 1:
        raise ValueError('Дубликаты Arizona в Faugus')
    if matching:
        record = matching[0]
        old = Path(record.get('prefix', '')).expanduser()
        if old != prefix:
            raise ValueError('Arizona в Faugus уже использует другой префикс. Укажите --prefix ' + shlex.quote(str(old)))
    else:
        record = {'gameid': GAMEID, 'title': 'Arizona RP', 'game_arguments': '',
                  'launch_arguments': '', 'playtime': 0, 'hidden': False, 'runtime': 'umu-steamrt4'}
        games.append(record)
    record.update(path=str(exe), prefix=str(prefix), runner=str(runner))
    for key in ['mangohud', 'gamemode', 'sdl_enabled', 'no_sleep', 'disable_umu', 'discord_rpc']:
        record.setdefault(key, '')
    if target.exists() and target.read_bytes() != original:
        raise ValueError('Faugus изменил games.json. Закройте его и повторите.')
    snapshot.write(target, json.dumps(games, ensure_ascii=False, indent=2) + '\n')
    # Also supply UMU where Faugus itself expects it; never replace an existing copy.
    if not (FAUGUS / 'umu-run').exists():
        snapshot.write(FAUGUS / 'umu-run', (DATA / 'umu-run').read_bytes())
        (FAUGUS / 'umu-run').chmod(0o755)


def install_hud():
    import re
    runtime = call(['flatpak', 'info', '--show-runtime', APP], capture_output=True, text=True).stdout.strip()
    location = call(['flatpak', 'info', '--show-location', runtime], capture_output=True, text=True).stdout.strip()
    text = (Path(location) / 'metadata').read_text()
    section = re.search(r'\[Extension org\.freedesktop\.Platform\.VulkanLayer\]\n([^\[]*)', text)
    version = re.search(r'^version\s*=\s*(\S+)', section[1], re.M) if section else None
    if not version:
        raise ValueError('В runtime не найдена ветка MangoHud')
    ref = 'org.freedesktop.Platform.VulkanLayer.MangoHud//' + version[1]
    if subprocess.run(['flatpak', 'info', ref], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        call(['flatpak', 'install', '--user', '-y', 'flathub', ref])
    import samp_linux
    samp_linux.configure_hud(GAMEID)


def install_shortcut(snapshot):
    # Copy the runtime helpers so moving the downloaded repository doesn't break launch.
    runtime = DATA / 'tools/scripts'
    for name in ['arizona.py', 'samp_linux.py', 'arizona.sh', 'install.py']:
        snapshot.write(runtime / name, (ROOT / 'scripts' / name).read_bytes())
    for name in ['MangoHud.conf', 'presets.conf', 'downloads.json']:
        snapshot.write(DATA / 'tools/configs' / name, (ROOT / 'configs' / name).read_bytes())
    bins = HOME / '.local/bin'
    script = '#!/bin/sh\nexec python3 ' + shlex.quote(str(runtime / 'play.py')) + ' "$@"\n'
    snapshot.write(runtime / 'play.py', (ROOT / 'scripts/play.py').read_bytes())
    snapshot.write(bins / 'arizona', script)
    (bins / 'arizona').chmod(0o755)
    applications = Path(os.environ.get('XDG_DATA_HOME', HOME / '.local/share')) / 'applications'
    snapshot.write(applications / 'linux-arizona-rp.desktop',
        '[Desktop Entry]\nType=Application\nName=Arizona RP\nComment=Arizona RP через Faugus и Proton\n'
        'Exec="' + str(bins / 'arizona').replace('\\', '\\\\').replace('"', '\\"').replace('`','\\`').replace('$','\\$').replace('%','%%') + '"\n'
        'Icon=applications-games\nTerminal=false\nCategories=Game;\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--yes', action='store_true', help='подтверждение системной части дано оболочке')
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--no-system-packages', action='store_true')
    parser.add_argument('--no-hud', action='store_true')
    parser.add_argument('--installer', type=Path)
    parser.add_argument('--windows-fonts', type=Path)
    parser.add_argument('--fonts-only', action='store_true')
    parser.add_argument('--restore', type=Path)
    parser.add_argument('--prefix', type=Path, default=HOME / 'Games/arizona-rp/prefix')
    args = parser.parse_args()
    if args.prefix.expanduser().is_symlink():
        raise ValueError('Префикс не должен быть символической ссылкой')
    prefix = args.prefix.expanduser().resolve()
    if args.plan:
        print('Префикс:', prefix)
        print('Компоненты: GE-Proton 11-11, UMU 1.4.4-patch, актуальный официальный Arizona Launcher, Noto Color Emoji, DejaVu Sans')
        print('MangoHud:', 'пропустить' if args.no_hud else 'установить под runtime Faugus')
        print('Изменений и сетевых запросов нет.')
        return 0
    if os.getuid() == 0:
        raise ValueError('Запускайте без sudo')
    if sys.version_info < (3, 10):
        raise ValueError('Нужен Python 3.10 или новее')
    if args.restore:
        with operation_lock():
            restore(args.restore)
        return 0
    if platform.machine() != 'x86_64':
        raise ValueError('Эта сборка подготовлена для Linux x86_64')
    if not prefix.is_relative_to(HOME) or prefix.is_symlink():
        raise ValueError('Префикс должен быть обычной папкой внутри домашнего каталога')
    for binary in ['flatpak', 'fc-match', 'fc-cache']:
        if not shutil.which(binary):
            raise ValueError('Не найдена зависимость ' + binary + '; запустите bash install.sh')
    require_closed()
    with operation_lock():
        snapshot = Snapshot()
        print('Резервная копия / план отката:', snapshot.root / 'restore.json', flush=True)
        logs = STATE / 'logs' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        logs.mkdir(parents=True, mode=0o700)
        setup_flatpak()
        runner = ensure_runner()
        ensure_umu()
        exe = launcher_in(prefix)
        if args.fonts_only and not exe:
            raise ValueError('Для --fonts-only нужен уже установленный лаунчер в этом префиксе')
        if not exe:
            if prefix.exists() and any(prefix.iterdir()) and not (prefix / '.linux-arizona-rp-managed').is_file():
                raise ValueError('Каталог префикса не пуст и не содержит Arizona: выберите новый --prefix')
            if args.installer:
                installer = local_installer(args.installer)
            else:
                spec, version = latest_launcher()
                installer = fetch(spec, CACHE / 'launchers' / version / 'Arizona-Games-Launcher.exe')
            if not installer.is_file():
                raise ValueError('Не найден установщик')
            with installer.open('rb') as installer_file:
                signature = installer_file.read(2)
            if signature != b'MZ':
                raise ValueError('Установщик должен быть Windows EXE с официального сайта')
            prefix.mkdir(parents=True, exist_ok=True)
            atomic(prefix / '.linux-arizona-rp-managed', 'Created by linux-arizona-rp installer\n')
            print('Запускается официальный установщик. Если он открыл лаунчер — закройте лаунчер, чтобы продолжить.', flush=True)
            run_logged(command(prefix, runner, installer, logs, ['/S']), logs / 'launcher-install.log')
            exe = launcher_in(prefix)
            if not exe:
                raise ValueError('Лаунчер не найден в стандартном пути. См. журнал ' + str(logs))
        install_fonts(prefix, runner, logs, snapshot, args.windows_fonts)
        if args.fonts_only:
            print('Шрифты установлены. Откат: ' + str(snapshot.root / 'restore.json'))
            return 0
        register(exe, prefix, runner, snapshot)
        if not args.no_hud:
            # The installer-wide snapshot already contains the original Faugus record.
            install_hud()
        install_shortcut(snapshot)
        print('\nГотово: ~/.local/bin/arizona\nВ лаунчере скачайте клиент Arizona RP и войдите в аккаунт.')
        print('Возврат изменённых файлов: bash install.sh --restore ' + shlex.quote(str(snapshot.root / 'restore.json')))
    return 0


if __name__ == '__main__':
    os.umask(0o077)
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as exc:
        sys.exit('ОСТАНОВЛЕНО: ' + str(exc))
