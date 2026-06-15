const initApp = async () => {
  // Selectors
  const processBtn = document.getElementById('processBtn');
  const downloadTwitchBtn = document.getElementById('downloadTwitchBtn');
  const videoInput = document.getElementById('videoInput');
  const twitchUrlInput = document.getElementById('twitchUrlInput');
  const downloadModeSelect = document.getElementById('downloadModeSelect');
  const whisperModelSelect = document.getElementById('whisperModelSelect');
  const summaryBackendSelect = document.getElementById('summaryBackendSelect');
  const layoutSelect = document.getElementById('layoutSelect');
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
  const resTabClips = document.getElementById('resTabClips');
  const resTabSummary = document.getElementById('resTabSummary');
  const resTabTranscript = document.getElementById('resTabTranscript');
  const resTabSrt = document.getElementById('resTabSrt');
  
  // Result Panels
  const resPanelClips = document.getElementById('resPanelClips');
  const resPanelSummary = document.getElementById('resPanelSummary');
  const resPanelTranscript = document.getElementById('resPanelTranscript');
  const resPanelSrt = document.getElementById('resPanelSrt');

  // Clips specific selectors
  const clipsGrid = document.getElementById('clipsGrid');
  const manualStartInput = document.getElementById('manualStartInput');
  const manualEndInput = document.getElementById('manualEndInput');
  const manualTitleInput = document.getElementById('manualTitleInput');
  const manualCutBtn = document.getElementById('manualCutBtn');

  // Result Text Contents
  const summaryText = document.getElementById('summaryText');
  const transcriptText = document.getElementById('transcriptText');
  const srtText = document.getElementById('srtText');

  let pollTimer = null;
  let selectedFile = null;
  let currentVideoName = null;

  // Set buttons disabled state
  const setBusy = (busy) => {
    if (processBtn) {
      processBtn.disabled = busy;
      processBtn.style.opacity = busy ? '0.6' : '1';
    }
    if (downloadTwitchBtn) {
      downloadTwitchBtn.disabled = busy;
      downloadTwitchBtn.style.opacity = busy ? '0.6' : '1';
    }
    if (clearCacheBtn) {
      clearCacheBtn.disabled = busy;
    }
  };

  // Switch Input Source Tabs
  if (tabLocalBtn) {
    tabLocalBtn.addEventListener('click', () => {
      tabLocalBtn.classList.add('active');
      if (tabWebBtn) tabWebBtn.classList.remove('active');
      if (panelLocal) panelLocal.classList.remove('hidden');
      if (panelWeb) panelWeb.classList.add('hidden');
    });
  }

  if (tabWebBtn) {
    tabWebBtn.addEventListener('click', () => {
      tabWebBtn.classList.add('active');
      if (tabLocalBtn) tabLocalBtn.classList.remove('active');
      if (panelWeb) panelWeb.classList.remove('hidden');
      if (panelLocal) panelLocal.classList.add('hidden');
    });
  }

  // Switch Result View Tabs
  const switchResultTab = (activeTab, activePanel) => {
    [resTabClips, resTabSummary, resTabTranscript, resTabSrt].forEach(tab => {
      if (tab) tab.classList.remove('active');
    });
    [resPanelClips, resPanelSummary, resPanelTranscript, resPanelSrt].forEach(panel => {
      if (panel) panel.classList.add('hidden');
    });
    
    if (activeTab) activeTab.classList.add('active');
    if (activePanel) activePanel.classList.remove('hidden');
  };

  if (resTabClips) resTabClips.addEventListener('click', () => switchResultTab(resTabClips, resPanelClips));
  if (resTabSummary) resTabSummary.addEventListener('click', () => switchResultTab(resTabSummary, resPanelSummary));
  if (resTabTranscript) resTabTranscript.addEventListener('click', () => switchResultTab(resTabTranscript, resPanelTranscript));
  if (resTabSrt) resTabSrt.addEventListener('click', () => switchResultTab(resTabSrt, resPanelSrt));

  // Drag and Drop implementation
  if (dropZone) {
    dropZone.addEventListener('click', () => videoInput && videoInput.click());

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
  }

  if (videoInput) {
    videoInput.addEventListener('change', () => {
      if (videoInput.files.length) {
        handleFileSelection(videoInput.files[0]);
      }
    });
  }

  const handleFileSelection = (file) => {
    selectedFile = file;
    if (dropZoneText) dropZoneText.classList.add('hidden');
    if (dropZoneFileInfo) {
      dropZoneFileInfo.classList.remove('hidden');
      const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
      dropZoneFileInfo.textContent = `Выбран файл: ${file.name} (${sizeMb} MB)`;
    }
  };

  // Copy to clipboard buttons
  document.querySelectorAll('.btn-copy').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-target');
      const targetEl = document.getElementById(targetId);
      if (!targetEl) return;
      const text = targetEl.textContent;
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
  if (clearCacheBtn) {
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
  }

  // Populate drop downs and status badges
  const fillSelect = (select, items, defaultId) => {
    if (!select) return;
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
    if (options.whisper_gpu && gpuStatus) {
      gpuStatus.classList.add('active');
    }
    if (options.genapi_configured && genapiStatus) {
      genapiStatus.classList.add('active');
    }
  } catch (e) {
    console.error('Ошибка инициализации параметров:', e);
  }

  const getOptions = () => ({
    whisper_model: whisperModelSelect ? whisperModelSelect.value : null,
    summary_backend: summaryBackendSelect ? summaryBackendSelect.value : null,
    with_timestamps: timestampsCheckbox ? timestampsCheckbox.checked : true,
    layout: layoutSelect ? layoutSelect.value : 'vertical_reels',
  });

  const showProgress = (show) => {
    if (progressSection) progressSection.classList.toggle('hidden', !show);
    if (!show && pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  };

  const updateProgress = (data) => {
    if (progressBar) progressBar.style.width = `${data.progress}%`;
    if (progressPctText) progressPctText.textContent = `${data.progress}%`;
    if (progressMessage) progressMessage.textContent = data.message || '…';
    if (data.log_lines?.length && progressLog) {
      progressLog.textContent = data.log_lines.join('\n');
      progressLog.scrollTop = progressLog.scrollHeight;
    }
  };

  const showResult = (data) => {
    if (resultSection) resultSection.classList.remove('hidden');
    currentVideoName = data.filename;
    if (transcriptText) transcriptText.textContent = data.transcript || '';
    
    const hasSrt = Boolean(data.transcript_srt);
    if (srtText) srtText.textContent = data.transcript_srt || '';
    if (resTabSrt) resTabSrt.classList.toggle('hidden', !hasSrt);

    const hasSummary = Boolean(data.summary);
    if (summaryText) summaryText.textContent = data.summary || '';
    if (resTabSummary) resTabSummary.classList.toggle('hidden', !hasSummary);

    const opts = getOptions();
    const isVertical = opts.layout && opts.layout.startsWith('vertical_');
    if (isVertical && clipsGrid) {
      clipsGrid.classList.add('vertical-layout');
    } else if (clipsGrid) {
      clipsGrid.classList.remove('vertical-layout');
    }

    // Populate Clips Grid
    if (clipsGrid) {
      clipsGrid.innerHTML = '';
      if (data.clips && data.clips.length > 0) {
        if (resTabClips) resTabClips.classList.remove('hidden');
        data.clips.forEach(clip => {
          const card = document.createElement('div');
          card.className = 'clip-card';
          card.innerHTML = `
            <div class="clip-video-wrapper">
              <video class="clip-video" src="/output/${clip.filename}" controls preload="metadata"></video>
            </div>
            <div class="clip-info">
              <div class="clip-header">
                <span class="clip-title">${clip.title || 'Без названия'}</span>
                ${clip.score ? `<span class="clip-score">★ ${clip.score}</span>` : ''}
              </div>
              <span class="clip-time">⏱ ${clip.start_str} - ${clip.end_str}</span>
              <p class="clip-desc">${clip.description || ''}</p>
              <div class="clip-actions">
                <a href="/output/${clip.filename}" download class="btn btn-primary" style="flex: 1; text-decoration: none; text-align: center;">
                  📥 Скачать
                </a>
              </div>
            </div>
          `;
          clipsGrid.appendChild(card);
        });
        switchResultTab(resTabClips, resPanelClips);
      } else {
        clipsGrid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 2rem;">Автоматические клипы не найдены. Вы можете вырезать клип вручную ниже!</div>`;
        if (hasSummary) {
          switchResultTab(resTabSummary, resPanelSummary);
        } else {
          switchResultTab(resTabTranscript, resPanelTranscript);
        }
      }
    }

    if (downloadBtn) {
      const stem = data.filename.split('.').slice(0, -1).join('.');
      downloadBtn.onclick = () => { window.location.href = `/download/${stem}`; };
    }
    
    // Scroll to results
    if (resultSection) {
      resultSection.scrollIntoView({ behavior: 'smooth' });
    }
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

  const uploadFile = (file) => {
    return new Promise((resolve, reject) => {
      const form = new FormData();
      form.append('file', file);
      const opts = getOptions();
      form.append('whisper_model', opts.whisper_model);
      form.append('summary_backend', opts.summary_backend);
      form.append('with_timestamps', opts.with_timestamps);
      form.append('layout', opts.layout);

      setBusy(true);
      showProgress(true);
      resultSection.classList.add('hidden');
      progressBar.style.width = '0%';
      progressPctText.textContent = '0%';
      progressMessage.textContent = 'Подготовка к загрузке...';
      progressLog.textContent = 'Запуск загрузки файла...';

      const xhr = new XMLHttpRequest();
      
      // Отслеживание прогресса загрузки
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percentComplete = Math.round((event.loaded / event.total) * 100);
          progressBar.style.width = `${percentComplete}%`;
          progressPctText.textContent = `${percentComplete}%`;
          progressMessage.textContent = `Загрузка файла на сервер: ${percentComplete}%`;
          progressLog.textContent = `Отправлено: ${(event.loaded / (1024 * 1024)).toFixed(1)} MB из ${(event.total / (1024 * 1024)).toFixed(1)} MB...`;
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText);
            resolve(data.job_id);
          } catch (err) {
            reject(new Error('Не удалось прочитать ответ сервера'));
          }
        } else {
          let errMsg = 'Не удалось отправить файл';
          try {
            const errJson = JSON.parse(xhr.responseText);
            errMsg = errJson.detail || errMsg;
          } catch (e) {}
          reject(new Error(errMsg));
        }
      };

      xhr.onerror = () => {
        reject(new Error('Ошибка сети при загрузке файла'));
      };

      xhr.open('POST', '/process');
      xhr.send(form);
    });
  };

  if (processBtn) {
    processBtn.addEventListener('click', async () => {
      if (!selectedFile) {
        alert('Пожалуйста, выберите или перетащите файл');
        return;
      }
      try {
        const jobId = await uploadFile(selectedFile);
        showResult(await waitForJob(jobId));
      } catch (e) {
        alert('Ошибка при обработке файла: ' + e.message);
        showProgress(false);
      } finally {
        setBusy(false);
      }
    });
  }

  if (downloadTwitchBtn) {
    downloadTwitchBtn.addEventListener('click', async () => {
      const url = twitchUrlInput.value.trim();
      if (!url) { alert('Пожалуйста, введите URL-ссылку на видео'); return; }

      setBusy(true);
      try {
        const resp = await fetch('/twitch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url, download_mode: downloadModeSelect.value, ...getOptions() }),
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
  }

  if (manualCutBtn) {
    manualCutBtn.addEventListener('click', async () => {
      if (!currentVideoName) {
        alert('Сначала обработайте видеофайл!');
        return;
      }
      const start = manualStartInput.value.trim();
      const end = manualEndInput.value.trim();
      const title = manualTitleInput.value.trim();
      
      if (!start || !end) {
        alert('Пожалуйста, укажите время начала и окончания клипа!');
        return;
      }
      
      manualCutBtn.disabled = true;
      manualCutBtn.textContent = '✂️ Нарезка...';
      
      try {
        const opts = getOptions();
        const resp = await fetch('/api/cut-manual', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            video_name: currentVideoName,
            start_str: start,
            end_str: end,
            title: title,
            layout: opts.layout,
            with_timestamps: opts.with_timestamps
          })
        });
        
        if (!resp.ok) {
          const err = await resp.json();
          throw new Error(err.detail || 'Не удалось вырезать клип');
        }
        
        const { clip } = await resp.json();
        
        // Добавляем новый клип в начало сетки
        const emptyMsg = clipsGrid.querySelector('div[style*="text-align: center"]');
        if (emptyMsg) emptyMsg.remove();
        
        const card = document.createElement('div');
        card.className = 'clip-card';
        card.innerHTML = `
          <div class="clip-video-wrapper">
            <video class="clip-video" src="/output/${clip.filename}" controls autoplay preload="metadata"></video>
          </div>
          <div class="clip-info">
            <div class="clip-header">
              <span class="clip-title">${clip.title}</span>
              <span class="clip-score" style="background: rgba(99, 102, 241, 0.1); color: var(--primary); border-color: rgba(99, 102, 241, 0.2)">Ручной</span>
            </div>
            <span class="clip-time">⏱ ${clip.start_str} - ${clip.end_str}</span>
            <p class="clip-desc">${clip.description}</p>
            <div class="clip-actions">
              <a href="/output/${clip.filename}" download class="btn btn-primary" style="flex: 1; text-decoration: none; text-align: center;">
                📥 Скачать
              </a>
            </div>
          </div>
        `;
        clipsGrid.insertBefore(card, clipsGrid.firstChild);
        
        // Сбросить поля
        manualStartInput.value = '';
        manualEndInput.value = '';
        manualTitleInput.value = '';
        
        alert('Новый клип успешно нарезан!');
      } catch (e) {
        alert('Ошибка при нарезке клипа: ' + e.message);
      } finally {
        manualCutBtn.disabled = false;
        manualCutBtn.textContent = '✂️ Вырезать клип';
      }
    });
  }
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}
