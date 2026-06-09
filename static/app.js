document.addEventListener('DOMContentLoaded', async () => {
  const processBtn = document.getElementById('processBtn');
  const downloadTwitchBtn = document.getElementById('downloadTwitchBtn');
  const videoInput = document.getElementById('videoInput');
  const twitchUrlInput = document.getElementById('twitchUrlInput');
  const whisperModelSelect = document.getElementById('whisperModelSelect');
  const summaryBackendSelect = document.getElementById('summaryBackendSelect');
  const timestampsCheckbox = document.getElementById('timestampsCheckbox');
  const progressSection = document.getElementById('progressSection');
  const progressBar = document.getElementById('progressBar');
  const progressMessage = document.getElementById('progressMessage');
  const progressLog = document.getElementById('progressLog');
  const resultSection = document.getElementById('resultSection');
  const transcriptText = document.getElementById('transcriptText');
  const srtText = document.getElementById('srtText');
  const srtHeading = document.getElementById('srtHeading');
  const summaryText = document.getElementById('summaryText');
  const summaryHeading = document.getElementById('summaryHeading');
  const downloadBtn = document.getElementById('downloadBtn');

  let pollTimer = null;

  const setBusy = (busy) => {
    processBtn.disabled = busy;
    downloadTwitchBtn.disabled = busy;
  };

  const showProgress = (show) => {
    progressSection.classList.toggle('hidden', !show);
    if (!show && pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  };

  const updateProgress = (data) => {
    progressBar.style.width = `${data.progress}%`;
    progressMessage.textContent = data.message || '…';
    if (data.log_lines?.length) {
      progressLog.textContent = data.log_lines.join('\n');
      progressLog.scrollTop = progressLog.scrollHeight;
    }
  };

  const fillSelect = (select, items, defaultId) => {
    select.innerHTML = '';
    for (const item of items) {
      const opt = document.createElement('option');
      opt.value = item.id;
      opt.textContent = item.label + (item.size_mb ? ` (~${item.size_mb} MB)` : '');
      select.appendChild(opt);
    }
    if (defaultId) select.value = defaultId;
  };

  try {
    const resp = await fetch('/api/options');
    const options = await resp.json();
    fillSelect(whisperModelSelect, options.whisper_models, options.default_whisper);
    fillSelect(summaryBackendSelect, options.summary_backends, options.default_summary);
  } catch (e) {
    console.error(e);
  }

  const getOptions = () => ({
    whisper_model: whisperModelSelect.value,
    summary_backend: summaryBackendSelect.value,
    with_timestamps: timestampsCheckbox.checked,
  });

  const showResult = (data) => {
    resultSection.classList.remove('hidden');
    transcriptText.textContent = data.transcript || '';
    const hasSrt = Boolean(data.transcript_srt);
    srtText.textContent = data.transcript_srt || '';
    srtText.classList.toggle('hidden', !hasSrt);
    srtHeading.classList.toggle('hidden', !hasSrt);

    const hasSummary = Boolean(data.summary);
    summaryText.textContent = data.summary || '';
    summaryText.classList.toggle('hidden', !hasSummary);
    summaryHeading.classList.toggle('hidden', !hasSummary);

    const stem = data.filename.split('.').slice(0, -1).join('.');
    downloadBtn.onclick = () => { window.location.href = `/download/${stem}`; };
  };

  const waitForJob = (jobId) => new Promise((resolve, reject) => {
    showProgress(true);
    resultSection.classList.add('hidden');
    progressBar.style.width = '0%';
    progressLog.textContent = '';

    const poll = async () => {
      try {
        const resp = await fetch(`/api/jobs/${jobId}`);
        if (!resp.ok) throw new Error('Не удалось получить статус');
        const data = await resp.json();
        updateProgress(data);

        if (data.status === 'done') {
          if (pollTimer) clearInterval(pollTimer);
          pollTimer = null;
          showProgress(false);
          resolve(data.result);
        } else if (data.status === 'error') {
          if (pollTimer) clearInterval(pollTimer);
          pollTimer = null;
          showProgress(false);
          reject(new Error(data.error || 'Ошибка обработки'));
        }
      } catch (e) {
        showProgress(false);
        reject(e);
      }
    };

    poll();
    pollTimer = setInterval(poll, 1000);
  });

  const uploadFile = async (file) => {
    const form = new FormData();
    form.append('file', file);
    const opts = getOptions();
    form.append('whisper_model', opts.whisper_model);
    form.append('summary_backend', opts.summary_backend);
    form.append('with_timestamps', opts.with_timestamps);

    setBusy(true);
    try {
      const resp = await fetch('/process', { method: 'POST', body: form });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail);
      }
      const { job_id } = await resp.json();
      showResult(await waitForJob(job_id));
    } catch (e) {
      alert('Ошибка: ' + e.message);
    } finally {
      setBusy(false);
    }
  };

  processBtn.addEventListener('click', () => {
    const files = videoInput?.files;
    if (files?.length) uploadFile(files[0]);
    else alert('Выберите файл');
  });

  downloadTwitchBtn.addEventListener('click', async () => {
    const url = twitchUrlInput.value.trim();
    if (!url) { alert('Введите URL Twitch‑видео'); return; }

    setBusy(true);
    try {
      const resp = await fetch('/twitch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, ...getOptions() }),
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail);
      }
      const { job_id } = await resp.json();
      showResult(await waitForJob(job_id));
    } catch (e) {
      alert('Ошибка: ' + e.message);
    } finally {
      setBusy(false);
    }
  });
});
