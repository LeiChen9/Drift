const PROGRESS_KEY_PREFIX = "echo:progress:";
const PROGRESS_SAVE_INTERVAL_MS = 5000;

const params = new URLSearchParams(window.location.search);
const seriesParam = params.get("series");

const els = {
  siteTitle: document.getElementById("site-title"),
  seriesTitle: document.getElementById("series-title"),
  episodeList: document.getElementById("episode-list"),
  nowPlaying: document.getElementById("now-playing"),
  audio: document.getElementById("audio"),
  statusText: document.getElementById("status-text"),
};

let state = {
  seriesId: null,
  episodes: [],
  currentEpisodeId: null,
  progressTimer: null,
};

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`请求失败 ${url} (${response.status})`);
  }
  return response.json();
}

function progressKey(seriesId, episodeId) {
  return `${PROGRESS_KEY_PREFIX}${seriesId}:${episodeId}`;
}

function readProgress(seriesId, episodeId) {
  const raw = localStorage.getItem(progressKey(seriesId, episodeId));
  if (!raw) return 0;
  const seconds = parseFloat(raw);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : 0;
}

function saveProgress(seriesId, episodeId, seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return;
  localStorage.setItem(progressKey(seriesId, episodeId), String(seconds));
}

function clearProgressTimer() {
  if (state.progressTimer) {
    clearInterval(state.progressTimer);
    state.progressTimer = null;
  }
}

function startProgressTimer() {
  clearProgressTimer();
  state.progressTimer = setInterval(() => {
    if (!state.currentEpisodeId || els.audio.paused) return;
    saveProgress(state.seriesId, state.currentEpisodeId, els.audio.currentTime);
  }, PROGRESS_SAVE_INTERVAL_MS);
}

function resolveAudioUrl(config, episode) {
  if (episode.audio_url) {
    return episode.audio_url;
  }
  if (episode.audio_path) {
    const base = config.r2_public_base.replace(/\/$/, "");
    return `${base}/${episode.audio_path}`;
  }
  throw new Error(`集 ${episode.episode_id} 缺少 audio_url 或 audio_path`);
}

function renderEpisodeList() {
  els.episodeList.innerHTML = "";

  if (state.episodes.length === 0) {
    els.episodeList.innerHTML =
      '<li class="episode-item"><p class="placeholder">暂无已发布的集数</p></li>';
    return;
  }

  for (const episode of state.episodes) {
    const li = document.createElement("li");
    li.className = "episode-item";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "episode-button";
    button.dataset.episodeId = episode.episode_id;
    if (episode.episode_id === state.currentEpisodeId) {
      button.classList.add("active");
    }

    const idSpan = document.createElement("span");
    idSpan.className = "episode-id";
    idSpan.textContent = episode.episode_id;

    const titleSpan = document.createElement("span");
    titleSpan.className = "episode-name";
    titleSpan.textContent = episode.title;

    button.append(idSpan, titleSpan);
    button.addEventListener("click", () => playEpisode(episode.episode_id));
    li.appendChild(button);
    els.episodeList.appendChild(li);
  }
}

function renderNowPlaying(episode) {
  els.nowPlaying.innerHTML = `
    <h3 class="episode-title">${escapeHtml(episode.title)}</h3>
    <p class="episode-question">${escapeHtml(episode.central_question || "")}</p>
  `;
}

function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function playEpisode(episodeId) {
  const episode = state.episodes.find((item) => item.episode_id === episodeId);
  if (!episode) return;

  if (state.currentEpisodeId && state.currentEpisodeId !== episodeId) {
    saveProgress(state.seriesId, state.currentEpisodeId, els.audio.currentTime);
  }

  state.currentEpisodeId = episodeId;
  renderEpisodeList();
  renderNowPlaying(episode);

  const audioUrl = resolveAudioUrl(state.config, episode);
  if (els.audio.src !== audioUrl) {
    els.audio.src = audioUrl;
    els.audio.load();
  }

  const saved = readProgress(state.seriesId, episodeId);
  if (saved > 0) {
    els.audio.currentTime = saved;
  }

  els.audio.play().catch(() => {
    els.statusText.textContent = "点击播放按钮开始收听";
  });
}

function bindAudioEvents() {
  els.audio.addEventListener("loadedmetadata", () => {
    if (!state.currentEpisodeId) return;
    const saved = readProgress(state.seriesId, state.currentEpisodeId);
    if (saved > 0 && saved < els.audio.duration) {
      els.audio.currentTime = saved;
    }
  });

  els.audio.addEventListener("play", startProgressTimer);
  els.audio.addEventListener("pause", () => {
    if (state.currentEpisodeId) {
      saveProgress(state.seriesId, state.currentEpisodeId, els.audio.currentTime);
    }
  });

  els.audio.addEventListener("ended", () => {
    if (state.currentEpisodeId) {
      localStorage.removeItem(progressKey(state.seriesId, state.currentEpisodeId));
    }
  });
}

async function resolveSeriesEntry(catalog) {
  if (seriesParam) {
    const match = catalog.series.find((item) => item.series_id === seriesParam);
    if (!match) {
      throw new Error(`未找到系列: ${seriesParam}`);
    }
    return match;
  }
  if (catalog.series.length === 1) {
    return catalog.series[0];
  }
  throw new Error("存在多个系列，请使用 ?series=系列ID 指定");
}

function showError(message) {
  els.nowPlaying.innerHTML = `<div class="error-box">${escapeHtml(message)}</div>`;
  els.statusText.textContent = "";
}

async function init() {
  bindAudioEvents();

  try {
    const [config, catalog] = await Promise.all([
      fetchJson("/config.json"),
      fetchJson("/data/catalog.json"),
    ]);

    if (config.r2_public_base.includes("REPLACE_ME")) {
      showError("请先在 config.json 中配置 R2 公开访问域名（r2_public_base）");
      return;
    }

    const seriesEntry = await resolveSeriesEntry(catalog);
    const manifest = await fetchJson(seriesEntry.manifest);
    const episodes = (manifest.episodes || [])
      .filter((item) => item.published === true)
      .sort((a, b) => a.episode_id.localeCompare(b.episode_id));

    state = {
      ...state,
      config,
      seriesId: manifest.series_id,
      episodes,
    };

    els.siteTitle.textContent = "Echo";
    els.seriesTitle.textContent = manifest.book_title;
    els.statusText.textContent = `${episodes.length} 集已发布`;

    renderEpisodeList();

    if (episodes.length > 0) {
      const resumeId = params.get("ep") || episodes[0].episode_id;
      if (episodes.some((item) => item.episode_id === resumeId)) {
        playEpisode(resumeId);
      }
    }
  } catch (error) {
    console.error(error);
    showError(error.message || "加载失败，请稍后重试");
  }
}

init();
