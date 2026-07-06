const state = {
  siteConfig: null,
  catalog: null,
  seriesEntry: null,
  manifest: null,
  episodes: [],
  currentEpisode: null,
  currentIndex: -1
};

const els = {
  statusText: document.getElementById("status-text"),
  seriesCards: document.getElementById("series-cards"),
  seriesTitle: document.getElementById("series-title"),
  bookTitle: document.getElementById("book-title"),
  bookDesc: document.getElementById("book-desc"),
  episodeList: document.getElementById("episode-list"),
  backToSeries: document.getElementById("back-to-series"),
  playerShell: document.getElementById("player-shell"),
  playerArt: document.getElementById("player-art"),
  playerArtLetter: document.getElementById("player-art-letter"),
  playerBook: document.getElementById("player-book"),
  playerTitle: document.getElementById("player-title"),
  playerSubtitle: document.getElementById("player-subtitle"),
  progressBar: document.getElementById("progress-bar"),
  timeCurrent: document.getElementById("time-current"),
  timeDuration: document.getElementById("time-duration"),
  btnPlay: document.getElementById("btn-play"),
  btnPrev: document.getElementById("btn-prev"),
  btnRewind: document.getElementById("btn-rewind"),
  btnForward: document.getElementById("btn-forward"),
  btnNext: document.getElementById("btn-next"),
  audio: document.getElementById("audio")
};

function seekAudioBy(offsetSeconds) {
  const audio = els.audio;
  if (!audio || !Number.isFinite(offsetSeconds)) return;

  const duration = audio.duration;
  let targetTime = audio.currentTime + offsetSeconds;
  if (targetTime < 0) targetTime = 0;
  if (Number.isFinite(duration) && duration > 0 && targetTime > duration) {
    targetTime = duration;
  }

  audio.currentTime = targetTime;
  updateProgressUi();
}

const paths = {
  siteConfig: "./config.json",
  catalog: "./data/catalog.json"
};

function getQueryParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

function getPageType() {
  if (els.seriesCards) return "home";
  if (els.episodeList && !els.playerShell) return "series";
  if (els.playerShell) return "play";
  return "unknown";
}

function setStatus(message) {
  if (els.statusText) {
    els.statusText.textContent = message || "";
  }
}

function resolveUrl(relativePath) {
  return new URL(relativePath, window.location.href).toString();
}

function resolveManifestUrl(manifestPath) {
  if (!manifestPath) return null;
  if (/^https?:\/\//i.test(manifestPath)) return manifestPath;
  if (manifestPath.startsWith("/")) {
    return new URL(manifestPath, window.location.origin).toString();
  }
  return resolveUrl(`./data/${manifestPath}`);
}

function resolveMediaUrl(episode) {
  if (!episode) return null;
  if (episode.audio_url) return episode.audio_url;

  const audioPath = episode.audio_path;
  if (!audioPath) return null;
  if (/^https?:\/\//i.test(audioPath)) return audioPath;

  const base = state.siteConfig?.r2_public_base;
  if (base && !base.includes("xxxxxxxx")) {
    return `${base.replace(/\/$/, "")}/${audioPath.replace(/^\//, "")}`;
  }

  return resolveUrl(`./data/${audioPath}`);
}

function resolveCoverUrl(seriesEntry) {
  if (!seriesEntry?.cover) return null;
  if (/^https?:\/\//i.test(seriesEntry.cover)) return seriesEntry.cover;
  if (seriesEntry.cover.startsWith("/")) {
    return new URL(seriesEntry.cover, window.location.origin).toString();
  }
  return resolveUrl(`./data/${seriesEntry.cover}`);
}

function formatTime(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const total = Math.floor(seconds);
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

function progressKey(seriesId, episodeId) {
  return `echo:progress:${seriesId}:${episodeId}`;
}

function getSavedProgress(seriesId, episodeId) {
  try {
    const raw = localStorage.getItem(progressKey(seriesId, episodeId));
    if (raw == null) return null;
    const value = Number.parseFloat(raw);
    return Number.isFinite(value) ? value : null;
  } catch {
    return null;
  }
}

function saveProgress(seriesId, episodeId, seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return;
  try {
    localStorage.setItem(progressKey(seriesId, episodeId), String(seconds));
  } catch {
    /* ignore */
  }
}

function clearProgress(seriesId, episodeId) {
  try {
    localStorage.removeItem(progressKey(seriesId, episodeId));
  } catch {
    /* ignore */
  }
}

function getPublishedEpisodes() {
  return (state.episodes || []).filter((ep) => ep.published !== false);
}

async function loadSiteConfig() {
  try {
    const res = await fetch(resolveUrl(paths.siteConfig), { cache: "no-store" });
    if (!res.ok) throw new Error("config load failed");
    state.siteConfig = await res.json();
    return state.siteConfig;
  } catch (err) {
    console.error(err);
    return null;
  }
}

function loadInlineCatalog() {
  const node = document.getElementById("catalog-data");
  if (!node?.textContent?.trim()) return null;

  try {
    const catalog = JSON.parse(node.textContent);
    if (Array.isArray(catalog?.series) && catalog.series.length) {
      state.catalog = catalog;
      return catalog;
    }
  } catch (err) {
    console.error(err);
  }

  return null;
}

async function loadCatalog() {
  const inline = loadInlineCatalog();
  if (inline) return inline;

  try {
    const res = await fetch(resolveUrl(paths.catalog), { cache: "no-store" });
    if (!res.ok) throw new Error("catalog load failed");
    state.catalog = await res.json();
    return state.catalog;
  } catch (err) {
    console.error(err);
    if (els.seriesCards?.querySelector(".series-card-link")) {
      return null;
    }
    setStatus("无法加载书目目录");
    return null;
  }
}

async function loadSeriesManifest(seriesEntry) {
  if (!seriesEntry?.manifest) return null;

  try {
    const res = await fetch(resolveManifestUrl(seriesEntry.manifest), { cache: "no-store" });
    if (!res.ok) throw new Error("manifest load failed");
    const manifest = await res.json();
    state.manifest = manifest;
    state.episodes = Array.isArray(manifest.episodes) ? manifest.episodes : [];
    return manifest;
  } catch (err) {
    console.error(err);
    setStatus("无法加载系列内容");
    return null;
  }
}

function findSeriesEntry(catalog, seriesId) {
  return (catalog?.series || []).find((entry) => entry.series_id === seriesId) || null;
}

function renderHomePage() {
  if (!els.seriesCards) return;

  const seriesList = state.catalog?.series;
  if (!Array.isArray(seriesList) || !seriesList.length) {
    if (els.seriesCards.querySelector(".series-card-link")) return;
    els.seriesCards.innerHTML = '<p class="empty">暂无书目</p>';
    return;
  }

  els.seriesCards.innerHTML = "";

  seriesList.forEach((item) => {
    const link = document.createElement("a");
    link.className = "series-card-link";
    link.href = `./series.html?series=${encodeURIComponent(item.series_id)}`;

    const coverLetter = (item.book_title || item.series_id || "书").charAt(0);
    const coverUrl = resolveCoverUrl(item);
    const coverHtml = coverUrl
      ? `<img class="card-cover-img" src="${coverUrl}" alt="" loading="lazy" />`
      : `<div class="card-cover">${coverLetter}</div>`;

    link.innerHTML = `
      <article class="series-card">
        ${coverHtml}
        <div class="card-body">
          <h3>${item.book_title || item.series_id}</h3>
          <p class="card-desc">${item.description || ""}</p>
          <span class="card-link">查看集数 →</span>
        </div>
      </article>
    `;

    els.seriesCards.appendChild(link);
  });
}

function renderSeriesPage() {
  const entry = state.seriesEntry;
  const title = entry?.book_title || entry?.series_id || "";

  if (els.seriesTitle) els.seriesTitle.textContent = title;
  if (els.bookTitle) els.bookTitle.textContent = title;
  if (els.bookDesc) {
    els.bookDesc.textContent =
      entry?.description || state.manifest?.description || "";
  }

  if (!els.episodeList) return;

  const published = getPublishedEpisodes();
  els.episodeList.innerHTML = "";

  if (!published.length) {
    els.episodeList.innerHTML =
      '<li class="episode-empty">当前还没有可播放的集数</li>';
    return;
  }

  published.forEach((episode, index) => {
    const li = document.createElement("li");
    li.className = "episode-item";

    const link = document.createElement("a");
    link.className = "episode-link";
    link.href = `./play.html?series=${encodeURIComponent(entry.series_id)}&ep=${encodeURIComponent(episode.episode_id)}`;
    link.innerHTML = `
      <span class="episode-index">${String(index + 1).padStart(2, "0")}</span>
      <span class="episode-content">
        <span class="episode-title">${episode.title || "未命名集数"}</span>
        <span class="episode-question">${episode.central_question || ""}</span>
      </span>
      <span class="episode-play-icon" aria-hidden="true">▶</span>
    `;

    li.appendChild(link);
    els.episodeList.appendChild(li);
  });
}

function updateTransportButtons() {
  const published = getPublishedEpisodes();
  const hasPrev = state.currentIndex > 0;
  const hasNext = state.currentIndex >= 0 && state.currentIndex < published.length - 1;

  if (els.btnPrev) els.btnPrev.disabled = !hasPrev;
  if (els.btnNext) els.btnNext.disabled = !hasNext;
}

function updatePlayButton(isPlaying) {
  if (!els.btnPlay) return;
  els.btnPlay.textContent = isPlaying ? "⏸" : "▶";
  els.btnPlay.setAttribute("aria-label", isPlaying ? "暂停" : "播放");
}

function updateProgressUi() {
  const audio = els.audio;
  if (!audio || !els.progressBar) return;

  const duration = audio.duration;
  const current = audio.currentTime;

  if (Number.isFinite(duration) && duration > 0) {
    els.progressBar.value = String(Math.round((current / duration) * 1000));
    if (els.timeDuration) els.timeDuration.textContent = formatTime(duration);
  } else {
    els.progressBar.value = "0";
    if (els.timeDuration) els.timeDuration.textContent = "0:00";
  }

  if (els.timeCurrent) els.timeCurrent.textContent = formatTime(current);
}

function bindAudioEvents() {
  const audio = els.audio;
  if (!audio) return;

  let progressTimer = null;

  const persistCurrentProgress = () => {
    const episode = state.currentEpisode;
    const seriesId = state.seriesEntry?.series_id;
    if (!episode || !seriesId) return;
    saveProgress(seriesId, episode.episode_id, audio.currentTime);
  };

  audio.addEventListener("loadedmetadata", () => {
    const episode = state.currentEpisode;
    const seriesId = state.seriesEntry?.series_id;
    if (!episode || !seriesId) return;

    const saved = getSavedProgress(seriesId, episode.episode_id);
    if (saved != null && saved < audio.duration - 2) {
      audio.currentTime = saved;
    }
    updateProgressUi();
  });

  audio.addEventListener("timeupdate", updateProgressUi);

  audio.addEventListener("play", () => {
    updatePlayButton(true);
    progressTimer = window.setInterval(persistCurrentProgress, 5000);
  });

  audio.addEventListener("pause", () => {
    updatePlayButton(false);
    if (progressTimer) {
      window.clearInterval(progressTimer);
      progressTimer = null;
    }
    persistCurrentProgress();
  });

  audio.addEventListener("ended", () => {
    updatePlayButton(false);
    const episode = state.currentEpisode;
    const seriesId = state.seriesEntry?.series_id;
    if (episode && seriesId) clearProgress(seriesId, episode.episode_id);

    const published = getPublishedEpisodes();
    if (state.currentIndex >= 0 && state.currentIndex < published.length - 1) {
      loadEpisode(published[state.currentIndex + 1], true);
    }
  });

  if (els.progressBar) {
    els.progressBar.addEventListener("input", () => {
      const duration = audio.duration;
      if (!Number.isFinite(duration) || duration <= 0) return;
      const ratio = Number(els.progressBar.value) / 1000;
      audio.currentTime = duration * ratio;
      updateProgressUi();
    });
  }

  if (els.btnPlay) {
    els.btnPlay.addEventListener("click", () => {
      if (audio.paused) {
        audio.play().catch(() => setStatus("请点击播放按钮开始收听"));
      } else {
        audio.pause();
      }
    });
  }

  if (els.btnPrev) {
    els.btnPrev.addEventListener("click", () => {
      const published = getPublishedEpisodes();
      if (state.currentIndex > 0) {
        loadEpisode(published[state.currentIndex - 1], true);
      }
    });
  }

  if (els.btnRewind) {
    els.btnRewind.addEventListener("click", () => seekAudioBy(-15));
  }

  if (els.btnForward) {
    els.btnForward.addEventListener("click", () => seekAudioBy(15));
  }

  if (els.btnNext) {
    els.btnNext.addEventListener("click", () => {
      const published = getPublishedEpisodes();
      if (state.currentIndex >= 0 && state.currentIndex < published.length - 1) {
        loadEpisode(published[state.currentIndex + 1], true);
      }
    });
  }
}

function loadEpisode(episode, autoplay) {
  if (!episode || !state.seriesEntry) return;

  const previous = state.currentEpisode;
  const seriesId = state.seriesEntry.series_id;

  if (previous && els.audio && !els.audio.paused) {
    saveProgress(seriesId, previous.episode_id, els.audio.currentTime);
  }

  state.currentEpisode = episode;
  const published = getPublishedEpisodes();
  state.currentIndex = published.findIndex(
    (item) => item.episode_id === episode.episode_id
  );

  const title = episode.title || "未命名集数";
  const bookTitle = state.seriesEntry.book_title || seriesId;

  if (els.playerTitle) els.playerTitle.textContent = title;
  if (els.playerSubtitle) {
    els.playerSubtitle.textContent = episode.central_question || "";
  }
  if (els.playerBook) els.playerBook.textContent = bookTitle;
  if (els.seriesTitle) els.seriesTitle.textContent = bookTitle;

  const coverLetter = bookTitle.charAt(0) || "E";
  if (els.playerArtLetter) els.playerArtLetter.textContent = coverLetter;

  const coverUrl = resolveCoverUrl(state.seriesEntry);
  if (els.playerArt) {
    if (coverUrl) {
      els.playerArt.style.backgroundImage = `url("${coverUrl}")`;
      if (els.playerArtLetter) els.playerArtLetter.style.display = "none";
    } else {
      els.playerArt.style.backgroundImage = "";
      if (els.playerArtLetter) els.playerArtLetter.style.display = "";
    }
  }

  document.title = `${title} — Susur`;

  const mediaUrl = resolveMediaUrl(episode);
  if (!els.audio) return;

  if (!mediaUrl) {
    els.audio.removeAttribute("src");
    setStatus("当前集数没有音频地址");
    updateTransportButtons();
    return;
  }

  els.audio.src = mediaUrl;
  els.audio.load();
  updateTransportButtons();
  setStatus("");

  if (autoplay) {
    els.audio.play().catch(() => {
      setStatus("当前浏览器阻止了自动播放，请点播放按钮");
    });
  }
}

function renderPlayPage(episodeId) {
  const entry = state.seriesEntry;
  const published = getPublishedEpisodes();

  if (els.backToSeries) {
    els.backToSeries.href = `./series.html?series=${encodeURIComponent(entry.series_id)}`;
  }

  if (!published.length) {
    if (els.playerTitle) els.playerTitle.textContent = "暂无可播放集数";
    setStatus("该系列还没有已发布的集数");
    return;
  }

  let target =
    published.find((item) => item.episode_id === episodeId) || published[0];

  if (episodeId && !published.some((item) => item.episode_id === episodeId)) {
    setStatus(`找不到集数 ${episodeId}，已播放第一集`);
  }

  loadEpisode(target, Boolean(episodeId));
}

async function init() {
  setStatus("加载中…");

  await loadSiteConfig();
  const catalog = await loadCatalog();
  const pageType = getPageType();

  if (pageType === "home") {
    if (catalog) renderHomePage();
    setStatus("");
    return;
  }

  if (!catalog) return;

  const seriesId = getQueryParam("series");

  if (pageType === "series" && !seriesId && els.episodeList) {
    window.location.replace("./index.html");
    return;
  }

  if (!seriesId) {
    setStatus("请从首页选择一本书");
    return;
  }

  const seriesEntry = findSeriesEntry(catalog, seriesId);
  if (!seriesEntry) {
    setStatus("找不到该系列");
    return;
  }

  state.seriesEntry = seriesEntry;
  await loadSeriesManifest(seriesEntry);

  if (pageType === "series") {
    renderSeriesPage();
    setStatus(getPublishedEpisodes().length ? "" : "暂无已发布集数");
    return;
  }

  if (pageType === "play") {
    bindAudioEvents();
    renderPlayPage(getQueryParam("ep"));
    return;
  }

  setStatus("未知页面类型");
}

document.addEventListener("DOMContentLoaded", init);
