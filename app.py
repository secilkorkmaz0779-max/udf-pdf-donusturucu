
import io
import os
import re
import zipfile
import defusedxml.ElementTree as ET  # normal ElementTree yerine: XML "bomba" / XXE saldırılarına karşı güvenli
 
from flask import Flask, request, send_file
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
 
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # tek dosya için üst sınır: 25 MB (kötüye kullanım/DoS'a karşı)
 
# ---------------------------------------------------------------------------
# 1) TÜRKÇE KARAKTER DESTEKLİ FONT BUL VE KAYDET
#    (Standart PDF fontları ı, ğ, ş, İ gibi harfleri düzgün basmaz.
#     Bu yüzden sistemde bulunan bir Unicode TTF fontu kaydediyoruz.)
# ---------------------------------------------------------------------------
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\times.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    os.path.join(os.path.dirname(__file__), "DejaVuSans.ttf"),
]
 
FONT_NAME = "Helvetica"  # reportlab dahili yedek (Türkçe karakterlerde sorun çıkarabilir)
FONT_BOLD = "Helvetica-Bold"
 
for path in FONT_CANDIDATES:
    if os.path.exists(path):
        try:
            pdfmetrics.registerFont(TTFont("UdfFont", path))
            pdfmetrics.registerFont(TTFont("UdfFont-Bold", path))
            FONT_NAME = "UdfFont"
            FONT_BOLD = "UdfFont-Bold"
            break
        except Exception:
            continue
 
if FONT_NAME == "Helvetica":
    print("UYARI: Türkçe karakter destekli bir font bulunamadı. "
          "ı/ğ/ş/İ gibi harfler hatalı çıkabilir. Çözüm için "
          "https://dejavu-fonts.github.io adresinden DejaVuSans.ttf indirip "
          "bu script ile aynı klasöre koyun.")
 
UPLOAD_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>UDF &rarr; PDF Dönüştürücü (Gayriresmî)</title>
<style>
 *{box-sizing:border-box}
 body{font-family:'Segoe UI',Tahoma,sans-serif;background:radial-gradient(circle at top,#2b2320 0%,#171213 70%);
      margin:0;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:48px 16px}
 .card{background:#fff;padding:42px 40px;border-radius:14px;box-shadow:0 12px 32px rgba(0,0,0,.45);
       text-align:center;max-width:460px;width:100%;border-top:4px solid #7a1f2b}
 h2{color:#3a1418;letter-spacing:.3px}
 label{background:#7a1f2b;color:#fff;padding:14px 28px;border-radius:8px;cursor:pointer;
       display:inline-block;font-weight:bold;transition:.2s}
 label:hover{background:#5e1620}
 input[type=file]{display:none}
 button{background:#1f1b1a;color:#fff;border:0;padding:14px 28px;border-radius:8px;
        cursor:pointer;font-weight:bold;font-size:16px;width:100%;margin-top:15px;transition:.2s}
 button:hover{background:#3a1418}
 #filename{margin-top:12px;color:#6b4d4f;font-weight:600;font-size:14px}
 
 .legal{max-width:460px;width:100%;margin-top:22px;background:#241d1c;border-radius:10px;
        padding:18px 22px;box-shadow:0 4px 16px rgba(0,0,0,.3);font-size:12.5px;
        color:#c9b8b6;line-height:1.6;text-align:left;border-left:3px solid #7a1f2b}
 .legal b{color:#e8d3ce}
 footer{margin-top:22px;font-size:12px;color:#8a7573;text-align:center}
</style>
</head>
<body>
<div class="card">
  <h2>UDF &rarr; PDF Dönüştürücü</h2>
  <p>Bir .udf dosyası seçin, doğrudan PDF olarak indirin.</p>
  <form action="/convert" method="post" enctype="multipart/form-data">
    <label for="f">Dosya Seç</label>
    <input type="file" id="f" name="file" accept=".udf" required
           onchange="document.getElementById('filename').innerText=this.files[0].name">
    <div id="filename">Henüz dosya seçilmedi</div>
    <button type="submit">PDF'e Dönüştür ve İndir</button>
  </form>
</div>
 
<div class="legal">
  <p><b>Bu site resmî bir UYAP/Adalet Bakanlığı hizmeti değildir.</b>
  Herkesin kullanabilmesi için hazırlanmış, bağımsız ve ücretsiz bir dönüştürme aracıdır.</p>
  <p>Yüklediğiniz dosyalar sunucuda <b>saklanmaz</b>; sadece anlık olarak PDF'e
  çevrilip yanıt gönderildikten hemen sonra bellekten silinir, hiçbir kayıt veya
  yedek tutulmaz.</p>
  <p>Üretilen PDF'ler yalnızca <b>bilgi amaçlıdır</b>; belgelerin doğruluğu, güncelliği
  veya resmî geçerliliği için her zaman UYAP üzerindeki orijinal belgeyi esas alın.
  Dönüştürme sırasında oluşabilecek eksik/hatalı gösterimlerden site sorumlu tutulamaz.</p>
</div>
 
<footer>by SEÇİL KORKMAZ</footer>
</body>
</html>
"""
 
 
def extract_udf(file_bytes: bytes):
    """UDF (zip) içinden ham metni, biçim bilgisiyle paragrafları ve
    varsa resimleri çıkarır.
 
    UDF yapısı:
      <content><![CDATA[ ... belgenin TÜM düz metni ... ]]></content>
      <elements>
        <header><paragraph Alignment=".."><content startOffset=".." length=".." bold=".."/></paragraph></header>
        <paragraph Alignment=".." Bulleted=".." LeftIndent="..">
            <content startOffset=".." length=".." bold=".." size=".."/>
            <field startOffset=".." length=".."/>
            <tab/>
            <image imageData="BASE64..."/>
        </paragraph>
        ...
        <footer>...</footer>
      </elements>
 
    Gerçek metin SADECE <content><![CDATA[...]]></content> içinde var.
    <elements> içindeki her <paragraph>, o ana metnin hangi aralığının
    (startOffset/length) hangi biçimle (kalın, hizalama, madde işareti,
    girinti) gösterileceğini tarif ediyor. Resimler ise <image
    imageData="..."/> attribute'u içinde base64 olarak gömülü.
    """
    import base64
 
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
        names = z.namelist()
 
        content_name = next((n for n in names if n.lower().endswith("content.xml")), None)
        if not content_name:
            raise ValueError(f"content.xml bulunamadı. Zip içeriği: {names}")
 
        xml_bytes = z.read(content_name)
        root = ET.fromstring(xml_bytes)
 
        content_el = root.find("content")
        full_text = content_el.text if content_el is not None else None
        if not full_text:
            raise ValueError("content.xml içinde <content> metni boş geldi.")
 
        elements_el = root.find("elements")
        paragraphs = []  # her biri dict: {runs:[(text,bold,size)], images:[bytes,...], align, bulleted, indent}
 
        def slice_text(start, length):
            try:
                start = int(start)
                length = int(length)
                return full_text[start:start + length]
            except Exception:
                return ""
 
        def process_paragraph(p_el):
            runs = []
            para_images = []
            for child in p_el:
                tag = child.tag
                if tag in ("content", "field", "space"):
                    seg = slice_text(child.attrib.get("startOffset", 0), child.attrib.get("length", 0))
                    if seg:
                        runs.append((seg, child.attrib.get("bold") == "true", child.attrib.get("size")))
                elif tag == "tab":
                    runs.append(("\u00A0\u00A0\u00A0\u00A0", False, None))
                elif tag == "image":
                    b64 = child.attrib.get("imageData")
                    if b64:
                        try:
                            raw = base64.b64decode(b64)
                            if len(raw) > 5000:  # küçük süs ikonlarını ele
                                para_images.append(raw)
                        except Exception:
                            pass
            paragraphs.append({
                "runs": runs,
                "images": para_images,
                "align": p_el.attrib.get("Alignment", "0"),
                "bulleted": p_el.attrib.get("Bulleted") == "true",
                "indent": float(p_el.attrib.get("LeftIndent", 0) or 0),
            })
 
        if elements_el is not None:
            for node in elements_el:
                if node.tag == "header":
                    for p in node.findall("paragraph"):
                        process_paragraph(p)
                elif node.tag == "paragraph":
                    process_paragraph(node)
                elif node.tag == "footer":
                    for p in node.findall("paragraph"):
                        process_paragraph(p)
                # 'styles' vb. diğer etiketler yok sayılır
 
        # Zip içinde ayrıca gerçek resim dosyası varsa (nadir durum) sona ekle
        extra_images = []
        for n in names:
            if n.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                extra_images.append(z.read(n))
 
        return paragraphs, extra_images
 
 
def build_pdf(paragraphs: list, extra_images: list) -> bytes:
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image, KeepTogether)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
    from reportlab.lib.utils import ImageReader
    from xml.sax.saxutils import escape as xml_escape
 
    ALIGN_MAP = {"0": TA_LEFT, "1": TA_CENTER, "2": TA_RIGHT, "3": TA_JUSTIFY}
 
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=2 * cm, rightMargin=2 * cm,
                             topMargin=1.8 * cm, bottomMargin=1.8 * cm)
 
    usable_width = A4[0] - 4 * cm
    flow = []
 
    for para in paragraphs:
        runs = para["runs"]
        images = para["images"]
 
        if runs:
            pieces = []
            max_size = 10.5
            for text, bold, size in runs:
                safe = xml_escape(text).replace("\n", "<br/>")
                if size:
                    try:
                        max_size = max(max_size, float(size) * 0.85)
                    except ValueError:
                        pass
                if bold:
                    pieces.append(f"<b>{safe}</b>")
                else:
                    pieces.append(safe)
            joined = "".join(pieces).strip("\u00A0")
            if joined.strip():
                style = ParagraphStyle(
                    "p", fontName=FONT_NAME, fontSize=min(max_size, 13),
                    leading=min(max_size, 13) * 1.25,
                    alignment=ALIGN_MAP.get(para["align"], TA_LEFT),
                    leftIndent=para["indent"] * 0.9 if para["bulleted"] else 0,
                    bulletIndent=max(para["indent"] * 0.9 - 12, 0),
                    spaceAfter=2,
                )
                bullet = "\u2022" if para["bulleted"] else None
                try:
                    flow.append(Paragraph(joined, style, bulletText=bullet))
                except Exception:
                    flow.append(Paragraph(xml_escape("".join(t for t, _, _ in runs)), style))
            else:
                flow.append(Spacer(1, 6))
        elif not images:
            flow.append(Spacer(1, 6))
 
        for img_bytes in images:
            try:
                reader = ImageReader(io.BytesIO(img_bytes))
                iw, ih = reader.getSize()
                scale = min(usable_width / iw, (A4[1] - 6 * cm) / ih, 1.0)
                flow.append(Spacer(1, 8))
                flow.append(Image(io.BytesIO(img_bytes), width=iw * scale, height=ih * scale))
                flow.append(Spacer(1, 8))
            except Exception:
                pass
 
    for img_bytes in extra_images:
        try:
            reader = ImageReader(io.BytesIO(img_bytes))
            iw, ih = reader.getSize()
            scale = min(usable_width / iw, (A4[1] - 6 * cm) / ih, 1.0)
            flow.append(Image(io.BytesIO(img_bytes), width=iw * scale, height=ih * scale))
            flow.append(Spacer(1, 8))
        except Exception:
            pass
 
    if not flow:
        flow.append(Paragraph("(Belge içeriği boş görünüyor)", ParagraphStyle("p", fontName=FONT_NAME)))
 
    doc.build(flow)
    buf.seek(0)
    return buf.read()
 
 
@app.route("/")
def index():
    return UPLOAD_HTML
 
 
@app.route("/convert", methods=["POST"])
def convert():
    file = request.files.get("file")
    if not file or file.filename == "":
        return "Dosya seçilmedi", 400
    try:
        paragraphs, extra_images = extract_udf(file.read())
        pdf_bytes = build_pdf(paragraphs, extra_images)
    except Exception as e:
        return f"<h2>Hata</h2><p>{e}</p><a href='/'>Geri dön</a>", 500
 
    out_name = re.sub(r"\.udf$", "", file.filename, flags=re.I) + ".pdf"
    return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf",
                      as_attachment=True, download_name=out_name)
 
 
if __name__ == "__main__":
    # UYARI: debug=True SADECE kendi bilgisayarında test ederken kullanılır.
    # Bir sunucuya/internete açarken MUTLAKA debug=False olmalı — açık kalırsa
    # tarayıcıdan sunucunda keyfi Python kodu çalıştırılabilir (Werkzeug debug
    # konsolu). Aşağıda ortam değişkeninden otomatik ayarlanıyor.
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode, host="127.0.0.1", port=5000)
 