# Smart Notes Generator

A small Flask webapp that extracts text from PDFs/PPTs, generates structured study notes using Gemini AI, and can translate documents into several languages with downloadable PDFs.

## Features
- Home: upload a document and generate structured study notes. The Home summarizer preserves the original language (no automatic translation).
- Translator: upload a document and choose a target language — the site translates the document and provides a downloadable translated PDF.
- About: explains what the site does and the difference between Home and Translator.
- Font handling: the app attempts to download and embed appropriate Noto/DejaVu fonts at runtime so scripts like Devanagari, Tamil, Malayalam, and Telugu render correctly in generated PDFs.

## Files
- "APP.py" — main Flask application and logic for extraction, summarization, translation, and PDF generation.
- `templates/` — HTML templates (`index.html`, `translator.html`, `about.html`).
- `static/style.css` — site styles.
- `fonts/` — downloaded fonts (created at runtime).

## Requirements
Use the provided virtual environment or create one and install dependencies:

```powershell
cd D:\Aditya\python\website
python -m venv venv
& .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If you don't have `requirements.txt`, install these packages:
```powershell
pip install flask google-generativeai pymupdf reportlab requests python-pptx fpdf
```

## Configuration
- The app uses Gemini (Google) via `google.genai.Client`. The API key is currently set inside `app.py` as `GEMINI_KEY`. For security, consider moving this to an environment variable instead of hardcoding.

## Run
```powershell
& .\venv\Scripts\Activate.ps1
python app.py
```
Open http://127.0.0.1:5000 in your browser.

## Routes / Pages
- `/` (Home): Generate structured notes from uploaded document. Output appears on the page and a PDF can be downloaded.
- `/translator`: Translate uploaded document to a target language and download translated PDF.
- `/about`: Project description and feature notes.
- `/download`: Download the last generated summary PDF from Home (`AI_Notes.pdf`).
- `/download_translated`: Download the last translated PDF (`Translated_AI_Notes.pdf`).

## How it works (high level)
1. The app extracts raw text from uploaded PDFs using PyMuPDF (`fitz`).
2. It calls Gemini to summarize or translate content.
3. The summary/translation is formatted and written to a PDF using ReportLab.
4. Fonts are downloaded from the Google Noto or DejaVu repositories when needed and registered with ReportLab so non-Latin scripts render correctly.

## Notes & Troubleshooting
- If you see missing glyphs (□ boxes) in PDFs, the app will try to download a matching Noto font for the language. If internet access is restricted, bundle the required font files into the `fonts/` folder and restart the app.
- The app currently uses a simple heuristic to detect scripts (Hindi/Tamil/Malayalam/Telugu). Expand `detect_language_from_text` in `app.py` for more accurate detection.
- For production use:
	- Move `GEMINI_KEY` into an environment variable.
	- Add proper error handling and input validation.
	- Consider rate limits and costs for the Gemini API.

