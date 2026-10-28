"""
MoMo Shield — Report Export Utilities
Generates PDF and Excel reports from detection results.
"""
import io
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_pdf_report(job, transactions) -> bytes:
    """Generate a PDF fraud report using ReportLab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph,
        Spacer, HRFlowable
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
                             topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    title_style = ParagraphStyle('Title', fontSize=18, fontName='Helvetica-Bold',
                                  spaceAfter=6, textColor=colors.HexColor('#0d1f2d'))
    elements.append(Paragraph("MoMo Shield — Fraud Detection Report", title_style))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%d %b %Y %H:%M')} | "
                               f"Job #{job.pk}: {job.original_filename}", styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#00d68f')))
    elements.append(Spacer(1, 0.4*cm))

    # Summary table
    summary_data = [
        ['Metric', 'Value'],
        ['Total Transactions', str(job.total_records)],
        ['Fraud Detected', str(job.fraud_count)],
        ['Legitimate', str(job.legitimate_count)],
        ['Fraud Rate', f"{job.fraud_rate:.2f}%"],
    ]
    summary_table = Table(summary_data, colWidths=[8*cm, 6*cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d1f2d')),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f9ff')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d0d8e4')),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.6*cm))

    # Fraud transactions table
    elements.append(Paragraph("Flagged Transactions", styles['Heading2']))
    elements.append(Spacer(1, 0.2*cm))

    fraud_txns = transactions.filter(is_fraud=True)[:100]
    if fraud_txns:
        headers = ['Transaction ID', 'Sender', 'Amount (UGX)', 'Type', 'Prob.', 'Risk']
        rows = [headers]
        for t in fraud_txns:
            rows.append([
                t.transaction_id,
                t.sender,
                f"{int(t.amount):,}",
                t.transaction_type,
                f"{t.fraud_probability:.1%}",
                t.risk_level.upper(),
            ])
        txn_table = Table(rows, colWidths=[3.5*cm, 3.5*cm, 2.5*cm, 2.5*cm, 1.8*cm, 1.8*cm])
        txn_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#c0392b')),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, -1), 7),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fff5f5')]),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e0c0c0')),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(txn_table)
    else:
        elements.append(Paragraph("No fraud transactions detected.", styles['Normal']))

    doc.build(elements)
    return buf.getvalue()


def generate_excel_report(job, transactions) -> bytes:
    """Generate an Excel report using openpyxl."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()

    # Summary sheet
    ws_summary = wb.active
    ws_summary.title = "Summary"
    header_fill = PatternFill("solid", fgColor="0D1F2D")
    header_font = Font(bold=True, color="FFFFFF")

    ws_summary['A1'] = 'MoMo Shield Fraud Detection Report'
    ws_summary['A1'].font = Font(bold=True, size=14)
    ws_summary['A2'] = f"Job: {job.original_filename} | Generated: {datetime.now().strftime('%d %b %Y %H:%M')}"

    summary_rows = [
        ['Metric', 'Value'],
        ['Total Transactions', job.total_records],
        ['Fraud Detected', job.fraud_count],
        ['Legitimate', job.legitimate_count],
        ['Fraud Rate (%)', round(job.fraud_rate, 2)],
    ]
    for i, row in enumerate(summary_rows, start=4):
        for j, val in enumerate(row, start=1):
            cell = ws_summary.cell(row=i, column=j, value=val)
            if i == 4:
                cell.fill = header_fill
                cell.font = header_font

    # Transactions sheet
    ws_txn = wb.create_sheet("All Transactions")
    txn_headers = ['Transaction ID', 'Sender', 'Receiver', 'Amount (UGX)',
                   'Type', 'Is Fraud', 'Fraud Probability', 'Fraud Score', 'Risk Level']
    for j, h in enumerate(txn_headers, 1):
        cell = ws_txn.cell(row=1, column=j, value=h)
        cell.fill = header_fill
        cell.font = header_font

    for i, t in enumerate(transactions[:10000], start=2):
        ws_txn.cell(row=i, column=1, value=t.transaction_id)
        ws_txn.cell(row=i, column=2, value=t.sender)
        ws_txn.cell(row=i, column=3, value=t.receiver)
        ws_txn.cell(row=i, column=4, value=float(t.amount))
        ws_txn.cell(row=i, column=5, value=t.transaction_type)
        ws_txn.cell(row=i, column=6, value='YES' if t.is_fraud else 'NO')
        ws_txn.cell(row=i, column=7, value=round(t.fraud_probability or 0, 4))
        ws_txn.cell(row=i, column=8, value=round(t.fraud_score or 0, 2))
        ws_txn.cell(row=i, column=9, value=t.risk_level.upper())

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
