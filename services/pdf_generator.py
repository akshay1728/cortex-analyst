"""PDF Generator Service for Manufacturing OEE Application."""

import io
from datetime import datetime
import pandas as pd
from PIL import Image as PILImage

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generate_conversation_pdf(
    messages: list,
    logo_bytes: bytes = None,
    title: str = "OEE Conversational Analytics Report",
    subtitle: str = "Manufacturing Plant Performance Insights"
) -> bytes:
    """Generate a PDF document containing the conversation history, logo, title, and timestamp."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#242B6B')
    )

    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#6C7290')
    )

    meta_style = ParagraphStyle(
        'MetaText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1E2233')
    )

    user_bubble_style = ParagraphStyle(
        'UserBubble',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#1E2233')
    )

    assistant_bubble_style = ParagraphStyle(
        'AssistantBubble',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#1E2233')
    )

    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Code'],
        fontName='Courier',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#242B6B'),
        backColor=colors.HexColor('#F6F7FD')
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#1E2233')
    )

    elements = []

    # --- Header Section (Logo + Title + Meta) ---
    header_data = []
    logo_img = None
    if logo_bytes:
        try:
            pil_img = PILImage.open(io.BytesIO(logo_bytes))
            w, h = pil_img.size
            aspect = h / float(w)
            target_w = 110
            target_h = min(60, target_w * aspect)
            logo_img = RLImage(io.BytesIO(logo_bytes), width=target_w, height=target_h)
        except Exception:
            logo_img = None

    download_date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    header_text_elements = [
        Paragraph(title, title_style),
        Spacer(1, 4),
        Paragraph(subtitle, subtitle_style),
        Spacer(1, 6),
        Paragraph(f"<b>Downloaded Date:</b> {download_date_str}", meta_style)
    ]

    if logo_img:
        header_table = Table([[header_text_elements, logo_img]], colWidths=[420, 120])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))
        elements.append(header_table)
    else:
        for elem in header_text_elements:
            elements.append(elem)

    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#E4E7F3'), spaceAfter=15))

    # --- Conversation Body ---
    for idx, msg in enumerate(messages):
        role = msg.get("role", "user")
        content = msg.get("content", "")

        # Clean basic markdown bold formatting for ReportLab paragraph tags
        clean_content = content.replace("**", "<b>").replace("**", "</b>") if content else ""
        clean_content = clean_content.replace("\n", "<br/>")

        if role == "user":
            role_p = Paragraph("<b>🧑‍🏭 User</b>", meta_style)
            msg_p = Paragraph(clean_content, user_bubble_style)
            card_table = Table([[role_p], [Spacer(1, 4)], [msg_p]], colWidths=[540])
            card_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F3F5FC')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#E4E7F3')),
                ('ROUNDEDCORNERS', [6, 6, 6, 6]),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ]))
            elements.append(card_table)
            elements.append(Spacer(1, 10))

        else:
            role_p = Paragraph("<b>🤖 Assistant</b>", meta_style)
            msg_p = Paragraph(clean_content, assistant_bubble_style)
            inner_elements = [role_p, Spacer(1, 4), msg_p]

            sql_query = msg.get("sql_query")
            if sql_query:
                inner_elements.append(Spacer(1, 6))
                inner_elements.append(Paragraph("<b>Generated SQL Query:</b>", meta_style))
                sql_clean = sql_query.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
                inner_elements.append(Paragraph(sql_clean, code_style))

            data = msg.get("data")
            if data is not None and isinstance(data, pd.DataFrame) and not data.empty:
                inner_elements.append(Spacer(1, 8))
                inner_elements.append(Paragraph("<b>Queried Data:</b>", meta_style))

                # Format dataframe for PDF table
                df_subset = data.head(15)  # Limit rows for PDF layout
                cols = list(df_subset.columns)
                table_rows = [[Paragraph(str(c), table_header_style) for c in cols]]

                for _, row in df_subset.iterrows():
                    row_cells = []
                    for val in row:
                        val_str = f"{val:.2f}" if isinstance(val, (float, int)) and not isinstance(val, bool) else str(val)
                        row_cells.append(Paragraph(val_str, table_cell_style))
                    table_rows.append(row_cells)

                # Calculate col widths
                num_cols = len(cols)
                col_width = max(40, min(520 / num_cols, 120))
                df_table = Table(table_rows, colWidths=[col_width] * num_cols)
                df_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#242B6B')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E4E7F3')),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ]))
                inner_elements.append(df_table)

            card_table = Table([[inner_elements]], colWidths=[540])
            card_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFFFFF')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#E4E7F3')),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ]))
            elements.append(card_table)
            elements.append(Spacer(1, 10))

    doc.build(elements)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data
