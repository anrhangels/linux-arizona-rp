[← Главная](../README.md)

# Официальные источники компонентов

| Компонент | Источник |
|---|---|
| Arizona RP и официальный лаунчер | [arizona-rp.com](https://arizona-rp.com/) |
| Официальные публикации Arizona о распространении лаунчера | [Канал Arizona](https://t.me/s/arizona_rpcom?before=335), содержит ссылку на хранилище официального лаунчера |
| Faugus | [Исходный код](https://github.com/Faugus/faugus-launcher) · [Flathub](https://flathub.org/apps/io.github.Faugus.faugus-launcher) |
| GE-Proton | [Официальные выпуски](https://github.com/GloriousEggroll/proton-ge-custom/releases) |
| UMU | [Проект](https://github.com/Open-Wine-Components/umu-launcher) · [Сборка Faugus](https://github.com/Faugus/umu-launcher/releases) |
| Flatpak и Flathub | [Настройка дистрибутива](https://flathub.org/setup) · [Документация](https://docs.flatpak.org/en/latest/) |
| Noto Emoji | [googlefonts/noto-emoji](https://github.com/googlefonts/noto-emoji) |
| DejaVu | [Проект](https://dejavu-fonts.github.io/) |
| MangoHud | [Исходный код и настройки](https://github.com/flightlessmango/MangoHud) |

Автоматический загрузчик получает актуальный EXE из официального хранилища лаунчера, на которое ссылается Arizona. На главной странице репозитория указывается официальный сайт; адрес скачивания не фиксируется навсегда на одном выпуске. Правило поиска текущего установщика находится в `scripts/install.py`.

Сборки среды и Noto закреплены в `configs/downloads.json`, чтобы результат подготовки зависел от проверяемых файлов. Для исполняемых загрузок используется SHA-256; для закреплённого Noto — размер и Git blob ID из дерева официального исходника. Закреплённый файл и TLS проверяются; частичные скачивания не запускаются.

Скрипт не использует игровые зеркала, не отключает проверку TLS, не собирает учётные данные и не распространяет Microsoft-шрифты. Лицензии сторонних компонентов остаются у их авторов; скачивание не делает их частью MIT-лицензии этого репозитория.
