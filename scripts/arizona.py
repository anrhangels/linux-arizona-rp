#!/usr/bin/env python3
"""Arizona RP: проверка, запуск и обратимое исправление служебных файлов."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
import samp_linux as lab


def installed_game(gameid):
    game = lab.select_game(lab.read_games(), gameid)
    exe = Path(game.get('path', '')).expanduser()
    prefix = Path(game.get('prefix', '')).expanduser()
    if not exe.is_file() or exe.name != 'Arizona Games Launcher.exe':
        raise ValueError('В Faugus укажите установленный Arizona Games Launcher.exe, затем повторите команду.')
    if not (prefix / 'drive_c').is_dir() or not exe.resolve().is_relative_to(prefix.resolve()):
        raise ValueError('Лаунчер должен находиться внутри выбранного Wine-префикса с drive_c.')
    return game, exe, prefix


def require_closed():
    # A conservative guard: never move client files while Wine/Faugus is active.
    busy = []
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            name = (proc / 'comm').read_text().strip().lower()
        except OSError:
            continue
        if any(part in name for part in ('wineserver', 'wine64', 'wine-preloader', 'gta_sa', 'arizona', 'faugus')):
            busy.append(name)
    if busy:
        raise ValueError('Закройте игру, лаунчер, Faugus и приложения Wine: ' + ', '.join(sorted(set(busy))))


def font_sidecars(client):
    if not client.is_dir():
        raise ValueError('Клиент ещё не загружен через лаунчер: ' + str(client))
    found = []
    for path in sorted(client.rglob('*:Zone.Identifier')):
        real = path.with_name(path.name.removesuffix(':Zone.Identifier'))
        if (path.is_file() and not path.is_symlink() and real.is_file()
                and not real.is_symlink() and real.suffix.lower() in ('.ttf', '.otf')
                and path.resolve().is_relative_to(client.resolve())):
            found.append(path)
    return found


def fix_fonts(client, apply=False):
    paths = font_sidecars(client)
    print(f'Служебных файлов рядом с настоящими шрифтами: {len(paths)}')
    for path in paths:
        print('  ' + str(path.relative_to(client)))
    if not apply:
        print('Это просмотр. Для переноса с резервной копией добавьте --apply.')
        return
    require_closed()
    if not paths:
        return
    folder = lab.STATE / 'backups' / ('fonts-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    folder.mkdir(parents=True, mode=0o700)
    # Write the complete recovery plan before moving the first file.
    plan = [{'source': str(p.absolute()), 'backup': str(folder / 'files' / p.relative_to(client))} for p in paths]
    lab.atomic_text(folder / 'restore.json', json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
    print('План отката: ' + str(folder / 'restore.json'), flush=True)
    for item in plan:
        dest = Path(item['backup'])
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(item['source'], dest)
    print('Готово. Настоящие шрифты не изменены.')


def restore_fonts(manifest):
    require_closed()
    manifest = manifest.expanduser().resolve()
    root = (lab.STATE / 'backups').resolve()
    if not manifest.is_relative_to(root) or manifest.name != 'restore.json':
        raise ValueError('Выберите restore.json из локального каталога резервных копий.')
    plan = json.loads(manifest.read_text())
    for item in plan:
        src, dest = Path(item['backup']), Path(item['source'])
        if not src.resolve().is_relative_to(manifest.parent / 'files') or not dest.is_absolute() or not dest.name.endswith(':Zone.Identifier'):
            raise ValueError('Некорректный план восстановления.')
        if src.exists() and dest.exists():
            raise ValueError('Лаунчер уже восстановил файл; перезапись запрещена: ' + str(dest))
    for item in plan:
        src, dest = Path(item['backup']), Path(item['source'])
        if src.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dest)
    print('Перенесённые файлы восстановлены. Отсутствующие в копии пропущены.')


def check(gameid):
    if not shutil.which('flatpak'):
        raise ValueError('Установите Flatpak: https://flatpak.org/setup/')
    subprocess.run(['flatpak', 'info', lab.APP], check=True, stdout=subprocess.DEVNULL)
    game, exe, prefix = installed_game(gameid)
    runner = game.get('runner', '')
    if not runner or 'latest' in runner.lower():
        raise ValueError('Выберите в Faugus конкретную установленную сборку GE-Proton вместо Latest.')
    candidates = [lab.DATA / 'Steam/compatibilitytools.d' / runner,
                  lab.HOME / '.var/app/com.valvesoftware.Steam/data/Steam/compatibilitytools.d' / runner,
                  lab.HOME / '.var/app' / lab.APP / 'data/Steam/compatibilitytools.d' / runner,
                  Path(runner)]
    print('Лаунчер:', exe)
    print('Префикс:', prefix)
    print('Proton:', runner)
    if not any((p / 'proton').is_file() for p in candidates):
        raise ValueError('Сборка Proton не найдена в известных каталогах. Проверьте её установку в Faugus.')
    umu = lab.GAMES.parent / 'umu-run'
    if not umu.is_file():
        raise ValueError('Не найден umu-run. Откройте Faugus и завершите загрузку его компонентов.')
    client = exe.parent / 'bin/arizona'
    print('Клиент:', 'загружен' if (client / 'gta_sa.exe').is_file() else 'загрузите/проверьте через официальный лаунчер')
    print('Сессия:', __import__('os').environ.get('XDG_SESSION_TYPE', 'не определена'))
    print('Базовые проверки пройдены. Доступ из Flatpak, Vulkan и вход на сервер проверяются при запуске.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'launch', 'fix-fonts', 'restore-fonts', 'hud'])
    parser.add_argument('--game', default='arizona-launcher', help='ID записи Faugus; см. samp_linux.py list')
    parser.add_argument('--apply', action='store_true', help='применить fix-fonts; без флага только просмотр')
    parser.add_argument('--manifest', type=Path, help='путь restore.json для restore-fonts')
    args = parser.parse_args()
    if args.command == 'restore-fonts':
        if not args.manifest:
            parser.error('нужен --manifest /путь/к/restore.json')
        restore_fonts(args.manifest)
    elif args.command == 'fix-fonts':
        _, exe, _ = installed_game(args.game)
        fix_fonts(exe.parent / 'bin/arizona', args.apply)
    elif args.command == 'hud':
        require_closed()
        lab.configure_hud(args.game)
    else:
        check(args.game)
        if args.command == 'launch':
            return lab.launch(args.game)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit('Ошибка: ' + str(error))
