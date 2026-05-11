(function () {
  const $ = id => document.getElementById(id);
  const dropzone = $('dropzone');
  const fileInput = $('file-input');
  const browseBtn = $('browse-btn');
  const preview = $('preview');
  const fileName = $('file-name');
  const fileSize = $('file-size');
  const fileIcon = $('file-icon');
  const removeBtn = $('remove-btn');
  const controls = $('controls');
  const generateBtn = $('generate-btn');
  const statusText = $('status-text');
  const progressBar = $('progress-bar');
  const progressFill = $('progress-fill');
  const player = $('player');
  const audioPlayer = $('audio-player');
  const downloadBtn = $('download-btn');
  const voiceSelect = $('voice-select');
  const shareBtn = $('share-btn');

  let currentFile = null;
  let extractedText = '';

  const ICONS = { pdf: '📕', txt: '📄', md: '📝', jpg: '🖼️', jpeg: '🖼️', png: '🖼️', tiff: '🖼️', bmp: '🖼️', webp: '🖼️' };
  const ext = name => name.split('.').pop().toLowerCase();
  const fmt = bytes => bytes < 1024 ? bytes + ' B' : bytes < 1048576 ? (bytes / 1024).toFixed(1) + ' KB' : (bytes / 1048576).toFixed(1) + ' MB';

  // --- Voci ---
  function loadVoices() {
    const v = speechSynthesis.getVoices().filter(v => v.lang.startsWith('it'));
    if (v.length) {
      voiceSelect.innerHTML = '<option value="">Italiano (automatico)</option>';
      v.forEach(v => {
        const o = document.createElement('option');
        o.value = v.name;
        o.textContent = v.name.replace(/^Microsoft /, '').replace(/ - Italian$/, '').replace(/^Google /, '');
        voiceSelect.appendChild(o);
      });
    }
  }
  speechSynthesis.addEventListener('voiceschanged', loadVoices);
  loadVoices();

  // --- File handling ---
  function handleFile(file) {
    const e = ext(file.name);
    if (!['pdf', 'txt', 'md', 'jpg', 'jpeg', 'png', 'tiff', 'bmp', 'webp'].includes(e)) {
      setStatus('❌ Formato non supportato'); return;
    }
    currentFile = file;
    fileIcon.textContent = ICONS[e] || '📄';
    fileName.textContent = file.name;
    fileSize.textContent = fmt(file.size);
    dropzone.classList.add('hidden');
    preview.classList.remove('hidden');
    controls.classList.remove('hidden');
    player.classList.add('hidden');
    generateBtn.disabled = false;
    setStatus('✅ File caricato');
  }

  function resetAll() {
    currentFile = null; extractedText = '';
    window.speechSynthesis && window.speechSynthesis.cancel();
    dropzone.classList.remove('hidden');
    preview.classList.add('hidden');
    controls.classList.add('hidden');
    player.classList.add('hidden');
    progressBar.classList.add('hidden');
    generateBtn.disabled = true;
    fileInput.value = '';
    setStatus('');
  }

  dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('dragover'); });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
  dropzone.addEventListener('drop', e => { e.preventDefault(); dropzone.classList.remove('dragover'); handleFile(e.dataTransfer.files[0]); });
  browseBtn.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => { if (fileInput.files[0]) handleFile(fileInput.files[0]); });
  removeBtn.addEventListener('click', resetAll);

  // --- Extraction ---
  async function extractPDF(file) {
    const buf = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: buf }).promise;
    let text = '';
    for (let i = 1; i <= pdf.numPages; i++) {
      const p = await pdf.getPage(i);
      const c = await p.getTextContent();
      text += c.items.map(it => it.str).join(' ') + '\n';
      progress(10 + (i / pdf.numPages) * 30);
    }
    return text;
  }

  async function OCRImage(file) {
    const img = await createImageBitmap(file);
    setStatus('🧠 OCR in corso (primo avvio scarica modello ~10MB)…');
    const r = await Tesseract.recognize(img, 'ita+eng', {
      logger: m => { if (m.status === 'recognizing text') progress(10 + m.progress * 30); }
    });
    return r.data.text;
  }

  function cleanText(t) {
    return t
      .replace(/\b\d{1,3}\s*\/\s*\d{1,3}\b/g, '')
      .replace(/^pag(?:ina)?\.?\s*\d+\s*$/gmi, '')
      .replace(/^slide\s*\d+\s*$/gmi, '')
      .replace(/^-{3,}\s*$/gm, '').replace(/_{3,}\s*$/gm, '')
      .replace(/^\s*\d+\s*$/gm, '')
      .split('\n').map(l => l.trim()).filter(l => l).join('\n');
  }

  // --- Generate ---
  generateBtn.addEventListener('click', async () => {
    if (!currentFile) return;
    generateBtn.disabled = true;
    generateBtn.textContent = '⏳  Elaborazione…';
    player.classList.add('hidden');

    try {
      const e = ext(currentFile.name);
      setStatus('📖 Estrazione testo…'); progress(10);

      if (e === 'pdf') extractedText = await extractPDF(currentFile);
      else if (['txt', 'md'].includes(e)) extractedText = await currentFile.text();
      else extractedText = await OCRImage(currentFile);

      extractedText = cleanText(extractedText);
      if (!extractedText.trim()) throw new Error('Nessun testo estratto');

      setStatus('✅ ' + extractedText.length + ' caratteri. Riproduzione…');
      progress(70);
      await playTTS(extractedText);
      progress(100);
      setStatus('✅ Fatto — premi Riproduci per riascoltare');
      generateBtn.disabled = false;
      generateBtn.textContent = '🔁  Rielabora';
    } catch (err) {
      setStatus('❌ ' + err.message);
      generateBtn.disabled = false;
      generateBtn.textContent = '🎤  Genera Audio';
    }
  });

  // --- Playback ---
  function playTTS(text) {
    return new Promise((resolve, reject) => {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = 'it-IT'; u.rate = 1.0;
      if (voiceSelect.value) {
        const match = speechSynthesis.getVoices().find(v => v.name === voiceSelect.value);
        if (match) u.voice = match;
      }
      u.onstart = () => { progress(80); player.classList.remove('hidden'); audioPlayer.style.display = 'none'; };
      u.onend = resolve;
      u.onerror = e => reject(new Error(e.error));
      window.speechSynthesis.speak(u);
    });
  }

  // --- Share ---
  shareBtn.addEventListener('click', async () => {
    if (!extractedText) return;
    if (navigator.share) {
      try { await navigator.share({ title: 'Appunti estratti', text: extractedText }); }
      catch { /* user cancelled */ }
    } else {
      // fallback: download text
      const blob = new Blob([extractedText], { type: 'text/plain' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = (currentFile ? currentFile.name.replace(/\.[^.]+$/, '') : 'appunti') + '.txt';
      a.click();
      URL.revokeObjectURL(blob);
    }
  });

  // --- Download ---
  downloadBtn.addEventListener('click', () => {
    if (!extractedText) return;
    const blob = new Blob([extractedText], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = (currentFile ? currentFile.name.replace(/\.[^.]+$/, '') : 'appunti') + '.txt';
    a.click();
    URL.revokeObjectURL(blob);
    setStatus('✅ Testo salvato');
  });

  function setStatus(msg) { statusText.textContent = msg; }

  function progress(pct) {
    progressBar.classList.remove('hidden');
    progressFill.style.width = Math.min(pct, 100) + '%';
    if (pct >= 100) setTimeout(() => progressBar.classList.add('hidden'), 600);
  }

  // --- Service Worker ---
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  }
})();
