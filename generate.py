# generate.py (или app.py)

from flask import Flask, render_template, request, url_for, redirect
import os
import zipfile
import xml.etree.ElementTree as ET
import shutil
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Пути
UPLOAD_FOLDER = "uploads"
IMAGE_ROOT = "static/images"
COMICS_DATA_FILE = "comics_data.json"  # Файл для хранения информации о комиксах
PLAYLISTS_DATA_FILE = "playlists_data.json" # Файл для хранения информации о плейлистах

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

# ---------- parse playlist (обновлено для нескольких плейлистов) ----------
def parse_playlist(pl_path):
    playlists_dict = {}
    try:
        tree = ET.parse(pl_path)
        root = tree.getroot()

        # Находим все элементы <playlist>
        playlist_elements = root.findall(".//playlist")
        for plist_elem in playlist_elements:
            plist_name = plist_elem.get("name", "unnamed_playlist")
            content_names = []
            for cont in plist_elem.findall(".//content"):
                cname = cont.get("name")
                if cname:
                    content_names.append(cname)
            playlists_dict[plist_name] = content_names

    except Exception as e:
        print(f"Ошибка при парсинге плейлиста {pl_path}: {e}")
        return {}
    return playlists_dict

# ---------- parse comics (обновлено для name_rus) ----------
def parse_comics(xml_path):
    comics = {}
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for node in root.findall("comic"): # Используем 'comic' вместо 'comix'
            name = node.get("name")
            name_rus = node.get("name_rus", name) # Если name_rus нет, используем name
            pics = int(node.get("pics", 0))
            tags = node.get("tags", "")
            comics[name] = {"name": name, "name_rus": name_rus, "pics": pics, "tags": tags}
    except Exception as e:
        print(f"Ошибка при парсинге комиксов {xml_path}: {e}")
        pass
    return comics

# ------------------ Админская часть (новый маршрут) ------------------
@app.route("/upload")
def upload_index():
    """Страница загрузки XML и ZIP файлов"""
    return render_template("upload.html")

@app.route("/upload", methods=["POST"])
def upload_files():
    """Обработка загрузки файлов и генерация данных о комиксах и плейлистах"""
    xml_file = request.files.get("xml") # data.xml
    zip_file = request.files.get("zip")
    playlists_file = request.files.get("playlists") # playlist.xml

    if not xml_file or not zip_file or not playlists_file:
        return "Ошибка: необходимо загрузить XML (data), ZIP и XML (playlists) файлы.", 400

    # Очистка папки uploads
    if os.path.exists(UPLOAD_FOLDER):
        shutil.rmtree(UPLOAD_FOLDER)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    extract_dir = os.path.join(UPLOAD_FOLDER, "extracted")
    os.makedirs(extract_dir, exist_ok=True)

    # Сохраняем файлы
    xml_path = os.path.join(UPLOAD_FOLDER, secure_filename(xml_file.filename))
    zip_path = os.path.join(UPLOAD_FOLDER, secure_filename(zip_file.filename))
    playlists_path = os.path.join(UPLOAD_FOLDER, secure_filename(playlists_file.filename))

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

    # Чтение XML плейлистов (обновлено)
    global playlists_data
    playlists_data = parse_playlist(playlists_path)
    logs.append(f"Загружено плейлистов: {len(playlists_data)}")
    for name, content in playlists_data.items():
        logs.append(f"  - '{name}': {', '.join(content)}")

    # Создание папки для каждого плейлиста и копирование изображений
    jpg_files_global = []
    for playlist_name, content_names in playlists_data.items():
        playlist_dir = os.path.join(IMAGE_ROOT, playlist_name)
        os.makedirs(playlist_dir, exist_ok=True)

        jpg_files_playlist = []
        for rootp, _, files in os.walk(extract_dir):
            for f in files:
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
                    dst_path = os.path.join(playlist_dir, f)
                    shutil.copy2(os.path.join(rootp, f), dst_path)
                    jpg_files_playlist.append(f)
        jpg_files_global.extend(jpg_files_playlist)
        logs.append(f"  - В плейлист '{playlist_name}' скопировано изображений: {len(jpg_files_playlist)}")

    logs.append(f"Всего изображений скопировано (включая дубликаты в разные плейлисты): {len(jpg_files_global)}")

    return render_template("result.html", logs=logs, files=list(playlists_data.keys()))


# ------------------ Пользовательский интерфейс (новый маршрут для /) ------------------
@app.route("/")
def index_page():
    """Пользовательский интерфейс: выбор плейлиста с превью (ранее /comics)"""
    # Используем глобальные данные
    playlists_list = []
    for playlist_name, content_names in playlists_data.items():
        playlist_dir = os.path.join(IMAGE_ROOT, playlist_name)
        if os.path.exists(playlist_dir):
            # Превью берём из первого изображения, связанного с первым комиксом в плейлисте
            preview = None
            if content_names:
                 first_comic_name = content_names[0]
                 comic_imgs = [f for f in os.listdir(playlist_dir) if f.lower().startswith(first_comic_name.lower()) and f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
                 sorted_comic_imgs = sorted(comic_imgs)
                 if sorted_comic_imgs:
                     preview = url_for('static', filename=f'images/{playlist_name}/{sorted_comic_imgs[0]}')
            if not preview:
                imgs = sorted([f for f in os.listdir(playlist_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))])
                preview = url_for('static', filename=f'images/{playlist_name}/{imgs[0]}') if imgs else None

            playlists_list.append({"name": playlist_name, "preview": preview})

    # Сортировка по имени
    playlists_list.sort(key=lambda x: x['name'])

    return render_template("comics.html", playlists=playlists_list, view_mode='playlists')

# Старый маршрут /comics перенаправляет на /
@app.route("/comics")
def old_comics_route():
    return redirect(url_for('index_page'))

@app.route("/comics/<playlist_name>")
def show_playlist(playlist_name):
    """Отображение содержимого конкретного плейлиста"""
    if playlist_name not in playlists_
        return "Плейлист не найден.", 404

    playlist_dir = os.path.join(IMAGE_ROOT, playlist_name)
    if not os.path.exists(playlist_dir):
        return "Папка плейлиста не найдена.", 404

    content_names = playlists_data[playlist_name]
    content_list = []
    for content_name in content_names:
        # Превью берём из первого изображения, связанного с этим комиксом
        content_imgs = [f for f in os.listdir(playlist_dir) if f.lower().startswith(content_name.lower()) and f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
        sorted_content_imgs = sorted(content_imgs)
        preview = url_for('static', filename=f'images/{playlist_name}/{sorted_content_imgs[0]}') if sorted_content_imgs else None

        # Если не нашли по имени, используем первое изображение в папке (старое поведение)
        if not preview:
            imgs = sorted([f for f in os.listdir(playlist_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))])
            preview = url_for('static', filename=f'images/{playlist_name}/{imgs[0]}') if imgs else None

        # Получаем name_rus из глобального comics_data
        display_name = content_name # Имя по умолчанию
        if content_name in comics_data:
            comic_info = comics_data[content_name]
            display_name = comic_info.get("name_rus", content_name) # Используем name_rus, если есть

        content_list.append({"name": content_name, "display_name": display_name, "preview": preview})

    return render_template("playlist.html", playlist_name=playlist_name, contents=content_list)


# --- НОВЫЙ маршрут для поиска по тегам, плейлистам и названиям ---
@app.route("/search")
def search_comics():
    """Поиск комиксов по тегу, названию или плейлисту"""
    query = request.args.get('q', '').strip().lower()
    search_type = request.args.get('type', 'all') # 'tag', 'playlist', 'comic_name', 'all'

    if not query:
        return render_template("comics.html", playlists=[], comics=[], search_query=query, message="Пожалуйста, введите поисковый запрос.", view_mode='search')

    found_playlists = []
    found_comics = []

    if search_type in ['all', 'playlist']:
        # Поиск по плейлистам
        for playlist_name, content_names in playlists_data.items():
            if query in playlist_name.lower():
                playlist_dir = os.path.join(IMAGE_ROOT, playlist_name)
                if os.path.exists(playlist_dir):
                    # Превью для плейлиста - первое изображение первого комикса
                    preview = None
                    if content_names:
                         first_comic_name = content_names[0]
                         comic_imgs = [f for f in os.listdir(playlist_dir) if f.lower().startswith(first_comic_name.lower()) and f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
                         sorted_comic_imgs = sorted(comic_imgs)
                         if sorted_comic_imgs:
                             preview = url_for('static', filename=f'images/{playlist_name}/{sorted_comic_imgs[0]}')
                    if not preview:
                        imgs = sorted([f for f in os.listdir(playlist_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))])
                        preview = url_for('static', filename=f'images/{playlist_name}/{imgs[0]}') if imgs else None

                    found_playlists.append({"name": playlist_name, "preview": preview})

    if search_type in ['all', 'tag']:
        # Поиск по тегам в комиксах
        for comic_name, comic_info in comics_data.items():
            if query in comic_info.get("tags", "").lower():
                # Найти, в каких плейлистах находится этот комикс
                for playlist_name, content_names in playlists_data.items():
                    if comic_name in content_names:
                        playlist_dir = os.path.join(IMAGE_ROOT, playlist_name)
                        if os.path.exists(playlist_dir):
                            # Превью для комикса в поиске - первое изображение, связанное с ним
                            content_imgs = [f for f in os.listdir(playlist_dir) if f.lower().startswith(comic_name.lower()) and f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
                            sorted_content_imgs = sorted(content_imgs)
                            preview = url_for('static', filename=f'images/{playlist_name}/{sorted_content_imgs[0]}') if sorted_content_imgs else None
                            if not preview:
                                imgs = sorted([f for f in os.listdir(playlist_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))])
                                preview = url_for('static', filename=f'images/{playlist_name}/{imgs[0]}') if imgs else None

                            found_comics.append({"name": comic_name, "display_name": comic_info.get("name_rus", comic_name), "playlist": playlist_name, "preview": preview})
                        # break # Комикс может быть в нескольких плейлистах, покажем все вхождения

    if search_type in ['all', 'comic_name']:
        # Поиск по названию комикса (name или name_rus)
        for comic_name, comic_info in comics_data.items():
            # Ищем в оригинальном имени и в name_rus
            if query in comic_name.lower() or query in comic_info.get("name_rus", "").lower():
                # Найти, в каких плейлистах находится этот комикс
                for playlist_name, content_names in playlists_data.items():
                    if comic_name in content_names:
                        playlist_dir = os.path.join(IMAGE_ROOT, playlist_name)
                        if os.path.exists(playlist_dir):
                            # Превью для комикса в поиске - первое изображение, связанное с ним
                            content_imgs = [f for f in os.listdir(playlist_dir) if f.lower().startswith(comic_name.lower()) and f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
                            sorted_content_imgs = sorted(content_imgs)
                            preview = url_for('static', filename=f'images/{playlist_name}/{sorted_content_imgs[0]}') if sorted_content_imgs else None
                            if not preview:
                                imgs = sorted([f for f in os.listdir(playlist_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))])
                                preview = url_for('static', filename=f'images/{playlist_name}/{imgs[0]}') if imgs else None

                            found_comics.append({"name": comic_name, "display_name": comic_info.get("name_rus", comic_name), "playlist": playlist_name, "preview": preview})
                        # break # Комикс может быть в нескольких плейлистах, покажем все вхождения


    # Сортировка результатов
    found_playlists.sort(key=lambda x: x['name'])
    found_comics.sort(key=lambda x: x['display_name'])

    # Объединяем результаты, убирая дубликаты (по имени комикса и плейлисту)
    seen_comics = set()
    unique_found_comics = []
    for c in found_comics:
        identifier = (c['name'], c['playlist'])
        if identifier not in seen_comics:
            unique_found_comics.append(c)
            seen_comics.add(identifier)

    processed_results = []
    for p in found_playlists:
        processed_results.append({"type": "playlist", "name": p["name"], "preview": p["preview"]})
    for c in unique_found_comics:
        processed_results.append({"type": "comic", "name": c["name"], "display_name": c["display_name"], "playlist": c["playlist"], "preview": c["preview"]})

    if not processed_results:
        message = f"Ничего не найдено по запросу '{query}'."
    else:
        message = f"Результаты поиска по запросу '{query}' (тип: {search_type}):"

    return render_template("comics.html", playlists=[], comics=processed_results, search_query=query, message=message, view_mode='search')


# Новый маршрут для отображения конкретного комикса (content) внутри плейлиста
@app.route("/comics/<playlist_name>/<content_name>")
def show_comic_content(playlist_name, content_name):
    """Отображение конкретного комикса (content) внутри плейлиста"""
    # Проверяем, что плейлист и контент существуют
    if playlist_name not in playlists_data or content_name not in playlists_data[playlist_name]:
        return "Комикс или плейлист не найден.", 404

    playlist_dir = os.path.join(IMAGE_ROOT, playlist_name)
    if not os.path.exists(playlist_dir):
        return "Папка плейлиста не найдена.", 404

    # Получаем теги и name_rus из глобального comics_data
    tags = "N/A"
    display_name = content_name # Имя по умолчанию, если не найдено в comics_data
    if content_name in comics_
        comic_info = comics_data[content_name]
        tags = comic_info.get("tags", "N/A") # Теги доступны для отображения в show_comic.html
        display_name = comic_info.get("name_rus", content_name) # Используем name_rus, если есть

    # Считываем изображения из папки плейлиста
    imgs = sorted([f for f in os.listdir(playlist_dir) if f.lower().startswith(content_name.lower()) and f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))])
    img_urls = [url_for('static', filename=f'images/{playlist_name}/{img}') for img in imgs]

    # Если не нашли файлов по имени, покажем все (на всякий случай)
    if not imgs:
        imgs = sorted([f for f in os.listdir(playlist_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))])
        img_urls = [url_for('static', filename=f'images/{playlist_name}/{img}') for img in imgs]

    # Передаём display_name (name_rus или name) в шаблон
    return render_template("show_comic.html", name=display_name, img_urls=img_urls, tags=tags, playlist_name=playlist_name)


# Удаляем блок if __name__ == "__main__": или оставляем для локальной отладки
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
