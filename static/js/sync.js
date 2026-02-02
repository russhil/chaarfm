const SyncManager = {
    isSyncing: false,

    async startSync() {
        if (this.isSyncing) return;
        this.isSyncing = true;

        try {
            updateSyncUI("Checking library...", 0);

            // 1. Get Server List
            const res = await fetch('/api/library');
            const serverFiles = await res.json();

            // 2. Get Local List
            const localKeys = await LocalMusic.getAllKeys();
            const localSet = new Set(localKeys);

            // 3. Diff
            const toDownload = serverFiles.filter(f => !localSet.has(f.filename));

            if (toDownload.length === 0) {
                updateSyncUI("Library Up to Date", 100);
                setTimeout(() => hideSyncUI(), 2000);
                this.isSyncing = false;
                return;
            }

            // 4. Download Loop
            let completed = 0;
            const total = toDownload.length;

            for (const file of toDownload) {
                if (!this.isSyncing) break; // Check for cancel

                updateSyncUI(`Downloading ${completed + 1}/${total}`, (completed / total) * 100);

                try {
                    const url = `/stream/${encodeURIComponent(file.filename)}`;
                    const trackRes = await fetch(url);
                    if (!trackRes.ok) throw new Error("Fetch failed");

                    const blob = await trackRes.blob();
                    await LocalMusic.saveTrack(file.filename, blob);

                    console.log(`Saved ${file.filename}`);
                    completed++;
                } catch (e) {
                    console.error(`Failed to download ${file.filename}`, e);
                }
            }

            updateSyncUI("Sync Complete", 100);
            setTimeout(() => hideSyncUI(), 3000);

        } catch (e) {
            console.error("Sync Error:", e);
            updateSyncUI("Sync Error", 0);
        } finally {
            this.isSyncing = false;
        }
    }
};

// UI Helpers (Assuming elements exist in index.html)
function updateSyncUI(text, percent) {
    const status = document.getElementById('sync-status');
    const bar = document.getElementById('sync-progress-fill');
    const container = document.getElementById('sync-container');

    if (container) container.style.display = 'block';
    if (status) status.innerText = text;
    if (bar) bar.style.width = percent + '%';
}

function hideSyncUI() {
    const container = document.getElementById('sync-container');
    if (container) container.style.display = 'none';
}
