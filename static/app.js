document.addEventListener('DOMContentLoaded', async () => {
  // Selectors
  const processBtn = document.getElementById('processBtn');
  const downloadTwitchBtn = document.getElementById('downloadTwitchBtn');
  const videoInput = document.getElementById('videoInput');
  const twitchUrlInput = document.getElementById('twitchUrlInput');
  const whisperModelSelect = document.getElementById('whisperModelSelect');
  const summaryBackendSelect = document.getElementById('summaryBackendSelect');
  const timestampsCheckbox = document.getElementById('timestampsCheckbox');
  const clearCacheBtn = document.getElementById('clearCacheBtn');
  
  // Status Badges
  const gpuStatus = document.getElementById('gpuStatus');
  const genapiStatus = document.getElementById('genapiStatus');

  // Input Tabs
  const tabLocalBtn = document.getElementById('tabLocalBtn');
  const tabWebBtn = document.getElementById('tabWebBtn');
  const panelLocal = document.getElementById('panelLocal');
  const panelWeb = document.getElementById('panelWeb');

  // Drag and Drop
  const dropZone = document.getElementById('dropZone');
  const dropZoneText = document.getElementById('dropZoneText');
  const dropZoneFileInfo = document.getElementById('dropZoneFileInfo');

  // Progress Section
  const progressSection = document.getElementById('progressSection');
  const progressBar = document.getElementById('progressBar');
  const progressPctText = document.getElementById('progressPctText');
  const progressMessage = document.getElementById('progressMessage');
  const progressLog = document.getElementById('progressLog');

  // Result Section
  const resultSection = document.getElementById('resultSection');
  const downloadBtn = document.getElementById('downloadBtn');
  
  // Result Tabs
  const resTabSummary = document.getElementById('resTabSummary');
  const resTabTranscript = document.getElementById('resTabTranscript');
  const resTabSrt = document.getElementById('resTabSrt');
  
  // Result Panels
  const resPanelSummary = document.getElementById('resPanelSummary');
  const resPanelTranscript = document.getElementById('resPanelTranscript');
  const resPanelSrt = document.getElementById('resPanelSrt');

  // Result Text Contents
  const summaryText = document.getElementById('summaryText');
  const transcriptText = document.getElementById('transcriptText');
  const srtText = document.getElementById('srtText');

  let pollTimer = null;
  let selectedFile = null;

  // Set buttons disabled state
  const setBusy = (busy) => {
    processBtn.disabled = busy;
    downloadTwitchBtn.disabled = busy;
    clearCacheBtn.disabled = busy;
    if (busy) {
      processBtn.style.opacity = '0.6';
      downloadTwitchBtn.style.opacity = '0.6';
    } else {
      processBtn.style.opacity = '1';
      downloadTwitchBtn.style.opacity = '1';
    }
  };

  // Switch Input Source Tabs
  tabLocalBtn.addEventListener('click', () => {
    tabLocalBtn.classList.add('active');
    tabWebBtn.classList.remove('active');
    panelLocal.classList.remove('hidden');
    panelWeb.classList.add('hidden');
  });

  tabWebBtn.addEventListener('click', () => {
    tabWebBtn.classList.add('active');
    tabLocalBtn.classList.remove('active');
    panelWeb.classList.remove('hidden');
    panelLocal.classList.add('hidden');
  });

  // Switch Result View Tabs
  const switchResultTab = (activeTab, activePanel) => {
    [resTabSummary, resTabTranscript, resTabSrt].forEach(tab => tab.classList.remove('active'));
    [resPanelSummary, resPanelTranscript, resPanelSrt].forEach(panel => panel.classList.add('hidden'));
    
    activeTab.classList.add('active');
    activePanel.classList.remove('hidden');
  };

  resTabSummary.addEventListener('click', () => switchResultTab(resTabSummary, resPanelSummary));
  resTabTranscript.addEventListener('click', () => switchResultTab(resTabTranscript, resPanelTranscript));
  resTabSrt.addEventListener('click', () => switchResultTab(resTabSrt, resPanelSrt));

  // Drag and Drop implementation
  dropZone.addEventListener('click', () => videoInput.click());

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });

  ['dragleave', 'dragend'].forEach(type => {
    dropZone.addEventListener(type, () => {
      dropZone.classList.remove('dragover');
    });
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
      handleFileSelection(e.dataTransfer.files[0]);
    }
  });

  videoInput.addEventListener('change', () => {
    if (videoInput.files.length) {
      handleFileSelection(videoInput.files[0]);
    }
  });

  const handleFileSelection = (file) => {
    selectedFile = file;
    dropZoneText.classList.add('hidden');
    dropZoneFileInfo.classList.remove('hidden');
    
    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    dropZoneFileInfo.textContent = `Выбран файл: ${file.name} (${sizeMb} MB)`;
  };

  // Copy to clipboard buttons
  document.querySelectorAll('.btn-copy').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-target');
      const text = document.getElementById(targetId).textContent;
      if (!text) return;
      
      navigator.clipboard.writeText(text).then(() => {
        const originalText = btn.textContent;
        btn.textContent = 'Скопировано!';
        btn.classList.add('copied');
        setTimeout(() => {
          btn.textContent = originalText;
          btn.classList.remove('copied');
        }, 2000);
      }).catch(err => {
        console.error('Ошибка копирования:', err);
      });
    });
  });

  // Clear cache button action
  clearCacheBtn.addEventListener('click', async () => {
    if (!confirm('Вы действительно хотите очистить кэш скачанных видео, аудио и результатов?')) {
      return;
    }
    setBusy(true);
    try {
      const resp = await fetch('/api/clear-cache', { method: 'POST' });
      if (!resp.ok) throw new Error('Не удалось очистить кэш');
      const data = await resp.json();
      alert(`Кэш очищен! Освобождено: ${data.cleaned_mb} MB`);
    } catch (e) {
      alert('Ошибка при очистке кэша: ' + e.message);
    } finally {
      setBusy(false);
    }
  });

  // Populate drop downs and status badges
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
    
    // Set status badges
    if (options.whisper_gpu) {
      gpuStatus.classList.add('active');
    }
    if (options.genapi_configured) {
      genapiStatus.classList.add('active');
    }
  } catch (e) {
    console.error('Ошибка инициализации параметров:', e);
  }

  const getOptions = () => ({
    whisper_model: whisperModelSelect.value,
    summary_backend: summaryBackendSelect.value,
    with_timestamps: timestampsCheckbox.checked,
  });

  const showProgress = (show) => {
    progressSection.classList.toggle('hidden', !show);
    if (!show && pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  };

  const updateProgress = (data) => {
    progressBar.style.width = `${data.progress}%`;
    progressPctText.textContent = `${data.progress}%`;
    progressMessage.textContent = data.message || '…';
    if (data.log_lines?.length) {
      progressLog.textContent = data.log_lines.join('\n');
      progressLog.scrollTop = progressLog.scrollHeight;
    }
  };

  const showResult = (data) => {
    resultSection.classList.remove('hidden');
    transcriptText.textContent = data.transcript || '';
    
    const hasSrt = Boolean(data.transcript_srt);
    srtText.textContent = data.transcript_srt || '';
    resTabSrt.classList.toggle('hidden', !hasSrt);

    const hasSummary = Boolean(data.summary);
    summaryText.textContent = data.summary || '';
    resTabSummary.classList.toggle('hidden', !hasSummary);

    // Default to summary if available, else transcript
    if (hasSummary) {
      switchResultTab(resTabSummary, resPanelSummary);
    } else {
      switchResultTab(resTabTranscript, resPanelTranscript);
    }

    const stem = data.filename.split('.').slice(0, -1).join('.');
    downloadBtn.onclick = () => { window.location.href = `/download/${stem}`; };
    
    // Scroll to results
    resultSection.scrollIntoView({ behavior: 'smooth' });
  };

  const waitForJob = (jobId) => new Promise((resolve, reject) => {
    showProgress(true);
    resultSection.classList.add('hidden');
    progressBar.style.width = '0%';
    progressPctText.textContent = '0%';
    progressLog.textContent = '';

    const poll = async () => {
      try {
        const resp = await fetch(`/api/jobs/${jobId}`);
        if (!resp.ok) throw new Error('Не удалось получить статус задачи');
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
    pollTimer = setInterval(poll, 1500);
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
        throw new Error(err.detail || 'Не удалось отправить файл');
      }
      const { job_id } = await resp.json();
      showResult(await waitForJob(job_id));
    } catch (e) {
      alert('Ошибка при обработке файла: ' + e.message);
    } finally {
      setBusy(false);
    }
  };

  processBtn.addEventListener('click', () => {
    if (selectedFile) uploadFile(selectedFile);
    else alert('Пожалуйста, выберите или перетащите файл');
  });

  downloadTwitchBtn.addEventListener('click', async () => {
    const url = twitchUrlInput.value.trim();
    if (!url) { alert('Пожалуйста, введите URL-ссылку на видео'); return; }

    setBusy(true);
    try {
      const resp = await fetch('/twitch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, ...getOptions() }),
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || 'Не удалось обработать ссылку');
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
