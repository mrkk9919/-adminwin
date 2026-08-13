#!/usr/bin/env bash
set -euo pipefail

DOMAIN=${1:-wingdigital.fit}

if ! command -v dig >/dev/null 2>&1; then
  echo "Error: dig is not installed. Install dnsutils or bind-tools."
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "Error: curl is not installed."
  exit 1
fi

echo "Checking domain: $DOMAIN"
echo
printf '%s\n' '=== Nameservers ==='
dig +short NS "$DOMAIN" | sort || true
echo
printf '%s\n' '=== A records ==='
dig +short A "$DOMAIN" | sort -u || true
echo
printf '%s\n' '=== CAA records ==='
dig +short CAA "$DOMAIN" | sort -u || true
echo
printf '%s\n' '=== HTTP HEAD ==='
curl -I -L --max-time 10 "http://$DOMAIN" 2>&1 | sed -n '1,20p' || true
echo
printf '%s\n' '=== HTTPS HEAD ==='
curl -I -L --max-time 10 "https://$DOMAIN" 2>&1 | sed -n '1,20p' || true
echo
printf '%s\n' '=== WWW HTTPS HEAD ==='
curl -I -L --max-time 10 "https://www.$DOMAIN" 2>&1 | sed -n '1,20p' || true
