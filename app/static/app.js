document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const searchForm = document.getElementById('search-form');
    const videoUrlInput = document.getElementById('video-url');
    const btnPaste = document.getElementById('btn-paste');
    const btnAnalyze = document.getElementById('btn-analyze');
    
    const loadingState = document.getElementById('loading-state');
    const errorBanner = document.getElementById('error-banner');
    const errorMessage = document.getElementById('error-message');
    
    const previewSection = document.getElementById('preview-section');
    const videoThumb = document.getElementById('video-thumb');
    const videoDuration = document.getElementById('video-duration');
    const videoUploader = document.getElementById('video-uploader');
    const videoTitle = document.getElementById('video-title');
    const videoViews = document.getElementById('video-views');
    
    const videoFormatList = document.getElementById('video-format-list');
    const audioFormatList = document.getElementById('audio-format-list');
    const btnDownloadSelected = document.getElementById('btn-download-selected');
    
    const downloadsSection = document.getElementById('downloads-section');
    const dlTitle = document.getElementById('dl-title');
    const dlSpeed = document.getElementById('dl-speed');
    const dlDownloaded = document.getElementById('dl-downloaded');
    const dlEta = document.getElementById('dl-eta');
    const progressFill = document.getElementById('progress-fill');
    const dlPercent = document.getElementById('dl-percent');
    
    const historyList = document.getElementById('history-list');
    const btnOpenFolder = document.getElementById('btn-open-folder');

    let currentVideoData = null;
    let selectedFormat = null;
    let eventSource = null;

    // Clipboard Paste Button
    btnPaste.addEventListener('click', async () => {
        try {
            const text = await navigator.clipboard.readText();
            if (text) {
                videoUrlInput.value = text;
            }
        } catch (err) {
            console.error('Không thể đọc clipboard:', err);
        }
    });

    // Tab Switching Logic
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            
            btn.classList.add('active');
            const tabId = btn.getAttribute('data-tab');
            document.getElementById(tabId).classList.add('active');
        });
    });

    // Search Form Submit
    searchForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const url = videoUrlInput.value.trim();
        if (!url) return;

        showLoading(true);
        hideError();
        hidePreview();

        try {
            const response = await fetch('/api/info', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Không thể lấy thông tin video');
            }

            currentVideoData = await response.json();
            renderVideoPreview(currentVideoData);
        } catch (err) {
            showError(err.message);
        } finally {
            showLoading(false);
        }
    });

    function renderVideoPreview(data) {
        videoThumb.src = data.thumbnail || 'https://via.placeholder.com/640x360?text=No+Thumbnail';
        videoDuration.textContent = data.duration || '00:00';
        videoUploader.innerHTML = `<i class="fa-regular fa-user"></i> ${data.uploader || 'Tác giả'}`;
        videoTitle.textContent = data.title || 'Untitled';
        videoViews.textContent = data.view_count ? data.view_count.toLocaleString('vi-VN') : '0';

        videoFormatList.innerHTML = '';
        audioFormatList.innerHTML = '';

        selectedFormat = null;

        data.formats.forEach((fmt, index) => {
            const item = document.createElement('label');
            item.className = 'format-option';
            
            const isChecked = index === 0;
            if (isChecked) {
                selectedFormat = fmt;
            }

            item.innerHTML = `
                <input type="radio" name="format_choice" class="format-radio" ${isChecked ? 'checked' : ''}>
                <div class="format-info">
                    <div class="res">${fmt.resolution}</div>
                    <div class="ext">${fmt.note}</div>
                </div>
            `;

            item.addEventListener('click', () => {
                document.querySelectorAll('.format-option').forEach(el => el.classList.remove('selected'));
                item.classList.add('selected');
                item.querySelector('input').checked = true;
                selectedFormat = fmt;
            });

            if (isChecked) item.classList.add('selected');

            if (fmt.is_audio) {
                audioFormatList.appendChild(item);
            } else {
                videoFormatList.appendChild(item);
            }
        });

        previewSection.classList.remove('hidden');
    }

    // Handle Start Download Button Click
    btnDownloadSelected.addEventListener('click', async () => {
        if (!currentVideoData || !selectedFormat) return;

        try {
            const response = await fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: currentVideoData.webpage_url,
                    format_id: selectedFormat.format_id,
                    is_audio: selectedFormat.is_audio
                })
            });

            if (!response.ok) {
                throw new Error('Khởi tạo tiến trình tải thất bại');
            }

            const data = await response.json();
            startSSEProgress(data.task_id, currentVideoData.title);
        } catch (err) {
            showError(err.message);
        }
    });

    // Server-Sent Events (SSE) Real-time Progress Tracking
    function startSSEProgress(taskId, title) {
        if (eventSource) {
            eventSource.close();
        }

        downloadsSection.classList.remove('hidden');
        dlTitle.textContent = title;
        progressFill.style.width = '0%';
        dlPercent.textContent = '0%';
        dlSpeed.innerHTML = `<i class="fa-solid fa-gauge-high"></i> Đang chuẩn bị...`;

        eventSource = new EventSource(`/api/progress/${taskId}`);

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.percentage !== undefined) {
                const percent = Math.min(100, Math.max(0, data.percentage));
                progressFill.style.width = `${percent}%`;
                dlPercent.textContent = `${percent.toFixed(1)}%`;
            }

            if (data.speed) {
                dlSpeed.innerHTML = `<i class="fa-solid fa-gauge-high"></i> ${data.speed}`;
            }
            if (data.downloaded_str && data.total_str) {
                dlDownloaded.innerHTML = `<i class="fa-solid fa-hard-drive"></i> ${data.downloaded_str} / ${data.total_str}`;
            }
            if (data.eta) {
                dlEta.innerHTML = `<i class="fa-regular fa-clock"></i> ETA: ${data.eta}`;
            }

            if (data.status === 'finished') {
                eventSource.close();
                dlPercent.textContent = '100% (Hoàn thành)';
                progressFill.style.width = '100%';
                loadHistory();
            } else if (data.status === 'error') {
                eventSource.close();
                showError(`Lỗi khi tải: ${data.error || 'Unknown error'}`);
            }
        };

        eventSource.onerror = (err) => {
            console.error('SSE Error:', err);
            eventSource.close();
        };
    }

    // Load History Files
    async function loadHistory() {
        try {
            const res = await fetch('/api/history');
            if (res.ok) {
                const files = await res.json();
                renderHistory(files);
            }
        } catch (err) {
            console.error('Không thể tải lịch sử file:', err);
        }
    }

    function renderHistory(files) {
        if (!files || files.length === 0) {
            historyList.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-box-open empty-icon"></i>
                    <p>Chưa có file nào được tải về trong thư mục.</p>
                </div>
            `;
            return;
        }

        historyList.innerHTML = '';
        files.forEach(file => {
            const item = document.createElement('div');
            item.className = 'history-item';
            
            const isAudio = file.name.endsWith('.mp3') || file.name.endsWith('.m4a');
            const iconClass = isAudio ? 'fa-solid fa-music' : 'fa-solid fa-film';

            item.innerHTML = `
                <div class="history-file-info">
                    <i class="${iconClass} file-icon"></i>
                    <div>
                        <div class="file-name" title="${file.name}">${file.name}</div>
                        <div class="file-meta">${file.size} • ${file.mtime}</div>
                    </div>
                </div>
                <a href="/api/files/${encodeURIComponent(file.name)}" download class="btn-outline">
                    <i class="fa-solid fa-download"></i> Tải Về Máy
                </a>
            `;
            historyList.appendChild(item);
        });
    }

    // Open Downloads Folder
    btnOpenFolder.addEventListener('click', async () => {
        try {
            await fetch('/api/open-folder', { method: 'POST' });
        } catch (err) {
            console.error('Không thể mở thư mục:', err);
        }
    });

    // Helper functions
    function showLoading(show) {
        if (show) loadingState.classList.remove('hidden');
        else loadingState.classList.add('hidden');
    }

    function showError(msg) {
        errorMessage.textContent = msg;
        errorBanner.classList.remove('hidden');
    }

    function hideError() {
        errorBanner.classList.add('hidden');
    }

    function hidePreview() {
        previewSection.classList.add('hidden');
    }

    // Initial Load
    loadHistory();
});
