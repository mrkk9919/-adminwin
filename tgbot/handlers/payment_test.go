package handlers

import (
	"strings"
	"testing"
	"time"

	"tgbot/db"
)

func TestFormatPaymentMessage_UsesTransferTemplate(t *testing.T) {
	state := &paymentState{
		recipient: "SRO PHEARIN",
		account:   "855969357160",
		amount:    500,
		currency:  "USD",
		hash:      "bqr_test_e2e_1785760021",
		bank:      "ABA Bank",
		ref:       "104197081",
	}

	msg := formatPaymentMessage(state)
	for _, want := range []string{
		"✅ Transaction Successful",
		"Type: Transfer",
		"Amount: 500.00 USD",
		"Account: 855969357160",
		"To: SRO PHEARIN — 855969357160",
		"Description: Channel: ABA Bank | Hash: bqr_test_e2e_1785760021",
		"Ref: 104197081",
		"Thank you for banking with ABA.",
	} {
		if !strings.Contains(msg, want) {
			t.Fatalf("expected %q in message, got: %s", want, msg)
		}
	}
}

func TestResolveRecipientTelegramID_UsesPhoneLookup(t *testing.T) {
	id, ok, err := resolveRecipientTelegramID(func(phone string) (*db.Customer, error) {
		if phone != "855969357160" {
			t.Fatalf("unexpected phone lookup: %s", phone)
		}
		return &db.Customer{TelegramID: 123456789}, nil
	}, "855969357160")
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if !ok {
		t.Fatal("expected recipient to be resolved")
	}
	if id != 123456789 {
		t.Fatalf("expected telegram id 123456789, got %d", id)
	}
}

func TestResolveRecipientTelegramID_NormalizesPhoneBeforeLookup(t *testing.T) {
	id, ok, err := resolveRecipientTelegramID(func(phone string) (*db.Customer, error) {
		if phone != "855969357160" {
			t.Fatalf("expected normalized phone lookup, got: %s", phone)
		}
		return &db.Customer{TelegramID: 987654321}, nil
	}, "+855 969 357 160")
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if !ok {
		t.Fatal("expected recipient to be resolved")
	}
	if id != 987654321 {
		t.Fatalf("expected telegram id 987654321, got %d", id)
	}
}

func TestNotifyPaymentRecipientAsync_UsesBackgroundDispatch(t *testing.T) {
	started := make(chan struct{})
	notifyPaymentRecipientAsync(nil, 0, func() error {
		close(started)
		return nil
	})

	select {
	case <-started:
	case <-time.After(100 * time.Millisecond):
		t.Fatal("expected background notification dispatch to start")
	}
}
