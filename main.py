import yaml
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import csv
from typing import List, Dict, Any, Optional
from nicegui import ui
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.units import inch
from reportlab.lib import colors
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

# ============================================================================
# KONFIGURATION LADEN
# ============================================================================
import argparse

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--data-path', dest='data_path', type=str, default=None)
args, _ = parser.parse_known_args()

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

MEASUREMENTS_PATH = Path(args.data_path) if args.data_path else Path(config['data']['measurements_path'])

# ============================================================================
# DATENLADEN UND PARSING
# ============================================================================
def load_measurements() -> List[Dict[str, Any]]:
    """Lädt alle CSV-Dateien aus dem Messprotokoll-Verzeichnis."""
    measurements = []
    
    if not MEASUREMENTS_PATH.exists():
        return measurements
    
    for csv_file in sorted(MEASUREMENTS_PATH.glob('Breitbandmessung_*.csv')):
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    try:
                        # Datum und Zeit zusammenführen
                        date_str = row.get('Messzeitpunkt', '').strip('"')
                        time_str = row.get('Uhrzeit', '').strip('"')
                        datetime_str = f"{date_str} {time_str}"
                        
                        # Deutsche Datumsformat zu deutschem Objektformat
                        measurement_date = datetime.strptime(datetime_str, "%d.%m.%Y %H:%M:%S")
                        
                        measurements.append({
                            'datetime': measurement_date,
                            'date': date_str,
                            'time': time_str,
                            'download': float(row.get('Download (Mbit/s)', '0').replace(',', '.')),
                            'upload': float(row.get('Upload (Mbit/s)', '0').replace(',', '.')),
                            'ping': float(row.get('Laufzeit (ms)', '0')),
                            'test_id': row.get('Test-ID', '').strip('"'),
                            'version': row.get('Version', '').strip('"'),
                            'os': row.get('Betriebssystem', '').strip('"'),
                            'browser': row.get('Internet-Browser', '').strip('"'),
                        })
                    except ValueError as e:
                        print(f"Fehler beim Parsen der Zeile: {e}")
                        continue
        except Exception as e:
            print(f"Fehler beim Lesen von {csv_file}: {e}")
            continue
    
    return sorted(measurements, key=lambda x: x['datetime'])

def filter_measurements_by_timeframe(measurements: List[Dict], days: int) -> List[Dict]:
    """Filtert Messungen nach Zeitfenster (letzte X Tage)."""
    cutoff_date = datetime.now() - timedelta(days=days)
    return [m for m in measurements if m['datetime'] >= cutoff_date]

# ============================================================================
# STATISTIKFUNKTIONEN
# ============================================================================
def calculate_statistics(measurements: List[Dict]) -> Dict[str, Any]:
    """Berechnet Statistiken für eine Liste von Messungen."""
    if not measurements:
        return {
            'count': 0, 'avg_download': 0, 'avg_upload': 0, 'avg_ping': 0,
            'min_download': 0, 'max_download': 0, 'min_upload': 0, 'max_upload': 0,
            'min_ping': 0, 'max_ping': 0
        }
    
    downloads = [m['download'] for m in measurements]
    uploads = [m['upload'] for m in measurements]
    pings = [m['ping'] for m in measurements]
    
    return {
        'count': len(measurements),
        'avg_download': sum(downloads) / len(downloads),
        'avg_upload': sum(uploads) / len(uploads),
        'avg_ping': sum(pings) / len(pings),
        'min_download': min(downloads),
        'max_download': max(downloads),
        'min_upload': min(uploads),
        'max_upload': max(uploads),
        'min_ping': min(pings),
        'max_ping': max(pings),
    }

def export_to_markdown(rows: List[Dict]) -> str:
    """Erstellt Markdown-Tabelle aus Messungen."""
    if not rows:
        return "# Breitbandmessung Export\n\nKeine Daten verfügbar."
    
    markdown = "# Breitbandmessung - Messdaten Export\n\n"
    markdown += f"**Exportiert am**: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
    markdown += f"**Anzahl Messungen**: {len(rows)}\n\n"
    
    markdown += "## Statistiken\n\n"
    downloads = [float(r['Download (Mbit/s)']) for r in rows]
    uploads = [float(r['Upload (Mbit/s)']) for r in rows]
    pings = [float(r['Ping (ms)']) for r in rows]
    
    markdown += f"| Metrik | Wert |\n"
    markdown += f"|--------|------|\n"
    markdown += f"| Ø Download | {sum(downloads)/len(downloads):.2f} Mbit/s |\n"
    markdown += f"| Min Download | {min(downloads):.2f} Mbit/s |\n"
    markdown += f"| Max Download | {max(downloads):.2f} Mbit/s |\n"
    markdown += f"| Ø Upload | {sum(uploads)/len(uploads):.2f} Mbit/s |\n"
    markdown += f"| Min Upload | {min(uploads):.2f} Mbit/s |\n"
    markdown += f"| Max Upload | {max(uploads):.2f} Mbit/s |\n"
    markdown += f"| Ø Ping | {sum(pings)/len(pings):.2f} ms |\n"
    markdown += f"| Min Ping | {min(pings):.2f} ms |\n"
    markdown += f"| Max Ping | {max(pings):.2f} ms |\n\n"
    
    markdown += "## Messdaten\n\n"
    markdown += "| Datum/Uhrzeit | Download | Upload | Ping | OS | Browser |\n"
    markdown += "|---|---|---|---|---|---|\n"
    for row in rows:
        markdown += f"| {row['Datum/Uhrzeit']} | {row['Download (Mbit/s)']} | {row['Upload (Mbit/s)']} | {row['Ping (ms)']} | {row['Betriebssystem']} | {row['Internet-Browser']} |\n"
    
    return markdown

def generate_chart(rows: List[Dict]) -> bytes:
    """Erstellt ein Diagramm mit Download, Upload und Ping mit Datum/Uhrzeit auf X-Achse."""
    if not rows:
        return b''
    
    # Daten extrahieren
    datetimes = [datetime.fromisoformat(r['Datum/Uhrzeit']) if isinstance(r['Datum/Uhrzeit'], str) and 'T' in r['Datum/Uhrzeit'] 
                 else r['Datum/Uhrzeit'] for r in rows]
    downloads = [float(r['Download (Mbit/s)']) for r in rows]
    uploads = [float(r['Upload (Mbit/s)']) for r in rows]
    pings = [float(r['Ping (ms)']) for r in rows]
    
    # Plot erstellen
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6))
    
    x_pos = range(len(datetimes))
    
    # Download/Upload Plot
    ax1.plot(x_pos, downloads, 'b-o', label='Download', linewidth=2, markersize=4)
    ax1.plot(x_pos, uploads, 'g-s', label='Upload', linewidth=2, markersize=4)
    ax1.set_ylabel('Mbit/s', fontsize=10)
    ax1.set_title('Download & Upload', fontsize=12, fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Ping Plot
    ax2.plot(x_pos, pings, 'r-^', label='Ping', linewidth=2, markersize=4)
    ax2.set_ylabel('ms', fontsize=10)
    ax2.set_xlabel('Zeit', fontsize=10)
    ax2.set_title('Laufzeit (Ping)', fontsize=12, fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # X-Achsen Labels mit Datum/Uhrzeit
    # Zeige alle 5. Label um Überlappung zu vermeiden
    label_interval = max(1, len(datetimes) // 10)
    x_labels = [dt.strftime('%d.%m\n%H:%M') if i % label_interval == 0 else '' 
                for i, dt in enumerate(datetimes)]
    
    ax1.set_xticks(x_pos)
    ax1.set_xticklabels(x_labels, fontsize=8)
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(x_labels, fontsize=8)
    
    # Tight layout für bessere Spacing
    fig.tight_layout()
    
    # In BytesIO speichern
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=100, bbox_inches='tight')
    img_buffer.seek(0)
    plt.close(fig)
    
    return img_buffer.getvalue()

def markdown_to_pdf(markdown_content: str, rows: List[Dict], filename: str = "messdaten_export.pdf") -> bytes:
    """Konvertiert Markdown zu PDF mit Tabellen und Chart."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles_dict = get_pdf_styles()
    
    story = []
    
    # Titel
    story.append(Paragraph("Breitbandmessung - Messdaten Export", styles_dict['title']))
    story.append(Spacer(1, 0.1*inch))
    
    # Meta Info
    meta_text = f"<b>Exportiert am:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}<br/><b>Anzahl Messungen:</b> {len(rows)}"
    story.append(Paragraph(meta_text, styles_dict['normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Statistik Tabelle
    story.append(Paragraph("Statistiken", styles_dict['heading']))
    downloads = [float(r['Download (Mbit/s)']) for r in rows]
    uploads = [float(r['Upload (Mbit/s)']) for r in rows]
    pings = [float(r['Ping (ms)']) for r in rows]
    
    stats_data = [
        ['Metrik', 'Wert'],
        ['Ø Download', f"{sum(downloads)/len(downloads):.2f} Mbit/s"],
        ['Min Download', f"{min(downloads):.2f} Mbit/s"],
        ['Max Download', f"{max(downloads):.2f} Mbit/s"],
        ['Ø Upload', f"{sum(uploads)/len(uploads):.2f} Mbit/s"],
        ['Min Upload', f"{min(uploads):.2f} Mbit/s"],
        ['Max Upload', f"{max(uploads):.2f} Mbit/s"],
        ['Ø Ping', f"{sum(pings)/len(pings):.2f} ms"],
        ['Min Ping', f"{min(pings):.2f} ms"],
        ['Max Ping', f"{max(pings):.2f} ms"],
    ]
    
    stats_table = Table(stats_data, colWidths=[3*inch, 2*inch])
    stats_table.setStyle(get_header_table_style())
    story.append(stats_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Chart
    story.append(Paragraph("Visualisierung", styles_dict['heading']))
    chart_img_bytes = generate_chart(rows)
    if chart_img_bytes:
        chart_buffer = io.BytesIO(chart_img_bytes)
        chart_img = Image(chart_buffer, width=6*inch, height=3.6*inch)
        story.append(chart_img)
        story.append(Spacer(1, 0.2*inch))
    
    # Messdaten Tabelle
    story.append(PageBreak())
    story.append(Paragraph("Messdaten", styles_dict['heading']))
    
    # Messdaten kompakt formatieren
    header = ['Datum/Uhrzeit', 'Download', 'Upload', 'Ping', 'OS', 'Browser']
    body = []
    for row in rows:
        # Datum lesbar
        dt_disp = row['Datum/Uhrzeit']
        try:
            dt_disp = datetime.fromisoformat(row['Datum/Uhrzeit']).strftime('%d.%m.%Y %H:%M:%S')
        except Exception:
            pass
        body.append([
            Paragraph(dt_disp, styles_dict['small']),
            Paragraph(f"{float(row['Download (Mbit/s)']):.2f}", styles_dict['small']),
            Paragraph(f"{float(row['Upload (Mbit/s)']):.2f}", styles_dict['small']),
            Paragraph(f"{float(row['Ping (ms)']):.0f}", styles_dict['small']),
            Paragraph(str(row['Betriebssystem']), styles_dict['small']),
            Paragraph(str(row['Internet-Browser']), styles_dict['small']),
        ])

    measurements_table = Table([header] + body, colWidths=[1.8*inch, 0.9*inch, 0.9*inch, 0.6*inch, 1.0*inch, 2.4*inch])
    measurements_table.setStyle(get_header_table_style())
    story.append(measurements_table)
    
    # PDF-Metadaten setzen
    def _set_info(canvas, _doc):
        canvas.setTitle('Breitbandmessung - Messdaten Export')
        canvas.setAuthor('https://github.com/pzauner/NiceGUI-Breitbandmessung-Visualisierung')
        canvas.setSubject('Messdaten-Export')

    doc.build(story, onFirstPage=_set_info, onLaterPages=_set_info)
    buffer.seek(0)
    return buffer.getvalue()

def generate_bnetza_pdf(result: Dict, contract_download: float, contract_upload: float, selected_rows: List[Dict]) -> bytes:
    """Erstellt einen professionellen BNetzA-Prüfbericht als PDF."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles_dict = get_pdf_styles()
    
    story = []
    
    # Titel
    story.append(Paragraph("Prüfzusammenfassung gemäß BNetzA-Anforderungen (informativ)", styles_dict['title']))
    story.append(Paragraph(f"<b>Generiert:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}", styles_dict['normal']))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph(
        "Diese Auswertung ist eine Orientierung anhand Ihrer Messreihen (Breitbandmessung Desktop-App).\n"
        "Der rechtssichere Nachweis erfolgt ausschließlich über das Messprotokoll der Bundesnetzagentur.",
        styles_dict['normal'])
    )
    story.append(Spacer(1, 0.2*inch))
    
    # Vertragsparameter
    story.append(Paragraph("Vertragsparameter", styles_dict['heading']))
    contract_data = [
        ['Parameter', 'Wert'],
        ['Download-Geschwindigkeit', f'{contract_download:.0f} Mbit/s'],
        ['Upload-Geschwindigkeit', f'{contract_upload:.0f} Mbit/s'],
    ]
    contract_table = Table(contract_data, colWidths=[3*inch, 2*inch])
    contract_table.setStyle(get_header_table_style())
    story.append(contract_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Anforderungen Status
    story.append(Paragraph("Kriterien gemäß BNetzA-Anforderungen (informativ)", styles_dict['heading']))
    if result['valid']:
        story.append(Paragraph("✅ Kriterien erfüllt", styles_dict['status_pass']))
    else:
        story.append(Paragraph("❌ Kriterien nicht erfüllt", styles_dict['status_fail']))
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph("<b>Hinweise:</b>", styles_dict['normal']))
        for error in result['errors']:
            story.append(Paragraph(f"• {error}", styles_dict['normal']))
    
    story.append(Spacer(1, 0.2*inch))
    
    # Minderleistung (informativ)
    story.append(Paragraph("Hinweise auf Minderleistung (informativ)", styles_dict['heading']))
    if result['valid']:
        if result['minderleistung']:
            story.append(Paragraph("⚠️ Hinweis: Kriterien deuten auf Minderleistung hin", styles_dict['status_warning']))
            story.append(Paragraph(result['minderleistung_reason'], styles_dict['normal']))
        else:
            story.append(Paragraph("✓ Kein Hinweis auf Minderleistung", styles_dict['status_pass']))
    else:
        story.append(Paragraph("Bewertung nicht möglich – Mindestkriterien (30 Messungen, 3 Tage, Abstände) nicht erfüllt", styles_dict['normal']))
    
    story.append(Spacer(1, 0.2*inch))
    
    # Statistiken
    story.append(Paragraph("Messdaten-Statistiken", styles_dict['heading']))
    stats = result['stats']
    stats_data = [
        ['Metrik', 'Wert'],
        ['Gesamte Messungen', str(stats['total_measurements'])],
        ['Messtage', str(stats['dates'])],
        ['Zeitraum', stats['date_range']],
        ['Ø Download', f"{stats['avg_download']:.2f} Mbit/s"],
        ['Min Download', f"{stats['min_download']:.2f} Mbit/s"],
        ['Max Download', f"{stats['max_download']:.2f} Mbit/s"],
        ['Ø Upload', f"{stats['avg_upload']:.2f} Mbit/s"],
        ['Min Upload', f"{stats['min_upload']:.2f} Mbit/s"],
        ['Max Upload', f"{stats['max_upload']:.2f} Mbit/s"],
        ['90% erreicht (DL/UL)', f"{stats.get('reached_90_pct_days_dl', 0)}/3 / {stats.get('reached_90_pct_days_ul', 0)}/3"],
        ['Minimalgeschwindigkeit unterschritten (DL/UL)', f"{stats.get('below_min_days_dl', 0)}/3 / {stats.get('below_min_days_ul', 0)}/3"],
        ['Normalgeschwindigkeit ≥ Vertrag (DL/UL)', f"{stats.get('percentage_normal_dl', 0.0):.1f}% / {stats.get('percentage_normal_ul', 0.0):.1f}%"],
    ]
    # Werte-Spalte etwas breiter machen
    stats_table = Table(stats_data, colWidths=[3.0*inch, 2.0*inch])
    stats_table.setStyle(get_header_table_style())
    story.append(stats_table)
    
    # Vereinfachte Minderung nach §57 Abs. 4 TKG (Satz 2)
    # Annahme: vertraglich maximal/normal/minimal = contract_* (vereinfachter Fall)
    try:
        avg_dl = float(stats.get('avg_download', 0.0))
        avg_ul = float(stats.get('avg_upload', 0.0))
        c_dl = float(stats.get('contract_download', contract_download))
        c_ul = float(stats.get('contract_upload', contract_upload))
        ratio_dl = min(avg_dl / c_dl, 1.0) if c_dl > 0 else 1.0
        ratio_ul = min(avg_ul / c_ul, 1.0) if c_ul > 0 else 1.0
        minderung_dl = max(0.0, (1.0 - ratio_dl) * 100.0)
        minderung_ul = max(0.0, (1.0 - ratio_ul) * 100.0)
        empfohlene_minderung = max(minderung_dl, minderung_ul)
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("Vereinfachte Minderungsberechnung (§57 Abs. 4 TKG)", styles_dict['heading']))
        mind_table = Table([
            ['Größe', 'Vertrag (Mbit/s)', 'Ø gemessen (Mbit/s)', 'Minderung %'],
            ['Download', f"{c_dl:.0f}", f"{avg_dl:.2f}", f"{minderung_dl:.1f}%"],
            ['Upload', f"{c_ul:.0f}", f"{avg_ul:.2f}", f"{minderung_ul:.1f}%"],
            ['Empfehlung', '-', '-', f"{empfohlene_minderung:.1f}%"],
        ], colWidths=[1.4*inch, 1.3*inch, 1.6*inch, 1.2*inch])
        mind_table.setStyle(get_header_table_style())
        story.append(mind_table)
        story.append(Paragraph("Hinweis: Vereinfachte Berechnung. Maßgeblich sind die Vorgaben der BNetzA und Ihr individueller Vertrag.", styles_dict['normal']))
    except Exception:
        pass
    
    # Warnungen
    if result['warnings']:
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("Warnungen", styles_dict['heading']))
        for warning in result['warnings']:
            story.append(Paragraph(f"⚠ {warning}", styles_dict['normal']))

    # Verweise
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("Weiterführende Informationen", styles_dict['heading']))
    story.append(Paragraph('Bundesnetzagentur: Internetgeschwindigkeit – Nachweisverfahren: <a href="https://www.bundesnetzagentur.de/DE/Vportal/TK/InternetTelefon/Internetgeschwindigkeit/start.html">Link</a>', styles_dict['normal']))
    story.append(Paragraph('Allgemeinverfügung (Az.: 120-3945-1/2021): <a href="https://www.bundesnetzagentur.de/DE/Fachthemen/Telekommunikation/Breitband/Breitbandgeschwindigkeiten/Allgemeinverfuegung_neu.pdf?__blob=publicationFile&v=1">PDF</a>', styles_dict['normal']))
    story.append(Paragraph('Handreichung zum Nachweisverfahren: <a href="https://www.bundesnetzagentur.de/DE/Fachthemen/Telekommunikation/Breitband/Breitbandgeschwindigkeiten/Handreichung_neu.pdf?__blob=publicationFile&v=1">PDF</a>', styles_dict['normal']))
    
    # Messdaten Tabelle
    story.append(PageBreak())
    story.append(Paragraph("Gemessene Daten", styles_dict['heading']))
    
    # Messdaten kompakt formatieren wie im normalen Export
    header = ['Datum/Uhrzeit', 'Download', 'Upload', 'Ping', 'OS', 'Browser']
    body = []
    for row in selected_rows:
        dt_disp = row['Datum/Uhrzeit']
        try:
            dt_disp = datetime.fromisoformat(row['Datum/Uhrzeit']).strftime('%d.%m.%Y %H:%M:%S')
        except Exception:
            pass
        body.append([
            Paragraph(dt_disp, styles_dict['small']),
            Paragraph(f"{float(row['Download (Mbit/s)']):.2f}", styles_dict['small']),
            Paragraph(f"{float(row['Upload (Mbit/s)']):.2f}", styles_dict['small']),
            Paragraph(f"{float(row['Ping (ms)']):.0f}", styles_dict['small']),
            Paragraph(str(row['Betriebssystem']), styles_dict['small']),
            Paragraph(str(row['Internet-Browser']), styles_dict['small']),
        ])
    measurements_table = Table([header] + body, colWidths=[1.8*inch, 0.9*inch, 0.9*inch, 0.6*inch, 1.0*inch, 2.4*inch])
    measurements_table.setStyle(get_header_table_style())
    story.append(measurements_table)
    
    # PDF-Metadaten setzen
    def _set_info(canvas, _doc):
        canvas.setTitle('Prüfzusammenfassung gemäß BNetzA-Anforderungen (informativ)')
        canvas.setAuthor('https://github.com/pzauner/NiceGUI-Breitbandmessung-Visualisierung')
        canvas.setSubject('Informative Prüfzusammenfassung gemäß BNetzA-Kriterien auf Basis Ihrer Messreihen')

    doc.build(story, onFirstPage=_set_info, onLaterPages=_set_info)
    buffer.seek(0)
    return buffer.getvalue()

# ============================================================================
# PDF HELPER FUNCTIONS
# ============================================================================
def get_pdf_styles():
    """Gibt alle benötigten PDF-Styles zurück."""
    styles = getSampleStyleSheet()
    
    return {
        'title': ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=12,
            fontName='Helvetica-Bold'
        ),
        'heading': ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#2c5aa0'),
            spaceAfter=8,
            fontName='Helvetica-Bold'
        ),
        'normal': styles['Normal'],
        'status_pass': ParagraphStyle(
            'StatusPass',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#16a34a'),
            fontName='Helvetica-Bold',
            spaceAfter=8
        ),
        'status_fail': ParagraphStyle(
            'StatusFail',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#dc2626'),
            fontName='Helvetica-Bold',
            spaceAfter=8
        ),
        'status_warning': ParagraphStyle(
            'StatusWarning',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#ea580c'),
            fontName='Helvetica-Bold',
            spaceAfter=8
        ),
        'small': ParagraphStyle(
            'Small',
            parent=styles['Normal'],
            fontSize=9,
            leading=11,
        ),
    }

def get_header_table_style():
    """Header-Tabellen-Style."""
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')]),
    ])

# ============================================================================
# BNETZA CHECKER
# ============================================================================
def check_bnetza_requirements(measurements: List[Dict], contract_download: float, contract_upload: float) -> Dict[str, Any]:
    """
    Prüft BNetzA-Anforderungen für Minderleistung bei Festnetz-Internetzugängen.
    Eine Minderleistung liegt vor, wenn MINDESTENS EINE dieser Bedingungen erfüllt ist:
    1. Nicht an mindestens 2 von 3 Messtagen jeweils mindestens einmal 90% der vertraglich 
       vereinbarten maximalen Geschwindigkeit erreicht
    2. Die normalerweise zur Verfügung stehende Geschwindigkeit nicht in 90% der Messungen erreicht
    3. An mindestens 2 von 3 Messtagen jeweils mindestens einmal die minimale Geschwindigkeit unterschritten
    Zusätzliche Anforderungen (müssen alle erfüllt sein):
    4. 30 Messungen an 3 unterschiedlichen Kalendertagen (10 pro Tag)
    5. Max. 14 Kalendertage Gesamtdauer, min. 1 Tag Abstand zwischen Messtagen
    6. Zwischen 5. und 6. Messung: min. 3 Stunden; zwischen anderen: min. 5 Minuten
    """
    
    from collections import defaultdict
    
    result = {
        'valid': False,
        'errors': [],
        'warnings': [],
        'stats': {},
        'minderleistung': False,
        'minderleistung_details': {},
        'minderleistung_reason': '',
    }
    
    if not measurements or len(measurements) < 30:
        result['errors'].append(f'Es werden mindestens 30 Messungen benötigt, gefunden: {len(measurements)}')
        return result
    
    print(f"DEBUG: check_bnetza_requirements gestartet mit {len(measurements)} Messungen")
    
    # ========== ANFORDERUNG 4: Gruppiere nach Datum ==========
    by_date = defaultdict(list)
    dates = set()
    
    for m in measurements:
        date = m['datetime'].date()
        dates.add(date)
        by_date[date].append(m)
    
    sorted_dates = sorted(dates)
    
    # Prüfe auf genau 3 Tage
    if len(sorted_dates) != 3:
        result['errors'].append(f'Es werden genau 3 unterschiedliche Tage benötigt, gefunden: {len(sorted_dates)}')
        # Initialisiere stats bei Fehler
        all_downloads = [m['download'] for m in measurements]
        all_uploads = [m['upload'] for m in measurements]
        result['stats'] = {
            'total_measurements': len(measurements),
            'dates': len(sorted_dates),
            'date_range': f'{sorted_dates[0]} bis {sorted_dates[-1]}' if sorted_dates else 'N/A',
            'avg_download': sum(all_downloads) / len(all_downloads) if all_downloads else 0,
            'min_download': min(all_downloads) if all_downloads else 0,
            'max_download': max(all_downloads) if all_downloads else 0,
            'avg_upload': sum(all_uploads) / len(all_uploads) if all_uploads else 0,
            'min_upload': min(all_uploads) if all_uploads else 0,
            'max_upload': max(all_uploads) if all_uploads else 0,
            'contract_download': 0, 'contract_upload': 0,
            'reached_90_pct_days_dl': 0, 'reached_90_pct_days_ul': 0,
            'below_min_days_dl': 0, 'below_min_days_ul': 0,
            'percentage_normal_dl': 0, 'percentage_normal_ul': 0,
        }
        return result
    
    # 10 Messungen pro Tag?
    for date in sorted_dates:
        count = len(by_date[date])
        if count != 10:
            result['errors'].append(f'Tag {date}: {count} Messungen gefunden (benötigt: 10)')
    
    if result['errors']:
        return result
    
    # ========== ANFORDERUNG 5: Max. 14 Tage Gesamtdauer? ==========
    duration_days = (sorted_dates[-1] - sorted_dates[0]).days
    if duration_days > 14:
        result['errors'].append(f'Messungen über {duration_days} Tage verteilt (max. 14 Tage)')
        return result
    
    # Min. 1 Tag Abstand zwischen Messtagen?
    for i in range(len(sorted_dates) - 1):
        gap_days = (sorted_dates[i+1] - sorted_dates[i]).days
        if gap_days < 2:  # 2 Tage Differenz = 1 Tag Abstand
            result['errors'].append(f'Abstand Tag {sorted_dates[i]} zu {sorted_dates[i+1]}: {gap_days-1} Tag(e) (benötigt: min. 1)')
    
    if result['errors']:
        return result
    
    # ========== ANFORDERUNG 6: Abstände zwischen Messungen pro Tag ==========
    for date in sorted_dates:
        day_measurements = sorted(by_date[date], key=lambda m: m['datetime'])
        for i in range(len(day_measurements) - 1):
            time_diff = day_measurements[i+1]['datetime'] - day_measurements[i]['datetime']
            time_diff_minutes = time_diff.total_seconds() / 60
            
            if i == 4:  # Zwischen 5. und 6. Messung
                if time_diff_minutes < 180:  # 3 Stunden
                    result['warnings'].append(
                        f'Tag {date}: Abstand zw. 5. und 6. Messung: {time_diff_minutes:.0f} Min (benötigt: 180 Min)'
                    )
            else:
                if time_diff_minutes < 5:
                    result['warnings'].append(
                        f'Tag {date}: Abstand zw. Messung {i+1} und {i+2}: {time_diff_minutes:.1f} Min (benötigt: 5 Min)'
                    )
    
    # Wenn bis hier ok, ist die Basisanforderung erfüllt
    result['valid'] = True
    print(f"DEBUG: Basisanforderung erfüllt (3 Tage, 10 Messungen/Tag)")
    
    # ========== MINDERLEISTUNG PRÜFEN ==========
    
    # Normalerweise verfügbare Geschwindigkeit = Vertragsgeschwindigkeit
    normal_speed_dl = contract_download
    normal_speed_ul = contract_upload
    
    # 90% der Vertragsgeschwindigkeit
    threshold_90_pct_dl = contract_download * 0.9
    threshold_90_pct_ul = contract_upload * 0.9
    
    # Minimale Geschwindigkeit = 30% der Vertragsgeschwindigkeit (BNetzA-Standard)
    min_speed_dl = contract_download * 0.3
    min_speed_ul = contract_upload * 0.3
    
    print(f"DEBUG: normal={normal_speed_dl}, 90%={threshold_90_pct_dl}, min={min_speed_dl}")
    
    # ========== BEDINGUNG 1: 90% an mindestens 2 von 3 Tagen erreicht? ==========
    days_reached_90_pct_dl = 0
    days_reached_90_pct_ul = 0
    
    for date in sorted_dates:
        day_measurements = by_date[date]
        if any(m['download'] >= threshold_90_pct_dl for m in day_measurements):
            days_reached_90_pct_dl += 1
        if any(m['upload'] >= threshold_90_pct_ul for m in day_measurements):
            days_reached_90_pct_ul += 1
    
    condition1_dl_failed = days_reached_90_pct_dl < 2
    condition1_ul_failed = days_reached_90_pct_ul < 2
    condition1_failed = condition1_dl_failed or condition1_ul_failed
    
    result['minderleistung_details']['condition1'] = {
        'check': 'Mindestens 2 von 3 Tagen mit 90% Vertragsgeschwindigkeit',
        'download': {'reached_days': days_reached_90_pct_dl, 'failed': condition1_dl_failed},
        'upload': {'reached_days': days_reached_90_pct_ul, 'failed': condition1_ul_failed},
        'failed': condition1_failed
    }
    print(f"DEBUG: Bedingung 1 - Download {days_reached_90_pct_dl}/3, Upload {days_reached_90_pct_ul}/3")
    
    # ========== BEDINGUNG 2: 90% der Messungen mit Normalgeschwindigkeit ==========
    measurements_reaching_normal_dl = sum(1 for m in measurements if m['download'] >= normal_speed_dl)
    measurements_reaching_normal_ul = sum(1 for m in measurements if m['upload'] >= normal_speed_ul)
    
    pct_normal_dl = (measurements_reaching_normal_dl / len(measurements)) * 100
    pct_normal_ul = (measurements_reaching_normal_ul / len(measurements)) * 100
    
    condition2_dl_failed = pct_normal_dl < 90
    condition2_ul_failed = pct_normal_ul < 90
    condition2_failed = condition2_dl_failed or condition2_ul_failed
    
    result['minderleistung_details']['condition2'] = {
        'check': '90% aller Messungen mit Normalgeschwindigkeit',
        'download': {'percentage': pct_normal_dl, 'failed': condition2_dl_failed},
        'upload': {'percentage': pct_normal_ul, 'failed': condition2_ul_failed},
        'failed': condition2_failed
    }
    print(f"DEBUG: Bedingung 2 - Download {pct_normal_dl:.1f}%, Upload {pct_normal_ul:.1f}%")
    
    # ========== BEDINGUNG 3: Minimale Geschwindigkeit unterschritten an 2+ Tagen ==========
    days_below_min_dl = 0
    days_below_min_ul = 0
    
    for date in sorted_dates:
        day_measurements = by_date[date]
        if any(m['download'] < min_speed_dl for m in day_measurements):
            days_below_min_dl += 1
        if any(m['upload'] < min_speed_ul for m in day_measurements):
            days_below_min_ul += 1
    
    condition3_dl_failed = days_below_min_dl >= 2
    condition3_ul_failed = days_below_min_ul >= 2
    condition3_failed = condition3_dl_failed or condition3_ul_failed
    
    result['minderleistung_details']['condition3'] = {
        'check': 'Minimale Geschwindigkeit unterschritten an 2+ Tagen',
        'download': {'failed_days': days_below_min_dl, 'failed': condition3_dl_failed},
        'upload': {'failed_days': days_below_min_ul, 'failed': condition3_ul_failed},
        'failed': condition3_failed
    }
    print(f"DEBUG: Bedingung 3 - Download {days_below_min_dl}/3 Tage, Upload {days_below_min_ul}/3 Tage")
    
    # Minderleistung wenn MINDESTENS EINE Bedingung erfüllt
    if condition1_failed or condition2_failed or condition3_failed:
        result['minderleistung'] = True
        reasons = []
        
        if condition1_dl_failed:
            reasons.append(f'Download: Nur {days_reached_90_pct_dl}/3 Tagen 90% erreicht')
        if condition1_ul_failed:
            reasons.append(f'Upload: Nur {days_reached_90_pct_ul}/3 Tagen 90% erreicht')
        if condition2_dl_failed:
            reasons.append(f'Download: {pct_normal_dl:.1f}% Messungen mit Normalgeschwindigkeit (benötigt 90%)')
        if condition2_ul_failed:
            reasons.append(f'Upload: {pct_normal_ul:.1f}% Messungen mit Normalgeschwindigkeit (benötigt 90%)')
        if condition3_dl_failed:
            reasons.append(f'Download: Minimale Geschwindigkeit an {days_below_min_dl} Tagen unterschritten')
        if condition3_ul_failed:
            reasons.append(f'Upload: Minimale Geschwindigkeit an {days_below_min_ul} Tagen unterschritten')
        
        result['minderleistung_reason'] = ' | '.join(reasons)
        print(f"DEBUG: MINDERLEISTUNG ERKANNT")
    else:
        result['minderleistung_reason'] = 'Keine Minderleistung erkannt - alle Anforderungen erfüllt'
        print(f"DEBUG: KEINE MINDERLEISTUNG")
    
    # Statistiken
    all_downloads = [m['download'] for m in measurements]
    all_uploads = [m['upload'] for m in measurements]
    
    result['stats'] = {
        'total_measurements': len(measurements),
        'dates': len(sorted_dates),
        'date_range': f'{sorted_dates[0]} bis {sorted_dates[-1]}',
        'avg_download': sum(all_downloads) / len(all_downloads),
        'min_download': min(all_downloads),
        'max_download': max(all_downloads),
        'avg_upload': sum(all_uploads) / len(all_uploads),
        'min_upload': min(all_uploads),
        'max_upload': max(all_uploads),
        'contract_download': contract_download,
        'contract_upload': contract_upload,
        'reached_90_pct_days_dl': days_reached_90_pct_dl,
        'reached_90_pct_days_ul': days_reached_90_pct_ul,
        'below_min_days_dl': days_below_min_dl,
        'below_min_days_ul': days_below_min_ul,
        'percentage_normal_dl': pct_normal_dl,
        'percentage_normal_ul': pct_normal_ul,
    }
    
    return result

# Helper: Wähle verbraucherfreundliches 30er-Subset (3 Tage x 10 Messungen)
from itertools import combinations

def select_bnetza_subset(measurements: List[Dict]) -> List[Dict] | None:
    """Wählt ein gültiges Subset von genau 30 Messungen (3 Tage x 10),
    das die BNetzA-Anforderungen (Punkte 4-6) erfüllt. Liefert None, wenn keins gefunden.
    """
    if not measurements or len(measurements) < 30:
        return None
    # Gruppieren nach Datum
    by_date: Dict[datetime.date, List[Dict]] = {}
    for m in measurements:
        by_date.setdefault(m['datetime'].date(), []).append(m)
    all_dates = sorted(by_date.keys())
    # Versuche alle 3er-Kombinationen von Tagen
    for d1, d2, d3 in combinations(all_dates, 3):
        # Max 14 Tage Spanne
        if (d3 - d1).days > 14:
            continue
        # Mindestens 1 Tag Abstand zwischen Messtagen (Differenz >= 2)
        if (d2 - d1).days < 2 or (d3 - d2).days < 2:
            continue
        # Für jeden Tag 10 Messungen mit Abständen auswählen
        selected: List[Dict] = []
        ok = True
        for day in [d1, d2, d3]:
            day_measurements = sorted(by_date[day], key=lambda m: m['datetime'])
            if len(day_measurements) < 10:
                ok = False
                break
            # Greedy Auswahl mit Abstandsregeln
            chosen: List[Dict] = []
            for m in day_measurements:
                if not chosen:
                    chosen.append(m)
                else:
                    diff_min = (m['datetime'] - chosen[-1]['datetime']).total_seconds() / 60
                    # Zwischen 5. und 6. Messung: >= 180 min
                    if len(chosen) == 5:
                        diff_5_6 = (m['datetime'] - chosen[4]['datetime']).total_seconds() / 60
                        if diff_min >= 5 and diff_5_6 >= 180:
                            chosen.append(m)
                    else:
                        if diff_min >= 5:
                            chosen.append(m)
                if len(chosen) == 10:
                    break
            if len(chosen) != 10:
                ok = False
                break
            selected.extend(chosen)
        if ok and len(selected) == 30:
            return selected
    return None

# ============================================================================
# DATEN LADEN
# ============================================================================
all_measurements = load_measurements()
stats_all = calculate_statistics(all_measurements)
# aktuell im Plot anzuzeigende Messungen (Zeitfilter/Selektion)
current_plot_measurements: List[Dict] = all_measurements

# ============================================================================
# UI AUFBAU
# ============================================================================
ui.page_title(config['ui']['title'])

with ui.header(elevated=True).classes('w-full'):
    ui.label(config['ui']['title']).classes('text-2xl font-bold')

with ui.row().classes('w-full gap-4 p-4'):
    # LINKE SPALTE: Filter und AGGrid
    with ui.column().classes('flex-1'):
        # Filter-Bereich
        with ui.card().classes('w-full'):
            ui.label('Filter').classes('text-lg font-bold')
            
            timeframe_select = ui.select(
                {
                    'all': 'Alle Daten',
                    '1': 'Letzte 24 Stunden',
                    '7': 'Letzte 7 Tage',
                    '30': 'Letzte 30 Tage'
                },
                value='7',
                label='Zeitraum'
            ).classes('w-full')
        
        # AGGrid für Messreihen
        with ui.card().classes('w-full h-[75vh]'):
            ui.label('Messdaten').classes('text-lg font-bold')
            
            # Initial nach Zeitraum filtern
            _initial_selected = timeframe_select.value
            _initial_measurements = (
                all_measurements if _initial_selected == 'all'
                else filter_measurements_by_timeframe(all_measurements, int(_initial_selected))
            )

            grid_data = [
                {
                    'datetime': m['datetime'].isoformat(),
                    'download': m['download'],
                    'upload': m['upload'],
                    'ping': m['ping'],
                    'os': m['os'],
                    'browser': m['browser'],
                }
                for m in _initial_measurements
            ]
            
            grid = ui.aggrid({
                'columnDefs': [
                    {'headerName': 'Datum/Uhrzeit', 'field': 'datetime', 'filter': 'agTextColumnFilter', 'sort': 'desc', ':valueFormatter': 'params => params.value ? new Date(params.value).toLocaleDateString("de-DE") + " " + new Date(params.value).toLocaleTimeString("de-DE") : ""'},
                    {'headerName': 'Download (Mbit/s)', 'field': 'download', 'filter': 'agNumberColumnFilter', 'sortable': True, ':valueFormatter': 'params => params.value ? params.value.toFixed(2) : ""'},
                    {'headerName': 'Upload (Mbit/s)', 'field': 'upload', 'filter': 'agNumberColumnFilter', 'sortable': True, ':valueFormatter': 'params => params.value ? params.value.toFixed(2) : ""'},
                    {'headerName': 'Ping (ms)', 'field': 'ping', 'filter': 'agNumberColumnFilter', 'sortable': True, ':valueFormatter': 'params => params.value ? params.value.toFixed(0) : ""'},
                    {'headerName': 'Betriebssystem', 'field': 'os', 'filter': 'agTextColumnFilter'},
                    {'headerName': 'Browser', 'field': 'browser', 'filter': 'agTextColumnFilter'},
                ],
                'rowData': grid_data,
                'rowSelection': {'mode': 'multiRow'},
                'pagination': {'pageSize': 20},
                'paginationPageSize': 20,
                'domLayout': 'normal'
            }).classes('w-full h-[72vh]')
            
            # Export-Buttons (unten, mit Abstand)
            async def export_pdf():
                selected_rows = await grid.get_selected_rows()
                if not selected_rows:
                    ui.notify('Keine Zeilen ausgewählt')
                    return
                
                notif = ui.notification('PDF wird generiert...', type='ongoing', spinner=True, timeout=None)
                try:
                    # Felder für Markdown vorbereiten
                    rows_with_names = []
                    for row in selected_rows:
                        rows_with_names.append({
                            'Datum/Uhrzeit': row['datetime'],
                            'Download (Mbit/s)': row['download'],
                            'Upload (Mbit/s)': row['upload'],
                            'Ping (ms)': row['ping'],
                            'Betriebssystem': row['os'],
                            'Internet-Browser': row['browser'],
                        })
                    
                    notif.message = 'Konvertiere zu PDF...'
                    markdown_content = export_to_markdown(rows_with_names)
                    pdf_bytes = markdown_to_pdf(markdown_content, rows_with_names)
                    ui.download(pdf_bytes, f'messdaten_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')
                    notif.message = '✓ PDF exportiert'
                    notif.type = 'positive'
                except Exception as e:
                    notif.message = f'Fehler beim PDF-Export: {str(e)}'
                    notif.type = 'negative'
                    print(f"DEBUG: Error in export_pdf: {e}")
                    import traceback
                    traceback.print_exc()
                finally:
                    try:
                        notif.dismiss()
                    except Exception:
                        try:
                            notif.delete()
                        except Exception:
                            pass
            
            async def export_csv():
                selected_rows = await grid.get_selected_rows()
                if not selected_rows:
                    ui.notify('Keine Zeilen ausgewählt')
                    return
                
                notif = ui.notification('CSV wird generiert...', type='ongoing', spinner=True, timeout=None)
                try:
                    output = io.StringIO()
                    fieldnames = ['Datum/Uhrzeit', 'Download (Mbit/s)', 'Upload (Mbit/s)', 'Ping (ms)', 'Betriebssystem', 'Browser']
                    writer = csv.DictWriter(output, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for row in selected_rows:
                        writer.writerow({
                            'Datum/Uhrzeit': row['datetime'],
                            'Download (Mbit/s)': row['download'],
                            'Upload (Mbit/s)': row['upload'],
                            'Ping (ms)': row['ping'],
                            'Betriebssystem': row['os'],
                            'Browser': row['browser'],
                        })
                    
                    csv_content = output.getvalue()
                    ui.download(csv_content.encode('utf-8'), f'messdaten_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
                    notif.message = '✓ CSV exportiert'
                    notif.type = 'positive'
                except Exception as e:
                    notif.message = f'Fehler beim CSV-Export: {str(e)}'
                    notif.type = 'negative'
                    print(f"DEBUG: Error in export_csv: {e}")
                    import traceback
                    traceback.print_exc()
                finally:
                    try:
                        notif.dismiss()
                    except Exception:
                        try:
                            notif.delete()
                        except Exception:
                            pass
            
            async def reload_data():
                global all_measurements
                notif = ui.notification('Lade Messungen...', type='ongoing', spinner=True, timeout=None)
                try:
                    all_measurements = load_measurements()
                    notif.message = f'Verarbeite {len(all_measurements)} Messungen...'
                    
                    # Grid aktualisieren (unter Berücksichtigung des aktuellen Zeitfilters)
                    sel = timeframe_select.value
                    filtered_after_reload = (
                        all_measurements if sel == 'all' else filter_measurements_by_timeframe(all_measurements, int(sel))
                    )
                    new_grid_data = [
                        {
                            'datetime': m['datetime'].isoformat(),
                            'download': m['download'],
                            'upload': m['upload'],
                            'ping': m['ping'],
                            'os': m['os'],
                            'browser': m['browser'],
                        }
                        for m in filtered_after_reload
                    ]
                    grid.options['rowData'] = new_grid_data
                    grid.update()
                    
                    # Statistiken aktualisieren
                    global stats_all
                    stats_all = calculate_statistics(all_measurements)
                    new_stats_rows = [
                        {'metric': 'Anzahl Messungen', 'gesamt': stats_all['count'], 'auswahl': '-'},
                        {'metric': 'Ø Download (Mbit/s)', 'gesamt': f"{stats_all['avg_download']:.2f}", 'auswahl': '-'},
                        {'metric': 'Min Download', 'gesamt': f"{stats_all['min_download']:.2f}", 'auswahl': '-'},
                        {'metric': 'Max Download', 'gesamt': f"{stats_all['max_download']:.2f}", 'auswahl': '-'},
                        {'metric': 'Ø Upload (Mbit/s)', 'gesamt': f"{stats_all['avg_upload']:.2f}", 'auswahl': '-'},
                        {'metric': 'Min Upload', 'gesamt': f"{stats_all['min_upload']:.2f}", 'auswahl': '-'},
                        {'metric': 'Max Upload', 'gesamt': f"{stats_all['max_upload']:.2f}", 'auswahl': '-'},
                        {'metric': 'Ø Ping (ms)', 'gesamt': f"{stats_all['avg_ping']:.2f}", 'auswahl': '-'},
                        {'metric': 'Min Ping', 'gesamt': f"{stats_all['min_ping']:.2f}", 'auswahl': '-'},
                        {'metric': 'Max Ping', 'gesamt': f"{stats_all['max_ping']:.2f}", 'auswahl': '-'},
                    ]
                    stats_table.rows = new_stats_rows
                    stats_table.update()
                    
                    notif.message = 'Plot wird aktualisiert...'
                    # Plot und globalen Zustand auf den gefilterten Bestand setzen
                    update_line_plot_data(filtered_after_reload)
                    
                    notif.message = f'✓ {len(all_measurements)} Messungen geladen'
                    notif.type = 'positive'
                except Exception as e:
                    notif.message = f'Fehler beim Laden: {str(e)}'
                    notif.type = 'negative'
                    print(f"DEBUG: Error in reload_data: {e}")
                    import traceback
                    traceback.print_exc()
                finally:
                    try:
                        notif.dismiss()
                    except Exception:
                        try:
                            notif.delete()
                        except Exception:
                            pass
            
            # BNetzA Checker Button
            async def check_bnetza():
                """BNetzA Checker - Verwendet automatisch ALLE Messdaten."""
                print(f"DEBUG: BNetzA Check gestartet mit {len(all_measurements)} Messungen")
                
                if len(all_measurements) < 30:
                    ui.notify(f'Zu wenig Messungen ({len(all_measurements)}/30 benötigt)', type='negative')
                    return
                
                # Dialog für Vertragsdaten
                with ui.dialog() as dialog:
                    with ui.card().classes('w-96'):
                        ui.label('BNetzA Checker').classes('text-lg font-bold')
                        ui.label('Prüft automatisch ALLE Messdaten gegen BNetzA-Anforderungen').classes('text-sm text-gray-600')
                        ui.label(f'Verfügbar: {len(all_measurements)} Messungen').classes('text-sm text-blue-600 font-semibold')
                        ui.separator()
                        
                        ui.label('Vertragliche Geschwindigkeiten eingeben:').classes('text-md font-semibold pt-2')
                        contract_dl = ui.number('Download (Mbit/s)', value=300, min=1).classes('w-full')
                        contract_ul = ui.number('Upload (Mbit/s)', value=150, min=1).classes('w-full')
                        
                        # Zeitraum-Auswahl (Alle, 30 Tage, 90 Tage)
                        timeframe_select = ui.select(
                            {
                                'all': 'Alle Messungen',
                                '30': 'Letzte 30 Tage',
                                '90': 'Letzte 90 Tage',
                            },
                            value='30',
                            label='Zeitraum'
                        ).classes('w-full')
                        
                        async def run_check():
                            """Starte die BNetzA-Prüfung."""
                            notif = ui.notification('Prüfe BNetzA-Anforderungen...', type='ongoing', spinner=True, timeout=None)
                            try:
                                import asyncio
                                print("DEBUG: run_check entered")
                                # kurzen Yield, damit die Notification sichtbar wird
                                await asyncio.sleep(0)
                                # Zeitraumfilter anwenden
                                base_measurements = all_measurements
                                if timeframe_select.value != 'all':
                                    try:
                                        days = int(timeframe_select.value)
                                        cutoff = datetime.now() - timedelta(days=days)
                                        base_measurements = [m for m in all_measurements if m['datetime'] >= cutoff]
                                        notif.message = f"Zeitraum: letzte {days} Tage ({len(base_measurements)} Messungen)"
                                        print(f"DEBUG: timeframe={days} days -> base_measurements={len(base_measurements)}")
                                    except Exception:
                                        pass
                                
                                if len(base_measurements) < 30:
                                    notif.message = f"Zu wenig Messungen im gewählten Zeitraum: {len(base_measurements)}/30"
                                    notif.type = 'negative'
                                    notif.spinner = False
                                    notif.timeout = 5.0
                                    print("DEBUG: abort because <30 measurements after timeframe filter")
                                    return
                                
                                # Verbraucherfreundlich: wähle gültiges 30er-Subset, falls möglich (im Thread, damit UI nicht blockiert)
                                print("DEBUG: selecting subset...")
                                subset = await asyncio.to_thread(select_bnetza_subset, base_measurements)
                                if subset:
                                    used_measurements = subset
                                    notif.message = 'Gültiges 30er-Subset gewählt (3 Tage x 10)'
                                    print("DEBUG: subset selected with 30 measurements")
                                else:
                                    # Kein gültiges 30er-Subset gefunden: Verbraucherfreundliche Fehlermeldung vorbereiten
                                    print(f"DEBUG: no subset -> cannot form required 3x10 within 14 days; base={len(base_measurements)}")
                                    # Diagnose: Top-3 Tage mit Messungsanzahl
                                    from collections import defaultdict as _dd
                                    _by_date = _dd(list)
                                    for m in base_measurements:
                                        _by_date[m['datetime'].date()].append(m)
                                    _counts = sorted(((d, len(v)) for d, v in _by_date.items()), key=lambda x: x[1], reverse=True)
                                    top3 = ', '.join([f"{d}: {c}" for d, c in _counts[:3]]) if _counts else 'keine'
                                    result = {
                                        'valid': False,
                                        'errors': [
                                            'Es konnten keine 30 Messungen auf 3 Kalendertage (je 10) innerhalb von 14 Tagen mit geforderten Abständen gebildet werden.',
                                            f'Top-Tage (Anzahl Messungen): {top3}',
                                        ],
                                        'warnings': [],
                                        'minderleistung': False,
                                        'minderleistung_details': {},
                                        'minderleistung_reason': 'Prüfung nicht möglich: Mindestanforderungen an Messplan nicht erfüllt',
                                        'stats': {
                                            'total_measurements': len(base_measurements),
                                            'dates': len(_by_date),
                                            'date_range': f"{min(_by_date.keys())} bis {max(_by_date.keys())}" if _by_date else 'N/A',
                                            'avg_download': sum(m['download'] for m in base_measurements)/len(base_measurements) if base_measurements else 0.0,
                                            'min_download': min((m['download'] for m in base_measurements), default=0.0),
                                            'max_download': max((m['download'] for m in base_measurements), default=0.0),
                                            'avg_upload': sum(m['upload'] for m in base_measurements)/len(base_measurements) if base_measurements else 0.0,
                                            'min_upload': min((m['upload'] for m in base_measurements), default=0.0),
                                            'max_upload': max((m['upload'] for m in base_measurements), default=0.0),
                                            'contract_download': float(contract_dl.value),
                                            'contract_upload': float(contract_ul.value),
                                            'reached_90_pct_days_dl': 0,
                                            'reached_90_pct_days_ul': 0,
                                            'below_min_days_dl': 0,
                                            'below_min_days_ul': 0,
                                            'percentage_normal_dl': 0.0,
                                            'percentage_normal_ul': 0.0,
                                        },
                                    }
                                    notif.message = 'Prüfung nicht möglich: Mindestanforderungen (3 Tage × 10) nicht erfüllbar'
                                    notif.type = 'warning'
                                    notif.spinner = False
                                    notif.dismiss()
                                    print("DEBUG: generating PDF with failure explanation instead of running check...")
                                    # Dialog schließen und direkt PDF erzeugen
                                    dialog.close()
                                    try:
                                        # Gemessene Daten für PDF aufbereiten
                                        pdf_rows = [
                                            {
                                                'Datum/Uhrzeit': m['datetime'].isoformat(),
                                                'Download (Mbit/s)': m['download'],
                                                'Upload (Mbit/s)': m['upload'],
                                                'Ping (ms)': m['ping'],
                                                'Betriebssystem': m['os'],
                                                'Internet-Browser': m['browser'],
                                            }
                                            for m in base_measurements
                                        ]
                                        pdf_bytes = generate_bnetza_pdf(
                                            result,
                                            float(contract_dl.value),
                                            float(contract_ul.value),
                                            pdf_rows
                                        )
                                        ui.download(pdf_bytes, f'bnetza_bericht_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')
                                        ui.notification('BNetzA PDF exportiert (Prüfung nicht möglich)', type='warning')
                                    except Exception as e:
                                        import traceback as _tb
                                        print(f"DEBUG: Error during PDF generation (no-subset): {e}")
                                        _tb.print_exc()
                                        ui.notification(f'Fehler beim PDF-Export: {e}', type='negative')
                                    return
                                
                                # Hauptprüfung im Thread ausführen
                                print("DEBUG: calling check_bnetza_requirements...")
                                result = await asyncio.to_thread(
                                    check_bnetza_requirements,
                                    used_measurements,
                                    float(contract_dl.value),
                                    float(contract_ul.value),
                                )
                                print(f"DEBUG: check completed -> valid={result.get('valid')}, errors={len(result.get('errors', []))}, warnings={len(result.get('warnings', []))}")
                                notif.message = '✓ Prüfung abgeschlossen, Ergebnisse werden angezeigt...'
                                notif.type = 'positive'
                                notif.spinner = False
                                notif.dismiss()
                            except Exception as e:
                                print(f"DEBUG: Error in check_bnetza_requirements: {e}")
                                import traceback
                                traceback.print_exc()
                                notif.message = f'Fehler: {str(e)}'
                                notif.type = 'negative'
                                notif.spinner = False
                                notif.timeout = 6.0
                                return
                            
                            print("DEBUG: generating PDF instead of opening result dialog...")
                            try:
                                # Gemessene Daten für PDF aufbereiten (verwendete Daten)
                                pdf_rows = [
                                    {
                                        'Datum/Uhrzeit': m['datetime'].isoformat(),
                                        'Download (Mbit/s)': m['download'],
                                        'Upload (Mbit/s)': m['upload'],
                                        'Ping (ms)': m['ping'],
                                        'Betriebssystem': m['os'],
                                        'Internet-Browser': m['browser'],
                                    }
                                    for m in used_measurements
                                ]
                                pdf_bytes = generate_bnetza_pdf(
                                    result,
                                    float(contract_dl.value),
                                    float(contract_ul.value),
                                    pdf_rows
                                )
                                ui.download(pdf_bytes, f'bnetza_bericht_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf')
                                ui.notification('BNetzA PDF exportiert', type='positive')
                                print("DEBUG: PDF download triggered")
                            except Exception as e:
                                print(f"DEBUG: Error during PDF generation: {e}")
                                import traceback as _tb
                                _tb.print_exc()
                                ui.notification(f'Fehler beim PDF-Export: {e}', type='negative')
                
                        # Aktionen im Eingabe-Dialog
                        with ui.row().classes('gap-2 pt-4'):
                            ui.button('Prüfen', on_click=run_check, color='primary', icon='check_circle')
                            ui.button('Abbrechen', on_click=dialog.close)

                dialog.open()
                
            with ui.row().classes('gap-2 pt-2'):
                ui.button('Als PDF exportieren', on_click=export_pdf, icon='file_download')
                ui.button('Als CSV exportieren', on_click=export_csv, icon='table_chart')
                ui.button('Daten neuladen', on_click=reload_data, icon='refresh')
                ui.button('Minderleistungsprüfung', on_click=check_bnetza, icon='check_circle')
            
            
            
            
            
            # Helper-Funktion für Stats-Tabelle UND Plot Updates
            def update_stats_and_plot(selected_rows: List[Dict] = None):
                """Aktualisiert die Statistik-Tabelle und den Plot basierend auf Auswahl."""
                if selected_rows:
                    downloads = [float(r['download']) for r in selected_rows]
                    uploads = [float(r['upload']) for r in selected_rows]
                    pings = [float(r['ping']) for r in selected_rows]
                    auswahl = {
                        'count': len(selected_rows),
                        'avg_download': sum(downloads)/len(downloads),
                        'min_download': min(downloads),
                        'max_download': max(downloads),
                        'avg_upload': sum(uploads)/len(uploads),
                        'min_upload': min(uploads),
                        'max_upload': max(uploads),
                        'avg_ping': sum(pings)/len(pings),
                        'min_ping': min(pings),
                        'max_ping': max(pings),
                    }
                    
                    # Konvertiere Grid-Daten zurück zu Measurement-Format
                    plot_measurements = [
                        {
                            'datetime': datetime.fromisoformat(r['datetime']),
                            'download': r['download'],
                            'upload': r['upload'],
                            'ping': r['ping'],
                        }
                        for r in selected_rows
                    ]
                else:
                    auswahl = {k: None for k in stats_all.keys()}
                    plot_measurements = None
                
                new_stats_rows = [
                    {'metric': 'Anzahl Messungen', 'gesamt': stats_all['count'], 'auswahl': auswahl['count'] if auswahl['count'] is not None else '-'},
                    {'metric': 'Ø Download (Mbit/s)', 'gesamt': f"{stats_all['avg_download']:.2f}", 'auswahl': f"{auswahl['avg_download']:.2f}" if auswahl['avg_download'] is not None else '-'},
                    {'metric': 'Min Download', 'gesamt': f"{stats_all['min_download']:.2f}", 'auswahl': f"{auswahl['min_download']:.2f}" if auswahl['min_download'] is not None else '-'},
                    {'metric': 'Max Download', 'gesamt': f"{stats_all['max_download']:.2f}", 'auswahl': f"{auswahl['max_download']:.2f}" if auswahl['max_download'] is not None else '-'},
                    {'metric': 'Ø Upload (Mbit/s)', 'gesamt': f"{stats_all['avg_upload']:.2f}", 'auswahl': f"{auswahl['avg_upload']:.2f}" if auswahl['avg_upload'] is not None else '-'},
                    {'metric': 'Min Upload', 'gesamt': f"{stats_all['min_upload']:.2f}", 'auswahl': f"{auswahl['min_upload']:.2f}" if auswahl['min_upload'] is not None else '-'},
                    {'metric': 'Max Upload', 'gesamt': f"{stats_all['max_upload']:.2f}", 'auswahl': f"{auswahl['max_upload']:.2f}" if auswahl['max_upload'] is not None else '-'},
                    {'metric': 'Ø Ping (ms)', 'gesamt': f"{stats_all['avg_ping']:.2f}", 'auswahl': f"{auswahl['avg_ping']:.2f}" if auswahl['avg_ping'] is not None else '-'},
                    {'metric': 'Min Ping', 'gesamt': f"{stats_all['min_ping']:.2f}", 'auswahl': f"{auswahl['min_ping']:.2f}" if auswahl['min_ping'] is not None else '-'},
                    {'metric': 'Max Ping', 'gesamt': f"{stats_all['max_ping']:.2f}", 'auswahl': f"{auswahl['max_ping']:.2f}" if auswahl['max_ping'] is not None else '-'},
                ]
                stats_table.rows = new_stats_rows
                stats_table.update()
                
                # Plot aktualisieren
                update_line_plot_data(plot_measurements)
            
            # Event Handler für Grid Selection
            async def on_grid_selection_change():
                selected_rows = await grid.get_selected_rows()
                update_stats_and_plot(selected_rows if selected_rows else None)
            
            grid.on('selectionChanged', on_grid_selection_change)
    
    # RECHTE SPALTE: Statistiken und Diagramme
    with ui.column().classes('flex-1'):
        # Statistik-Tabelle
        with ui.card().classes('w-full'):
            ui.label('Statistiken').classes('text-lg font-bold')
            
            stats_table = ui.table(
                columns=[
                    {'name': 'metric', 'label': 'Metrik', 'field': 'metric', 'align': 'left'},
                    {'name': 'gesamt', 'label': 'Gesamt', 'field': 'gesamt', 'align': 'right'},
                    {'name': 'auswahl', 'label': 'Auswahl', 'field': 'auswahl', 'align': 'right'},
                ],
                rows=[
                    {'metric': 'Anzahl Messungen', 'gesamt': stats_all['count'], 'auswahl': '-'},
                    {'metric': 'Ø Download (Mbit/s)', 'gesamt': f"{stats_all['avg_download']:.2f}", 'auswahl': '-'},
                    {'metric': 'Min Download', 'gesamt': f"{stats_all['min_download']:.2f}", 'auswahl': '-'},
                    {'metric': 'Max Download', 'gesamt': f"{stats_all['max_download']:.2f}", 'auswahl': '-'},
                    {'metric': 'Ø Upload (Mbit/s)', 'gesamt': f"{stats_all['avg_upload']:.2f}", 'auswahl': '-'},
                    {'metric': 'Min Upload', 'gesamt': f"{stats_all['min_upload']:.2f}", 'auswahl': '-'},
                    {'metric': 'Max Upload', 'gesamt': f"{stats_all['max_upload']:.2f}", 'auswahl': '-'},
                    {'metric': 'Ø Ping (ms)', 'gesamt': f"{stats_all['avg_ping']:.2f}", 'auswahl': '-'},
                    {'metric': 'Min Ping', 'gesamt': f"{stats_all['min_ping']:.2f}", 'auswahl': '-'},
                    {'metric': 'Max Ping', 'gesamt': f"{stats_all['max_ping']:.2f}", 'auswahl': '-'},
                ],
                row_key='metric'
            ).classes('w-full max-h-96')
        
        # Line Plot
        with ui.card().classes('w-full'):
            ui.label('Zeitserie: Download, Upload & Ping').classes('text-lg font-bold')
            
            # Selectable Chips für Plot-Filter
            with ui.row().classes('gap-2 pb-3'):
                show_download = ui.chip('Download', icon='cloud_download', color='blue', selectable=True, selected=True)
                show_upload = ui.chip('Upload', icon='cloud_upload', color='orange', selectable=True, selected=True)
                show_ping = ui.chip('Ping', icon='speed', color='green', selectable=True, selected=True)
            
            # Matplotlib-basiertes Plot mit dual-axis
            plot_container = ui.matplotlib(figsize=tuple(config['plot']['figsize']))
            async def download_plot_image():
                # Figure als PNG in Bytes exportieren
                buf = io.BytesIO()
                plot_container.figure.savefig(buf, format='png', dpi=150, bbox_inches='tight')
                buf.seek(0)
                ui.download(buf.getvalue(), f'plot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png')
            
            with ui.row().classes('gap-2 pb-2'):
                ui.button('Schaubild herunterladen', on_click=download_plot_image, icon='image')
            
            def update_line_plot_data(measurements: List[Dict] = None):
                """Aktualisiert den Plot mit den übergebenen Messungen."""
                global current_plot_measurements
                if measurements is not None:
                    current_plot_measurements = measurements
                plot_data = current_plot_measurements
                
                if not plot_data:
                    return
                
                # Sortiere nach Datetime
                plot_data = sorted(plot_data, key=lambda m: m['datetime'])
                
                # Matplotlib Plot erstellen
                plot_container.figure.clear()
                
                if len(plot_data) == 0:
                    return
                
                # X-Achsen-Labels vorbereiten (nur jedes N-te Label anzeigen für Übersichtlichkeit)
                x_indices = list(range(len(plot_data)))
                x_labels = [m['datetime'].strftime('%d.%m\n%H:%M') for m in plot_data]
                
                # Daten sammeln
                downloads = []
                uploads = []
                pings = []
                
                for measurement in plot_data:
                    downloads.append(measurement['download'])
                    uploads.append(measurement['upload'])
                    pings.append(measurement['ping'])
                
                # Primäre Achse für Download & Upload (Mbit/s)
                ax1 = plot_container.figure.gca()
                ax1.set_xlabel('Zeitpunkt', fontsize=10, fontweight='bold')
                ax1.set_ylabel('Geschwindigkeit (Mbit/s)', fontsize=10, fontweight='bold', color='black')
                
                # Plot Download & Upload
                line1 = None
                line2 = None
                if show_download.selected:
                    line1, = ax1.plot(x_indices, downloads, 'b-o', label='Download (Mbit/s)', linewidth=2, markersize=4)
                if show_upload.selected:
                    line2, = ax1.plot(x_indices, uploads, 'orange', marker='s', label='Upload (Mbit/s)', linewidth=2, markersize=4)
                
                ax1.tick_params(axis='y', labelcolor='black')
                ax1.grid(True, alpha=0.3)
                
                # Sekundäre Achse für Ping (ms) - nur wenn selektiert
                if show_ping.selected:
                    ax2 = ax1.twinx()
                    ax2.set_ylabel('Ping (ms)', fontsize=10, fontweight='bold', color='green')
                    line3, = ax2.plot(x_indices, pings, 'g-^', label='Ping (ms)', linewidth=2, markersize=4)
                    ax2.tick_params(axis='y', labelcolor='green')
                    
                    # Kombinierte Legende
                    lines = [line1, line2, line3] if line1 and line2 else ([line1, line3] if line1 else ([line2, line3] if line2 else [line3]))
                    labels = []
                    if line1:
                        labels.append('Download (Mbit/s)')
                    if line2:
                        labels.append('Upload (Mbit/s)')
                    if line3:
                        labels.append('Ping (ms)')
                    plot_container.figure.legend(lines, labels, loc='upper left', fontsize=9)
                else:
                    # Nur primäre Legende wenn Ping nicht aktiv
                    lines = []
                    labels = []
                    if line1:
                        lines.append(line1)
                        labels.append('Download (Mbit/s)')
                    if line2:
                        lines.append(line2)
                        labels.append('Upload (Mbit/s)')
                    if lines:
                        plot_container.figure.legend(lines, labels, loc='upper left', fontsize=9)
                
                # X-Achsen-Labels setzen (nur jedes 5. Label anzeigen wenn zu viele)
                tick_interval = max(1, len(x_labels) // 10)
                ax1.set_xticks([i for i in range(0, len(x_indices), tick_interval)])
                ax1.set_xticklabels([x_labels[i] if i < len(x_labels) else '' for i in range(0, len(x_indices), tick_interval)], fontsize=8)
                
                plot_container.figure.tight_layout()
                plot_container.update()
            
            # Initial rendern mit aktuellem Zeitraum-Filter
            _sel = timeframe_select.value
            _initial_plot_data = (
                all_measurements if _sel == 'all'
                else filter_measurements_by_timeframe(all_measurements, int(_sel))
            )
            update_line_plot_data(_initial_plot_data)
            
            # Update wenn Chips selektiert werden
            show_download.on_selection_change(lambda: update_line_plot_data(None))
            show_upload.on_selection_change(lambda: update_line_plot_data(None))
            show_ping.on_selection_change(lambda: update_line_plot_data(None))

# ============================================================================
# EVENT HANDLER
# ============================================================================
def on_timeframe_change():
    """Aktualisiert die Daten basierend auf dem ausgewählten Zeitfenster."""
    selected_value = timeframe_select.value
    
    if selected_value == 'all':
        filtered = all_measurements
    else:
        days = int(selected_value)
        filtered = filter_measurements_by_timeframe(all_measurements, days)
    
    # AGGrid aktualisieren
    new_grid_data = [
        {
            'datetime': m['datetime'].isoformat(),
            'download': m['download'],
            'upload': m['upload'],
            'ping': m['ping'],
            'os': m['os'],
            'browser': m['browser'],
        }
        for m in filtered
    ]
    grid.options['rowData'] = new_grid_data
    grid.update()
    
    # Statistiken aktualisieren
    global stats_all
    stats = calculate_statistics(filtered)
    new_stats_rows = [
        {'metric': 'Anzahl Messungen', 'gesamt': stats_all['count'], 'auswahl': stats['count']},
        {'metric': 'Ø Download (Mbit/s)', 'gesamt': f"{stats_all['avg_download']:.2f}", 'auswahl': f"{stats['avg_download']:.2f}"},
        {'metric': 'Min Download', 'gesamt': f"{stats_all['min_download']:.2f}", 'auswahl': f"{stats['min_download']:.2f}"},
        {'metric': 'Max Download', 'gesamt': f"{stats_all['max_download']:.2f}", 'auswahl': f"{stats['max_download']:.2f}"},
        {'metric': 'Ø Upload (Mbit/s)', 'gesamt': f"{stats_all['avg_upload']:.2f}", 'auswahl': f"{stats['avg_upload']:.2f}"},
        {'metric': 'Min Upload', 'gesamt': f"{stats_all['min_upload']:.2f}", 'auswahl': f"{stats['min_upload']:.2f}"},
        {'metric': 'Max Upload', 'gesamt': f"{stats_all['max_upload']:.2f}", 'auswahl': f"{stats['max_upload']:.2f}"},
        {'metric': 'Ø Ping (ms)', 'gesamt': f"{stats_all['avg_ping']:.2f}", 'auswahl': f"{stats['avg_ping']:.2f}"},
        {'metric': 'Min Ping', 'gesamt': f"{stats_all['min_ping']:.2f}", 'auswahl': f"{stats['min_ping']:.2f}"},
        {'metric': 'Max Ping', 'gesamt': f"{stats_all['max_ping']:.2f}", 'auswahl': f"{stats['max_ping']:.2f}"},
    ]
    stats_table.rows = new_stats_rows
    stats_table.update()
    
    # Plot aktualisieren und globalen Zustand setzen
    update_line_plot_data(filtered)

timeframe_select.on('update:model-value', on_timeframe_change)

ui.run(
    host=config['ui']['host'],
    port=config['ui']['port'],
    title=config['ui']['title']
)
