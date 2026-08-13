package handlers

import (
	"fmt"
	"strconv"
	"strings"
)

// KHQRData holds the parsed fields from a KHQR payload.
type KHQRData struct {
	AccountID string
	BankCode  string
	Amount    string
	Currency  string
	Name      string
	City      string
	GUID      string
	CRC       string
	CRCValid  bool
}

// khqrTLV encodes a single EMVCo TLV element: tag(2) + length(2) + value.
func khqrTLV(tag, value string) string {
	return fmt.Sprintf("%s%02d%s", tag, len(value), value)
}

// GenerateKHQR creates an EMVCo-compliant KHQR payload string for BAkong.
//
// Parameters:
//   - accountID:  Bakong account number / merchant ID
//   - bankCode:   Bank identifier (e.g. "wing_bank")
//   - amount:     Transaction amount (empty = dynamic QR)
//   - currency:   "USD" or "KHR"
//   - name:       Recipient / merchant name
func GenerateKHQR(accountID, bankCode, amount, currency, name string) string {
	// Tag 00: Payload Format Indicator
	payload := khqrTLV("00", "01")

	// Tag 01: Point of Initiation Method (12=dynamic, 11=static)
	if amount != "" {
		payload += khqrTLV("01", "12")
	} else {
		payload += khqrTLV("01", "11")
	}

	// Tag 29: Merchant Account Information — Bakong
	inner := khqrTLV("00", "kh.org.bakong")
	inner += khqrTLV("01", accountID)
	if bankCode != "" {
		inner += khqrTLV("02", bankCode)
	}
	payload += khqrTLV("29", inner)

	// Tag 52: Merchant Category Code
	payload += khqrTLV("52", "0000")

	// Tag 53: Transaction Currency
	curCode := "840" // USD
	if currency == "KHR" || currency == "khr" {
		curCode = "116"
	}
	payload += khqrTLV("53", curCode)

	// Tag 54: Transaction Amount
	if amount != "" {
		payload += khqrTLV("54", amount)
	}

	// Tag 58: Country Code
	payload += khqrTLV("58", "KH")

	// Tag 59: Merchant Name (max 25 chars)
	if len(name) > 25 {
		name = name[:25]
	}
	payload += khqrTLV("59", name)

	// Tag 60: Merchant City
	payload += khqrTLV("60", "Phnom Penh")

	// Tag 62: Additional Data Field
	payload += khqrTLV("62", khqrTLV("05", "***"))

	// Tag 63: CRC placeholder
	payload += "6304"
	crc := khqrCRC16(payload)
	payload += crc

	return payload
}

// khqrCRC16 computes CRC16-CCITT (polynomial 0x1021, init 0xFFFF).
func khqrCRC16(data string) string {
	crc := uint16(0xFFFF)
	for _, ch := range data {
		crc ^= uint16(ch) << 8
		for i := 0; i < 8; i++ {
			if crc&0x8000 != 0 {
				crc = (crc << 1) ^ 0x1021
			} else {
				crc = crc << 1
			}
		}
	}
	return fmt.Sprintf("%04X", crc)
}

// DecodeKHQR parses a KHQR payload string into a KHQRData struct.
func DecodeKHQR(payload string) (*KHQRData, error) {
	if len(payload) < 8 {
		return nil, fmt.Errorf("payload too short")
	}

	data := &KHQRData{}
	i := 0
	for i < len(payload)-4 {
		if i+4 > len(payload) {
			break
		}
		tag := payload[i : i+2]
		lengthStr := payload[i+2 : i+4]
		length, err := strconv.Atoi(lengthStr)
		if err != nil {
			break
		}
		end := i + 4 + length
		if end > len(payload) {
			break
		}
		value := payload[i+4 : end]
		i = end

		switch tag {
		case "29": // Merchant Account — Bakong
			j := 0
			for j < len(value) {
				if j+4 > len(value) {
					break
				}
				stag := value[j : j+2]
				slen, serr := strconv.Atoi(value[j+2 : j+4])
				if serr != nil {
					break
				}
				send := j + 4 + slen
				if send > len(value) {
					break
				}
				sval := value[j+4 : send]
				j = send
				switch stag {
				case "00":
					data.GUID = sval
				case "01":
					data.AccountID = sval
				case "02":
					data.BankCode = sval
				}
			}
		case "53":
			if value == "840" {
				data.Currency = "USD"
			} else if value == "116" {
				data.Currency = "KHR"
			} else {
				data.Currency = value
			}
		case "54":
			data.Amount = value
		case "59":
			data.Name = sval_safe(value)
		case "60":
			data.City = sval_safe(value)
		case "63":
			data.CRC = value
			computed := khqrCRC16(payload[:len(payload)-4])
			data.CRCValid = strings.EqualFold(value, computed)
		}
	}

	if data.AccountID == "" {
		return nil, fmt.Errorf("no account ID found in KHQR")
	}
	return data, nil
}

// sval_safe returns the string, trimmed of whitespace.
func sval_safe(s string) string {
	return strings.TrimSpace(s)
}
