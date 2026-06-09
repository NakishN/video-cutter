// app.js
document.addEventListener('DOMContentLoaded', () => {
  const processBtn = document.getElementById('processBtn');
  const downloadTwitchBtn = document.getElementById('downloadTwitchBtn');
  const videoInput = document.getElementById('videoInput');
  const twitchUrlInput = document.getElementById('twitchUrlInput');
  const spinner = document.getElementById('spinner');
  const resultSection = document.getElementById('resultSection');
  const summaryText = document.getElementById('summaryText');
  const downloadBtn = document.getElementById('downloadBtn');

  const showSpinner = (show) => {
    spinner.classList.toggle('hidden', !show);
  };

  const showResult = (summary, filename) => {
    summaryText.textContent = summary;
    downloadBtn.onclick = () => {
      window.location.href = `/download/${filename.split('.').slice(0, -1).join('.')}`;
    };
    resultSection.classList.remove('hidden');
  };

  const uploadFile = async (file) => {
    const form = new FormData();
    form.append('file', file);
    showSpinner(true);
    const resp = await fetch('/process', {
      method: 'POST',
      body: form,
    });
    showSpinner(false);
    if (!resp.ok) {
      const err = await resp.json();
      alert('Ошибка: ' + err.detail);
      return;
    }
    const data = await resp.json();
    showResult(data.summary, data.filename);
  };

  processBtn.addEventListener('click', () => {
    const files = videoInput?.files;
    if (files && files.length) {
      uploadFile(files[0]);
    } else {
      alert('Выберите файл к загрузке');
    }
  });

  // Simple Twitch downloader placeholder – expects a server endpoint to handle it later
  downloadTwitchBtn.addEventListener('click', async () => {
    const url = twitchUrlInput.value.trim();
    if (!url) { alert('Введите URL Twitch‑видео'); return; }
    // For demo we just fetch the URL and treat it as a file (needs real implementation)
    alert('Скачивание Twitch‑видео пока не реализовано. Добавьте серверный обработчик.');
  });
});
