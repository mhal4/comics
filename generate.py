<<<<<<< HEAD
# app.py

import os
import shutil
import xml.etree.ElementTree as ET
import zipfile

from flask import Flask, render_template, request, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Пути
UPLOAD_FOLDER = "uploads"
IMAGE_ROOT = "static/images"
COMICS_DATA_FILE = "comics_data.json"  # Файл для хранения информации о комиксах
PLAYLISTS_DATA_FILE = "playlists_data.json"  # Файл для хранения информации о плейлистах

# Создание папок
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(IMAGE_ROOT, exist_ok=True)

# Глобальные переменные для хранения данных (временное решение, не работает между перезапусками на Render)
comics_data = {}
playlists_data = {}


# ---------- safe unzip ----------
def safe_extract(zip_path, dest_dir):
    abs_dest = os.path.abspath(dest_dir)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            name = info.filename
            if not name:
                continue
            target = os.path.normpath(os.path.join(dest_dir, *name.split("/")))
            abs_target = os.path.abspath(target)
            if os.path.commonpath([abs_dest, abs_target]) != abs_dest:
                raise RuntimeError(f"Unsafe zip entry: {name}")
        zf.extractall(dest_dir)


# ---------- parse playlist ----------
def parse_playlist(pl_path):
    playlist_name = "default_playlist"
    content_names = []
    try:
        tree = ET.parse(pl_path)
        root = tree.getroot()
        playlist_name = root.get("name", "default_playlist")
        for cont in root.findall(".//content"):
            cname = cont.get("name")
            if cname:
                content_names.append(cname)
    except Exception as e:
        print(f"Ошибка при парсинге плейлиста {pl_path}: {e}")  # Логируем ошибку
        pass
    return playlist_name, content_names


# ---------- parse comics ----------
def parse_comics(xml_path):
    comics = {}
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for node in root.findall("comix"):
            name = node.get("name")
            pics = int(node.get("pics", 0))
            tags = node.get("tags", "")
            comics[name] = {"name": name, "pics": pics, "tags": tags}
    except Exception as e:
        print(f"Ошибка при парсинге комиксов {xml_path}: {e}")  # Логируем ошибку
        pass
    return comics


# ---------- Routes ----------
@app.route("/")
def index():
    """Страница загрузки XML и ZIP файлов"""
    return render_template("upload.html")


@app.route("/upload", methods=["POST"])
def upload():
    """Обработка загрузки файлов и генерация данных о комиксах и плейлистах"""
    xml_file = request.files.get("xml")  # data.xml
    zip_file = request.files.get("zip")
    playlists_file = request.files.get("playlists")  # playlist.xml

    if not xml_file or not zip_file or not playlists_file:
        return (
            "Ошибка: необходимо загрузить XML (data), ZIP и XML (playlists) файлы.",
            400,
        )

    # Очистка папки uploads
    if os.path.exists(UPLOAD_FOLDER):
        shutil.rmtree(UPLOAD_FOLDER)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    extract_dir = os.path.join(UPLOAD_FOLDER, "extracted")
    os.makedirs(extract_dir, exist_ok=True)

    # Сохраняем файлы
    xml_path = os.path.join(UPLOAD_FOLDER, secure_filename(xml_file.filename))
    zip_path = os.path.join(UPLOAD_FOLDER, secure_filename(zip_file.filename))
    playlists_path = os.path.join(
        UPLOAD_FOLDER, secure_filename(playlists_file.filename)
    )

    xml_file.save(xml_path)
    zip_file.save(zip_path)
    playlists_file.save(playlists_path)

    # Распаковка ZIP
    try:
        safe_extract(zip_path, extract_dir)
    except Exception as e:
        return f"Ошибка при распаковке ZIP: {e}", 400

    # Очистка и создание папки для картинок
    if os.path.exists(IMAGE_ROOT):
        shutil.rmtree(IMAGE_ROOT)
    os.makedirs(IMAGE_ROOT, exist_ok=True)

    # Чтение XML комиксов
    global comics_data
    comics_data = parse_comics(xml_path)
    logs = [f"Загружено комиксов из data.xml: {len(comics_data)}"]

    # Чтение XML плейлистов
    global playlists_data
    playlist_name, content_names = parse_playlist(playlists_path)
    playlists_data[playlist_name] = content_names
    logs.append(
        f"Загружен плейлист '{playlist_name}' с контентом: {', '.join(content_names)}"
    )

    # Создание папки плейлиста
    playlist_dir = os.path.join(IMAGE_ROOT, playlist_name)
    os.makedirs(playlist_dir, exist_ok=True)

    # Копирование изображений в папку плейлиста
    jpg_files = []
    for rootp, _, files in os.walk(extract_dir):
        for f in files:
            if f.lower().endswith(
                (".jpg", ".jpeg", ".png", ".gif")
            ):  # Добавим другие форматы, если нужно
                dst_path = os.path.join(playlist_dir, f)
                shutil.copy2(os.path.join(rootp, f), dst_path)
                jpg_files.append(f)
    logs.append(f"Скопировано изображений в '{playlist_name}': {len(jpg_files)}")

    # Создание папки для каждого content внутри плейлиста (опционально, для структурирования)
    # В новой логике этого не было, но мы можем создать структуру, где все изображения в корне папки плейлиста
    # и отображение будет основано на data.xml и playlist.xml
    # Для простоты оставим изображения в корне папки плейлиста
    # В show_comic_content мы будем читать изображения из папки плейлиста
    # И теги будем брать из глобального comics_data

    return render_template("result.html", logs=logs, files=list(playlists_data.keys()))


# ------------------ Пользовательский интерфейс ------------------
@app.route("/comics")
def comics():
    """Пользовательский интерфейс: выбор плейлиста с превью"""
    # Используем глобальные данные
    playlists_list = []
    for playlist_name, content_names in playlists_data.items():
        playlist_dir = os.path.join(IMAGE_ROOT, playlist_name)
        if os.path.exists(playlist_dir):
            # Превью берём из первого изображения в папке плейлиста
            imgs = sorted(
                [
                    f
                    for f in os.listdir(playlist_dir)
                    if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif"))
                ]
            )
            preview = (
                url_for("static", filename=f"images/{playlist_name}/{imgs[0]}")
                if imgs
                else None
            )
            # Пытаемся получить теги для первого комикса в плейлисте
            tags = "N/A"
            if content_names:
                first_comic_name = content_names[0]
                if first_comic_name in comics_data:
                    tags = comics_data[first_comic_name].get("tags", "N/A")
            playlists_list.append(
                {"name": playlist_name, "preview": preview, "tags": tags}
            )

    # Сортировка по имени
    playlists_list.sort(key=lambda x: x["name"])

    return render_template(
        "comics.html", playlists=playlists_list, view_mode="playlists"
    )


@app.route("/comics/<playlist_name>")
def show_playlist(playlist_name):
    """Отображение содержимого конкретного плейлиста"""
    if playlist_name not in playlists_data:
        return "Плейлист не найден.", 404

    playlist_dir = os.path.join(IMAGE_ROOT, playlist_name)
    if not os.path.exists(playlist_dir):
        return "Папка плейлиста не найдена.", 404

    content_names = playlists_data[playlist_name]
    content_list = []
    for content_name in content_names:
        imgs = sorted(
            [
                f
                for f in os.listdir(playlist_dir)
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif"))
            ]
        )
        preview = (
            url_for("static", filename=f"images/{playlist_name}/{imgs[0]}")
            if imgs
            else None
        )
        # Получаем теги из глобального comics_data
        tags = "N/A"
        if content_name in comics_data:
            tags = comics_data[content_name].get("tags", "N/A")
        content_list.append({"name": content_name, "preview": preview, "tags": tags})

    return render_template(
        "playlist.html", playlist_name=playlist_name, contents=content_list
    )


# --- НОВЫЙ маршрут для поиска по тегам и плейлистам ---
@app.route("/search")
def search_comics():
    """Поиск комиксов по тегу или плейлисту"""
    query = request.args.get("q", "").strip().lower()
    search_type = request.args.get("type", "all")  # 'tag', 'playlist', 'all'

    if not query:
        return render_template(
            "comics.html",
            playlists=[],
            comics=[],
            search_query=query,
            message="Пожалуйста, введите поисковый запрос.",
            view_mode="search",
        )

    found_playlists = []
    found_comics = []

    if search_type in ["all", "playlist"]:
        # Поиск по плейлистам
        for playlist_name, content_names in playlists_data.items():
            if query in playlist_name.lower():
                playlist_dir = os.path.join(IMAGE_ROOT, playlist_name)
                if os.path.exists(playlist_dir):
                    imgs = sorted(
                        [
                            f
                            for f in os.listdir(playlist_dir)
                            if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif"))
                        ]
                    )
                    preview = (
                        url_for("static", filename=f"images/{playlist_name}/{imgs[0]}")
                        if imgs
                        else None
                    )
                    tags = "N/A"
                    if content_names:
                        first_comic_name = content_names[0]
                        if first_comic_name in comics_data:
                            tags = comics_data[first_comic_name].get("tags", "N/A")
                    found_playlists.append(
                        {"name": playlist_name, "preview": preview, "tags": tags}
                    )
                break  # Нашли плейлист, можно остановиться, если ищем только по плейлистам

    if search_type in ["all", "tag"]:
        # Поиск по тегам в комиксах
        for comic_name, comic_info in comics_data.items():
            if query in comic_info.get("tags", "").lower():
                # Найти, в каких плейлистах находится этот комикс
                for playlist_name, content_names in playlists_data.items():
                    if comic_name in content_names:
                        playlist_dir = os.path.join(IMAGE_ROOT, playlist_name)
                        if os.path.exists(playlist_dir):
                            imgs = sorted(
                                [
                                    f
                                    for f in os.listdir(playlist_dir)
                                    if f.lower().endswith(
                                        (".jpg", ".jpeg", ".png", ".gif")
                                    )
                                ]
                            )
                            preview = (
                                url_for(
                                    "static",
                                    filename=f"images/{playlist_name}/{imgs[0]}",
                                )
                                if imgs
                                else None
                            )
                            found_comics.append(
                                {
                                    "name": comic_name,
                                    "playlist": playlist_name,
                                    "preview": preview,
                                    "tags": comic_info.get("tags"),
                                }
                            )
                        break  # Комикс может быть в нескольких плейлистах, покажем первый найденный

    # Сортировка результатов
    found_playlists.sort(key=lambda x: x["name"])
    found_comics.sort(key=lambda x: x["name"])

    # Объединяем результаты или показываем отдельно, в зависимости от поиска
    # Для простоты, покажем плейлисты, если они найдены, иначе комиксы
    # Или покажем всё вместе
    combined_results = found_playlists + found_comics

    if not combined_results:
        message = f"Ничего не найдено по запросу '{query}'."
    else:
        message = f"Результаты поиска по запросу '{query}' (тип: {search_type}):"

    # Возвращаем результаты в comics.html, указывая view_mode='search'
    # comics.html должен уметь отображать как плейлисты, так и отдельные комиксы
    # Мы передадим список, где каждый элемент будет иметь тип (playlist или comic)
    processed_results = []
    for p in found_playlists:
        processed_results.append(
            {
                "type": "playlist",
                "name": p["name"],
                "preview": p["preview"],
                "tags": p["tags"],
            }
        )
    for c in found_comics:
        processed_results.append(
            {
                "type": "comic",
                "name": c["name"],
                "playlist": c["playlist"],
                "preview": c["preview"],
                "tags": c["tags"],
            }
        )

    return render_template(
        "comics.html",
        playlists=[],
        comics=processed_results,
        search_query=query,
        message=message,
        view_mode="search",
    )


# Новый маршрут для отображения конкретного комикса (content) внутри плейлиста
# Новый маршрут для отображения конкретного комикса (content) внутри плейлиста
@app.route("/comics/<playlist_name>/<content_name>")
def show_comic_content(playlist_name, content_name):
    """Отображение конкретного комикса (content) внутри плейлиста"""
    # Проверяем, что плейлист и контент существуют
    if (
        playlist_name not in playlists_data
        or content_name not in playlists_data[playlist_name]
    ):
        return "Комикс или плейлист не найден.", 404

    playlist_dir = os.path.join(IMAGE_ROOT, playlist_name)
    if not os.path.exists(playlist_dir):
        return "Папка плейлиста не найдена.", 404

    # Получаем теги из глобального comics_data
    tags = "N/A"
    if content_name in comics_data:
        tags = comics_data[content_name].get("tags", "N/A")

    # Считываем изображения из папки плейлиста
    imgs = sorted(
        [
            f
            for f in os.listdir(playlist_dir)
            if f.lower().startswith(content_name.lower())
            and f.lower().endswith((".jpg", ".jpeg", ".png", ".gif"))
        ]
    )
    img_urls = [
        url_for("static", filename=f"images/{playlist_name}/{img}") for img in imgs
    ]

    # Если не нашли файлов по имени, покажем все
    if not imgs:
        imgs = sorted(
            [
                f
                for f in os.listdir(playlist_dir)
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif"))
            ]
        )
        img_urls = [
            url_for("static", filename=f"images/{playlist_name}/{img}") for img in imgs
        ]

    # Передаём playlist_name в шаблон
    return render_template(
        "show_comic.html",
        name=content_name,
        img_urls=img_urls,
        tags=tags,
        playlist_name=playlist_name,
    )


# Удаляем блок if __name__ == "__main__": или оставляем для локальной отладки
if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
