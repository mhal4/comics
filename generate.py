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

# Создание папок
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(IMAGE_ROOT, exist_ok=True)


# ------------------ Админская часть ------------------
@app.route("/")
def index():
    """Страница загрузки XML и ZIP файлов"""
    return render_template("upload.html")


@app.route("/upload", methods=["POST"])
def upload():
    """Обработка загрузки файлов и генерация данных о комиксах"""
    xml_file = request.files.get("xml")
    zip_file = request.files.get("zip")
    playlists_file = request.files.get("playlists")

    if not xml_file or not zip_file:
        return "Ошибка: необходимо загрузить XML и ZIP файлы."

    # Очистка папки uploads
    if os.path.exists(UPLOAD_FOLDER):
        shutil.rmtree(UPLOAD_FOLDER)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    extract_dir = os.path.join(UPLOAD_FOLDER, "extracted")
    os.makedirs(extract_dir, exist_ok=True)

    # Сохраняем файлы
    xml_path = os.path.join(UPLOAD_FOLDER, secure_filename(xml_file.filename))
    zip_path = os.path.join(UPLOAD_FOLDER, secure_filename(zip_file.filename))
    xml_file.save(xml_path)
    zip_file.save(zip_path)

    playlists_path = None
    if playlists_file and playlists_file.filename:
        playlists_path = os.path.join(
            UPLOAD_FOLDER, secure_filename(playlists_file.filename)
        )
        playlists_file.save(playlists_path)

    # Распаковка ZIP
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_dir)

    # Очистка и создание папки для картинок
    if os.path.exists(IMAGE_ROOT):
        shutil.rmtree(IMAGE_ROOT)
    os.makedirs(IMAGE_ROOT, exist_ok=True)

    # Чтение XML комиксов
    tree = ET.parse(xml_path)
    root = tree.getroot()

    comics_data = {}
    logs = []

    for node in root.findall("comix"):
        name = node.get("name")
        pics = int(node.get("pics", 0))
        tags = node.get("tags", "")

        comic_dir = os.path.join(IMAGE_ROOT, name)
        os.makedirs(comic_dir, exist_ok=True)

        # Поиск изображений
        found_files = []
        for f in os.listdir(extract_dir):
            if name.lower() in f.lower():
                shutil.copy2(os.path.join(extract_dir, f), os.path.join(comic_dir, f))
                found_files.append(f)

        logs.append(
            f"Комикс '{name}': найдено {len(found_files)} файлов (ожидалось {pics}), теги: {tags}"
        )

        # Сохраняем информацию о комиксе
        comics_data[name] = {
            "name": name,
            "pics": pics,
            "tags": tags,
            "images": sorted(found_files),
        }

    # Здесь можно сохранить comics_data в JSON файл (опционально, но не надёжно на Render)
    # Вместо этого, будем хранить в памяти или читать папки при каждом запросе

    # Обработка плейлистов (если есть) - можно сохранить аналогично

    return render_template("result.html", logs=logs, files=list(comics_data.keys()))


# ------------------ Пользовательский интерфейс ------------------
@app.route("/comics")
def comics():
    """Пользовательский интерфейс: выбор комикса с превью"""
    comics_list = []
    for name in os.listdir(IMAGE_ROOT):
        img_dir = os.path.join(IMAGE_ROOT, name)
        if os.path.isdir(img_dir):
            imgs = sorted(os.listdir(img_dir))
            if imgs:
                preview = url_for("static", filename=f"images/{name}/{imgs[0]}")
                # Попробуем прочитать теги из XML для списка
                tags = "N/A"  # Заглушка, если не найдём
                xml_path = os.path.join(UPLOAD_FOLDER, "data.xml")
                if os.path.exists(xml_path):
                    try:
                        tree = ET.parse(xml_path)
                        root = tree.getroot()
                        for node in root.findall("comix"):
                            if node.get("name") == name:
                                tags = node.get("tags", "N/A")
                                break
                    except:
                        pass  # Если XML нет или сломан, теги не покажем
                comics_list.append({"name": name, "preview": preview, "tags": tags})

    # Сортировка по имени
    comics_list.sort(key=lambda x: x["name"])

    return render_template("comics.html", comics=comics_list)


# --- НОВЫЙ маршрут для поиска по тегам ---
@app.route("/search")
def search_comics():
    """Поиск комиксов по тегу"""
    query = request.args.get("tag", "").strip().lower()
    if not query:
        # Если тег не указан, можно вернуть пустой список или всё
        # Лучше вернуть на главную или показать сообщение
        return render_template(
            "comics.html",
            comics=[],
            search_query=query,
            message="Пожалуйста, введите тег для поиска.",
        )

    comics_list = []
    for name in os.listdir(IMAGE_ROOT):
        img_dir = os.path.join(IMAGE_ROOT, name)
        if os.path.isdir(img_dir):
            imgs = sorted(os.listdir(img_dir))
            if imgs:
                preview = url_for("static", filename=f"images/{name}/{imgs[0]}")
                # Попробуем прочитать теги из XML для списка
                tags = "N/A"  # Заглушка, если не найдём
                xml_path = os.path.join(UPLOAD_FOLDER, "data.xml")
                if os.path.exists(xml_path):
                    try:
                        tree = ET.parse(xml_path)
                        root = tree.getroot()
                        for node in root.findall("comix"):
                            if node.get("name") == name:
                                tags = node.get("tags", "N/A")
                                break
                    except:
                        pass  # Если XML нет или сломан, теги не покажем

                # Фильтрация: добавляем комикс, если тег найден
                if query in tags.lower():
                    comics_list.append({"name": name, "preview": preview, "tags": tags})

    # Сортировка по имени
    comics_list.sort(key=lambda x: x["name"])

    if not comics_list:
        message = f"Комиксы с тегом '{query}' не найдены."
    else:
        message = f"Результаты поиска по тегу '{query}':"

    return render_template(
        "comics.html", comics=comics_list, search_query=query, message=message
    )


# Новый маршрут для отображения конкретного комикса
@app.route("/comics/<name>")
def show_comic(name):
    """Отображение конкретного комикса"""
    comic_dir = os.path.join(IMAGE_ROOT, name)
    if not os.path.exists(comic_dir):
        return "Комикс не найден.", 404

    # Считываем XML для получения тегов
    tags = "N/A"  # Заглушка, если не найдём
    xml_path = os.path.join(
        UPLOAD_FOLDER, "data.xml"
    )  # Предполагаем, что XML всегда называется так
    if os.path.exists(xml_path):
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            for node in root.findall("comix"):
                if node.get("name") == name:
                    tags = node.get("tags", "N/A")
                    break
        except:
            pass  # Если XML нет или сломан, теги не покажем

    imgs = sorted(os.listdir(comic_dir))
    img_urls = [url_for("static", filename=f"images/{name}/{img}") for img in imgs]

    return render_template("show_comic.html", name=name, img_urls=img_urls, tags=tags)


# Удаляем блок if __name__ == "__main__": или оставляем для локальной отладки
if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
