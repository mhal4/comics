// --- Глобальные переменные ---
let comicsData = null;
let playlistsData = null;
let allTags = new Set();

// --- Загрузка XML ---
async function loadXML(url) {
  const response = await fetch(url);
  const text = await response.text();
  const parser = new DOMParser();
  return parser.parseFromString(text, "application/xml");
}

function parseComics(xmlDoc) {
  const comics = xmlDoc.querySelectorAll("comic");
  const result = {};
  comics.forEach((comic) => {
    const name = comic.getAttribute("name");
    const pics = parseInt(comic.getAttribute("pics")) || 1;
    const tags = (comic.getAttribute("tags") || "").split(" ").filter((t) => t);
    result[name] = { name, pics, tags };
    tags.forEach((tag) => allTags.add(tag));
  });
  return result;
}

function parsePlaylists(xmlDoc) {
  const playlists = xmlDoc.querySelectorAll("playlist");
  const result = {};
  playlists.forEach((playlist) => {
    const name = playlist.getAttribute("name");
    const content = Array.from(playlist.querySelectorAll("content")).map((c) =>
      c.getAttribute("comic"),
    );
    result[name] = { name, content };
  });
  return result;
}

// --- Основная инициализация ---
document.addEventListener("DOMContentLoaded", async () => {
  try {
    const [comicsXml, playlistsXml] = await Promise.all([
      loadXML("data.xml"),
      loadXML("playlists.xml"),
    ]);

    comicsData = parseComics(comicsXml);
    playlistsData = parsePlaylists(playlistsXml);

    // --- Обработка главной страницы ---
    if (
      window.location.pathname.endsWith("index.html") ||
      window.location.pathname === "/"
    ) {
      renderPlaylists();
      renderTagPanel();
      renderRandomTagGroups();
    }

    // --- Обработка страницы комиксов ---
    if (window.location.pathname.includes("comics.html")) {
      renderComicPage();
    }

    // --- Обработка страницы по тегу ---
    if (window.location.pathname.includes("tag.html")) {
      renderTagPage();
    }

    // --- Обработчики UI ---
    setupTagPanelToggle();
  } catch (error) {
    console.error("Ошибка при загрузке или обработке XML:", error);
    document.getElementById("mainContent").innerHTML =
      "<p>Ошибка загрузки данных.</p>";
  }
});

// --- Функции рендеринга ---

function renderPlaylists() {
  const container = document.getElementById("playlistsContainer");
  if (!container) return;

  container.innerHTML = "";
  for (const [name, playlist] of Object.entries(playlistsData)) {
    const div = document.createElement("div");
    div.className = "playlist-item";
    div.innerHTML = `<h3><a href="comics.html?playlist=${encodeURIComponent(name)}">${name}</a></h3>`;
    const comicPreviews = playlist.content
      .slice(0, 3)
      .map((cn) => {
        const comic = comicsData[cn];
        if (comic) {
          // Исправлено: начинаем с 0
          const imgName =
            comic.pics > 1 ? `pictures/${cn}_0.jpg` : `pictures/${cn}.jpg`;
          return `<img src="pictures/${imgName}" alt="pictures/${cn}" class="comic-image" style="max-width: 100px; height: auto;">`;
        }
        return "";
      })
      .join("");
    div.innerHTML += `<div>${comicPreviews}</div>`;
    container.appendChild(div);
  }
}

function renderTagPanel() {
  const list = document.getElementById("tagList");
  if (!list) return;

  list.innerHTML = "";
  Array.from(allTags)
    .sort()
    .forEach((tag) => {
      const li = document.createElement("li");
      li.innerHTML = `<a href="tag.html?tag=${encodeURIComponent(tag)}">${tag}</a>`;
      list.appendChild(li);
    });
}

function renderRandomTagGroups() {
  const container = document.getElementById("randomTagsContainer");
  if (!container) return;

  container.innerHTML = "";
  const shuffledTags = Array.from(allTags).sort(() => 0.5 - Math.random());
  const selectedTags = shuffledTags.slice(0, 3);

  selectedTags.forEach((tag) => {
    const comicsWithTag = Object.values(comicsData).filter((c) =>
      c.tags.includes(tag),
    );
    if (comicsWithTag.length > 0) {
      const groupDiv = document.createElement("div");
      groupDiv.className = "random-tag-group";
      groupDiv.innerHTML = `<h4>${tag}</h4>`;
      const comicPreviews = comicsWithTag
        .slice(0, 2)
        .map((comic) => {
          // Исправлено: начинаем с 0
          const imgName =
            comic.pics > 1
              ? `pictures/${comic.name}_0.jpg`
              : `pictures/${comic.name}.jpg`;
          return `<img src="pictures/${imgName}" alt="pictures/${comic.name}" class="comic-image" style="max-width: 80px; height: auto;">`;
        })
        .join("");
      groupDiv.innerHTML += `<div>${comicPreviews}</div>`;
      container.appendChild(groupDiv);
    }
  });
}

function renderComicPage() {
  const urlParams = new URLSearchParams(window.location.search);
  const playlistName = urlParams.get("playlist");
  const comicName = urlParams.get("comic");

  const contentDiv = document.getElementById("comicContent");
  if (!contentDiv) return;

  if (playlistName && playlistsData[playlistName]) {
    const playlist = playlistsData[playlistName];
    contentDiv.innerHTML = `<h2>${playlist.name}</h2>`;
    playlist.content.forEach((cn) => {
      const comic = comicsData[cn];
      if (comic) {
        const comicDiv = document.createElement("div");
        comicDiv.className = "comic-item";
        let images = "";
        // Исправлено: начинаем с 0 и идем до pics-1
        for (let i = 0; i < comic.pics; i++) {
          const imgName =
            comic.pics > 1 ? `pictures/${cn}_${i}.jpg` : `pictures/${cn}.jpg`;
          images += `<img src="pictures/${imgName}" alt="pictures/${cn}_${i}" class="comic-image">`;
        }
        comicDiv.innerHTML = `<h3>${comic.name}</h3>${images}`;
        contentDiv.appendChild(comicDiv);
      }
    });
  } else if (comicName && comicsData[comicName]) {
    const comic = comicsData[comicName];
    contentDiv.innerHTML = `<h2>${comic.name}</h2>`;
    const comicDiv = document.createElement("div");
    comicDiv.className = "comic-item";
    let images = "";
    // Исправлено: начинаем с 0 и идем до pics-1
    for (let i = 0; i < comic.pics; i++) {
      const imgName =
        comic.pics > 1
          ? `pictures/${comicName}_${i}.jpg`
          : `pictures/${comicName}.jpg`;
      images += `<img src="pictures/${imgName}" alt="pictures/${comic.name}_${i}" class="comic-image">`;
    }
    comicDiv.innerHTML = images;
    contentDiv.appendChild(comicDiv);
  } else {
    contentDiv.innerHTML = "<p>Комикс или плейлист не найден.</p>";
  }
}

function renderTagPage() {
  const urlParams = new URLSearchParams(window.location.search);
  const tagName = urlParams.get("tag");

  const contentDiv = document.getElementById("tagContent");
  if (!contentDiv) return;

  if (tagName) {
    contentDiv.innerHTML = `<h2>Комиксы по тегу: ${tagName}</h2>`;
    const comicsWithTag = Object.values(comicsData).filter((c) =>
      c.tags.includes(tagName),
    );
    comicsWithTag.forEach((comic) => {
      const comicDiv = document.createElement("div");
      comicDiv.className = "comic-item";
      // Исправлено: начинаем с 0
      const imgName =
        comic.pics > 1
          ? `pictures/${comic.name}_0.jpg`
          : `pictures/${comic.name}.jpg`;
      comicDiv.innerHTML = `<h3><a href="comics.html?comic=${encodeURIComponent(comic.name)}">${comic.name}</a></h3>
                                  <img src="pictures/${imgName}" alt="pictures/${comic.name}" class="comic-image">`;
      contentDiv.appendChild(comicDiv);
    });
  } else {
    contentDiv.innerHTML = "<p>Тег не указан.</p>";
  }
}

// --- UI функции ---

function setupTagPanelToggle() {
  const toggleBtn = document.getElementById("tagPanelToggle");
  const panel = document.getElementById("tagPanel");
  if (toggleBtn && panel) {
    toggleBtn.addEventListener("click", () => {
      panel.classList.toggle("active");
    });
  }
}
