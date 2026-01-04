import os
import fitz
from flask import Flask, render_template, request, send_file
from google import genai

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import requests  # added for font download

app = Flask(__name__)

# ================= GEMINI SETUP =================
GEMINI_KEY = "AIzaSyB3B1C2Pf-buTVLSxzTnqy_tQgF5Q8abgY"
client = genai.Client(api_key=GEMINI_KEY)

# ================= GLOBAL STORAGE =================
latest_summary = ""   # 🔥 THIS IS THE KEY

# ================= PDF TEXT EXTRACTION =================
def extract_text_from_pdf(pdf_path):
    text = ""
    doc = fitz.open(pdf_path)
    for page in doc:
        t = page.get_text("text")
        if t:
            text += t + "\n"
    doc.close()
    return text.strip()

# ================= FONT HELPERS =================
def ensure_font(language):
    """Ensure a font file suitable for `language` is present locally and return its path.
    Tries Noto fonts for specific scripts, falls back to DejaVu.
    """
    font_dir = "fonts"
    os.makedirs(font_dir, exist_ok=True)

    # Map languages to font filenames and download URLs (Noto or DejaVu)
    font_map = {
        "English": ("DejaVuSans.ttf", "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf"),
        "French": ("DejaVuSans.ttf", "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf"),
        "Hindi": ("NotoSansDevanagari-Regular.ttf", "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansDevanagari/NotoSansDevanagari-Regular.ttf"),
        "Tamil": ("NotoSansTamil-Regular.ttf", "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansTamil/NotoSansTamil-Regular.ttf"),
        "Malayalam": ("NotoSansMalayalam-Regular.ttf", "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansMalayalam/NotoSansMalayalam-Regular.ttf"),
        "Telugu": ("NotoSansTelugu-Regular.ttf", "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansTelugu/NotoSansTelugu-Regular.ttf"),
    }

    fname, url = font_map.get(language, font_map["English"])
    font_path = os.path.join(font_dir, fname)
    if os.path.exists(font_path):
        return font_path

    # Attempt to download the font
    try:
        r = requests.get(url, timeout=20)
        if r.status_code == 200 and r.content:
            with open(font_path, "wb") as f:
                f.write(r.content)
            return font_path
    except Exception:
        pass

    # As a last resort, try DejaVu (if not already attempted)
    fallback_path = os.path.join(font_dir, "DejaVuSans.ttf")
    if os.path.exists(fallback_path):
        return fallback_path
    try:
        r = requests.get("https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf", timeout=15)
        if r.status_code == 200 and r.content:
            with open(fallback_path, "wb") as f:
                f.write(r.content)
            return fallback_path
    except Exception:
        pass

    return None

# ================= GEMINI SUMMARY =================
def summarize_text(text, language):
    # Ask Gemini to produce spaced, clear notes with labeled sections.
    if not language:
        # keep same language as source
        lang_desc = "the same language as the source text"
    else:
        lang_desc = language

    prompt = (
        f"Convert the following study material into clear, well-structured notes in {lang_desc}.\n"
        "Structure the output exactly with these sections and a blank line between them:\n"
        "Title: (one line)\n"
        "One-line summary: (one sentence)\n"
        "Key Points: (bullet list, each bullet short)\n"
        "Explanations: (a short 1-2 sentence explanation for each key point)\n\n"
        "Keep language simple and concise so notes are easy to scan.\n\n"
        f"Source material:\n{text}\n\n"
        "Output only the labeled sections requested above."
    )

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[{"role": "user", "parts": [{"text": prompt}]}]
    )

    return response.candidates[0].content.parts[0].text.strip()

# ================= CREATE PDF =================
def create_pdf(summary_text, font_path=None):
    styles = getSampleStyleSheet()

    # If a font path is supplied, try to register it
    registered_font_name = None
    if font_path and os.path.exists(font_path):
        try:
            registered_font_name = os.path.splitext(os.path.basename(font_path))[0]
            pdfmetrics.registerFont(TTFont(registered_font_name, font_path))
        except Exception:
            registered_font_name = None

    # Configure styles
    normal_style = styles["Normal"]
    heading_style = styles.get("Heading2", styles["Normal"])

    if registered_font_name:
        normal_style.fontName = registered_font_name
        heading_style.fontName = registered_font_name

    normal_style.fontSize = 11
    normal_style.leading = 15
    heading_style.fontSize = 13
    heading_style.leading = 16

    doc = SimpleDocTemplate(
        "summary.pdf",
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    story = []
    # Split into paragraphs by double newlines to avoid overly congested single-line paragraphs
    paragraphs = [p.strip() for p in summary_text.split("\n\n") if p.strip()]

    for p in paragraphs:
        # Treat short lines or lines ending with ':' as headings for better PDF layout
        single_line = "\n" not in p and len(p) < 120
        if single_line and (p.endswith(":") or p.isupper() or len(p.split()) <= 8):
            story.append(Paragraph(f"<b>{p}</b>", heading_style))
        else:
            # Preserve internal newlines as <br/> for paragraphs containing bullets or multiple lines
            p_html = p.replace("\n", "<br/>")
            story.append(Paragraph(p_html, normal_style))
        story.append(Spacer(1, 8))

    doc.build(story)


# ================= LANGUAGE DETECTION (simple heuristic) =================
def detect_language_from_text(text):
    # Basic unicode-block checks for some scripts we support
    for ch in text:
        code = ord(ch)
        if 0x0900 <= code <= 0x097F:
            return "Hindi"
        if 0x0B80 <= code <= 0x0BFF:
            return "Tamil"
        if 0x0D00 <= code <= 0x0D7F:
            return "Malayalam"
        if 0x0C00 <= code <= 0x0C7F:
            return "Telugu"
    return "English"


def translate_text(text, target_language):
    prompt = (
        f"Translate the following text into {target_language}. Keep formatting and headings intact.\n\n"
        f"Text:\n{text}"
    )
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[{"role": "user", "parts": [{"text": prompt}]}]
    )
    return response.candidates[0].content.parts[0].text.strip()

# ================= MAIN ROUTE =================
@app.route("/", methods=["GET", "POST"])
def index():
    global latest_summary

    summary = None
    error = None
    pdf_ready = False
    language = None

    if request.method == "POST":
        file = request.files.get("pdf")
        language = request.form.get("language")

        if not file or file.filename == "":
            error = "Please upload a file."
        else:
            temp_path = "temp_upload.pdf"
            file.save(temp_path)

            text = extract_text_from_pdf(temp_path)
            os.remove(temp_path)

            if not text:
                error = "No readable text found in the uploaded file."
            else:
                # Home: summarize without translating — keep original language
                language = detect_language_from_text(text)
                summary = summarize_text(text, None)
                latest_summary = summary   # save website text

                # Choose a font based on detected language so PDF renders correctly
                font_path = ensure_font(language)
                create_pdf(summary, font_path=font_path)
                pdf_ready = True

    return render_template(
        "index.html",
        summary=summary,
        error=error,
        pdf_ready=pdf_ready,
        language=language
    )

# ================= DOWNLOAD ROUTE =================
@app.route("/download")
def download_pdf():
    return send_file(
        "summary.pdf",
        as_attachment=True,
        download_name="AI_Notes.pdf"
    )


@app.route("/translator", methods=["GET", "POST"])
def translator():
    translated = None
    translated_ready = False
    target_language = None

    if request.method == "POST":
        file = request.files.get("pdf")
        target_language = request.form.get("target_language") or "English"
        if not file or file.filename == "":
            translated = None
        else:
            temp_path = "temp_translate.pdf"
            file.save(temp_path)
            text = extract_text_from_pdf(temp_path)
            os.remove(temp_path)
            if text:
                translated = translate_text(text, target_language)
                # ensure font and create translated PDF
                font_path = ensure_font(target_language)
                # save translated PDF separately
                create_pdf(translated, font_path=font_path)
                # rename to translated.pdf so download route can serve it
                try:
                    os.replace("summary.pdf", "translated.pdf")
                except Exception:
                    pass
                translated_ready = True

    return render_template("translator.html", translated=translated, translated_ready=translated_ready, target_language=target_language)


@app.route('/download_translated')
def download_translated():
    return send_file('translated.pdf', as_attachment=True, download_name='Translated_AI_Notes.pdf')


@app.route('/about')
def about():
    return render_template('about.html')

# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True, port=5000)
