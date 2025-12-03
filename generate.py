from flask import Flask, render_template, request
import os
import zipfile
import xml.etree.ElementTree as ET
import shutil
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Пути
UPLOAD_FOLDER = "uploads"
IMAGE_ROOT = "static/images"
HTML_OUTPUT = "static/comics_html"

# Создание папок
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(IMAGE_ROOT, exist_ok=True)
os.makedirs(HTML_OUTPUT, exist_ok=True)

# ------------------ Админская часть ------------------
@app.route("/")
def index():
    """Страница загрузки XML и ZIP файлов"""
    return render_template("upload.html")


@app.route("/upload", methods=["POST"])
def upload():
    """Обработка загрузки файлов и генерация HTML комиксов"""
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
        playlists_path = os.path.join(UPLOAD_FOLDER, secure_filename(playlists_file.filename))
        playlists_file.save(playlists_path)

    # Распаковка ZIP
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_dir)

    # Очистка и создание папок для картинок и HTML
    if os.path.exists(IMAGE_ROOT):
        shutil.rmtree(IMAGE_ROOT)
    os.makedirs(IMAGE_ROOT, exist_ok=True)

    if os.path.exists(HTML_OUTPUT):
        shutil.rmtree(HTML_OUTPUT)
    os.makedirs(HTML_OUTPUT, exist_ok=True)

    # Чтение XML комиксов
    tree = ET.parse(xml_path)
    root = tree.getroot()

    logs = []
    comic_html_files = []

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
                shutil.copy2(os.path.join(extract_dir, f),
                             os.path.join(comic_dir, f))
                found_files.append(f)

        logs.append(f"Комикс '{name}': найдено {len(found_files)} файлов (ожидалось {pics}), теги: {tags}")

        # Генерация HTML для комикса (вертикальные карточки)
        html_path = os.path.join(HTML_OUTPUT, f"{name}.html")
        comic_html_files.append(f"{name}.html")

        with open(html_path, "w", encoding="utf-8") as h:
            h.write(f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <title>{name}</title>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            font-family: "Segoe UI", Arial, sans-serif;
            background: #f4f4f8;
        }}
        h1 {{
            text-align: center;
            margin-bottom: 10px;
            color: #222;
        }}
        .tags {{
            text-align: center;
            color: #666;
            margin-bottom: 25px;
        }}
        .gallery {{
            display: flex;
            flex-direction: column;
            gap: 30px;
            max-width: 800px;
            margin: 0 auto;
        }}
        .card {{
            background: white;
            border-radius: 10px;
            box-shadow: 0 6px 15px rgba(0,0,0,0.2);
            padding: 20px;
            transition: transform 0.2s;
        }}
        .card:hover {{
            transform: scale(1.02);
        }}
        img {{
            width: 100%;
            border-radius: 10px;
            display: block;
        }}
        .back {{
            display: inline-block;
            margin: 30px auto 0;
            padding: 12px 20px;
            background: #0066cc;
            color: white;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 500;
        }}
        .back:hover {{
            background: #004c99;
        }}
        .center {{
            text-align: center;
        }}
    </style>
</head>
<body>
    <h1>{name}</h1>
    <div class="tags">Теги: {tags}</div>
    <div class="gallery">
""")
            for img in sorted(found_files):
                img_path = f"/static/images/{name}/{img}"
                h.write(f"""
        <div class="card">
            <img src="{img_path}" alt="{img}">
        </div>
""")
            h.write("""
    </div>
    <div class="center">
        <a class="back" href="/comics">← Назад к списку комиксов</a>
    </div>
</body>
</html>
""")

    # Обработка плейлистов (если есть)
    if playlists_path:
        try:
            tree = ET.parse(playlists_path)
            root = tree.getroot()
            logs.append("")
            logs.append("🎵 Найдены плейлисты:")
            for plist in root.findall("playlist"):
                pl_name = plist.get("name", "без_имени")
                items = [c.get("name") for c in plist.findall("content")]
                logs.append(f"Плейлист '{pl_name}': {', '.join(items)}")
        except Exception as e:
            logs.append(f"⚠️ Ошибка чтения файла плейлистов: {e}")

    return render_template("result.html", logs=logs, files=comic_html_files)


# ------------------ Пользовательский интерфейс ------------------
@app.route("/comics")
def comics():
    """Пользовательский интерфейс: выбор комикса с превью"""
    if not os.path.exists(HTML_OUTPUT):
        return "Комиксы ещё не загружены."

    comics_list = []
    for f in sorted(os.listdir(HTML_OUTPUT)):
        if f.endswith(".html"):
            name = f.replace(".html", "")
            img_dir = os.path.join(IMAGE_ROOT, name)
            preview = None
            if os.path.exists(img_dir):
                imgs = sorted(os.listdir(img_dir))
                if imgs:
                    preview = f"/static/images/{name}/{imgs[0]}"
            comics_list.append({"name": name, "file": f, "preview": preview})

    return render_template("comics.html", comics=comics_list)


if __name__ == "__main__":
    app.run(debug=True)
