#!/usr/bin/env bash
# Bootstrap: system packages only run here; Python handles user files.
set -euo pipefail
root_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Validate arguments before asking for privileges or installing any package.
arguments=("$@")
for ((i=0; i<${#arguments[@]}; i++)); do
    case "${arguments[i]}" in
        --plan|--yes|--no-system-packages|--no-hud|--fonts-only|--help|-h) ;;
        --installer|--windows-fonts|--prefix|--restore)
            if (( i+1 >= ${#arguments[@]} )); then printf 'У параметра %s должно быть значение.\n' "${arguments[i]}" >&2; exit 2; fi
            i=$((i+1)) ;;
        *) printf 'Неизвестный параметр: %s. См. --help.\n' "${arguments[i]}" >&2; exit 2 ;;
    esac
done
plan=0; assume_yes=0; skip_packages=0
for argument in "$@"; do
    case "$argument" in
        --plan) plan=1 ;;
        --yes) assume_yes=1 ;;
        --no-system-packages) skip_packages=1 ;;
        --help|-h)
            cat <<'HELP'
Arizona RP / Linux — подготовка и установка
  bash install.sh                 Полная установка с предварительным планом
  bash install.sh --plan          Только показать действия; ничего не менять
  bash install.sh --yes           Не спрашивать подтверждение плана
  bash install.sh --no-system-packages  Зависимости уже установлены
  bash install.sh --installer FILE      Свой официальный установщик; auto — найти в загрузках
  bash install.sh --windows-fonts DIR   Подключить свои Segoe UI / Emoji
  bash install.sh --prefix DIR          Отдельный префикс (по умолчанию ~/Games/arizona-rp/prefix)
  bash install.sh --no-hud              Не устанавливать панель FPS
  bash install.sh --fonts-only --prefix DIR  Шрифты для существующего префикса
  bash install.sh --restore MANIFEST    Восстановить файлы из резервной копии
После установки: ~/.local/bin/arizona
HELP
            exit 0 ;;
        --restore) skip_packages=1 ;;
    esac
done
if (( EUID == 0 )); then printf 'Запускайте без sudo: права запросят только системные пакеты.\n' >&2; exit 1; fi
# os-release is the distributor-owned file, not project/user input.
ID=unknown; ID_LIKE=''
if [[ -r /etc/os-release ]]; then source /etc/os-release; fi
family=''
for distro in "$ID" $ID_LIKE; do
    case "$distro" in
        arch|cachyos|manjaro|endeavouros) family=arch; break ;;
        debian|ubuntu|linuxmint|pop) family=debian; break ;;
        fedora) family=fedora; break ;;
        opensuse*|suse) family=opensuse; break ;;
    esac
done
packages=()
case "$family" in
    arch) packages=(pacman -S --needed python flatpak fontconfig ttf-dejavu vulkan-tools ca-certificates) ;;
    debian) packages=(apt-get install python3 flatpak fontconfig fonts-dejavu-core vulkan-tools ca-certificates) ;;
    fedora) packages=(dnf install python3 flatpak fontconfig dejavu-sans-fonts vulkan-tools ca-certificates) ;;
    opensuse) packages=(zypper install python3 flatpak fontconfig dejavu-fonts vulkan-tools ca-certificates) ;;
esac
if [[ -e /run/ostree-booted || "$ID" == steamos || "$ID" == nixos ]] && (( ! skip_packages )); then
    printf 'Неизменяемая ОС: установите зависимости средствами системы и повторите с --no-system-packages.\n' >&2
    exit 1
fi
if [[ -z "$family" ]] && (( ! skip_packages )); then
    printf 'Дистрибутив %s не поддержан автоматически. См. docs/distributions.md.\n' "$ID" >&2; exit 1
fi
printf '\n  ARIZONA / LINUX      INSTALL RECORD 01\n\n'
printf 'Система: %s · семейство: %s\n' "$ID" "${family:-ручная подготовка}"
if (( ! skip_packages )); then
    printf 'Системные пакеты (через sudo): '; printf '%q ' "${packages[@]}"; printf '\n'
fi
printf '%s\n' 'Далее: Flathub → Faugus → GE-Proton 11-11 → актуальный официальный лаунчер → шрифты/эмодзи → ярлык.'
printf '%s\n' 'Игровой клиент загрузит лаунчер. Вход в аккаунт выполняете вы. Драйвер видеокарты должен быть установлен.'
if (( plan )); then
    if command -v python3 >/dev/null; then python3 "$root_dir/scripts/install.py" "$@"; fi
    exit 0
fi
if [[ "$(uname -m)" != x86_64 ]]; then printf 'Требуется Linux x86_64.\n' >&2; exit 1; fi
if (( ! assume_yes )); then
    if [[ ! -t 0 ]]; then printf 'Без терминала используйте --yes или сначала --plan.\n' >&2; exit 1; fi
    read -r -p 'Начать установку? [y/N] ' reply
    [[ "$reply" == [yY] || "$reply" == [yY][eE][sS] || "$reply" == 'да' ]] || exit 0
fi
if (( ! skip_packages )); then
    if ! command -v sudo >/dev/null; then printf 'Нужен sudo или ручная подготовка (--no-system-packages).\n' >&2; exit 1; fi
    if [[ "$family" == debian ]]; then sudo apt-get update; fi
    if (( assume_yes )); then
        if [[ "$family" == arch ]]; then packages+=(--noconfirm)
        elif [[ "$family" == opensuse ]]; then packages=(zypper --non-interactive "${packages[@]:1}")
        else packages+=(-y); fi
    fi
    sudo "${packages[@]}"
fi
command -v python3 >/dev/null || { printf 'Нужен Python 3.10+.\n' >&2; exit 1; }
exec python3 "$root_dir/scripts/install.py" "$@"
