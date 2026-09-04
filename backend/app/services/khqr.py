"""KHQR Code Generator — EMVCo-compliant QR for BAkong (Cambodia).

Generates KHQR strings and QR code images that conform to the
National Bank of Cambodia's KHQR specification (based on EMVCo
Merchant-Presented Mode QR).

Usage:
    from app.services.khqr import generate_khqr, generate_khqr_image

    # Get the KHQR payload string
    payload = generate_khqr(
        account_id="012345678",
        bank_code="wing_bank",
        amount="300.00",
        currency="USD",
        merchant_name="Wing Bank",
    )

    # Get a PNG image (bytes)
    img_bytes = generate_khqr_image(payload, size=300)
"""
from __future__ import annotations

import io
import struct
from dataclasses import dataclass, field

import qrcode


# ---------------------------------------------------------------------------
# EMVCo CRC16-CCITT (polynomial 0x1021, init 0xFFFF)
# ---------------------------------------------------------------------------
def _crc16(data: str) -> str:
    """Compute CRC16-CCITT over *data* and return 4-digit uppercase hex."""
    crc = 0xFFFF
    for ch in data:
        crc ^= ord(ch) << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            crc &= 0xFFFF
    return f"{crc:04X}"


# ---------------------------------------------------------------------------
# TLV encoding helpers
# ---------------------------------------------------------------------------
def _tlv(tag: str, value: str) -> str:
    """Encode a single EMVCo TLV element: tag(2) + length(2) + value."""
    return f"{tag}{len(value):02d}{value}"


def _merchant_account_info(account_id: str, bank_code: str = "") -> str:
    """Build Tag-29 Merchant Account Information (Bakong).

    Sub-tags:
      00 — Globally Unique Identifier (always "kh.org.bakong")
      01 — Merchant/Account ID
      02 — Acquiring Bank identifier (optional)
    """
    inner = _tlv("00", "kh.org.bakong")
    inner += _tlv("01", account_id)
    if bank_code:
        inner += _tlv("02", bank_code)
    return _tlv("29", inner)


def _additional_data(reference: str = "", mobile: str = "", bill_number: str = "") -> str:
    """Build Tag-62 Additional Data Field Template."""
    inner = ""
    if bill_number:
        inner += _tlv("01", bill_number)
    if mobile:
        inner += _tlv("02", mobile)
    if reference:
        inner += _tlv("05", reference)
    if not inner:
        inner = _tlv("05", "***")  # EMVCo requires at least one sub-tag
    return _tlv("62", inner)


# ---------------------------------------------------------------------------
# Currency code mapping
# ---------------------------------------------------------------------------
_CURRENCY_CODE = {
    "USD": "840",
    "KHR": "116",
    "usd": "840",
    "khr": "116",
}


# ---------------------------------------------------------------------------
# Data class for KHQR parameters
# ---------------------------------------------------------------------------
@dataclass
class KHQRParams:
    """Parameters for generating a KHQR code."""

    account_id: str                         # Bakong account number
    bank_code: str = ""                     # Bank identifier (e.g. "wing_bank")
    amount: str = ""                        # Transaction amount (empty = dynamic)
    currency: str = "USD"                   # USD or KHR
    merchant_name: str = "Wing Bank"        # Merchant / recipient name
    merchant_city: str = "Phnom Penh"       # Merchant city
    reference: str = ""                     # Payment reference
    mobile: str = ""                        # Mobile number
    bill_number: str = ""                   # Bill number
    dynamic: bool = True                    # True = one-time QR, False = static


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate_khqr(
    account_id: str,
    bank_code: str = "",
    amount: str = "",
    currency: str = "USD",
    merchant_name: str = "Wing Bank",
    merchant_city: str = "Phnom Penh",
    reference: str = "",
    mobile: str = "",
    bill_number: str = "",
    dynamic: bool = True,
) -> str:
    """Generate an EMVCo-compliant KHQR payload string.

    Parameters
    ----------
    account_id : str
        The Bakong account number / merchant ID.
    bank_code : str
        Acquiring bank identifier (e.g. "wing_bank", "aba_bank").
    amount : str
        Transaction amount. Empty string means "dynamic" (user enters amount).
    currency : str
        "USD" or "KHR".
    merchant_name : str
        Recipient display name (max 25 chars).
    merchant_city : str
        City name (max 15 chars).
    reference : str
        Payment reference label.
    mobile : str
        Mobile number for additional data.
    bill_number : str
        Bill number for additional data.
    dynamic : bool
        If True, generates a one-time QR (Tag 01 = "12").
        If False, generates a static QR (Tag 01 = "11").

    Returns
    -------
    str
        The complete KHQR payload string (ready to encode as QR).
    """
    # Tag 00: Payload Format Indicator
    payload = _tlv("00", "01")

    # Tag 01: Point of Initiation Method
    poi = "12" if (dynamic and amount) else "11"
    payload += _tlv("01", poi)

    # Tag 29: Merchant Account Information — Bakong
    payload += _merchant_account_info(account_id, bank_code)

    # Tag 52: Merchant Category Code
    payload += _tlv("52", "0000")

    # Tag 53: Transaction Currency
    cur_code = _CURRENCY_CODE.get(currency, "840")
    payload += _tlv("53", cur_code)

    # Tag 54: Transaction Amount (only if specified)
    if amount:
        payload += _tlv("54", amount)

    # Tag 58: Country Code
    payload += _tlv("58", "KH")

    # Tag 59: Merchant Name (max 25 chars)
    payload += _tlv("59", merchant_name[:25])

    # Tag 60: Merchant City (max 15 chars)
    payload += _tlv("60", merchant_city[:15])

    # Tag 62: Additional Data Field
    payload += _additional_data(reference, mobile, bill_number)

    # Tag 63: CRC — placeholder "6304" then compute
    payload += "6304"
    crc = _crc16(payload)
    payload = payload + crc  # Replace "6304" is already in payload, append crc

    return payload


def generate_khqr_image(
    payload: str,
    size: int = 300,
    border: int = 4,
) -> bytes:
    """Generate a PNG QR code image from a KHQR payload string.

    Returns the raw PNG bytes suitable for HTTP response or file saving.
    """
    qr = qrcode.QRCode(
        version=None,  # auto-determine
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=border,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img = img.resize((size, size))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def decode_khqr(payload: str) -> dict:
    """Parse a KHQR payload string and return a dict of decoded fields.

    Useful for verifying generated QR codes or reading scanned ones.
    """
    result: dict = {}
    i = 0
    while i < len(payload) - 4:  # -4 for CRC tag
        tag = payload[i : i + 2]
        length = int(payload[i + 2 : i + 4])
        value = payload[i + 4 : i + 4 + length]
        i += 4 + length

        if tag == "29":
            # Parse sub-tags
            sub = {}
            j = 0
            while j < len(value):
                stag = value[j : j + 2]
                slen = int(value[j + 2 : j + 4])
                sval = value[j + 4 : j + 4 + slen]
                j += 4 + slen
                labels = {"00": "guid", "01": "account_id", "02": "bank_code"}
                sub[labels.get(stag, stag)] = sval
            result["merchant_account"] = sub
        elif tag == "62":
            sub = {}
            j = 0
            while j < len(value):
                stag = value[j : j + 2]
                slen = int(value[j + 2 : j + 4])
                sval = value[j + 4 : j + 4 + slen]
                j += 4 + slen
                labels = {"01": "bill_number", "02": "mobile", "05": "reference"}
                sub[labels.get(stag, stag)] = sval
            result["additional_data"] = sub
        elif tag == "63":
            result["crc"] = value
            # Verify CRC
            check_payload = payload[: i - 4 - length + 4 + length]  # up to "6304"
            computed = _crc16(payload[: -4])
            result["crc_valid"] = value == computed
        else:
            labels = {
                "00": "version",
                "01": "initiation_method",
                "52": "mcc",
                "53": "currency_code",
                "54": "amount",
                "58": "country",
                "59": "merchant_name",
                "60": "merchant_city",
            }
            key = labels.get(tag, f"tag_{tag}")
            result[key] = value

    # Decode currency code
    cur_map = {"840": "USD", "116": "KHR"}
    if "currency_code" in result:
        result["currency"] = cur_map.get(result["currency_code"], result["currency_code"])

    return result
