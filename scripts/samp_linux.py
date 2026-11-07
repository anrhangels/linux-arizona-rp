#!/usr/bin/env python3
"""Локальные инструменты для Faugus Flatpak: проверка среды, список игр, запуск и MangoHud."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

APP = "io.github.Faugus.faugus-launcher"
ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
STATE = Path(os.environ.get("XDG_STATE_HOME", HOME / ".local/state")) / "linux-arizona-rp"
DATA = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
GAMES = HOME / ".var/app" / APP / "data/faugus-launcher/games.json"


def read_games():
    data = json.loads(GAMES.read_text())
    if not isinstance(data, list):
        raise ValueError("Неожиданный формат games.json Faugus")
    return data


def select_game(games, gameid):
    matches = [g for g in games if g.get("gameid") == gameid]
    if len(matches) != 1:
        raise ValueError("ID должен соответствовать одной записи Faugus. Посмотрите ID командой list")
    return matches[0]


def backup(path, folder):
    if path.exists():
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, folder / path.name)


def atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(text)
    os.replace(temp, path)


def layer_runtime():
    # Do not guess the installed runtime branch: match the Faugus runtime metadata.
    info = subprocess.run(["flatpak", "info", "--show-runtime", APP],
                          check=True, capture_output=True, text=True).stdout.strip()
    location = subprocess.run(["flatpak", "info", "--show-location", info],
                              check=True, capture_output=True, text=True).stdout.strip()
    metadata = (Path(location) / "metadata").read_text()
    section = re.search(r"\[Extension org\.freedesktop\.Platform\.VulkanLayer\]\n([^\[]*)", metadata)
    if not section:
        raise ValueError("В метаданных runtime не найдено расширение VulkanLayer")
    match = re.search(r"^version\s*=\s*(\S+)", section.group(1), re.M)
    if not match:
        raise ValueError("Не удалось определить ветку VulkanLayer")
    branch = match.group(1)
    ref = f"org.freedesktop.Platform.VulkanLayer.MangoHud//{branch}"
    result = subprocess.run(["flatpak", "info", "--show-location", ref],
                            capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f"Сначала установите расширение: flatpak install --user flathub {ref}")
    return Path(result.stdout.strip()) / "files"


def configure_hud(gameid):
    games = read_games()
    game = select_game(games, gameid)
    runtime = layer_runtime()
    hud = DATA / "linux-arizona-rp" / gameid
    manifests = hud / "layers"
    sources = []
    for arch, abi in [("x86_64", "x86_64-linux-gnu"), ("x86", "i386-linux-gnu")]:
        src = runtime / "lib" / abi / "libMangoHud.so"
        manifest = runtime / "share/vulkan/implicit_layer.d" / f"MangoHud.{arch}.json"
        if not src.is_file() or not manifest.is_file():
            raise ValueError(f"Не найдена библиотека или манифест {abi}")
        sources.append((arch, abi, src, manifest))
    snapshot = STATE / "backups" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup(GAMES, snapshot)
    for name in ["MangoHud.conf", "presets.conf"]:
        backup(hud / name, snapshot)
    manifests.mkdir(parents=True, exist_ok=True)
    for arch, abi, src, manifest in sources:
        dest = hud / "lib" / abi / src.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        content = json.loads(manifest.read_text())
        content["layer"]["library_path"] = str(dest)
        atomic_text(manifests / f"MangoHud.{arch}.json", json.dumps(content, indent=2) + "\n")
    for name in ["MangoHud.conf", "presets.conf"]:
        atomic_text(hud / name, (ROOT / "configs" / name).read_text())
    # These labels are informational and refreshed on each configuration run.
    os_label = "Linux"
    for line in Path("/etc/os-release").read_text().splitlines():
        if line.startswith("PRETTY_NAME="):
            os_label = line.split("=", 1)[1].strip('"')
    preset = (hud / "presets.conf").read_text()
    preset = preset.replace("@OS@", os_label).replace("@KERNEL@", platform.release())
    preset = preset.replace("@PROTON@", str(game.get("runner", "Faugus default")))
    atomic_text(hud / "presets.conf", preset)
    # Preserve unrelated options, remove only our former HUD assignments.
    args = game.get("launch_arguments", "")
    keys = "DXVK_HUD|MANGOHUD|MANGOHUD_CONFIGFILE|MANGOHUD_PRESETSFILE|VK_ADD_IMPLICIT_LAYER_PATH"
    args = re.sub(rf"(?<!\S)(?:{keys})=(?:'[^']*'|\"[^\"]*\"|\S+)\s*", "", args)
    import shlex
    extra = {
        "DXVK_HUD": "0", "MANGOHUD": "1",
        "MANGOHUD_CONFIGFILE": str(hud / "MangoHud.conf"),
        "MANGOHUD_PRESETSFILE": str(hud / "presets.conf"),
        "VK_ADD_IMPLICIT_LAYER_PATH": str(manifests),
    }
    game["launch_arguments"] = (args.strip() + " " + " ".join(
        f"{k}={shlex.quote(v)}" for k, v in extra.items())).strip()
    game["mangohud"] = ""
    atomic_text(GAMES, json.dumps(games, ensure_ascii=False, indent=4) + "\n")
    print(f"HUD настроен. Резервная копия: {snapshot}")
    print("Перезапустите Faugus. F10: кратко / подробно / скрыто. F12: показать / скрыть.")


def flatpak_launch_command(game):
    args = ["flatpak", "run"]
    # Set inside the sandbox: host LANG alone can be overridden by LC_ALL.
    if game.get("gameid") == "arizona-launcher":
        args += ["--env=LANG=ru_RU.UTF-8", "--env=LC_ALL=ru_RU.UTF-8"]
    prefix = Path(game.get("prefix", "")).expanduser()
    runner = Path(game.get("runner", "")).expanduser()
    if prefix.is_absolute() and (prefix / "drive_c").is_dir():
        args.append("--filesystem=" + str(prefix.resolve()))
    if runner.is_absolute() and (runner / "proton").is_file():
        args.append("--filesystem=" + str(runner.resolve()) + ":ro")
    hud = DATA / "linux-arizona-rp" / game["gameid"]
    if hud.is_dir():
        args.append("--filesystem=" + str(hud.resolve()) + ":ro")
    return args + [APP, "--game", game["gameid"], "--logs"]


def launch(gameid):
    game = select_game(read_games(), gameid)
    logs = STATE / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    target = logs / (datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".log")
    print(f"Лог запуска: {target}", flush=True)
    with target.open("w") as output:
        with subprocess.Popen(flatpak_launch_command(game),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, errors="replace") as process:
            for line in process.stdout:
                output.write(line)
                output.flush()
                print(line, end="", flush=True)
            return process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["doctor", "list", "launch", "hud"])
    parser.add_argument("--game", default="arizona-launcher", help="ID записи Faugus (по умолчанию: arizona-launcher)")
    args = parser.parse_args()
    if args.command == "doctor":
        print("OS:", platform.system(), "Kernel:", platform.release())
        print("Конфигурация Faugus:", "найдена" if GAMES.is_file() else "не найдена — создайте запись игры в Faugus")
        for command in ["flatpak", "git", "nvidia-smi"]:
            print(command + ":", shutil.which(command) or "не установлен")
        print("Это локальная справка: учётные данные, реестр и чат не собираются.")
    elif args.command == "list":
        for game in read_games():
            print(game.get("gameid"), "|", game.get("title"), "|", game.get("runner"))
    elif args.command == "hud":
        configure_hud(args.game)
    else:
        return launch(args.game)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(f"Ошибка: {error}")
