#!/usr/bin/env python3
"""Arizona: сериализация запуска и применение точечного исправления шрифтов."""
import argparse
import os
import shutil
from pathlib import Path
import subprocess
import sys
import arizona
import install
import samp_linux


def set_primary_monitor(output):
    """Explicit Xwayland/X11 preference; never changes display modes or scaling."""
    if not os.environ.get('DISPLAY') or not shutil.which('xrandr'):
        raise ValueError('--monitor требует X11/Xwayland и установленный xrandr')
    result = subprocess.run(['xrandr', '--query'], check=True,
                            capture_output=True, text=True)
    connected = {line.split()[0] for line in result.stdout.splitlines()
                 if len(line.split()) > 1 and line.split()[1] == 'connected'}
    if output not in connected:
        raise ValueError('Монитор не подключён. Доступны: ' + ', '.join(sorted(connected)))
    subprocess.run(['xrandr', '--output', output, '--primary'], check=True,
                   stdout=subprocess.DEVNULL)
    print('Основной экран X11/Xwayland: ' + output, flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check', action='store_true')
    p.add_argument('--no-font-repair', action='store_true')
    p.add_argument('--monitor', metavar='OUTPUT', help='сделать подключённый выход основным для X11/Xwayland перед запуском')
    a = p.parse_args()
    if a.check:
        arizona.check(install.GAMEID)
        return 0
    with install.operation_lock():
        arizona.check(install.GAMEID)
        if not a.no_font_repair:
            arizona.require_closed()
            _, exe, _ = arizona.installed_game(install.GAMEID)
            if (exe.parent / 'bin/arizona').is_dir():
                arizona.fix_fonts(exe.parent / 'bin/arizona', apply=True)
        if a.monitor:
            arizona.require_closed()
            set_primary_monitor(a.monitor)
        return samp_linux.launch(install.GAMEID)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        sys.exit('Ошибка: ' + str(e))
