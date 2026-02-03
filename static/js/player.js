const audio = document.getElementById('audio-player');
const titleEl = document.getElementById('track-title');
const statusEl = document.getElementById('track-status');
const playBtn = document.getElementById('btn-play');
const playIcon = document.getElementById('play-icon');
const progressFill = document.getElementById('progress');
const batchLabel = document.getElementById('batch-label');

let currentTrackId = null;
let currentTrackUrl = null;
let currentTrackTitle = null;
let isPlaying = false;

// Batch tracking
let batchSize = 5;
let currentBatchPosition = 0;
let batchFeedback = {};

// History for Previous button
let trackHistory = [];
let historyIndex = -1;

// Search Elements
const searchOverlay = document.getElementById('search-overlay');
const searchInput = document.getElementById('search-input');
const searchResults = document.getElementById('search-results');
let searchTimeout = null;

// Button listeners
document.getElementById('btn-search').addEventListener('click', () => {
    searchOverlay.style.display = 'flex';
    searchInput.focus();
});

document.getElementById('btn-close-search').addEventListener('click', () => {
    searchOverlay.style.display = 'none';
});

// Reset Session
const resetBtn = document.getElementById('btn-reset');
if (resetBtn) {
    resetBtn.addEventListener('click', () => {
        fetch('/api/reset_session', { method: 'POST' })
            .then(() => {
                window.location.href = '/login'; // Redirect to Admin/Login instead of landing
            });
    });
}

searchInput.addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => performSearch(e.target.value), 300);
});

async function performSearch(query) {
    if (!query) {
        searchResults.innerHTML = '';
        return;
    }

    try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        const results = await res.json();

        searchResults.innerHTML = '';
        results.forEach(track => {
            const div = document.createElement('div');
            div.className = 'search-item';
            div.innerHTML = `<h4>${track.title}</h4>`;
            div.onclick = () => selectTrack(track.id);
            searchResults.appendChild(div);
        });
    } catch (e) {
        console.error(e);
    }
}

async function selectTrack(id) {
    try {
        const res = await fetch('/api/select', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: id })
        });
        const data = await res.json();

        if (data.url) {
            playTrackData(data);
            searchOverlay.style.display = 'none';
        }
    } catch (e) {
        console.error(e);
    }
}

// Core controls
document.getElementById('btn-next').addEventListener('click', () => nextTrack());
document.getElementById('btn-prev').addEventListener('click', () => previousTrack());
playBtn.addEventListener('click', togglePlay);

// Audio Events
audio.addEventListener('ended', () => {
    sendFeedback();
    nextTrack();
});

audio.addEventListener('timeupdate', () => {
    if (!currentTrackId) return;

    if (audio.duration) {
        const pct = (audio.currentTime / audio.duration) * 100;
        progressFill.style.width = pct + '%';

        // Update Media Session position
        if ('mediaSession' in navigator && audio.duration) {
            navigator.mediaSession.setPositionState({
                duration: audio.duration,
                playbackRate: audio.playbackRate,
                position: audio.currentTime
            });
        }
    }

    const elapsed = Math.floor(audio.currentTime);
    const mins = Math.floor(elapsed / 60);
    const secs = elapsed % 60;
    statusEl.innerText = `${mins}:${secs.toString().padStart(2, '0')}`;
});

// Seekable progress bar
document.querySelector('.progress-bar').addEventListener('click', (e) => {
    if (!audio.duration) return;
    const rect = e.target.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    audio.currentTime = pct * audio.duration;
});

function togglePlay() {
    if (!currentTrackId) {
        loadNextTrack();
        return;
    }

    if (audio.paused) {
        audio.play().then(() => {
            updatePlayButton(true);
        }).catch(e => console.error("Play error:", e));
    } else {
        audio.pause();
        updatePlayButton(false);
    }
}

function updatePlayButton(playing) {
    isPlaying = playing;
    playIcon.className = playing ? 'fas fa-pause' : 'fas fa-play';
}

// Media Session API for Android/iOS notification controls
function setupMediaSession() {
    if (!('mediaSession' in navigator)) return;

    navigator.mediaSession.setActionHandler('play', () => {
        audio.play();
        updatePlayButton(true);
    });

    navigator.mediaSession.setActionHandler('pause', () => {
        audio.pause();
        updatePlayButton(false);
    });

    navigator.mediaSession.setActionHandler('previoustrack', () => {
        previousTrack();
    });

    navigator.mediaSession.setActionHandler('nexttrack', () => {
        nextTrack();
    });

    navigator.mediaSession.setActionHandler('seekto', (details) => {
        if (details.seekTime !== undefined) {
            audio.currentTime = details.seekTime;
        }
    });

    navigator.mediaSession.setActionHandler('seekbackward', (details) => {
        const skipTime = details.seekOffset || 10;
        audio.currentTime = Math.max(audio.currentTime - skipTime, 0);
    });

    navigator.mediaSession.setActionHandler('seekforward', (details) => {
        const skipTime = details.seekOffset || 10;
        audio.currentTime = Math.min(audio.currentTime + skipTime, audio.duration || 0);
    });
}

function updateMediaSession(title) {
    if (!('mediaSession' in navigator)) return;

    // Parse artist from title (format: "Song Name - Artist.mp3")
    let songName = title;
    let artist = 'chaar.fm';

    if (title.includes(' - ')) {
        const parts = title.replace('.mp3', '').split(' - ');
        songName = parts[0];
        artist = parts.slice(1).join(' - ');
    }

    navigator.mediaSession.metadata = new MediaMetadata({
        title: songName,
        artist: artist,
        album: 'chaar.fm',
        artwork: [
            { src: '/static/images/logo.png', sizes: '512x512', type: 'image/png' }
        ]
    });
}

// Initialize Media Session
setupMediaSession();

// Local Link Map
const LocalLinkMap = new Map();

document.getElementById('btn-link-local')?.addEventListener('click', () => {
    document.getElementById('local-file-input')?.click();
});

document.getElementById('local-file-input')?.addEventListener('change', (e) => {
    const files = e.target.files;
    let count = 0;
    for (const file of files) {
        LocalLinkMap.set(file.name, file);
        count++;
    }
    alert(`Linked ${count} local files!`);
});

function playTrackData(data) {
    currentTrackId = data.id;
    currentTrackUrl = data.url;
    currentTrackTitle = data.title;

    titleEl.innerText = data.title;

    let audioSrc = data.url;

    // Check local files
    if (LocalLinkMap.has(data.title)) {
        const file = LocalLinkMap.get(data.title);
        audioSrc = URL.createObjectURL(file);
    }

    audio.src = audioSrc;

    // Update Media Session
    updateMediaSession(data.title);

    audio.play().then(() => {
        updatePlayButton(true);
    }).catch(e => {
        console.error("Autoplay error:", e);
        statusEl.innerText = "Click Play";
        updatePlayButton(false);
    });
}

async function loadNextTrack() {
    try {
        statusEl.innerText = "Loading...";
        const res = await fetch('/api/next');
        const data = await res.json();

        if (data.error) {
            titleEl.innerText = "Error loading music";
            return;
        }

        // Add to history
        if (currentTrackId) {
            trackHistory.push({
                id: currentTrackId,
                url: currentTrackUrl,
                title: currentTrackTitle
            });
        }
        historyIndex = trackHistory.length;

        // Update batch info
        if (data.queue_remaining !== undefined) {
            batchSize = data.batch_size || 5;
            currentBatchPosition = batchSize - data.queue_remaining - 1;

            if (currentBatchPosition === 0) {
                batchFeedback = {};
            }

            updateBatchIndicator();
        }

        playTrackData(data);

    } catch (e) {
        console.error(e);
        statusEl.innerText = "Error";
    }
}

function updateBatchIndicator() {
    for (let i = 0; i < 5; i++) {
        const dot = document.getElementById(`dot-${i}`);
        if (!dot) continue;

        dot.className = 'batch-dot';

        if (i < currentBatchPosition) {
            const fb = batchFeedback[i];
            if (fb === 'positive') {
                dot.classList.add('liked');
            } else if (fb === 'negative') {
                dot.classList.add('disliked');
            } else {
                dot.classList.add('played');
            }
        } else if (i === currentBatchPosition) {
            dot.classList.add('current');
        }
    }

    const remaining = batchSize - currentBatchPosition - 1;
    if (remaining > 0) {
        batchLabel.innerText = `${remaining} song${remaining > 1 ? 's' : ''} left`;
    } else {
        batchLabel.innerText = 'Last in batch';
    }
}

function nextTrack() {
    if (currentTrackId) {
        sendFeedback();
    }

    if (historyIndex < trackHistory.length - 1) {
        historyIndex++;
        const track = trackHistory[historyIndex];
        playTrackData(track);
    } else {
        loadNextTrack();
    }
}

function previousTrack() {
    if (historyIndex > 0) {
        if (currentTrackId) {
            sendFeedback();
        }

        historyIndex--;
        const track = trackHistory[historyIndex];
        playTrackData(track);
    } else {
        statusEl.innerText = "No previous track";
        setTimeout(() => {
            if (currentTrackId) {
                const elapsed = Math.floor(audio.currentTime);
                const mins = Math.floor(elapsed / 60);
                const secs = elapsed % 60;
                statusEl.innerText = `${mins}:${secs.toString().padStart(2, '0')}`;
            }
        }, 1500);
    }
}

async function sendFeedback() {
    if (!currentTrackId) return;

    const durationSec = audio.currentTime;

    try {
        await fetch('/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id: currentTrackId,
                duration: durationSec
            })
        });

        // Track feedback for dot colors
        if (durationSec < 5) {
            batchFeedback[currentBatchPosition] = 'negative';
        } else {
            batchFeedback[currentBatchPosition] = 'positive';
        }
        updateBatchIndicator();

    } catch (e) {
        console.error("Feedback error:", e);
    }
}

// Start prompt
titleEl.innerText = "Ready to Vibe?";
statusEl.innerText = "Click Play";
