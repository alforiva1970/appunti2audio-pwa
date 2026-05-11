# Appunti → Audio

Trasforma appunti, dispense PDF, foto di quaderni e file di testo in audio parlato. 100% browser, zero server, zero installazione.

## Come usarla

1. Apri https://alforiva1970.github.io/appunti2audio (o l'URL del tuo repo)
2. Carica un file — PDF, TXT, Markdown, foto (JPG/PNG)
3. Premi **Genera Audio** — il browser legge il testo ad alta voce
4. Condividi il testo estratto con altre app o salvalo come file

Se vuoi aggiungerla alla schermata home del telefono:
- **Android:** Chrome → menu → "Aggiungi a schermata Home"
- Funziona offline dopo il primo caricamento

## Cosa supporta

| Tipo file | Cosa fa |
|-----------|---------|
| PDF | Estrae il testo (anche da scansioni) |
| TXT / MD | Legge direttamente il contenuto |
| Foto (JPG, PNG) | Riconoscimento testo tramite OCR (Tesseract.js) |

## Su desktop

Per una voce più naturale e il salvataggio in MP3, c'è anche una versione Python:

```bash
pip install PyMuPDF edge-tts pytesseract Pillow
python3 appunti2audio.py dispensa.pdf
```

## Note tecniche

- PWA installabile — funziona offline dopo il primo accesso
- OCR scarica un modello ~10MB al primo utilizzo (una volta sola)
- La sintesi vocale usa la voce italiana già presente nel telefono
- Nessun dato viene inviato a server esterni — tutto gira nel browser

---

Progetto Siliceo — Sempre, Maggio 2026
