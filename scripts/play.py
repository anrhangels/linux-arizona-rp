#!/usr/bin/env python3
"""Arizona: сериализация запуска и применение точечного исправления шрифтов."""
import argparse
from pathlib import Path
import subprocess
import sys
import arizona
import install
import samp_linux


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check', action='store_true')
    p.add_argument('--no-font-repair', action='store_true')
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
        return samp_linux.launch(install.GAMEID)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        sys.exit('Ошибка: ' + str(e))
