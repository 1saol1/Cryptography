import json
import csv
from datetime import datetime
from typing import Dict, Any, List
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


class LogFormatter:

    def __init__(self, db_connection, signer=None):
        self.db = db_connection
        self.signer = signer

    def export_to_signed_json(self, entries: List[Dict[str, Any]],
                              output_path: str,
                              export_range: Dict[str, str] = None) -> bool:
        try:
            export_data = {
                'metadata': {
                    'export_timestamp': datetime.now().isoformat(),
                    'import_export': 'CryptoSafe Manager',
                    'version': '1.0',
                    'total_entries': len(entries),
                    'date_range': export_range or {}
                },
                'public_key': None,
                'entries': []
            }

            if self.signer and hasattr(self.signer, 'get_public_key_bytes'):
                pub_key = self.signer.get_public_key_bytes()
                if pub_key:
                    export_data['public_key'] = pub_key.hex()

            for entry in entries:
                entry_dict = {
                    'sequence_number': entry.get('sequence_number'),
                    'timestamp': entry.get('timestamp'),
                    'event_type': entry.get('event_type'),
                    'severity': entry.get('severity'),
                    'user_id': entry.get('user_id'),
                    'source': entry.get('source'),
                    'entry_hash': entry.get('entry_hash'),
                    'signature': entry.get('signature'),
                    'previous_hash': entry.get('previous_hash'),
                    'entry_data': None
                }

                entry_data = entry.get('entry_data')
                if isinstance(entry_data, bytes):
                    entry_data = entry_data.decode('utf-8')
                if isinstance(entry_data, str):
                    try:
                        entry_dict['entry_data'] = json.loads(entry_data)
                    except:
                        entry_dict['entry_data'] = entry_data
                else:
                    entry_dict['entry_data'] = entry_data

                export_data['entries'].append(entry_dict)

            if self.signer:
                export_json = json.dumps(export_data, sort_keys=True, default=str)
                signature = self.signer.sign(export_json.encode())
                export_data['export_signature'] = signature.hex()

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)

            return True

        except Exception as e:
            print(f"Error exporting to signed JSON: {e}")
            return False

    def export_to_csv(self, entries: List[Dict[str, Any]], output_path: str) -> bool:
        try:
            with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)

                writer.writerow([
                    'Sequence', 'Timestamp', 'Event Type', 'Severity',
                    'User ID', 'Source', 'Details'
                ])

                for entry in entries:
                    entry_data = entry.get('entry_data')
                    if isinstance(entry_data, bytes):
                        entry_data = entry_data.decode('utf-8')

                    details = ""
                    if isinstance(entry_data, str):
                        try:
                            data = json.loads(entry_data)
                            details = json.dumps(data.get('details', {}), ensure_ascii=False)[:500]
                        except:
                            details = entry_data[:500]

                    writer.writerow([
                        entry.get('sequence_number', ''),
                        entry.get('timestamp', ''),
                        entry.get('event_type', ''),
                        entry.get('severity', ''),
                        entry.get('user_id', ''),
                        entry.get('source', ''),
                        details
                    ])

            return True

        except Exception as e:
            print(f"Error exporting to CSV: {e}")
            return False

    def export_to_pdf(self, entries: List[Dict[str, Any]], output_path: str,
                      summary: Dict[str, Any] = None) -> bool:
        try:

            doc = SimpleDocTemplate(output_path, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()


            story.append(Paragraph("Audit Log Report", styles['Title']))
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph(f"Generated: {datetime.now()}", styles['Normal']))
            story.append(Spacer(1, 0.3 * inch))


            data = [['Time', 'Event', 'Severity', 'User', 'Details']]

            for entry in entries[:100]:
                entry_data = entry.get('entry_data', '')
                if isinstance(entry_data, bytes):
                    entry_data = entry_data.decode('utf-8', errors='ignore')

                details = entry_data[:50] if entry_data else ''

                data.append([
                    str(entry.get('timestamp', ''))[:16],
                    str(entry.get('event_type', ''))[:20],
                    str(entry.get('severity', '')),
                    str(entry.get('user_id', ''))[:15],
                    details
                ])

            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            story.append(table)
            doc.build(story)
            return True

        except Exception as e:
            print(f"PDF export error: {e}")
            return False

    def get_entries_for_export(self, start_date: str = None, end_date: str = None,
                               event_type: str = None) -> List[Dict[str, Any]]:

        query = """
            SELECT sequence_number, timestamp, event_type, severity, user_id, source,
                   entry_data, entry_hash, signature, previous_hash
            FROM audit_log
            WHERE 1=1
        """
        params = []

        if start_date:
            query += " AND date(timestamp) >= ?"
            params.append(start_date)

        if end_date:
            query += " AND date(timestamp) <= ?"
            params.append(end_date)

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)

        query += " ORDER BY sequence_number"

        cursor = self.db.execute(query, params)
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    @staticmethod
    def verify_signed_export(file_path: str) -> Dict[str, Any]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                export_data = json.load(f)

            results = {
                'verified': False,
                'has_export_signature': 'export_signature' in export_data,
                'entries_count': len(export_data.get('entries', [])),
                'errors': []
            }

            if 'export_signature' not in export_data:
                results['errors'].append("Export file missing signature")
                return results

            export_signature = bytes.fromhex(export_data.pop('export_signature'))

            export_json = json.dumps(export_data, sort_keys=True, default=str)

            if 'public_key' in export_data and export_data['public_key']:
                try:
                    public_key_bytes = bytes.fromhex(export_data['public_key'])
                    public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
                    public_key.verify(export_signature, export_json.encode())
                    results['verified'] = True
                    results['message'] = "Export signature is valid"
                except Exception as e:
                    results['errors'].append(f"Signature verification failed: {e}")
            else:
                results['errors'].append("No public key found for verification")

            return results

        except Exception as e:
            return {
                'verified': False,
                'has_export_signature': False,
                'entries_count': 0,
                'errors': [f"Failed to read export file: {e}"]
            }