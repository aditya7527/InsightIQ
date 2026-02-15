"""
PDF Report Generation Engine
Creates executive-grade PDF reports from analytics and insights
"""
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
from typing import Dict, Optional, List
import io


def generate_executive_report(
    dataset_name: str,
    analytics_data: Dict,
    confidence_score: int,
    industry: str,
    root_causes: Optional[Dict] = None,
    forecasts: Optional[List] = None
) -> io.BytesIO:
    """
    Generate executive PDF report
    
    Args:
        dataset_name: Name of dataset
        analytics_data: Analytics results
        confidence_score: Data confidence (0-100)
        industry: Detected industry
        root_causes: Root cause analysis results
        forecasts: Forecast data
    
    Returns:
        BytesIO object with PDF content
    """
    
    # Create PDF
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Build content
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#667eea'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#764ba2'),
        spaceAfter=12,
        spaceBefore=12
    )
    
    # ========== COVER PAGE ==========
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph("📊 EXECUTIVE REPORT", title_style))
    story.append(Spacer(1, 0.5*inch))
    
    # Cover table
    cover_data = [
        ['Dataset', dataset_name],
        ['Industry', industry.title()],
        ['Generated', datetime.now().strftime('%Y-%m-%d %H:%M')],
        ['Data Quality', f"{confidence_score}% - " + get_quality_label(confidence_score)]
    ]
    
    cover_table = Table(cover_data, colWidths=[2*inch, 3.5*inch])
    cover_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
    ]))
    story.append(cover_table)
    story.append(PageBreak())
    
    # ========== EXECUTIVE SUMMARY ==========
    story.append(Paragraph("Executive Summary", heading_style))
    
    total_rows = analytics_data.get('total_rows', 0)
    total_cols = analytics_data.get('total_columns', 0)
    
    summary_text = f"""
    This report presents a comprehensive analysis of your dataset containing 
    <b>{total_rows:,}</b> records across <b>{total_cols}</b> dimensions. 
    The data quality score of <b>{confidence_score}%</b> indicates {get_quality_label(confidence_score).lower()} 
    data reliability. The detected industry is <b>{industry.title()}</b>, 
    and analysis recommendations are tailored accordingly.
    """
    
    story.append(Paragraph(summary_text, styles['BodyText']))
    story.append(Spacer(1, 0.3*inch))
    
    # ========== KEY METRICS ==========
    story.append(Paragraph("Key Metrics", heading_style))
    
    metrics_data = [
        ['Metric', 'Value'],
        ['Total Records', f"{total_rows:,}"],
        ['Dimensions', f"{total_cols}"],
        ['Data Quality Score', f"{confidence_score}%"],
        ['Numeric Columns', f"{len(analytics_data.get('numeric_summary', []))}"],
        ['Categorical Columns', f"{len(analytics_data.get('categorical_summary', []))}"]
    ]
    
    metrics_table = Table(metrics_data, colWidths=[3*inch, 2.5*inch])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), TA_CENTER),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 0.3*inch))
    
    # ========== NUMERIC SUMMARY ==========
    if analytics_data.get('numeric_summary'):
        story.append(Paragraph("Numeric Analysis", heading_style))
        
        numeric_data = [['Column', 'Mean', 'Min', 'Max', 'Std Dev']]
        for col in analytics_data['numeric_summary'][:5]:
            numeric_data.append([
                col['name'],
                f"{col['mean']:.2f}",
                f"{col['min']:.2f}",
                f"{col['max']:.2f}",
                f"{col['std']:.2f}"
            ])
        
        numeric_table = Table(numeric_data, colWidths=[1.5*inch, 1*inch, 1*inch, 1*inch, 1.5*inch])
        numeric_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        story.append(numeric_table)
        story.append(Spacer(1, 0.3*inch))
    
    # ========== ROOT CAUSE ANALYSIS ==========
    if root_causes and root_causes.get('top_drivers'):
        story.append(PageBreak())
        story.append(Paragraph("Key Drivers & Root Causes", heading_style))
        
        drivers_text = "The following factors have the most significant impact on your metrics:<br/><br/>"
        for i, driver in enumerate(root_causes['top_drivers'][:5], 1):
            contribution = driver.get('contribution_percent', 0)
            drivers_text += f"<b>{i}. {driver['factor']}</b> - {contribution}% impact<br/>"
        
        story.append(Paragraph(drivers_text, styles['BodyText']))
        story.append(Spacer(1, 0.2*inch))
        
        if root_causes.get('recommendations'):
            story.append(Paragraph("Recommendations:", heading_style))
            for rec in root_causes['recommendations'][:3]:
                story.append(Paragraph(f"• {rec}", styles['BodyText']))
        
        story.append(Spacer(1, 0.3*inch))
    
    # ========== FORECASTS ==========
    if forecasts:
        story.append(Paragraph("3-Month Forecast", heading_style))
        
        forecast_text = "Based on historical trends, the following 3-month forecast is projected:<br/><br/>"
        forecast_data = [['Period', 'Date', 'Predicted Value']]
        
        for forecast in forecasts[:3]:
            forecast_data.append([
                f"M{forecast['period']}",
                forecast['date'],
                f"${forecast['predicted']:,.0f}"
            ])
        
        forecast_table = Table(forecast_data, colWidths=[1*inch, 2*inch, 2.5*inch])
        forecast_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#764ba2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        story.append(forecast_table)
        story.append(Spacer(1, 0.3*inch))
    
    # ========== FOOTER ==========
    story.append(Spacer(1, 0.5*inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    story.append(Paragraph(
        "InsightIQ - AI-Powered Business Intelligence | Confidential",
        footer_style
    ))
    
    # Build PDF
    doc.build(story)
    pdf_buffer.seek(0)
    
    return pdf_buffer


def get_quality_label(score: int) -> str:
    """Get quality description based on score"""
    if score >= 80:
        return "Excellent"
    elif score >= 60:
        return "Good"
    elif score >= 40:
        return "Fair"
    else:
        return "Poor"
