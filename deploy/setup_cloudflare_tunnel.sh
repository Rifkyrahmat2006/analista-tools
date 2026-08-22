#!/bin/bash
# Setup Cloudflare Tunnel untuk amertools.rifkyprakoso.my.id -> Analista Tools
# Jalankan SETELAH Zero Trust diaktifkan di dashboard Cloudflare.
#
# Prasyarat:
# - ~/.config/cloudflare/credentials berisi CLOUDFLARE_API_TOKEN & CLOUDFLARE_ACCOUNT_ID
#   dengan izin: Cloudflare Tunnel:Edit, DNS:Edit (zone rifkyprakoso.my.id)
# - cloudflared terpasang di ~/.local/bin/cloudflared
# - Container analista-tools sudah jalan di 127.0.0.1:8501

set -euo pipefail

source ~/.config/cloudflare/credentials
export PATH="$HOME/.local/bin:$PATH"

ZONE_ID="174e1decb7bc52941f85bc600ba91659"  # rifkyprakoso.my.id
SUBDOMAIN="amertools.rifkyprakoso.my.id"
TUNNEL_NAME="amertools-tunnel"

echo "=== 1. Membuat Cloudflare Tunnel ==="
TUNNEL_SECRET=$(openssl rand -base64 32)
RESP=$(curl -s -X POST "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/cfd_tunnel" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" -H "Content-Type: application/json" \
  --data "{\"name\":\"${TUNNEL_NAME}\",\"tunnel_secret\":\"${TUNNEL_SECRET}\",\"config_src\":\"cloudflare\"}")

SUCCESS=$(echo "$RESP" | grep -o '"success":[a-z]*' | head -1 | cut -d: -f2)
if [ "$SUCCESS" != "true" ]; then
  echo "GAGAL membuat tunnel:"
  echo "$RESP"
  exit 1
fi

TUNNEL_ID=$(echo "$RESP" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "Tunnel dibuat: $TUNNEL_ID"

echo "=== 2. Konfigurasi ingress (remote config via API) ==="
curl -s -X PUT "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/cfd_tunnel/${TUNNEL_ID}/configurations" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" -H "Content-Type: application/json" \
  --data "{\"config\":{\"ingress\":[{\"hostname\":\"${SUBDOMAIN}\",\"service\":\"http://127.0.0.1:8501\"},{\"service\":\"http_status:404\"}]}}" \
  | tee /tmp/tunnel_config_resp.json > /dev/null
echo "Ingress dikonfigurasi."

echo "=== 3. Buat DNS CNAME record ==="
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" -H "Content-Type: application/json" \
  --data "{\"type\":\"CNAME\",\"name\":\"amertools\",\"content\":\"${TUNNEL_ID}.cfargotunnel.com\",\"proxied\":true}" \
  | tee /tmp/dns_create_resp.json > /dev/null
echo "DNS record dibuat."

echo "=== 4. Ambil credentials tunnel & simpan token untuk systemd ==="
TOKEN_RESP=$(curl -s -X GET "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/cfd_tunnel/${TUNNEL_ID}/token" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}")
CF_TUNNEL_TOKEN=$(echo "$TOKEN_RESP" | grep -o '"result":"[^"]*"' | cut -d'"' -f4)

if [ -z "$CF_TUNNEL_TOKEN" ]; then
  echo "GAGAL mengambil tunnel token:"
  echo "$TOKEN_RESP"
  exit 1
fi

echo "$TUNNEL_ID" > /tmp/amertools_tunnel_id.txt
echo "$CF_TUNNEL_TOKEN" > /tmp/amertools_tunnel_token.txt
chmod 600 /tmp/amertools_tunnel_token.txt

echo ""
echo "=== SELESAI ==="
echo "Tunnel ID   : $TUNNEL_ID"
echo "Subdomain   : https://${SUBDOMAIN}"
echo "Token disimpan sementara di /tmp/amertools_tunnel_token.txt (untuk setup systemd service)"
echo ""
echo "Langkah berikutnya: jalankan cloudflared sebagai systemd service dengan token ini."
