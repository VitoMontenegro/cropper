# Утилита для сжатия изображений

Простое кроссплатформенное десктоп‑приложение на Python для пакетного сжатия фотографий
до заданного размера или качества. Поддерживает обработку сотен файлов (400+), рекурсивный
обход подпапок и минимальный GUI на `tkinter`.

## Возможности

- **Два режима сжатия**:
  - **По размеру**: целевой размер файла, например 80–150 КБ.
  - **По качеству**: фиксированный процент качества JPEG.
- **Рекурсивная обработка** папок.
- **Сохранение структуры директорий** (по желанию).
- **Конвертация в JPEG** для лучшего сжатия (можно отключить).
- **GUI‑режим** (по умолчанию) и **CLI‑режим** для работы из терминала/скриптов.

## Установка

Требуется Python 3.10+.

```bash
cd cropper  # корень проекта
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Запуск (GUI)

Из активированного виртуального окружения:

```bash
python -m src.app
```

Откроется окно, где можно:

- выбрать исходную и выходную папку;
- указать режим сжатия:
  - по размеру (КБ) — указываете целевой размер (например, `120`);
  - по качеству (%) — выбираете значение на слайдере;
- включить/выключить:
  - сохранение структуры папок;
  - конвертацию в JPEG.

После нажатия **«Старт»** приложение рекурсивно обработает все `.jpg`, `.jpeg`, `.png`
из выбранной папки. Прогресс и статус текущего файла будут показаны внизу окна.

## Запуск (CLI)

CLI‑режим включается, если передать параметры `--input` и `--output`:

```bash
python -m src.app \
  --input /путь/к/исходным/фото \
  --output /путь/к/сжатым/фото \
  --mode by_target_size \
  --target-size-kb 120
```

Основные параметры:

- `-i, --input` — исходная папка с изображениями.
- `-o, --output` — папка для сжатых изображений.
- `--mode` — `by_quality` или `by_target_size` (по умолчанию `by_target_size`).
- `--quality` — качество JPEG для режима `by_quality` (по умолчанию `85`).
- `--target-size-kb` — целевой размер файла в КБ для режима `by_target_size`
  (по умолчанию `120`).
- `--no-convert-to-jpeg` — не конвертировать в JPEG.
- `--no-keep-structure` — не сохранять структуру подпапок (сложить всё в одну папку).

## Сборка в единый бинарник (PyInstaller)

PyInstaller не умеет кросс‑компиляцию: macOS — на macOS, Windows — на Windows.

### macOS (Apple Silicon) — полный код сборки

```bash
cd ~/Desktop/cropper

# Создать venv, если ещё нет
python3 -m venv .venv
source .venv/bin/activate

# Зависимости
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# Очистить старую сборку (НЕ удаляем image-compressor.spec!)
rm -rf dist build

# Актуальная сборка
pyinstaller image-compressor.spec
```

Результат: `dist/image-compressor.app` и `dist/image-compressor`.

### Windows (x64) — полный код сборки

```bat
cd C:\Users\<Имя>\Desktop\cropper

python -m venv .venv
.\.venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

rmdir /s /q dist 2>nul
rmdir /s /q build 2>nul

pyinstaller image-compressor.spec
```

Результат: `dist\image-compressor\` с exe внутри.

### Windows exe через GitHub Actions (рекомендуется для Mac M1/M2)

Docker-образ `cdrx/pyinstaller-windows` не работает на Apple Silicon (Wine падает на ARM64).  
Используйте GitHub Actions — сборка идёт на нативном Windows runner.

1. Запушьте проект в GitHub.
2. Откройте **Actions** → **Build Windows exe** → **Run workflow**.
3. Скачайте артефакт `image-compressor-windows` (zip с exe и dll).

### Windows exe через Docker (только Intel Mac / Linux x64)

На Apple Silicon (M1/M2) Wine в Docker падает. На Intel Mac или Linux:

```bash
cd ~/Desktop/cropper
docker run --rm -v "$(pwd):/src" cdrx/pyinstaller-windows "pyinstaller image-compressor-win.spec"
```

---

После любого изменения кода — пересобирать: `pyinstaller image-compressor.spec`.  
Иначе в .app/.exe попадёт старая версия (ошибки вроде `unexpected keyword argument`).

