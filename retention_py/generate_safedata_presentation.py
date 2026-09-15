"""
Generate SafeData Case Study in both PPTX and PDF formats.
Matches 3Consulting design language, color palette, typography, and structure:
- 12 Slides, 4:5 aspect ratio (576 x 720 pt / 8 x 10 inches), optimized for executive presentations & LinkedIn carousels.
- Colors: Deep Slate Teal (#183B44), Warm Off-White/Sand (#F8F7F4), Brand Orange (#E27A20), Slate Dark (#1E293B), Muted (#64748B).
- 3Consulting logo embedded.
"""

import os
import sys

# PowerPoint generator
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

# PDF generator
from reportlab.pdfgen import canvas
from reportlab.lib import colors

LOGO_PATH = r"c:\Users\3Consult\Documents\ChidiGit\collabo\ADRS\Documents\3consulting_logo.png"
OUTPUT_DIR = r"c:\Users\3Consult\Documents\ChidiGit\collabo\ADRS\Documents"
ARTIFACTS_DIR = r"C:\Users\3Consult\.gemini\antigravity-ide\brain\ef42bc3d-a334-4035-b0a1-9e24125a70ba"

PPTX_PATH_1 = os.path.join(OUTPUT_DIR, "SafeData_Case_Study_3Consulting.pptx")
PDF_PATH_1 = os.path.join(OUTPUT_DIR, "SafeData_Case_Study_3Consulting.pdf")
PPTX_PATH_2 = os.path.join(ARTIFACTS_DIR, "SafeData_Case_Study_3Consulting.pptx")
PDF_PATH_2 = os.path.join(ARTIFACTS_DIR, "SafeData_Case_Study_3Consulting.pdf")

# Colors
COLOR_DARK_TEAL = RGBColor(24, 59, 68)     # #183B44
COLOR_CREAM = RGBColor(248, 247, 244)      # #F8F7F4
COLOR_ORANGE = RGBColor(226, 122, 32)      # #E27A20
COLOR_DARK_SLATE = RGBColor(30, 41, 59)    # #1E293B
COLOR_MUTED_SLATE = RGBColor(100, 116, 139)# #64748B
COLOR_WHITE = RGBColor(255, 255, 255)
COLOR_CARD_BG = RGBColor(255, 255, 255)
COLOR_CARD_BORDER = RGBColor(226, 232, 240)# #E2E8F0
COLOR_SOFT_BOX = RGBColor(237, 242, 247)   # #EDF2F7

RL_DARK_TEAL = colors.HexColor("#183B44")
RL_CREAM = colors.HexColor("#F8F7F4")
RL_ORANGE = colors.HexColor("#E27A20")
RL_DARK_SLATE = colors.HexColor("#1E293B")
RL_MUTED_SLATE = colors.HexColor("#64748B")
RL_WHITE = colors.HexColor("#FFFFFF")
RL_CARD_BORDER = colors.HexColor("#E2E8F0")
RL_SOFT_BOX = colors.HexColor("#EDF2F7")

SLIDE_DATA = [
    # Slide 1: Cover
    {
        "type": "dark",
        "category": "CASE STUDY",
        "headline": "Keeping Data Forever Isn't Safe.\nDeleting It Blindly Is Even Worse.",
        "subtitle": "How automated retention lifecycle governance turns toxic data liability into audit-proof compliance.",
        "footer": "DATA PROTECTION & RETENTION GOVERNANCE ADVISORY",
        "page": 1,
    },
    # Slide 2: The Problem
    {
        "type": "light",
        "category": "THE PROBLEM",
        "headline": "Collecting data isn't the whole job.",
        "subhead": "Organisations know how to acquire and store customer data.\nAlmost none know when — or how — to legally let it go.",
        "items": [
            ("Operational Data Stores", "Core Banking, CRM, HR & Analytics"),
            ("Accumulating Archives", "Data retained 'just in case' without statutory justification"),
            ("The Unseen Exposure", "Statutory retention clocks expire silently without action")
        ],
        "page": 2,
    },
    # Slide 3: The Reality
    {
        "type": "light",
        "category": "THE REALITY",
        "headline": "Retention doesn't happen by policy alone.",
        "points": [
            "Policies sit in forgotten PDF binders.",
            "Teams hoard data out of fear of deleting something important.",
            "Blind deletions destroy critical legal evidence.",
            "Statutory retention clocks expire unnoticed."
        ],
        "banner": "Yet most organisations believe having a static retention policy schedule is the same as enforcing it.",
        "page": 3,
    },
    # Slide 4: Defining the Term
    {
        "type": "dark",
        "category": "DEFINING THE TERM",
        "headline": "What is automated data retention governance?",
        "quote": "The continuous, rule-based tracking of personal data from lawful collection to verified, audit-proof disposal.",
        "body": "It is not a cron job that deletes database rows.\n\nIt is an end-to-end lifecycle system that enforces retention periods, respects statutory hold overrides, and cryptographically proves compliance to global regulators.",
        "page": 4,
    },
    # Slide 5: Where It Breaks Down
    {
        "type": "light",
        "category": "WHERE IT BREAKS DOWN",
        "headline": "Everyone holds data.\nNo one owns its disposal.",
        "flow": ["Business Units", "IT & DevOps", "Legal & Risk", "Privacy / DPO", "Archives"],
        "callout": "Each function treats data through its own narrow lens — but no single team coordinates the legal disposal clock. Marketing hoards leads, IT worries about storage, Legal issues holds via email, and DPOs lack verifiable proof. Assessments live in one silo, operational databases in another, and compliant disposal rarely happens at all.",
        "page": 5,
    },
    # Slide 6: The Missing Piece
    {
        "type": "light",
        "category": "THE MISSING PIECE",
        "headline": "A connected data retention lifecycle.",
        "row1": ["1. Categorise", "2. Lawful Basis", "3. Retention Clock", "4. Event Signals"],
        "row2": ["5. Review Alert", "6. Dual Approval", "7. Verified Disposal"],
        "repeat_note": "The cycle is continuous — data is actively governed, never abandoned.",
        "callout": "This is the piece most compliance programmes are missing: an automated governance engine, not a static spreadsheet schedule.",
        "page": 6,
    },
    # Slide 7: The Consent Paradox
    {
        "type": "light",
        "category": "THE CONSENT PARADOX",
        "headline": "Consent withdrawal is an inbound signal, not an in-app button.",
        "box_left_title": "Connected Customer Systems",
        "box_left_desc": "Customer revokes consent in CRM, banking app, or portal.\nSystem emits API event: POST /api/v1/consent/signal",
        "box_right_title": "SafeData Governance Engine",
        "box_right_desc": "Captures signal, initiates policy grace period (e.g. 30 days), monitors countdown, and coordinates compliant disposal.",
        "callout": "SafeData does not manage consent choices — your customer-facing applications do. SafeData strictly governs the resulting legal disposal obligation once consent is withdrawn.",
        "page": 7,
    },
    # Slide 8: Risk-Based Safeguards
    {
        "type": "light",
        "category": "RISK-BASED GOVERNANCE",
        "headline": "Should sensitive banking data get the same treatment as marketing leads?",
        "tiers": [
            ("TIER 1 — FOUR-EYES DUAL APPROVAL", "Sensitive data (financial, biometric, health, minors). Automated deletion is blocked; requires secondary compliance sign-off with step-up verification."),
            ("TIER 2 — INSTANT LITIGATION FREEZE", "Subpoena, regulatory inquiry, or active dispute. Disables automated deletion immediately to prevent evidence spoliation sanctions."),
            ("TIER 3 — RULE-BASED DISPOSAL PATHWAYS", "Configurable execution per category: permanent deletion, cryptographic anonymisation, or secure offline archival.")
        ],
        "page": 8,
    },
    # Slide 9: The Evidence Trap
    {
        "type": "dark",
        "category": "THE EVIDENCE TRAP",
        "headline": "If you cannot prove you deleted it,\nin the eyes of the regulator, you never did.",
        "quote": "When data protection authorities audit your organisation, verbal assurances and deleted database flags fail.",
        "body": "SafeData binds every lifecycle decision into an immutable, SHA-256 hash-chained audit ledger. Automated background tasks verify cryptographic chain integrity every 6 hours to ensure tamper evidence across the entire organisation.",
        "page": 9,
    },
    # Slide 10: The Transformation
    {
        "type": "light",
        "category": "THE TRANSFORMATION",
        "headline": "From toxic data liability to continuous compliance.",
        "before": [
            "Indefinite data hoarding",
            "Forgotten static policy schedules",
            "Blind, uncoordinated deletions",
            "No verifiable proof for regulators",
            "Massive regulatory & breach exposure"
        ],
        "after": [
            "Centralised retention register",
            "Automated event-driven countdowns",
            "Dual-approval safeguards & legal holds",
            "Cryptographic SHA-256 audit ledger",
            "Global multi-framework compliance"
        ],
        "page": 10,
    },
    # Slide 11: The Solution
    {
        "type": "dark",
        "category": "THE SOLUTION",
        "headline": "Introducing\nSafeData",
        "quote": "Automated retention register, event-driven disposal governance, and cryptographic compliance proof — brought together in one global platform.",
        "body": "Built by 3Consulting",
        "page": 11,
    },
    # Slide 12: The Summary / CTA
    {
        "type": "light",
        "category": "THE GOVERNANCE MANDATE",
        "headline": "Know your data.\n\nAutomate its retention clock.\n\nGovern its lawful disposal.\n\nProve compliance beyond doubt.",
        "cta_box": "Read the full case study & explore SafeData — link in the comments.",
        "footer": "3CONSULTING | DATA PROTECTION & RETENTION GOVERNANCE ADVISORY",
        "page": 12,
    },
]

# ---------------------------------------------------------------------------
#  1. BUILD PPTX PRESENTATION
# ---------------------------------------------------------------------------

def create_pptx(output_paths):
    prs = Presentation()
    prs.slide_width = Inches(8.0)
    prs.slide_height = Inches(10.0)
    blank_layout = prs.slide_layouts[6]

    for slide_info in SLIDE_DATA:
        slide = prs.slides.add_slide(blank_layout)
        is_dark = slide_info["type"] == "dark"

        # Background color
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(8.0), Inches(10.0))
        bg.fill.solid()
        bg.fill.fore_color.rgb = COLOR_DARK_TEAL if is_dark else COLOR_CREAM
        bg.line.color.rgb = COLOR_DARK_TEAL if is_dark else COLOR_CREAM

        # 3Consulting Logo & Page Number in header
        logo_w, logo_h = Inches(1.8), Inches(0.8)
        logo_x, logo_y = Inches(5.6), Inches(0.4)
        if is_dark:
            card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, logo_x - Inches(0.1), logo_y - Inches(0.05), logo_w + Inches(0.2), logo_h + Inches(0.1))
            card.fill.solid()
            card.fill.fore_color.rgb = COLOR_WHITE
            card.line.color.rgb = COLOR_WHITE
        
        if os.path.exists(LOGO_PATH):
            slide.shapes.add_picture(LOGO_PATH, logo_x, logo_y, width=logo_w)

        # Page number (for slides 2-12)
        page_num = slide_info.get("page", 1)
        if page_num > 1:
            pbox = slide.shapes.add_textbox(Inches(6.6), Inches(0.95), Inches(1.0), Inches(0.3))
            ptf = pbox.text_frame
            ptf.word_wrap = False
            pp = ptf.paragraphs[0]
            pp.text = f"{page_num} / 12"
            pp.font.size = Pt(11)
            pp.font.bold = True
            pp.font.color.rgb = COLOR_MUTED_SLATE if not is_dark else COLOR_WHITE

        # Category tag (top left)
        cat_box = slide.shapes.add_textbox(Inches(0.6), Inches(0.7), Inches(4.5), Inches(0.4))
        cat_tf = cat_box.text_frame
        cat_p = cat_tf.paragraphs[0]
        cat_p.text = slide_info.get("category", "")
        cat_p.font.size = Pt(13)
        cat_p.font.bold = True
        cat_p.font.color.rgb = COLOR_ORANGE

        # Page specific layout
        if page_num == 1:
            tbox = slide.shapes.add_textbox(Inches(0.6), Inches(3.0), Inches(6.8), Inches(2.5))
            ttf = tbox.text_frame
            ttf.word_wrap = True
            tp = ttf.paragraphs[0]
            tp.text = slide_info["headline"]
            tp.font.size = Pt(28)
            tp.font.bold = True
            tp.font.color.rgb = COLOR_WHITE

            line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(5.8), Inches(1.5), Inches(0.08))
            line.fill.solid()
            line.fill.fore_color.rgb = COLOR_ORANGE
            line.line.color.rgb = COLOR_ORANGE

            sbox = slide.shapes.add_textbox(Inches(0.6), Inches(6.1), Inches(6.8), Inches(1.5))
            stf = sbox.text_frame
            stf.word_wrap = True
            sp = stf.paragraphs[0]
            sp.text = slide_info["subtitle"]
            sp.font.size = Pt(15)
            sp.font.italic = True
            sp.font.color.rgb = COLOR_WHITE

            fbox = slide.shapes.add_textbox(Inches(0.6), Inches(9.2), Inches(6.8), Inches(0.4))
            ftf = fbox.text_frame
            fp = ftf.paragraphs[0]
            fp.text = slide_info["footer"]
            fp.font.size = Pt(9.5)
            fp.font.bold = True
            fp.font.color.rgb = COLOR_MUTED_SLATE

        elif page_num == 2:
            tbox = slide.shapes.add_textbox(Inches(0.6), Inches(1.5), Inches(6.8), Inches(1.0))
            ttf = tbox.text_frame
            ttf.word_wrap = True
            tp = ttf.paragraphs[0]
            tp.text = slide_info["headline"]
            tp.font.size = Pt(26)
            tp.font.bold = True
            tp.font.color.rgb = COLOR_DARK_SLATE

            sbox = slide.shapes.add_textbox(Inches(0.6), Inches(2.8), Inches(6.8), Inches(1.2))
            stf = sbox.text_frame
            stf.word_wrap = True
            sp = stf.paragraphs[0]
            sp.text = slide_info["subhead"]
            sp.font.size = Pt(14)
            sp.font.color.rgb = COLOR_DARK_SLATE

            y = 4.4
            for title, desc in slide_info["items"]:
                card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(y), Inches(6.8), Inches(1.2))
                card.fill.solid()
                card.fill.fore_color.rgb = COLOR_WHITE
                card.line.color.rgb = COLOR_CARD_BORDER
                
                tb = slide.shapes.add_textbox(Inches(0.8), Inches(y + 0.15), Inches(6.4), Inches(0.9))
                tf = tb.text_frame
                tf.word_wrap = True
                p1 = tf.paragraphs[0]
                p1.text = title
                p1.font.bold = True
                p1.font.size = Pt(13)
                p1.font.color.rgb = COLOR_ORANGE
                p2 = tf.add_paragraph()
                p2.text = desc
                p2.font.size = Pt(11)
                p2.font.color.rgb = COLOR_MUTED_SLATE
                y += 1.4

        elif page_num == 3:
            tbox = slide.shapes.add_textbox(Inches(0.6), Inches(1.5), Inches(6.8), Inches(1.0))
            ttf = tbox.text_frame
            ttf.word_wrap = True
            tp = ttf.paragraphs[0]
            tp.text = slide_info["headline"]
            tp.font.size = Pt(26)
            tp.font.bold = True
            tp.font.color.rgb = COLOR_DARK_SLATE

            y = 2.8
            for pt_text in slide_info["points"]:
                sq = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(y + 0.05), Inches(0.28), Inches(0.28))
                sq.fill.solid()
                sq.fill.fore_color.rgb = COLOR_ORANGE
                sq.line.color.rgb = COLOR_ORANGE

                tb = slide.shapes.add_textbox(Inches(1.1), Inches(y - 0.05), Inches(6.2), Inches(0.8))
                tf = tb.text_frame
                tf.word_wrap = True
                p = tf.paragraphs[0]
                p.text = pt_text
                p.font.size = Pt(14)
                p.font.bold = True
                p.font.color.rgb = COLOR_DARK_SLATE
                y += 1.05

            box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(7.3), Inches(6.8), Inches(1.4))
            box.fill.solid()
            box.fill.fore_color.rgb = COLOR_DARK_TEAL
            box.line.color.rgb = COLOR_DARK_TEAL
            
            btb = slide.shapes.add_textbox(Inches(0.9), Inches(7.55), Inches(6.2), Inches(1.0))
            btf = btb.text_frame
            btf.word_wrap = True
            bp = btf.paragraphs[0]
            bp.text = slide_info["banner"]
            bp.font.size = Pt(14)
            bp.font.italic = True
            bp.font.color.rgb = COLOR_WHITE

        elif page_num == 4:
            tbox = slide.shapes.add_textbox(Inches(0.6), Inches(2.2), Inches(6.8), Inches(1.2))
            ttf = tbox.text_frame
            ttf.word_wrap = True
            tp = ttf.paragraphs[0]
            tp.text = slide_info["headline"]
            tp.font.size = Pt(26)
            tp.font.bold = True
            tp.font.color.rgb = COLOR_WHITE

            line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(3.6), Inches(1.5), Inches(0.08))
            line.fill.solid()
            line.fill.fore_color.rgb = COLOR_ORANGE
            line.line.color.rgb = COLOR_ORANGE

            qbox = slide.shapes.add_textbox(Inches(0.6), Inches(4.0), Inches(6.8), Inches(1.6))
            qtf = qbox.text_frame
            qtf.word_wrap = True
            qp = qtf.paragraphs[0]
            qp.text = slide_info["quote"]
            qp.font.size = Pt(18)
            qp.font.italic = True
            qp.font.bold = True
            qp.font.color.rgb = COLOR_WHITE

            bbox = slide.shapes.add_textbox(Inches(0.6), Inches(6.0), Inches(6.8), Inches(2.2))
            btf = bbox.text_frame
            btf.word_wrap = True
            bp = btf.paragraphs[0]
            bp.text = slide_info["body"]
            bp.font.size = Pt(14)
            bp.font.color.rgb = COLOR_MUTED_SLATE

        elif page_num == 5:
            tbox = slide.shapes.add_textbox(Inches(0.6), Inches(1.5), Inches(6.8), Inches(1.1))
            ttf = tbox.text_frame
            ttf.word_wrap = True
            tp = ttf.paragraphs[0]
            tp.text = slide_info["headline"]
            tp.font.size = Pt(24)
            tp.font.bold = True
            tp.font.color.rgb = COLOR_DARK_SLATE

            bx_w = Inches(1.2)
            bx_h = Inches(1.0)
            bx_gap = Inches(0.18)
            x_start = Inches(0.6)
            y_box = Inches(3.8)

            for i, dept in enumerate(slide_info["flow"]):
                bx = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x_start + i * (bx_w + bx_gap), y_box, bx_w, bx_h)
                bx.fill.solid()
                bx.fill.fore_color.rgb = COLOR_WHITE
                bx.line.color.rgb = COLOR_DARK_TEAL
                bx.line.width = Pt(1.5)

                tb = slide.shapes.add_textbox(x_start + i * (bx_w + bx_gap), y_box + Inches(0.2), bx_w, Inches(0.6))
                tf = tb.text_frame
                tf.word_wrap = True
                p = tf.paragraphs[0]
                p.text = dept
                p.font.size = Pt(10)
                p.font.bold = True
                p.font.color.rgb = COLOR_DARK_SLATE
                p.alignment = PP_ALIGN.CENTER

            card = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(5.8), Inches(6.8), Inches(2.6))
            card.fill.solid()
            card.fill.fore_color.rgb = COLOR_SOFT_BOX
            card.line.color.rgb = COLOR_CARD_BORDER

            ctb = slide.shapes.add_textbox(Inches(0.9), Inches(6.0), Inches(6.2), Inches(2.2))
            ctf = ctb.text_frame
            ctf.word_wrap = True
            cp = ctf.paragraphs[0]
            cp.text = slide_info["callout"]
            cp.font.size = Pt(13)
            cp.font.color.rgb = COLOR_DARK_SLATE

        elif page_num == 6:
            tbox = slide.shapes.add_textbox(Inches(0.6), Inches(1.5), Inches(6.8), Inches(1.0))
            ttf = tbox.text_frame
            ttf.word_wrap = True
            tp = ttf.paragraphs[0]
            tp.text = slide_info["headline"]
            tp.font.size = Pt(25)
            tp.font.bold = True
            tp.font.color.rgb = COLOR_DARK_SLATE

            x_start = Inches(0.6)
            w1 = Inches(1.55)
            gap = Inches(0.18)
            y1 = Inches(3.2)
            for i, step in enumerate(slide_info["row1"]):
                bx = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x_start + i * (w1 + gap), y1, w1, Inches(0.9))
                bx.fill.solid()
                bx.fill.fore_color.rgb = COLOR_DARK_TEAL
                bx.line.color.rgb = COLOR_DARK_TEAL
                tb = slide.shapes.add_textbox(x_start + i * (w1 + gap), y1 + Inches(0.2), w1, Inches(0.5))
                tf = tb.text_frame
                p = tf.paragraphs[0]
                p.text = step
                p.font.size = Pt(10.5)
                p.font.bold = True
                p.font.color.rgb = COLOR_WHITE
                p.alignment = PP_ALIGN.CENTER

            w2 = Inches(2.1)
            y2 = Inches(4.5)
            for i, step in enumerate(slide_info["row2"]):
                bx = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x_start + i * (w2 + gap + Inches(0.05)), y2, w2, Inches(0.9))
                bx.fill.solid()
                bx.fill.fore_color.rgb = COLOR_DARK_TEAL
                bx.line.color.rgb = COLOR_DARK_TEAL
                tb = slide.shapes.add_textbox(x_start + i * (w2 + gap + Inches(0.05)), y2 + Inches(0.2), w2, Inches(0.5))
                tf = tb.text_frame
                p = tf.paragraphs[0]
                p.text = step
                p.font.size = Pt(11)
                p.font.bold = True
                p.font.color.rgb = COLOR_WHITE
                p.alignment = PP_ALIGN.CENTER

            rbox = slide.shapes.add_textbox(Inches(0.6), Inches(5.7), Inches(6.8), Inches(0.5))
            rtf = rbox.text_frame
            rp = rtf.paragraphs[0]
            rp.text = "↪ " + slide_info["repeat_note"]
            rp.font.size = Pt(12)
            rp.font.italic = True
            rp.font.bold = True
            rp.font.color.rgb = COLOR_ORANGE

            card = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(6.8), Inches(6.8), Inches(1.8))
            card.fill.solid()
            card.fill.fore_color.rgb = COLOR_SOFT_BOX
            card.line.color.rgb = COLOR_CARD_BORDER

            ctb = slide.shapes.add_textbox(Inches(0.9), Inches(7.1), Inches(6.2), Inches(1.2))
            ctf = ctb.text_frame
            ctf.word_wrap = True
            cp = ctf.paragraphs[0]
            cp.text = slide_info["callout"]
            cp.font.size = Pt(13)
            cp.font.color.rgb = COLOR_DARK_SLATE

        elif page_num == 7:
            tbox = slide.shapes.add_textbox(Inches(0.6), Inches(1.4), Inches(6.8), Inches(1.2))
            ttf = tbox.text_frame
            ttf.word_wrap = True
            tp = ttf.paragraphs[0]
            tp.text = slide_info["headline"]
            tp.font.size = Pt(24)
            tp.font.bold = True
            tp.font.color.rgb = COLOR_DARK_SLATE

            c1 = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(3.0), Inches(3.2), Inches(3.0))
            c1.fill.solid()
            c1.fill.fore_color.rgb = COLOR_WHITE
            c1.line.color.rgb = COLOR_CARD_BORDER

            tb1 = slide.shapes.add_textbox(Inches(0.8), Inches(3.2), Inches(2.8), Inches(2.5))
            tf1 = tb1.text_frame
            tf1.word_wrap = True
            p1 = tf1.paragraphs[0]
            p1.text = slide_info["box_left_title"]
            p1.font.size = Pt(13)
            p1.font.bold = True
            p1.font.color.rgb = COLOR_ORANGE
            p2 = tf1.add_paragraph()
            p2.text = slide_info["box_left_desc"]
            p2.font.size = Pt(11)
            p2.font.color.rgb = COLOR_DARK_SLATE

            c2 = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(4.2), Inches(3.0), Inches(3.2), Inches(3.0))
            c2.fill.solid()
            c2.fill.fore_color.rgb = COLOR_WHITE
            c2.line.color.rgb = COLOR_CARD_BORDER

            tb2 = slide.shapes.add_textbox(Inches(4.4), Inches(3.2), Inches(2.8), Inches(2.5))
            tf2 = tb2.text_frame
            tf2.word_wrap = True
            p1 = tf2.paragraphs[0]
            p1.text = slide_info["box_right_title"]
            p1.font.size = Pt(13)
            p1.font.bold = True
            p1.font.color.rgb = COLOR_DARK_TEAL
            p2 = tf2.add_paragraph()
            p2.text = slide_info["box_right_desc"]
            p2.font.size = Pt(11)
            p2.font.color.rgb = COLOR_DARK_SLATE

            card = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(6.5), Inches(6.8), Inches(2.0))
            card.fill.solid()
            card.fill.fore_color.rgb = COLOR_SOFT_BOX
            card.line.color.rgb = COLOR_CARD_BORDER

            ctb = slide.shapes.add_textbox(Inches(0.9), Inches(6.8), Inches(6.2), Inches(1.5))
            ctf = ctb.text_frame
            ctf.word_wrap = True
            cp = ctf.paragraphs[0]
            cp.text = slide_info["callout"]
            cp.font.size = Pt(13)
            cp.font.color.rgb = COLOR_DARK_SLATE

        elif page_num == 8:
            tbox = slide.shapes.add_textbox(Inches(0.6), Inches(1.4), Inches(6.8), Inches(1.3))
            ttf = tbox.text_frame
            ttf.word_wrap = True
            tp = ttf.paragraphs[0]
            tp.text = slide_info["headline"]
            tp.font.size = Pt(23)
            tp.font.bold = True
            tp.font.color.rgb = COLOR_DARK_SLATE

            y = 3.0
            for idx, (ttitle, tdesc) in enumerate(slide_info["tiers"]):
                card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(y), Inches(6.8), Inches(1.65))
                card.fill.solid()
                card.fill.fore_color.rgb = COLOR_WHITE
                card.line.color.rgb = COLOR_CARD_BORDER

                cir = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.9), Inches(y + 0.35), Inches(0.9), Inches(0.9))
                cir.fill.solid()
                cir.fill.fore_color.rgb = COLOR_DARK_TEAL
                cir.line.color.rgb = COLOR_DARK_TEAL

                ctb = slide.shapes.add_textbox(Inches(0.9), Inches(y + 0.45), Inches(0.9), Inches(0.7))
                ctf = ctb.text_frame
                cp = ctf.paragraphs[0]
                cp.text = str(idx + 1)
                cp.font.size = Pt(20)
                cp.font.bold = True
                cp.font.color.rgb = COLOR_WHITE
                cp.alignment = PP_ALIGN.CENTER

                tb = slide.shapes.add_textbox(Inches(2.1), Inches(y + 0.2), Inches(5.1), Inches(1.2))
                tf = tb.text_frame
                tf.word_wrap = True
                p1 = tf.paragraphs[0]
                p1.text = ttitle
                p1.font.size = Pt(12)
                p1.font.bold = True
                p1.font.color.rgb = COLOR_DARK_SLATE
                p2 = tf.add_paragraph()
                p2.text = tdesc
                p2.font.size = Pt(10.5)
                p2.font.color.rgb = COLOR_MUTED_SLATE
                y += 1.85

        elif page_num == 9:
            tbox = slide.shapes.add_textbox(Inches(0.6), Inches(2.0), Inches(6.8), Inches(1.4))
            ttf = tbox.text_frame
            ttf.word_wrap = True
            tp = ttf.paragraphs[0]
            tp.text = slide_info["headline"]
            tp.font.size = Pt(25)
            tp.font.bold = True
            tp.font.color.rgb = COLOR_WHITE

            line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(3.6), Inches(1.5), Inches(0.08))
            line.fill.solid()
            line.fill.fore_color.rgb = COLOR_ORANGE
            line.line.color.rgb = COLOR_ORANGE

            qbox = slide.shapes.add_textbox(Inches(0.6), Inches(4.0), Inches(6.8), Inches(1.4))
            qtf = qbox.text_frame
            qtf.word_wrap = True
            qp = qtf.paragraphs[0]
            qp.text = slide_info["quote"]
            qp.font.size = Pt(16)
            qp.font.italic = True
            qp.font.color.rgb = COLOR_WHITE

            bbox = slide.shapes.add_textbox(Inches(0.6), Inches(5.7), Inches(6.8), Inches(2.5))
            btf = bbox.text_frame
            btf.word_wrap = True
            bp = btf.paragraphs[0]
            bp.text = slide_info["body"]
            bp.font.size = Pt(13)
            bp.font.color.rgb = COLOR_MUTED_SLATE

        elif page_num == 10:
            tbox = slide.shapes.add_textbox(Inches(0.6), Inches(1.5), Inches(6.8), Inches(1.0))
            ttf = tbox.text_frame
            ttf.word_wrap = True
            tp = ttf.paragraphs[0]
            tp.text = slide_info["headline"]
            tp.font.size = Pt(25)
            tp.font.bold = True
            tp.font.color.rgb = COLOR_DARK_SLATE

            b_card = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(2.8), Inches(3.2), Inches(5.5))
            b_card.fill.solid()
            b_card.fill.fore_color.rgb = COLOR_SOFT_BOX
            b_card.line.color.rgb = COLOR_CARD_BORDER

            btb = slide.shapes.add_textbox(Inches(0.8), Inches(3.0), Inches(2.8), Inches(5.0))
            btf = btb.text_frame
            btf.word_wrap = True
            p = btf.paragraphs[0]
            p.text = "BEFORE"
            p.font.size = Pt(13)
            p.font.bold = True
            p.font.color.rgb = COLOR_MUTED_SLATE
            for item in slide_info["before"]:
                p2 = btf.add_paragraph()
                p2.text = "✗  " + item
                p2.font.size = Pt(11)
                p2.font.color.rgb = COLOR_DARK_SLATE

            a_card = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(4.2), Inches(2.8), Inches(3.2), Inches(5.5))
            a_card.fill.solid()
            a_card.fill.fore_color.rgb = COLOR_DARK_TEAL
            a_card.line.color.rgb = COLOR_DARK_TEAL

            atb = slide.shapes.add_textbox(Inches(4.4), Inches(3.0), Inches(2.8), Inches(5.0))
            atf = atb.text_frame
            atf.word_wrap = True
            p = atf.paragraphs[0]
            p.text = "AFTER"
            p.font.size = Pt(13)
            p.font.bold = True
            p.font.color.rgb = COLOR_ORANGE
            for item in slide_info["after"]:
                p2 = atf.add_paragraph()
                p2.text = "✓  " + item
                p2.font.size = Pt(11)
                p2.font.color.rgb = COLOR_WHITE

        elif page_num == 11:
            tbox = slide.shapes.add_textbox(Inches(0.6), Inches(2.2), Inches(6.8), Inches(2.0))
            ttf = tbox.text_frame
            ttf.word_wrap = True
            tp = ttf.paragraphs[0]
            tp.text = slide_info["headline"]
            tp.font.size = Pt(36)
            tp.font.bold = True
            tp.font.color.rgb = COLOR_WHITE

            line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(4.6), Inches(1.5), Inches(0.08))
            line.fill.solid()
            line.fill.fore_color.rgb = COLOR_ORANGE
            line.line.color.rgb = COLOR_ORANGE

            qbox = slide.shapes.add_textbox(Inches(0.6), Inches(5.2), Inches(6.8), Inches(1.8))
            qtf = qbox.text_frame
            qtf.word_wrap = True
            qp = qtf.paragraphs[0]
            qp.text = slide_info["quote"]
            qp.font.size = Pt(16)
            qp.font.color.rgb = COLOR_WHITE

            bbox = slide.shapes.add_textbox(Inches(0.6), Inches(7.5), Inches(6.8), Inches(0.5))
            btf = bbox.text_frame
            bp = btf.paragraphs[0]
            bp.text = slide_info["body"]
            bp.font.size = Pt(13)
            bp.font.italic = True
            bp.font.color.rgb = COLOR_MUTED_SLATE

        elif page_num == 12:
            tbox = slide.shapes.add_textbox(Inches(0.6), Inches(1.8), Inches(6.8), Inches(4.0))
            ttf = tbox.text_frame
            ttf.word_wrap = True
            lines = slide_info["headline"].split("\n\n")
            for idx, ln in enumerate(lines):
                if idx == 0:
                    p = ttf.paragraphs[0]
                else:
                    p = ttf.add_paragraph()
                p.text = ln
                p.font.size = Pt(26)
                p.font.bold = True
                p.font.color.rgb = COLOR_ORANGE if idx == 3 else COLOR_DARK_SLATE

            cbox = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(6.8), Inches(6.8), Inches(1.6))
            cbox.fill.solid()
            cbox.fill.fore_color.rgb = COLOR_DARK_TEAL
            cbox.line.color.rgb = COLOR_DARK_TEAL

            ctb = slide.shapes.add_textbox(Inches(0.9), Inches(7.3), Inches(6.2), Inches(1.0))
            ctf = ctb.text_frame
            ctf.word_wrap = True
            cp = ctf.paragraphs[0]
            cp.text = slide_info["cta_box"]
            cp.font.size = Pt(14)
            cp.font.bold = True
            cp.font.color.rgb = COLOR_WHITE

        if not is_dark:
            fbox = slide.shapes.add_textbox(Inches(0.6), Inches(9.4), Inches(6.8), Inches(0.3))
            ftf = fbox.text_frame
            fp = ftf.paragraphs[0]
            fp.text = "3CONSULTING | DATA PROTECTION & RETENTION GOVERNANCE ADVISORY"
            fp.font.size = Pt(8.5)
            fp.font.bold = True
            fp.font.color.rgb = COLOR_MUTED_SLATE

    for p in output_paths:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        prs.save(p)
        print(f"Saved PPTX: {p}")


# ---------------------------------------------------------------------------
#  2. BUILD PDF PRESENTATION (ReportLab)
# ---------------------------------------------------------------------------

def create_pdf(output_paths):
    W, H = 576, 720  # 4:5 aspect ratio (8 x 10 inches at 72 pt/in)
    
    for path in output_paths:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        c = canvas.Canvas(path, pagesize=(W, H))

        for slide in SLIDE_DATA:
            is_dark = slide["type"] == "dark"
            page_num = slide.get("page", 1)

            c.setFillColor(RL_DARK_TEAL if is_dark else RL_CREAM)
            c.rect(0, 0, W, H, fill=1, stroke=0)

            logo_w, logo_h = 130, 60
            logo_x, logo_y = W - logo_w - 40, H - logo_h - 25

            if is_dark:
                c.setFillColor(RL_WHITE)
                c.roundRect(logo_x - 8, logo_y - 4, logo_w + 16, logo_h + 8, 4, fill=1, stroke=0)
            
            if os.path.exists(LOGO_PATH):
                c.drawImage(LOGO_PATH, logo_x, logo_y, width=logo_w, height=logo_h, preserveAspectRatio=True, mask='auto')

            if page_num > 1:
                c.setFillColor(RL_MUTED_SLATE if not is_dark else RL_WHITE)
                c.setFont("Helvetica-Bold", 11)
                c.drawRightString(W - 40, H - 35, f"{page_num} / 12")

            c.setFillColor(RL_ORANGE)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(45, H - 55, slide.get("category", ""))

            if page_num == 1:
                c.setFillColor(RL_WHITE)
                c.setFont("Helvetica-Bold", 24)
                c.drawString(45, H - 240, "Keeping Data Forever Isn't Safe.")
                c.drawString(45, H - 275, "Deleting It Blindly Is Even Worse.")

                c.setFillColor(RL_ORANGE)
                c.rect(45, H - 305, 90, 5, fill=1, stroke=0)

                c.setFillColor(RL_WHITE)
                c.setFont("Helvetica-Oblique", 14)
                c.drawString(45, H - 350, "How a structured retention lifecycle governance approach")
                c.drawString(45, H - 370, "turns toxic data liability into audit-proof compliance.")

                c.setFillColor(RL_MUTED_SLATE)
                c.setFont("Helvetica-Bold", 9)
                c.drawString(45, 40, slide["footer"])

            elif page_num == 2:
                c.setFillColor(RL_DARK_SLATE)
                c.setFont("Helvetica-Bold", 24)
                c.drawString(45, H - 125, "Collecting data isn't")
                c.drawString(45, H - 155, "the whole job.")

                c.setFont("Helvetica", 13)
                c.drawString(45, H - 210, "Organisations know how to acquire and store customer data.")
                c.setFont("Helvetica-Bold", 13)
                c.drawString(45, H - 230, "Almost none know when — or how — to legally let it go.")

                y_card = H - 330
                for title, desc in slide["items"]:
                    c.setFillColor(RL_WHITE)
                    c.setStrokeColor(RL_CARD_BORDER)
                    c.roundRect(45, y_card, W - 90, 75, 8, fill=1, stroke=1)

                    c.setFillColor(RL_ORANGE)
                    c.setFont("Helvetica-Bold", 12)
                    c.drawString(65, y_card + 48, title)

                    c.setFillColor(RL_MUTED_SLATE)
                    c.setFont("Helvetica", 10.5)
                    c.drawString(65, y_card + 24, desc)

                    y_card -= 95

            elif page_num == 3:
                c.setFillColor(RL_DARK_SLATE)
                c.setFont("Helvetica-Bold", 24)
                c.drawString(45, H - 125, "Retention doesn't stay static.")

                y_pt = H - 210
                for pt in slide["points"]:
                    c.setFillColor(RL_ORANGE)
                    c.rect(45, y_pt + 2, 18, 18, fill=1, stroke=0)

                    c.setFillColor(RL_DARK_SLATE)
                    c.setFont("Helvetica-Bold", 13)
                    c.drawString(75, y_pt + 6, pt)
                    y_pt -= 70

                c.setFillColor(RL_DARK_TEAL)
                c.rect(45, 120, W - 90, 85, fill=1, stroke=0)

                c.setFillColor(RL_WHITE)
                c.setFont("Helvetica-Oblique", 12.5)
                c.drawString(65, 168, "Yet most organisations believe having a static retention policy")
                c.drawString(65, 148, "schedule is the same as enforcing it.")

            elif page_num == 4:
                c.setFillColor(RL_WHITE)
                c.setFont("Helvetica-Bold", 24)
                c.drawString(45, H - 180, "What is automated")
                c.drawString(45, H - 210, "data retention governance?")

                c.setFillColor(RL_ORANGE)
                c.rect(45, H - 240, 90, 5, fill=1, stroke=0)

                c.setFillColor(RL_WHITE)
                c.setFont("Helvetica-Oblique", 16)
                c.drawString(45, H - 290, "The exposure an organisation carries from holding data")
                c.drawString(45, H - 315, "long after its lawful business purpose has expired.")

                c.setFillColor(RL_MUTED_SLATE)
                c.setFont("Helvetica", 13)
                c.drawString(45, H - 420, "It doesn't end when a contract terminates —")
                c.drawString(45, H - 445, "it persists until compliant disposal is executed and proven.")

            elif page_num == 5:
                c.setFillColor(RL_DARK_SLATE)
                c.setFont("Helvetica-Bold", 24)
                c.drawString(45, H - 125, "Everyone holds data.")
                c.drawString(45, H - 155, "No one holds the whole picture.")

                bx_w = 88
                bx_h = 65
                bx_gap = 12
                x_start = 45
                y_box = H - 310

                for i, dept in enumerate(slide["flow"]):
                    c.setFillColor(RL_WHITE)
                    c.setStrokeColor(RL_DARK_TEAL)
                    c.setLineWidth(1.5)
                    c.roundRect(x_start + i * (bx_w + bx_gap), y_box, bx_w, bx_h, 6, fill=1, stroke=1)

                    c.setFillColor(RL_DARK_SLATE)
                    c.setFont("Helvetica-Bold", 9.5)
                    c.drawCentredString(x_start + i * (bx_w + bx_gap) + bx_w / 2, y_box + 26, dept)

                c.setFillColor(RL_SOFT_BOX)
                c.rect(45, 160, W - 90, 160, fill=1, stroke=0)

                c.setFillColor(RL_DARK_SLATE)
                c.setFont("Helvetica", 11.5)
                c.drawString(65, 280, "Each function sees the data through its own lens — but no single function")
                c.drawString(65, 258, "sees the full risk. Marketing hoards records, IT manages storage, Legal")
                c.drawString(65, 236, "issues litigation holds via email, and the DPO lacks operational tools.")
                c.drawString(65, 214, "Retention monitoring rarely happens at all.")

            elif page_num == 6:
                c.setFillColor(RL_DARK_SLATE)
                c.setFont("Helvetica-Bold", 24)
                c.drawString(45, H - 125, "A connected data")
                c.drawString(45, H - 155, "retention lifecycle.")

                w1 = 110
                gap = 15
                y1 = H - 260
                for i, step in enumerate(slide["row1"]):
                    c.setFillColor(RL_DARK_TEAL)
                    c.roundRect(45 + i * (w1 + gap), y1, w1, 55, 6, fill=1, stroke=0)
                    c.setFillColor(RL_WHITE)
                    c.setFont("Helvetica-Bold", 10.5)
                    c.drawCentredString(45 + i * (w1 + gap) + w1 / 2, y1 + 22, step)

                w2 = 148
                y2 = H - 350
                for i, step in enumerate(slide["row2"]):
                    c.setFillColor(RL_DARK_TEAL)
                    c.roundRect(45 + i * (w2 + gap + 4), y2, w2, 55, 6, fill=1, stroke=0)
                    c.setFillColor(RL_WHITE)
                    c.setFont("Helvetica-Bold", 11)
                    c.drawCentredString(45 + i * (w2 + gap + 4) + w2 / 2, y2 + 22, step)

                c.setFillColor(RL_ORANGE)
                c.setFont("Helvetica-Oblique", 12)
                c.drawString(45, H - 435, "↪ " + slide["repeat_note"])

                c.setFillColor(RL_SOFT_BOX)
                c.rect(45, 120, W - 90, 110, fill=1, stroke=0)
                c.setFillColor(RL_DARK_SLATE)
                c.setFont("Helvetica-Bold", 12)
                c.drawString(65, 185, "This is the piece most compliance programmes are missing:")
                c.setFont("Helvetica", 12)
                c.drawString(65, 160, "an automated lifecycle engine, not a one-time gate.")

            elif page_num == 7:
                c.setFillColor(RL_DARK_SLATE)
                c.setFont("Helvetica-Bold", 23)
                c.drawString(45, H - 125, "Consent withdrawal is an")
                c.drawString(45, H - 155, "inbound signal, not an in-app button.")

                c.setFillColor(RL_WHITE)
                c.setStrokeColor(RL_CARD_BORDER)
                c.roundRect(45, H - 380, 230, 190, 8, fill=1, stroke=1)
                c.setFillColor(RL_ORANGE)
                c.setFont("Helvetica-Bold", 12)
                c.drawString(60, H - 220, slide["box_left_title"])
                c.setFillColor(RL_DARK_SLATE)
                c.setFont("Helvetica", 10.5)
                c.drawString(60, H - 250, "Customer revokes consent in CRM,")
                c.drawString(60, H - 270, "banking app, or privacy portal.")
                c.drawString(60, H - 300, "System emits REST API signal:")
                c.setFont("Courier-Bold", 9.5)
                c.setFillColor(RL_DARK_TEAL)
                c.drawString(60, H - 325, "POST /api/v1/consent/signal")

                c.setFillColor(RL_WHITE)
                c.setStrokeColor(RL_CARD_BORDER)
                c.roundRect(300, H - 380, 230, 190, 8, fill=1, stroke=1)
                c.setFillColor(RL_DARK_TEAL)
                c.setFont("Helvetica-Bold", 12)
                c.drawString(315, H - 220, slide["box_right_title"])
                c.setFillColor(RL_DARK_SLATE)
                c.setFont("Helvetica", 10.5)
                c.drawString(315, H - 250, "Captures inbound signal.")
                c.drawString(315, H - 270, "Initiates policy grace period (30d).")
                c.drawString(315, H - 290, "Enforces disposal countdown.")
                c.drawString(315, H - 310, "Dispatches deletion webhooks.")

                c.setFillColor(RL_SOFT_BOX)
                c.rect(45, 130, W - 90, 130, fill=1, stroke=0)
                c.setFillColor(RL_DARK_SLATE)
                c.setFont("Helvetica-Bold", 11.5)
                c.drawString(65, 220, "SafeData does not manage customer consent decisions.")
                c.setFont("Helvetica", 11.5)
                c.drawString(65, 198, "Your customer-facing applications and CRM do.")
                c.drawString(65, 172, "SafeData strictly governs the legal disposal obligation")
                c.drawString(65, 150, "once consent is withdrawn.")

            elif page_num == 8:
                c.setFillColor(RL_DARK_SLATE)
                c.setFont("Helvetica-Bold", 22)
                c.drawString(45, H - 125, "Should sensitive banking data get the same")
                c.drawString(45, H - 155, "scrutiny as simple marketing leads?")

                y_tier = H - 290
                for idx, (ttitle, tdesc) in enumerate(slide["tiers"]):
                    c.setFillColor(RL_WHITE)
                    c.setStrokeColor(RL_CARD_BORDER)
                    c.roundRect(45, y_tier, W - 90, 100, 8, fill=1, stroke=1)

                    c.setFillColor(RL_DARK_TEAL)
                    c.circle(85, y_tier + 50, 22, fill=1, stroke=0)
                    c.setFillColor(RL_WHITE)
                    c.setFont("Helvetica-Bold", 14)
                    c.drawCentredString(85, y_tier + 45, str(idx + 1))

                    c.setFillColor(RL_DARK_SLATE)
                    c.setFont("Helvetica-Bold", 11.5)
                    c.drawString(120, y_tier + 68, ttitle)

                    c.setFillColor(RL_MUTED_SLATE)
                    c.setFont("Helvetica", 9.5)
                    words = tdesc.split()
                    l1 = " ".join(words[:11])
                    l2 = " ".join(words[11:])
                    c.drawString(120, y_tier + 48, l1)
                    c.drawString(120, y_tier + 32, l2)

                    y_tier -= 120

            elif page_num == 9:
                c.setFillColor(RL_WHITE)
                c.setFont("Helvetica-Bold", 23)
                c.drawString(45, H - 180, "If you cannot prove you deleted it,")
                c.drawString(45, H - 210, "in the eyes of the regulator, you never did.")

                c.setFillColor(RL_ORANGE)
                c.rect(45, H - 235, 90, 5, fill=1, stroke=0)

                c.setFillColor(RL_WHITE)
                c.setFont("Helvetica-Oblique", 14)
                c.drawString(45, H - 280, "When data protection authorities audit your organisation,")
                c.drawString(45, H - 302, "verbal assurances and deleted database flags fail.")

                c.setFillColor(RL_MUTED_SLATE)
                c.setFont("Helvetica", 12.5)
                c.drawString(45, H - 360, "SafeData binds every lifecycle decision into an immutable,")
                c.drawString(45, H - 382, "SHA-256 hash-chained audit ledger.")
                c.drawString(45, H - 420, "Automated background tasks verify cryptographic chain integrity")
                c.drawString(45, H - 442, "every 6 hours to provide indisputable regulatory proof.")

            elif page_num == 10:
                c.setFillColor(RL_DARK_SLATE)
                c.setFont("Helvetica-Bold", 24)
                c.drawString(45, H - 125, "From toxic data liability")
                c.drawString(45, H - 155, "to continuous compliance.")

                c.setFillColor(RL_SOFT_BOX)
                c.rect(45, 140, 230, 380, fill=1, stroke=0)
                c.setFillColor(RL_MUTED_SLATE)
                c.setFont("Helvetica-Bold", 12)
                c.drawString(60, 480, "BEFORE")

                y_it = 440
                for it in slide["before"]:
                    c.setFillColor(RL_ORANGE)
                    c.setFont("Helvetica-Bold", 11)
                    c.drawString(60, y_it, "✗")
                    c.setFillColor(RL_DARK_SLATE)
                    c.setFont("Helvetica", 10.5)
                    c.drawString(78, y_it, it)
                    y_it -= 50

                c.setFillColor(RL_DARK_TEAL)
                c.rect(300, 140, 230, 380, fill=1, stroke=0)
                c.setFillColor(RL_ORANGE)
                c.setFont("Helvetica-Bold", 12)
                c.drawString(315, 480, "AFTER")

                y_it = 440
                for it in slide["after"]:
                    c.setFillColor(RL_WHITE)
                    c.setFont("Helvetica-Bold", 11)
                    c.drawString(315, y_it, "✓")
                    c.setFont("Helvetica", 10.5)
                    c.drawString(333, y_it, it)
                    y_it -= 50

            elif page_num == 11:
                c.setFillColor(RL_WHITE)
                c.setFont("Helvetica", 16)
                c.drawString(45, H - 210, "Introducing")
                c.setFont("Helvetica-Bold", 36)
                c.drawString(45, H - 260, "SafeData")

                c.setFillColor(RL_ORANGE)
                c.rect(45, H - 285, 90, 5, fill=1, stroke=0)

                c.setFillColor(RL_WHITE)
                c.setFont("Helvetica", 14.5)
                c.drawString(45, H - 340, "Automated data retention register, event-driven disposal")
                c.drawString(45, H - 365, "governance, and cryptographic compliance proof —")
                c.drawString(45, H - 390, "brought together in one global platform.")

                c.setFillColor(RL_MUTED_SLATE)
                c.setFont("Helvetica-Oblique", 13)
                c.drawString(45, H - 460, "Built by 3Consulting")

            elif page_num == 12:
                c.setFillColor(RL_DARK_SLATE)
                c.setFont("Helvetica-Bold", 24)
                c.drawString(45, H - 180, "Know your data.")
                c.drawString(45, H - 240, "Automate its retention clock.")
                c.drawString(45, H - 300, "Govern its lawful disposal.")
                c.setFillColor(RL_ORANGE)
                c.drawString(45, H - 360, "Prove compliance beyond doubt.")

                c.setFillColor(RL_DARK_TEAL)
                c.rect(45, 140, W - 90, 110, fill=1, stroke=0)

                c.setFillColor(RL_WHITE)
                c.setFont("Helvetica-Bold", 13.5)
                c.drawString(65, 195, "Read the full case study & explore SafeData —")
                c.drawString(65, 172, "link in the comments.")

            if not is_dark:
                c.setFillColor(RL_MUTED_SLATE)
                c.setFont("Helvetica-Bold", 8)
                c.drawString(45, 30, "3CONSULTING | DATA PROTECTION & RETENTION GOVERNANCE ADVISORY")

            c.showPage()

        c.save()
        print(f"Saved PDF: {path}")


if __name__ == "__main__":
    pptx_targets = [PPTX_PATH_1, PPTX_PATH_2]
    pdf_targets = [PDF_PATH_1, PDF_PATH_2]
    
    print("Generating PPTX...")
    create_pptx(pptx_targets)
    
    print("Generating PDF...")
    create_pdf(pdf_targets)
    print("Execution complete.")
