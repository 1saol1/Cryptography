"""Public/private key exchange protocols and QR code handling."""

from typing import List, Optional


class KeyExchange:
    """Handles public key exchange and management."""

    def generate_key_pair(self, algorithm: str = "RSA-2048") -> dict:
        """
        Generate new key pair for sharing.

        Args:
            algorithm: "RSA-2048" or "ECC-P256"

        Returns:
            Dict with 'private_key' and 'public_key' (PEM format)
        """
        raise NotImplementedError("Key generation to be implemented")


class QRCodeService:
    """Handles QR code generation and scanning for key exchange."""

    def generate_qr_code(self, data: bytes, chunk_size: int = 2953) -> List[str]:
        """
        Generate QR code(s) for data, chunking if necessary.

        Args:
            data: Data to encode
            chunk_size: Max bytes per QR code

        Returns:
            List of QR code images (SVG strings)
        """
        raise NotImplementedError("QR generation to be implemented")

    def decode_qr_chunks(self, chunks: List[str]) -> Optional[bytes]:
        """
        Decode and reassemble data from QR chunks.

        Args:
            chunks: List of QR code chunk strings

        Returns:
            Decoded bytes or None if validation fails
        """
        raise NotImplementedError("QR decoding to be implemented")