"""PDF Generator Service for Manufacturing OEE Application."""

import io
import re
import html
import logging
from datetime import datetime
import pandas as pd
from PIL import Image as PILImage

import plotly.graph_objects as go
import plotly.io as pio

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

logger = logging.getLogger("pdf_generator")


def _markdown_to_reportlab_html(text: str) -> str:
    """Helper to convert markdown string to ReportLab compatible HTML."""
    if not text:
        return ""

    # 1. Strip emojis that are unsupported by Helvetica font in ReportLab
    text_clean = re.sub(r'[\U00010000-\U0010FFFF\u2600-\u27FF]', '', str(text))

    # 2. Convert markdown headers (### Title) to bold text before escaping
    text_clean = re.sub(r'(?m)^#{1,6}\s*(.*?)$', r'**\1**', text_clean)

    # 3. Escape HTML XML entities
    escaped = html.escape(text_clean)

    # 4. Convert **bold** to <b>bold</b> and *italic* to <i>italic</i>
    formatted = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', escaped, flags=re.DOTALL)
    formatted = re.sub(r'\*(.*?)\*', r'<i>\1</i>', formatted, flags=re.DOTALL)

    # 5. Convert newlines to <br/>
    formatted = formatted.replace('\n', '<br/>')

    return formatted


def _convert_figure_to_rl_image(fig_obj, width: float = 480, height: float = 230) -> RLImage:
    """Convert any Plotly figure representation (Figure, dict, json) into a ReportLab Image flowable."""
    if fig_obj is None:
        return None

    img_bytes = None

    try:
        # If it's already a Plotly Figure or has to_image
        if hasattr(fig_obj, "to_image"):
            try:
                img_bytes = fig_obj.to_image(format="png", width=750, height=360, scale=2)
            except Exception as e1:
                logger.warning(f"Direct fig_obj.to_image failed: {e1}")

        # If it's a dict or couldn't call to_image directly
        if img_bytes is None and isinstance(fig_obj, dict):
            try:
                fig = go.Figure(fig_obj)
                img_bytes = pio.to_image(fig, format="png", width=750, height=360, scale=2)
            except Exception as e2:
                logger.warning(f"pio.to_image with dict failed: {e2}")

        # If fig_obj is a go.Figure or has update_layout, sanitize colors & enforce explicit light background
        if hasattr(fig_obj, "update_layout"):
            try:
                fig_obj.update_layout(template="plotly_white", paper_bgcolor="white", plot_bgcolor="#F8F9FE")

                # Sanitize bar and histogram trace colors so they don't render as black
                if hasattr(fig_obj, "data"):
                    for trace in fig_obj.data:
                        trace_type = getattr(trace, "type", "")
                        if trace_type in ("bar", "histogram"):
                            m_color = getattr(trace.marker, "color", None) if hasattr(trace, "marker") else None
                            # If marker color is black, dark, or unset, override with brand navy blue
                            if m_color in ("black", "#000000", "#000", "rgb(0,0,0)", "rgb(0, 0, 0)", None):
                                trace.marker.color = "#242B6B"
                            if hasattr(trace, "textfont"):
                                trace.textfont.color = "white"
            except Exception as e_layout:
                logger.warning(f"Error sanitizing fig_obj layout colors: {e_layout}")

        # Fallback using pio.to_image directly
        if img_bytes is None:
            try:
                img_bytes = pio.to_image(fig_obj, format="png", width=750, height=360, scale=2)
            except Exception as e3:
                logger.warning(f"Fallback pio.to_image failed: {e3}")

        if img_bytes:
            # Composite RGBA image over clean solid white RGB canvas to preserve vibrant colors
            pil_img = PILImage.open(io.BytesIO(img_bytes))
            rgb_canvas = PILImage.new("RGB", pil_img.size, (255, 255, 255))
            if pil_img.mode in ("RGBA", "LA"):
                alpha = pil_img.split()[-1]
                rgb_canvas.paste(pil_img, mask=alpha)
            else:
                rgb_canvas.paste(pil_img.convert("RGB"))

            out_buf = io.BytesIO()
            rgb_canvas.save(out_buf, format="PNG")
            img_bytes = out_buf.getvalue()

            img_buf = io.BytesIO(img_bytes)
            return RLImage(img_buf, width=width, height=height)

    except Exception as e:
        logger.error(f"Error rendering chart to image for PDF: {e}")

    return None


def generate_conversation_pdf(
    messages: list,
    logo_bytes: bytes = None,
    title: str = "OEE Conversational Analytics Report",
    subtitle: str = "Manufacturing Plant Performance Insights"
) -> bytes:
    """Generate a PDF document containing the conversation history, logo, title, charts, and timestamp."""
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
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#242B6B')
    )

    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#6C7290')
    )

    meta_style = ParagraphStyle(
        'MetaText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#1E2233')
    )

    user_bubble_style = ParagraphStyle(
        'UserBubble',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#1E2233')
    )

    assistant_bubble_style = ParagraphStyle(
        'AssistantBubble',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
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
    logo_img = None
    if logo_bytes:
        try:
            pil_img = PILImage.open(io.BytesIO(logo_bytes))
            w, h = pil_img.size
            aspect = h / float(w)
            target_w = 110
            target_h = min(50, target_w * aspect)
            logo_img = RLImage(io.BytesIO(logo_bytes), width=target_w, height=target_h)
        except Exception:
            logo_img = None

    download_date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    header_text_elements = [
        Paragraph(_markdown_to_reportlab_html(title), title_style),
        Spacer(1, 3),
        Paragraph(_markdown_to_reportlab_html(subtitle), subtitle_style),
        Spacer(1, 4),
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

    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#E4E7F3'), spaceAfter=12))

    # --- Conversation Body ---
    for idx, msg in enumerate(messages):
        role = msg.get("role", "user")

        # Extract text content display string
        display_str = msg.get("display")
        if not display_str:
            content_val = msg.get("content", "")
            if isinstance(content_val, str):
                display_str = content_val
            elif isinstance(content_val, list):
                display_str = " ".join([
                    item.get("text", "") for item in content_val
                    if isinstance(item, dict) and item.get("type") == "text"
                ])
            else:
                display_str = str(content_val)

        clean_content = _markdown_to_reportlab_html(display_str)

        if role == "user":
            role_p = Paragraph("<b>User</b>", meta_style)
            msg_p = Paragraph(clean_content, user_bubble_style)

            u_table = Table([[role_p], [Spacer(1, 3)], [msg_p]], colWidths=[540])
            u_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F3F5FC')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#E4E7F3')),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ]))
            elements.append(u_table)
            elements.append(Spacer(1, 8))

        else:
            # Assistant Message Header & Text
            role_p = Paragraph("<b>Assistant</b>", meta_style)
            msg_p = Paragraph(clean_content, assistant_bubble_style)

            a_head_table = Table([[role_p], [Spacer(1, 3)], [msg_p]], colWidths=[540])
            a_head_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFFFFF')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#E4E7F3')),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ]))
            elements.append(a_head_table)
            elements.append(Spacer(1, 6))

            # Generated SQL Block
            sql_query = msg.get("sql_query")
            if sql_query:
                sql_title = Paragraph("<b>Generated SQL Query:</b>", meta_style)
                sql_clean = html.escape(str(sql_query)).replace("\n", "<br/>")
                sql_p = Paragraph(sql_clean, code_style)
                sql_table = Table([[sql_title], [Spacer(1, 2)], [sql_p]], colWidths=[540])
                sql_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8F9FE')),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E4E7F3')),
                    ('TOPPADDING', (0, 0), (-1, -1), 5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ]))
                elements.append(sql_table)
                elements.append(Spacer(1, 6))

            # Chart Visualization Block - extract figure from figure or chart_result
            fig = msg.get("figure")
            if fig is None and "chart_result" in msg and msg["chart_result"]:
                chart_res = msg["chart_result"]
                if hasattr(chart_res, "figure"):
                    fig = chart_res.figure
                elif isinstance(chart_res, dict) and "figure" in chart_res:
                    fig = chart_res["figure"]

            if fig is not None:
                rl_chart_img = _convert_figure_to_rl_image(fig, width=480, height=230)
                if rl_chart_img:
                    chart_title = Paragraph("<b>📊 Visualization Chart:</b>", meta_style)
                    chart_table = Table([[chart_title], [Spacer(1, 4)], [rl_chart_img]], colWidths=[540])
                    chart_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFFFFF')),
                        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E4E7F3')),
                        ('ALIGN', (0, 2), (0, 2), 'CENTER'),
                        ('TOPPADDING', (0, 0), (-1, -1), 6),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                        ('LEFTPADDING', (0, 0), (-1, -1), 8),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ]))
                    elements.append(KeepTogether([chart_table]))
                    elements.append(Spacer(1, 6))

            # Check for Cortex Agent blocks (chart / tool_results)
            blocks = msg.get("blocks", [])
            if isinstance(blocks, list):
                from services.cortex_agent import tool_results_to_df
                for b in blocks:
                    if b.get("type") == "tool_results":
                        block_df = tool_results_to_df(b.get("content"))
                        if block_df is not None and not block_df.empty:
                            msg["data"] = block_df

            # Queried Data Table Block
            data = msg.get("data")
            if data is not None and isinstance(data, pd.DataFrame) and not data.empty:
                data_title = Paragraph("<b>📋 Queried Data Table:</b>", meta_style)
                df_subset = data.head(15)  # Limit rows for PDF layout
                cols = list(df_subset.columns)
                table_rows = [[Paragraph(html.escape(str(c)), table_header_style) for c in cols]]

                for _, row in df_subset.iterrows():
                    row_cells = []
                    for val in row:
                        val_str = f"{val:.2f}" if isinstance(val, (float, int)) and not isinstance(val, bool) else str(val)
                        row_cells.append(Paragraph(html.escape(val_str), table_cell_style))
                    table_rows.append(row_cells)

                num_cols = len(cols)
                col_width = max(40, min(520 / num_cols, 120))
                df_table = Table(table_rows, colWidths=[col_width] * num_cols)
                df_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#242B6B')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E4E7F3')),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ]))

                dt_container = Table([[data_title], [Spacer(1, 3)], [df_table]], colWidths=[540])
                dt_container.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFFFFF')),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E4E7F3')),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ]))
                elements.append(dt_container)
                elements.append(Spacer(1, 6))

            elements.append(Spacer(1, 4))

    doc.build(elements)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data
