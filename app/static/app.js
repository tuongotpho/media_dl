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
    const downloadStatusBadge = document.getElementById('download-status-badge');
    const dlHeaderIcon = document.getElementById('dl-header-icon');
    const dlHeaderTitle = document.getElementById('dl-header-title');
    const dlActionsBar = document.getElementById('dl-actions-bar');
    const btnSaveBrowser = document.getElementById('btn-save-browser');
    const btnOpenFolderSuccess = document.getElementById('btn-open-folder-success');
    
    const historyList = document.getElementById('history-list');
    const btnOpenFolder = document.getElementById('btn-open-folder');
    const idlePlaceholder = document.getElementById('idle-placeholder');

    let currentVideoData = null;
    let selectedFormat = null;
    let eventSource = null;

    function updateIdleState() {
        if (!idlePlaceholder) return;
        const hasActiveState = !loadingState.classList.contains('hidden') ||
                               !previewSection.classList.contains('hidden') ||
                               !downloadsSection.classList.contains('hidden') ||
                               !errorBanner.classList.contains('hidden');
        if (hasActiveState) {
            idlePlaceholder.classList.add('hidden');
        } else {
            idlePlaceholder.classList.remove('hidden');
        }
    }

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

    // Sidebar Tab Switching (Thư Viện / Giới Thiệu)
    document.querySelectorAll('.sidebar-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.sidebar-tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.sidebar-pane').forEach(p => p.classList.remove('active'));
            
            btn.classList.add('active');
            const paneId = btn.getAttribute('data-sidebar-tab');
            document.getElementById(paneId).classList.add('active');
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
        updateIdleState();

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
            updateIdleState();
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
        updateIdleState();
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
        dlActionsBar.classList.add('hidden');
        dlTitle.textContent = title;
        progressFill.style.width = '0%';
        dlPercent.textContent = '0%';
        dlSpeed.innerHTML = `<i class="fa-solid fa-gauge-high"></i> Đang chuẩn bị...`;
        if (downloadStatusBadge) {
            downloadStatusBadge.className = 'badge badge-info';
            downloadStatusBadge.textContent = 'Đang tải...';
        }
        if (dlHeaderIcon) dlHeaderIcon.className = 'fa-solid fa-spinner fa-spin';
        updateIdleState();

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

            if (data.status === 'merging') {
                if (downloadStatusBadge) downloadStatusBadge.textContent = 'Đang ghép file...';
            } else if (data.status === 'finished') {
                eventSource.close();
                dlPercent.textContent = '100% (Hoàn thành)';
                progressFill.style.width = '100%';
                if (downloadStatusBadge) {
                    downloadStatusBadge.className = 'badge badge-success';
                    downloadStatusBadge.textContent = 'Đã hoàn thành';
                }
                if (dlHeaderIcon) dlHeaderIcon.className = 'fa-solid fa-circle-check';

                if (data.filename) {
                    const downloadUrl = `/api/files/${encodeURIComponent(data.filename)}`;
                    btnSaveBrowser.href = downloadUrl;
                    btnSaveBrowser.download = data.filename;
                    
                    // Auto-trigger browser download save dialog
                    const a = document.createElement('a');
                    a.href = downloadUrl;
                    a.download = data.filename;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                }

                dlActionsBar.classList.remove('hidden');
                loadHistory();
            } else if (data.status === 'error') {
                eventSource.close();
                showError(`Lỗi khi tải: ${data.error || 'Unknown error'}`);
                if (downloadStatusBadge) {
                    downloadStatusBadge.className = 'badge badge-danger';
                    downloadStatusBadge.textContent = 'Lỗi';
                }
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
                    <p>Chưa có file nào trong thư mục.</p>
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
                <a href="/api/files/${encodeURIComponent(file.name)}" download class="btn-outline btn-xs">
                    <i class="fa-solid fa-download"></i> Tải Về
                </a>
            `;
            historyList.appendChild(item);
        });
    }

    // Open Downloads Folder
    const handleOpenFolder = async () => {
        try {
            await fetch('/api/open-folder', { method: 'POST' });
        } catch (err) {
            console.error('Không thể mở thư mục:', err);
        }
    };

    btnOpenFolder.addEventListener('click', handleOpenFolder);
    if (btnOpenFolderSuccess) {
        btnOpenFolderSuccess.addEventListener('click', handleOpenFolder);
    }

    // Helper functions
    function showLoading(show) {
        if (show) loadingState.classList.remove('hidden');
        else loadingState.classList.add('hidden');
        updateIdleState();
    }

    function showError(msg) {
        errorMessage.textContent = msg;
        errorBanner.classList.remove('hidden');
        updateIdleState();
    }

    function hideError() {
        errorBanner.classList.add('hidden');
        updateIdleState();
    }

    function hidePreview() {
        previewSection.classList.add('hidden');
        updateIdleState();
    }

    // ================= LICENSE SYSTEM LOGIC =================
    const licenseBadge = document.getElementById('license-badge');
    const licenseBadgeText = document.getElementById('license-badge-text');
    const activationModal = document.getElementById('activation-modal');
    const btnCloseModal = document.getElementById('btn-close-modal');
    const btnOpenLicenseModal = document.getElementById('btn-open-license-modal');
    const modalMachineId = document.getElementById('modal-machine-id');
    const aboutMachineId = document.getElementById('about-machine-id');
    const aboutLicenseStatus = document.getElementById('about-license-status');
    const aboutExpiryRow = document.getElementById('about-expiry-row');
    const aboutLicenseExpiry = document.getElementById('about-license-expiry');
    const bankContent = document.getElementById('bank-content');
    
    const modalStatusBanner = document.getElementById('modal-status-banner');
    const modalStatusTitle = document.getElementById('modal-status-title');
    const modalStatusDesc = document.getElementById('modal-status-desc');
    
    const btnCopyMachineId = document.getElementById('btn-copy-machine-id');
    const btnCopyStk = document.getElementById('btn-copy-stk');
    const btnRequestActivation = document.getElementById('btn-request-activation');
    const requestFeedback = document.getElementById('request-feedback');
    const licenseForm = document.getElementById('license-form');
    const licenseKeyInput = document.getElementById('license-key-input');

    let currentMachineId = '';
    let isLicenseActive = false;

    let selectedPlan = '1year';

    // Plan Selection Logic
    const planCards = document.querySelectorAll('.plan-card');
    const trialActionBox = document.getElementById('trial-action-box');
    const paidPlanSection = document.getElementById('paid-plan-section');
    const activationSteps = document.querySelector('.activation-steps');
    const selectedPlanName = document.getElementById('selected-plan-name');
    const bankAmount = document.getElementById('bank-amount');
    const btnClaimTrial = document.getElementById('btn-claim-trial');

    const planConfig = {
        'trial': { name: 'Dùng Thử (7 Ngày)', price: '0 VNĐ', amountText: '0 VNĐ', suffix: 'TRIAL' },
        '6months': { name: '6 Tháng (19.000đ)', price: '19.000 VNĐ', amountText: '19.000 VNĐ', suffix: '6M' },
        '1year': { name: '1 Năm (29.000đ)', price: '29.000 VNĐ', amountText: '29.000 VNĐ', suffix: '1Y' },
        'lifetime': { name: 'Vĩnh Viễn (99.000đ)', price: '99.000 VNĐ', amountText: '99.000 VNĐ (Trọn Đời)', suffix: 'VIP' },
    };

    planCards.forEach(card => {
        card.addEventListener('click', () => {
            planCards.forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            selectedPlan = card.getAttribute('data-plan');

            const config = planConfig[selectedPlan] || planConfig['1year'];

            if (selectedPlan === 'trial') {
                if (trialActionBox) trialActionBox.classList.remove('hidden');
                if (paidPlanSection) paidPlanSection.classList.add('hidden');
                if (activationSteps) activationSteps.classList.add('hidden');
            } else {
                if (trialActionBox) trialActionBox.classList.add('hidden');
                if (paidPlanSection) paidPlanSection.classList.remove('hidden');
                if (activationSteps) activationSteps.classList.remove('hidden');

                if (selectedPlanName) selectedPlanName.textContent = config.name;
                if (bankAmount) bankAmount.textContent = config.amountText;
                if (bankContent && currentMachineId) {
                    bankContent.innerHTML = `MDS <span class="highlight-val">${currentMachineId}</span> <span class="text-muted">${config.suffix}</span>`;
                }
            }
        });
    });

    // Claim 7-Day Free Trial Button
    if (btnClaimTrial) {
        btnClaimTrial.addEventListener('click', async () => {
            btnClaimTrial.disabled = true;
            btnClaimTrial.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang Kích Hoạt...';

            try {
                const res = await fetch('/api/license/trial', { method: 'POST' });
                const data = await res.json();

                if (res.ok && data.success) {
                    alert('🎁 CHÚC MỪNG!\nKích hoạt dùng thử 7 ngày miễn phí thành công!');
                    closeModal();
                    await checkLicenseStatus();
                } else {
                    alert('❌ ' + (data.detail || 'Không thể kích hoạt dùng thử.'));
                }
            } catch (err) {
                alert('❌ Lỗi kết nối khi đăng ký dùng thử.');
            } finally {
                btnClaimTrial.disabled = false;
                btnClaimTrial.innerHTML = '<i class="fa-solid fa-bolt"></i> Kích Hoạt Dùng Thử 7 Ngày Ngay';
            }
        });
    }

    async function checkLicenseStatus() {
        try {
            const res = await fetch('/api/license');
            if (!res.ok) return;
            const data = await res.json();

            currentMachineId = data.machine_id || '';
            const previouslyActive = isLicenseActive;
            isLicenseActive = !!data.activated;

            // Update Machine ID & Bank Content displays
            if (modalMachineId) modalMachineId.textContent = currentMachineId;
            if (aboutMachineId) aboutMachineId.textContent = currentMachineId;
            
            const currentSuffix = (planConfig[selectedPlan] || planConfig['1year']).suffix;
            if (bankContent) bankContent.innerHTML = `MDS <span class="highlight-val">${currentMachineId}</span> <span class="text-muted">${currentSuffix}</span>`;

            // If just activated via auto-approval!
            if (isLicenseActive && !previouslyActive) {
                if (autoCheckInterval) {
                    clearInterval(autoCheckInterval);
                    autoCheckInterval = null;
                }
                closeModal();
                const timeText = data.is_lifetime ? 'Vĩnh Viễn (Trọn Đời)' : `${data.days_left} ngày`;
                alert(`🎉 CHÚC MỪNG!\nBản quyền Media Download Studio (${data.plan_name}) đã được kích hoạt thành công!\n\nHạn sử dụng: ${timeText}.`);
            }

            // Update UI elements based on activation
            if (isLicenseActive) {
                // Activated UI
                const timeBadgeText = data.is_lifetime ? 'Vĩnh Viễn' : `${data.days_left} ngày`;
                if (licenseBadge) {
                    licenseBadge.className = 'license-badge activated';
                    licenseBadgeText.textContent = `${data.plan_name} (${timeBadgeText})`;
                }

                if (aboutLicenseStatus) {
                    aboutLicenseStatus.className = 'text-success';
                    aboutLicenseStatus.textContent = `${data.plan_name} ✅`;
                }

                if (aboutExpiryRow && data.expiry) {
                    aboutExpiryRow.classList.remove('hidden');
                    if (data.is_lifetime) {
                        aboutLicenseExpiry.textContent = 'Vĩnh Viễn (Trọn Đời)';
                    } else {
                        const d = new Date(data.expiry);
                        aboutLicenseExpiry.textContent = `${d.getDate()}/${d.getMonth()+1}/${d.getFullYear()}`;
                    }
                }

                if (modalStatusBanner) {
                    modalStatusBanner.className = 'status-banner activated';
                    modalStatusTitle.textContent = `Bản quyền đã được kích hoạt (${data.plan_name})!`;
                    modalStatusDesc.textContent = data.is_lifetime 
                        ? 'Sử dụng không giới hạn thời gian. Cảm ơn bạn đã ủng hộ Media Download Studio!' 
                        : `Hạn sử dụng còn ${data.days_left} ngày (Đến ${data.expiry}). Cảm ơn bạn đã ủng hộ!`;
                }
            } else {
                // Unactivated UI
                if (licenseBadge) {
                    licenseBadge.className = 'license-badge unactivated';
                    licenseBadgeText.textContent = 'Chưa Kích Hoạt';
                }

                if (aboutLicenseStatus) {
                    aboutLicenseStatus.className = 'text-danger';
                    aboutLicenseStatus.textContent = 'Chưa Kích Hoạt ❌';
                }

                if (aboutExpiryRow) aboutExpiryRow.classList.add('hidden');

                if (modalStatusBanner) {
                    modalStatusBanner.className = 'status-banner unactivated';
                    modalStatusTitle.textContent = 'Ứng dụng chưa được kích hoạt';
                    modalStatusDesc.textContent = 'Vui lòng chọn gói bản quyền hoặc kích hoạt dùng thử 7 ngày để sử dụng.';
                }
            }
        } catch (err) {
            console.error('Không thể kiểm tra license:', err);
        }
    }

    // Modal Control
    function openModal() {
        if (activationModal) activationModal.classList.remove('hidden');
    }

    function closeModal() {
        if (activationModal) activationModal.classList.add('hidden');
    }

    if (licenseBadge) licenseBadge.addEventListener('click', openModal);
    if (btnOpenLicenseModal) btnOpenLicenseModal.addEventListener('click', openModal);
    if (btnCloseModal) btnCloseModal.addEventListener('click', closeModal);

    if (activationModal) {
        activationModal.addEventListener('click', (e) => {
            if (e.target === activationModal) closeModal();
        });
    }

    // Copy Machine ID
    if (btnCopyMachineId) {
        btnCopyMachineId.addEventListener('click', async () => {
            if (currentMachineId) {
                await navigator.clipboard.writeText(currentMachineId);
                btnCopyMachineId.innerHTML = '<i class="fa-solid fa-check"></i> Đã Copy';
                setTimeout(() => {
                    btnCopyMachineId.innerHTML = '<i class="fa-regular fa-copy"></i> Copy Mã Máy';
                }, 2000);
            }
        });
    }

    // Copy STK
    if (btnCopyStk) {
        btnCopyStk.addEventListener('click', async () => {
            await navigator.clipboard.writeText('938118');
            btnCopyStk.innerHTML = '<i class="fa-solid fa-check"></i>';
            setTimeout(() => {
                btnCopyStk.innerHTML = '<i class="fa-regular fa-copy"></i>';
            }, 2000);
        });
    }

    // Request Activation Button (Send selected plan to Telegram Bot)
    if (btnRequestActivation) {
        btnRequestActivation.addEventListener('click', async () => {
            btnRequestActivation.disabled = true;
            btnRequestActivation.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang Gửi Yêu Cầu...';
            requestFeedback.classList.add('hidden');

            try {
                const res = await fetch('/api/license/request', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ plan: selectedPlan })
                });
                const data = await res.json();

                if (res.ok && data.success) {
                    requestFeedback.className = 'request-feedback-text success';
                    requestFeedback.innerHTML = '✅ <strong>Đã gửi yêu cầu đến Admin Telegram!</strong><br/><i class="fa-solid fa-spinner fa-spin margin-top-sm"></i> <em>Đang chờ Admin bấm "Duyệt"... (Phần mềm sẽ tự động kích hoạt ngay lập tức)</em>';
                    requestFeedback.classList.remove('hidden');

                    // Start auto polling every 2 seconds
                    if (autoCheckInterval) clearInterval(autoCheckInterval);
                    autoCheckInterval = setInterval(checkLicenseStatus, 2000);
                } else {
                    requestFeedback.className = 'request-feedback-text error';
                    requestFeedback.textContent = data.detail || 'Không thể gửi yêu cầu.';
                    requestFeedback.classList.remove('hidden');
                }
            } catch (err) {
                requestFeedback.className = 'request-feedback-text error';
                requestFeedback.textContent = 'Lỗi kết nối server.';
                requestFeedback.classList.remove('hidden');
            } finally {
                btnRequestActivation.disabled = false;
                btnRequestActivation.innerHTML = '<i class="fa-paper-plane"></i> Gửi Yêu Cầu Kích Hoạt Tự Động Đến Admin';
            }
        });
    }

    // License Form Submit (Manual Key Entry)
    if (licenseForm) {
        licenseForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const key = licenseKeyInput.value.trim();
            if (!key) return;

            const btnSubmit = document.getElementById('btn-submit-key');
            if (btnSubmit) {
                btnSubmit.disabled = true;
                btnSubmit.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
            }

            try {
                const res = await fetch('/api/license/activate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key })
                });
                const data = await res.json();

                if (res.ok && data.success) {
                    alert('🎉 Kích hoạt bản quyền thành công!');
                    licenseKeyInput.value = '';
                    closeModal();
                    await checkLicenseStatus();
                } else {
                    alert('❌ Lỗi: ' + (data.detail || 'License Key không hợp lệ.'));
                }
            } catch (err) {
                alert('❌ Lỗi kết nối khi kích hoạt.');
            } finally {
                if (btnSubmit) {
                    btnSubmit.disabled = false;
                    btnSubmit.innerHTML = '<i class="fa-solid fa-circle-check"></i> Kích Hoạt';
                }
            }
        });
    }

    // Reset License Button (For Testing)
    const btnResetLicense = document.getElementById('btn-reset-license');
    if (btnResetLicense) {
        btnResetLicense.addEventListener('click', async () => {
            if (confirm('Bạn có chắc muốn xóa license hiện tại để test lại không?')) {
                try {
                    await fetch('/api/license/reset', { method: 'POST' });
                    alert('🔄 Đã xóa license! Ứng dụng đã chuyển về trạng thái Chưa Kích Hoạt.');
                    await checkLicenseStatus();
                } catch (err) {
                    alert('Lỗi kết nối khi reset.');
                }
            }
        });
    }

    // Initial Load & Auto Poll
    checkLicenseStatus();
    autoCheckInterval = setInterval(checkLicenseStatus, 3000);

    loadHistory();
    updateIdleState();
});
