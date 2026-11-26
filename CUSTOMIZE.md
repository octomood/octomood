# Настройка профиля GitHub в стиле Material 3 Expressive

## Быстрый старт

1. Откройте [`profile.config.json`](./profile.config.json) и замените демо-данные на свои:
   - `github_username`, `display_name`, `monogram`, `role`, `tagline`, `status_pill`
   - `about` — краткое описание и 3 строки фактов
   - `stack.items` — технологии (поддерживаются тона `primary`, `secondary`, `tertiary`, `surface`)
   - `projects` — 4 избранных проекта (каждая карточка в README кликабельна и ведёт на `url`)
   - `socials` — ссылки и контакты (каждая pill-кнопка кликабельна)
2. Перегенерируйте SVG-карточки и `README.md`:
   ```bash
   python3 generate_assets.py
   ```
   Чтобы автоматически подтянуть публичные репозитории, звёзды, подписчиков и языки из GitHub API:
   ```bash
   python3 generate_assets.py --fetch-github
   ```
3. Создайте на GitHub репозиторий с именем, совпадающим с вашим ником (`username/username`), и запушьте туда содержимое этой папки (`README.md`, `assets/`, `profile.config.json`, `generate_assets.py`, `.github/`).

## Что уже настроено

- **Автоматическая смена Light / Dark темы** через `<picture>` и `prefers-color-scheme`.
- **Палитра MD3 Expressive Violet & Mint** с тональными поверхностями (`surfaceContainerLow`, `primaryContainer`, `secondaryContainer`, `tertiaryContainer`).
- **Фирменные формы Material 3 Expressive**: сквирклы, pill-чипы, scalloped cookie/flower-рамка, клевер и волнистые акценты.
- **Автообновление статистики** через GitHub Actions (`.github/workflows/update-stats.yml`) — при желании можно запускать вручную во вкладке Actions.
