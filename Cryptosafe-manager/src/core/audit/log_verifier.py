from typing import Dict, Any, Optional, List
import hashlib
import logging

logger = logging.getLogger(__name__)


class LogVerifier:
    def __init__(self, db_connection, signer):
        self.db = db_connection
        self.signer = signer

    def verify_recent(self, count: int = 1000) -> Dict[str, Any]:

        cursor = self.db.execute("SELECT MAX(sequence_number) FROM audit_log")
        max_seq = cursor.fetchone()[0]

        if max_seq is None:
            return {
                'verified': True,
                'total_entries': 0,
                'message': 'No entries to verify'
            }

        start_seq = max(0, max_seq - count + 1)

        logger.info(f"Periodic verification of entries {start_seq} to {max_seq}")

        return self.verify_integrity(start_seq=start_seq)

    def verify_integrity(self, start_seq: int = 0, end_seq: Optional[int] = None) -> Dict[str, Any]:
        rows = self._fetch_entries(start_seq, end_seq)

        if not rows:
            return {
                'verified': True,
                'total_entries': 0,
                'valid_entries': 0,
                'invalid_entries': [],
                'chain_breaks': [],
                'tampering_detected': False
            }

        results = {
            'verified': True,
            'total_entries': len(rows),
            'valid_entries': 0,
            'invalid_entries': [],
            'chain_breaks': [],
            'tampering_detected': False
        }

        previous_hash = None
        previous_seq = None

        for seq_num, entry_data_blob, signature_hex, entry_hash, prev_hash, event_type, timestamp in rows:
            entry_data = entry_data_blob.decode('utf-8')
            signature = bytes.fromhex(signature_hex)

            if not self.signer.verify(entry_data.encode(), signature):
                results['invalid_entries'].append({
                    'sequence': seq_num,
                    'reason': 'Invalid signature',
                    'event_type': event_type
                })
                results['verified'] = False
                results['tampering_detected'] = True
                continue

            computed_hash = hashlib.sha256(entry_data.encode()).hexdigest()
            if computed_hash != entry_hash:
                results['invalid_entries'].append({
                    'sequence': seq_num,
                    'reason': 'Hash mismatch',
                    'event_type': event_type
                })
                results['verified'] = False
                results['tampering_detected'] = True
                continue

            if previous_hash is not None and prev_hash != previous_hash:
                results['chain_breaks'].append({
                    'sequence': seq_num,
                    'expected_previous_hash': previous_hash,
                    'actual_previous_hash': prev_hash,
                    'previous_sequence': previous_seq
                })
                results['verified'] = False
                results['tampering_detected'] = True

            results['valid_entries'] += 1
            previous_hash = entry_hash
            previous_seq = seq_num

        if rows:
            first_seq, _, _, _, first_prev_hash, _, _ = rows[0]
            if first_prev_hash != '0' * 64:
                results['chain_breaks'].append({
                    'sequence': first_seq,
                    'reason': 'Genesis entry has invalid previous_hash'
                })
                results['verified'] = False
                results['tampering_detected'] = True

        return results

    def _fetch_entries(self, start_seq: int = 0, end_seq: Optional[int] = None) -> List[tuple]:
        query = """
            SELECT sequence_number, entry_data, signature, entry_hash, previous_hash, event_type, timestamp
            FROM audit_log
            WHERE sequence_number >= ?
        """
        params = [start_seq]

        if end_seq is not None:
            query += " AND sequence_number <= ?"
            params.append(end_seq)

        query += " ORDER BY sequence_number"

        cursor = self.db.execute(query, params)
        return cursor.fetchall()

    def verify_full_with_report(self) -> Dict[str, Any]:
        result = self.verify_integrity()

        if result['verified']:
            result['report'] = (
                f"Audit Log Integrity Check passed\n"
                f"Total entries verified: {result['total_entries']}\n"
                f"Valid signatures: {result['valid_entries']}\n"
                f"Hash chain: intact\n"
                f"Tampering detected: no\n"
                f"Verification completed successfully."
            )
        else:
            result['report'] = (
                f"Audit Log Integrity Check failed\n"
                f"Total entries verified: {result['total_entries']}\n"
                f"Valid signatures: {result['valid_entries']}\n"
                f"Invalid signatures: {len(result['invalid_entries'])}\n"
                f"Chain breaks: {len(result['chain_breaks'])}\n"
                f"Tampering detected: yes\n"
            )

            if result['invalid_entries']:
                result['report'] += f"\nInvalid signatures found:\n"
                for inv in result['invalid_entries'][:10]:
                    result['report'] += f"   - Sequence {inv['sequence']}: {inv['reason']}\n"
                if len(result['invalid_entries']) > 10:
                    result['report'] += f"   ... and {len(result['invalid_entries']) - 10} more\n"

            if result['chain_breaks']:
                result['report'] += f"\nChain breaks found:\n"
                for br in result['chain_breaks'][:10]:
                    result['report'] += f"   - Break at sequence {br.get('sequence', '?')}\n"
                if len(result['chain_breaks']) > 10:
                    result['report'] += f"   ... and {len(result['chain_breaks']) - 10} more\n"

        return result
