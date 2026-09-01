"""
SafeData Documentation — Markdown to PDF Converter
Converts all .md files in this directory to professionally styled PDFs.
"""

import os
import sys
import glob
import markdown
from xhtml2pdf import pisa

# Directory setup
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.path.join(SCRIPT_DIR, "PDFs")
os.makedirs(PDF_DIR, exist_ok=True)

# Professional CSS styling for the PDFs
PDF_STYLE = """
@page {
    size: A4;
    margin: 2.5cm 2cm 2.5cm 2cm;
    @frame footer {
        -pdf-frame-content: footerContent;
        bottom: 0.5cm;
        margin-left: 2cm;
        margin-right: 2cm;
        height: 1cm;
    }
}

body {
    font-family: Helvetica, Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.6;
    color: #1a1a2e;
}

h1 {
    font-size: 20pt;
    color: #0f3460;
    border-bottom: 3px solid #0f3460;
    padding-bottom: 8px;
    margin-top: 0;
    margin-bottom: 16px;
}

h2 {
    font-size: 15pt;
    color: #16213e;
    border-bottom: 1.5px solid #e0e0e0;
    padding-bottom: 6px;
    margin-top: 24px;
    margin-bottom: 12px;
}

h3 {
    font-size: 12pt;
    color: #1a1a2e;
    margin-top: 18px;
    margin-bottom: 8px;
}

h4 {
    font-size: 11pt;
    color: #333;
    margin-top: 14px;
    margin-bottom: 6px;
}

p {
    margin-bottom: 8px;
    text-align: justify;
}

ul, ol {
    margin-bottom: 8px;
    padding-left: 20px;
}

li {
    margin-bottom: 4px;
}

strong {
    color: #0f3460;
}

code {
    font-family: Courier, monospace;
    font-size: 9pt;
    background-color: #f0f4f8;
    padding: 1px 4px;
    border: 1px solid #d0d7de;
}

pre {
    font-family: Courier, monospace;
    font-size: 8.5pt;
    background-color: #f6f8fa;
    border: 1px solid #d0d7de;
    padding: 12px;
    margin: 10px 0;
    line-height: 1.45;
    overflow: hidden;
    white-space: pre-wrap;
    word-wrap: break-word;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 9pt;
}

th {
    background-color: #0f3460;
    color: white;
    padding: 8px 10px;
    text-align: left;
    font-weight: bold;
    border: 1px solid #0f3460;
}

td {
    padding: 6px 10px;
    border: 1px solid #d0d7de;
}

tr:nth-child(even) td {
    background-color: #f6f8fa;
}

hr {
    border: none;
    border-top: 1.5px solid #e0e0e0;
    margin: 20px 0;
}

blockquote {
    border-left: 4px solid #0f3460;
    margin: 10px 0;
    padding: 8px 16px;
    background-color: #f0f4f8;
    color: #333;
}

.cover-header {
    text-align: center;
    margin-top: 120px;
    margin-bottom: 40px;
}

.cover-header h1 {
    font-size: 28pt;
    border-bottom: none;
    color: #0f3460;
}

.cover-meta {
    text-align: center;
    color: #555;
    font-size: 11pt;
    margin-top: 60px;
}

.footer-text {
    font-size: 8pt;
    color: #888;
    text-align: center;
}
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>{style}</style>
</head>
<body>
    {content}
    <div id="footerContent">
        <p class="footer-text">
            SafeData Documentation — 3Consulting &bull; Confidential
        </p>
    </div>
</body>
</html>"""


def convert_md_to_pdf(md_path, pdf_path):
    """Convert a single markdown file to PDF."""
    print(f"  Converting: {os.path.basename(md_path)}")
    
    # Read markdown content
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
    
    # Convert markdown to HTML
    extensions = [
        "tables",
        "fenced_code",
        "codehilite",
        "toc",
        "nl2br",
        "sane_lists",
    ]
    html_body = markdown.markdown(md_content, extensions=extensions)
    
    # Build full HTML document
    full_html = HTML_TEMPLATE.format(style=PDF_STYLE, content=html_body)
    
    # Convert HTML to PDF
    with open(pdf_path, "wb") as pdf_file:
        pisa_status = pisa.CreatePDF(full_html, dest=pdf_file)
    
    if pisa_status.err:
        print(f"    [FAIL] ERROR converting {os.path.basename(md_path)}: {pisa_status.err}")
        return False
    else:
        size_kb = os.path.getsize(pdf_path) / 1024
        print(f"    [OK] Saved: {os.path.basename(pdf_path)} ({size_kb:.1f} KB)")
        return True


def main():
    print("=" * 65)
    print("  SafeData Documentation -- Markdown to PDF Converter")
    print("  3Consulting Confidential")
    print("=" * 65)
    print()
    
    # Find all markdown files (excluding this script's directory artifacts)
    md_files = sorted(glob.glob(os.path.join(SCRIPT_DIR, "*.md")))
    
    if not md_files:
        print("No .md files found in the Documents directory.")
        sys.exit(1)
    
    print(f"Found {len(md_files)} document(s) to convert:\n")
    
    success_count = 0
    fail_count = 0
    
    for md_path in md_files:
        basename = os.path.splitext(os.path.basename(md_path))[0]
        pdf_path = os.path.join(PDF_DIR, f"{basename}.pdf")
        
        if convert_md_to_pdf(md_path, pdf_path):
            success_count += 1
        else:
            fail_count += 1
    
    print()
    print("-" * 65)
    print(f"  Conversion complete: {success_count} succeeded, {fail_count} failed")
    print(f"  PDFs saved to: {PDF_DIR}")
    print("-" * 65)


if __name__ == "__main__":
    main()
