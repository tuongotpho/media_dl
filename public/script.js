const DOWNLOAD_URL = "https://github.com/tuongotpho/media_dl/releases/download/v1.0.0/MediaDownloadStudio_v1.0.zip";

document.addEventListener('DOMContentLoaded', () => {
    // Copy STK
    const btnCopyStk = document.getElementById('btn-copy-stk');
    const stkVal = document.getElementById('stk-val');

    if (btnCopyStk && stkVal) {
        btnCopyStk.addEventListener('click', async () => {
            await navigator.clipboard.writeText('938118');
            btnCopyStk.innerHTML = '<i class="fa-solid fa-check"></i> Đã Copy';
            setTimeout(() => {
                btnCopyStk.innerHTML = '<i class="fa-regular fa-copy"></i> Sao chép';
            }, 2000);
        });
    }

    // Modal Control
    const bankModal = document.getElementById('bank-modal');
    const btnCloseModal = document.getElementById('btn-close-modal');
    const modalPlanTitle = document.getElementById('modal-plan-title');
    const modalPriceTag = document.getElementById('modal-price-tag');
    const modalCode = document.getElementById('modal-code');

    document.querySelectorAll('.open-bank-modal').forEach(btn => {
        btn.addEventListener('click', () => {
            const title = btn.getAttribute('data-plan-title');
            const price = btn.getAttribute('data-price');
            const code = btn.getAttribute('data-code');

            if (modalPlanTitle) modalPlanTitle.textContent = title;
            if (modalPriceTag) modalPriceTag.textContent = price;
            if (modalCode) modalCode.textContent = code;

            if (bankModal) bankModal.classList.remove('hidden');
        });
    });

    if (btnCloseModal) {
        btnCloseModal.addEventListener('click', () => {
            if (bankModal) bankModal.classList.add('hidden');
        });
    }

    if (bankModal) {
        bankModal.addEventListener('click', (e) => {
            if (e.target === bankModal) {
                bankModal.classList.add('hidden');
            }
        });
    }

    // FAQ Accordion Toggle
    document.querySelectorAll('.faq-question').forEach(q => {
        q.addEventListener('click', () => {
            const item = q.parentElement;
            const isOpen = item.classList.contains('active');
            document.querySelectorAll('.faq-item').forEach(i => i.classList.remove('active'));
            if (!isOpen) {
                item.classList.add('active');
            }
        });
    });
});
