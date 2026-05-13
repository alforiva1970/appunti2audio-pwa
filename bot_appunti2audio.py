#!/usr/bin/env python3
import os, re, sys, json, tempfile, asyncio, logging, subprocess
from pathlib import Path
from datetime import datetime

import httpx
import edge_tts
import fitz
from PIL import Image
import pytesseract
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

MAX_SIZE = 50 * 1024 * 1024
DATA_FILE = Path(__file__).parent / "bot_data.json"

LANGUAGES = {
    "it": {
        "name": "Italiano",
        "ocr": "ita+eng",
        "flag": "🇮🇹",
        "msg_hello": "Ciao! Mandami un file e lo trasformo in audio.",
        "msg_supported": "Supporto: PDF, TXT, MD, JPG, PNG",
        "msg_lang_set": "Lingua impostata su Italiano",
        "msg_unsupported": "Formato non supportato. Uso: PDF, TXT, MD, JPG, PNG",
        "msg_too_big": "File troppo grande (max 50MB).",
        "msg_received": "📥 Ricevuto, elaboro…",
        "msg_extracting": "📖 Estraggo testo…",
        "msg_ocr": "🧠 OCR in corso…",
        "msg_no_text": "❌ Nessun testo trovato nel file.",
        "msg_generating": "Genero audio…",
        "msg_sending": "📤 Invio audio…",
        "msg_error": "❌ Errore",
        "msg_help": "Manda un file (PDF, TXT, MD, JPG/PNG) o scrivi un testo.\nRiceverai indietro un audio parlato.\n\n/lang — cambia lingua\n/start — riavvia\n/help — questo messaggio"
    },
    "es": {
        "name": "Español",
        "ocr": "spa+eng",
        "flag": "🇪🇸",
        "msg_hello": "¡Hola! Envíame un archivo y lo convertiré en audio.",
        "msg_supported": "Soporte: PDF, TXT, MD, JPG, PNG",
        "msg_lang_set": "Idioma cambiado a Español",
        "msg_unsupported": "Formato no soportado. Uso: PDF, TXT, MD, JPG, PNG",
        "msg_too_big": "Archivo demasiado grande (máx 50MB).",
        "msg_received": "📥 Recibido, procesando…",
        "msg_extracting": "📖 Extrayendo texto…",
        "msg_ocr": "🧠 OCR en curso…",
        "msg_no_text": "❌ No se encontró texto en el archivo.",
        "msg_generating": "Generando audio…",
        "msg_sending": "📤 Enviando audio…",
        "msg_error": "❌ Error",
        "msg_help": "Envía un archivo (PDF, TXT, MD, JPG/PNG) o escribe un texto.\nRecibirás un audio.\n\n/lang — cambiar idioma\n/start — reiniciar\n/help — este mensaje"
    },
    "en": {
        "name": "English",
        "ocr": "eng",
        "flag": "🇬🇧",
        "msg_hello": "Hi! Send me a file and I'll turn it into audio.",
        "msg_supported": "Supported: PDF, TXT, MD, JPG, PNG",
        "msg_lang_set": "Language set to English",
        "msg_unsupported": "Format not supported. Use: PDF, TXT, MD, JPG, PNG",
        "msg_too_big": "File too large (max 50MB).",
        "msg_received": "📥 Received, processing…",
        "msg_extracting": "📖 Extracting text…",
        "msg_ocr": "🧠 OCR in progress…",
        "msg_no_text": "❌ No text found in file.",
        "msg_generating": "Generating audio…",
        "msg_sending": "📤 Sending audio…",
        "msg_error": "❌ Error",
        "msg_help": "Send a file (PDF, TXT, MD, JPG/PNG) or write text.\nYou'll receive audio back.\n\n/lang — change language\n/start — restart\n/help — this message"
    }
}

DIRTY = {
    "it": [
        (r'(?i)\bpag(?:ina)?\.?\s*\d+\s*/\s*\d+\b', ''),
        (r'(?i)\bpag(?:ina)?\.?\s*\d+\b', ''),
        (r'(?i)\bslide\s*\d+\b', ''),
        (r'^\s*[-•▪▸→➢‣⁃*]+\s*', ''),
        (r'[-]{2,}', ' '),
        (r'_{2,}', ' '),
        (r'[*]{2,}', ' '),
        (r'^\s*\d+\s*$', ''),
        (r'[/]', ' '),
        (r'_', ' '),
        (r'\s{2,}', ' '),
    ],
    "es": [
        (r'(?i)\bp[áa]g(?:ina)?\.?\s*\d+\s*/\s*\d+\b', ''),
        (r'(?i)\bp[áa]g(?:ina)?\.?\s*\d+\b', ''),
        (r'(?i)\bslide\s*\d+\b', ''),
        (r'^\s*[-•▪▸→➢‣⁃*]+\s*', ''),
        (r'[-]{2,}', ' '),
        (r'_{2,}', ' '),
        (r'[*]{2,}', ' '),
        (r'^\s*\d+\s*$', ''),
        (r'[/]', ' '),
        (r'_', ' '),
        (r'\s{2,}', ' '),
    ],
    "en": [
        (r'(?i)\bpage?\s*\d+\s*/\s*\d+\b', ''),
        (r'(?i)\bpage?\s*\d+\b', ''),
        (r'(?i)\bslide\s*\d+\b', ''),
        (r'^\s*[-•▪▸→➢‣⁃*]+\s*', ''),
        (r'[-]{2,}', ' '),
        (r'_{2,}', ' '),
        (r'[*]{2,}', ' '),
        (r'^\s*\d+\s*$', ''),
        (r'[/]', ' '),
        (r'_', ' '),
        (r'\s{2,}', ' '),
    ],
}

# --- Data persistence ---
def load_data():
    if DATA_FILE.exists():
        try: return json.loads(DATA_FILE.read_text())
        except: pass
    return {}

def save_data(data):
    DATA_FILE.write_text(json.dumps(data, indent=2))

def get_user_lang(user_id):
    return load_data().get(str(user_id), "it")

def set_user_lang(user_id, lang):
    data = load_data()
    data[str(user_id)] = lang
    save_data(data)

# --- Text cleaning ---
def clean(text: str, lang: str) -> str:
    patterns = DIRTY.get(lang, DIRTY["it"])
    for pat, repl in patterns:
        text = re.sub(pat, repl, text, flags=re.MULTILINE)
    lines = []
    for l in text.split('\n'):
        l = l.strip().strip('|:;- ').strip()
        if l:
            l = re.sub(r'[*_|▶▪▸➢‣⁃•·]', ' ', l)
            l = re.sub(r'[\U0001F300-\U0001F9FF]', ' ', l)
            l = re.sub(r'\s{2,}', ' ', l).strip()
            if l: lines.append(l)
    return '\n'.join(lines)

# --- Bot handlers ---
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_user_lang(uid)
    L = LANGUAGES[lang]
    await update.message.reply_text(f"{L['flag']} {L['msg_hello']}\n\n{L['msg_supported']}\n\n/help — aiuto\n/lang — {LANGUAGES['en']['msg_help'] if lang != 'en' else 'cambia lingua'}")

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_user_lang(uid)
    L = LANGUAGES[lang]
    await update.message.reply_text(L["msg_help"])

async def lang_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("🇮🇹 Italiano", callback_data="lang_it"),
        InlineKeyboardButton("🇪🇸 Español", callback_data="lang_es"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
    ]]
    await update.message.reply_text("Scegli la lingua / Choose language / Elige idioma:", reply_markup=InlineKeyboardMarkup(keyboard))

async def lang_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    code = query.data.split("_")[1]
    uid = update.effective_user.id
    set_user_lang(uid, code)
    L = LANGUAGES[code]
    await query.edit_message_text(f"{L['flag']} {L['msg_lang_set']}")

async def handle_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    uid = update.effective_user.id
    lang = get_user_lang(uid)
    L = LANGUAGES[lang]
    file = None; ext = ""

    if msg.document:
        file = msg.document
        ext = Path(file.file_name).suffix.lower()
    elif msg.photo:
        file = msg.photo[-1]
        ext = ".jpg"
    else:
        return

    if ext not in ('.pdf', '.txt', '.md', '.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.webp'):
        await msg.reply_text(L["msg_unsupported"]); return

    if file.file_size and file.file_size > MAX_SIZE:
        await msg.reply_text(L["msg_too_big"]); return

    status = await msg.reply_text(L["msg_received"])

    try:
        tg_file = await file.get_file()
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path = tmp.name
            await tg_file.download_to_drive(tmp_path)

        await status.edit_text(L["msg_extracting"])

        if ext == '.pdf':
            doc = fitz.open(tmp_path); text = ""
            for i, page in enumerate(doc):
                page_text = page.get_text().strip()
                if len(page_text) < 50:
                    pix = page.get_pixmap(dpi=200)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    page_text = pytesseract.image_to_string(img, lang=L["ocr"])
                text += page_text + "\n"
        elif ext in ('.txt', '.md'):
            with open(tmp_path, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
        else:
            await status.edit_text(L["msg_ocr"])
            text = pytesseract.image_to_string(Image.open(tmp_path), lang=L["ocr"])

        os.unlink(tmp_path)
        text = clean(text, lang)
        if not text.strip():
            await status.edit_text(L["msg_no_text"]); return

        await status.edit_text(f"✅ ({len(text)} car.). {L['msg_generating']}")

        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', Path(getattr(file, 'file_name', 'foto')).stem)[:20]
        audio_path = os.path.join(tempfile.gettempdir(), f"{safe_name}_{int(datetime.now().timestamp())}.mp3")
        await tts_engine(text, lang, audio_path)

        await status.edit_text(L["msg_sending"])
        with open(audio_path, 'rb') as f:
            await msg.reply_audio(f, title=f"Audio: {safe_name}", performer="Appunti2Audio")
        os.unlink(audio_path)
        await status.delete()

    except Exception as e:
        log.exception("Errore")
        await status.edit_text(f"{L['msg_error']}: {str(e)[:200]}")

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text or text.startswith('/'): return
    uid = update.effective_user.id
    lang = get_user_lang(uid)
    L = LANGUAGES[lang]
    text = clean(text, lang)
    if not text.strip(): return

    status = await update.message.reply_text(L["msg_generating"])
    try:
        safe = re.sub(r'[^a-zA-Z0-9]', '_', text[:20])
        audio_path = os.path.join(tempfile.gettempdir(), f"testo_{safe}_{int(datetime.now().timestamp())}.mp3")
        await tts_engine(text, lang, audio_path)

        await status.edit_text(L["msg_sending"])
        with open(audio_path, 'rb') as f:
            await update.message.reply_audio(f, title="Testo", performer="Appunti2Audio")
        os.unlink(audio_path)
        await status.delete()
    except Exception as e:
        log.exception("Errore")
        await status.edit_text(f"{L['msg_error']}: {str(e)[:200]}")

def text_to_ssml(text: str) -> str:
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    parts = []
    for para in paragraphs:
        sentences = re.split(r'(?<=[.!?])\s+', para)
        spoken = ' '.join(sentences)
        if spoken:
            parts.append(f'<p><prosody rate="medium" pitch="0%">{spoken}</prosody></p>')
    return '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="it-IT">' + '\n'.join(parts) + '</speak>'

# --- TTS backends ---
PIPER_BIN = os.environ.get("PIPER_BIN") or "/home/guardiano/Documenti/GitHub/nova-identity/daemon/voice/bin/piper"
PIPER_MODEL = os.environ.get("PIPER_MODEL") or "/home/guardiano/Documenti/GitHub/nova-identity/daemon/voice/models/it_IT-paola-medium.onnx"
PIPER_LENGTH_SCALE = os.environ.get("PIPER_LENGTH_SCALE") or "1.5"  # >1 = slower

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
EDGE_VOICES = {
    "it": "it-IT-ElsaNeural",
    "es": "es-ES-ElviraNeural",
    "en": "en-US-JennyNeural",
}

WAV_DIR = Path(__file__).parent / "wav"
WAV_DIR.mkdir(exist_ok=True)

def tts_piper(text: str, audio_path: str):
    flat = ' '.join(text.split())
    cmd = f'{PIPER_BIN} --model {PIPER_MODEL} --length_scale {PIPER_LENGTH_SCALE} --sentence_silence 0.05 --output_file {audio_path}'
    proc = subprocess.run(cmd, input=flat, shell=True, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"Piper error: {proc.stderr[:200]}")

async def tts_engine(text: str, lang: str, audio_path: str):
    text = text[:3000]
    if os.path.exists(PIPER_BIN):
        log.info("Usando Piper TTS (locale)")
        audio_path_wav = audio_path.replace('.mp3', '.wav')
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, tts_piper, text, audio_path_wav)
        # convert to mp3 for smaller size (ffmpeg needed) or keep wav
        try:
            import subprocess as sp
            subprocess.run(['ffmpeg', '-y', '-i', audio_path_wav, '-b:a', '32k', audio_path],
                         capture_output=True, timeout=30)
            os.unlink(audio_path_wav)
        except:
            # fallback: rename wav to mp3 (Telegram accepts wav too)
            import shutil
            shutil.move(audio_path_wav, audio_path)
    elif GOOGLE_API_KEY:
        log.info("Usando Google TTS")
        await tts_google(text, lang, audio_path)
    else:
        log.info("Usando edge-tts")
        communicate = edge_tts.Communicate(text, EDGE_VOICES.get(lang, "it-IT-ElsaNeural"))
        await communicate.save(audio_path)

# Google TTS (optional)
async def tts_google(text: str, lang: str, audio_path: str):
    voice_map = {"it": "it-IT-Neural2-C", "es": "es-ES-Neural2-B", "en": "en-US-Neural2-D"}
    voice = voice_map.get(lang, "it-IT-Neural2-C")
    payload = {
        "input": {"text": text},
        "voice": {"languageCode": lang + "-IT" if lang == "it" else (lang + "-ES" if lang == "es" else "en-US"), "name": voice},
        "audioConfig": {"audioEncoding": "MP3"},
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"https://texttospeech.googleapis.com/v1/text:synthesize?key={GOOGLE_API_KEY}",
            json=payload,
        )
        r.raise_for_status()
        import base64
        with open(audio_path, "wb") as f:
            f.write(base64.b64decode(r.json()["audioContent"]))

def main():
    token = os.environ.get("TG_BOT_TOKEN")
    if not token:
        print("❌ Imposta TG_BOT_TOKEN (variabile ambiente o .env)")
        sys.exit(1)

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("lang", lang_cmd))
    app.add_handler(CallbackQueryHandler(lang_callback, pattern="^lang_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file))

    log.info("🤖 Bot avviato…")
    app.run_polling()

if __name__ == "__main__":
    main()
