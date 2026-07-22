#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
	echo "Usage: $0 APP_PATH OUTPUT_DMG VERSION" >&2
	exit 2
fi

APP_PATH="$1"
OUTPUT_DMG="$2"
VERSION="$3"

required_variables=(
	APPLE_CERTIFICATE_P12_BASE64
	APPLE_CERTIFICATE_PASSWORD
	APPLE_DEVELOPER_ID
	APPLE_TEAM_ID
	APPLE_API_KEY_ID
	APPLE_API_ISSUER_ID
	APPLE_API_PRIVATE_KEY_BASE64
)

for variable_name in "${required_variables[@]}"; do
	if [[ -z "${!variable_name:-}" ]]; then
		echo "ERROR: Required Apple release secret is missing: ${variable_name}" >&2
		exit 1
	fi
done

if [[ "$APPLE_DEVELOPER_ID" != *"($APPLE_TEAM_ID)"* ]]; then
	echo "ERROR: APPLE_DEVELOPER_ID does not match APPLE_TEAM_ID" >&2
	exit 1
fi

if [[ ! -d "$APP_PATH" ]]; then
	echo "ERROR: App bundle not found: $APP_PATH" >&2
	exit 1
fi

WORK_DIR=$(mktemp -d)
KEYCHAIN_PATH="$WORK_DIR/release.keychain-db"
CERTIFICATE_PATH="$WORK_DIR/developer-id.p12"
API_KEY_PATH="$WORK_DIR/AuthKey_${APPLE_API_KEY_ID}.p8"
APP_ZIP_PATH="$WORK_DIR/SheetToConfig.app.zip"
KEYCHAIN_PASSWORD=$(python -c "import secrets; print(secrets.token_hex(24))")

cleanup() {
	security delete-keychain "$KEYCHAIN_PATH" >/dev/null 2>&1 || true
	rm -rf "$WORK_DIR"
}
trap cleanup EXIT

export CERTIFICATE_PATH API_KEY_PATH
python - <<'PY'
import base64
import os
from pathlib import Path

Path(os.environ["CERTIFICATE_PATH"]).write_bytes(
    base64.b64decode(os.environ["APPLE_CERTIFICATE_P12_BASE64"], validate=True)
)
Path(os.environ["API_KEY_PATH"]).write_bytes(
    base64.b64decode(os.environ["APPLE_API_PRIVATE_KEY_BASE64"], validate=True)
)
PY

chmod 600 "$CERTIFICATE_PATH" "$API_KEY_PATH"
security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
security set-keychain-settings -lut 21600 "$KEYCHAIN_PATH"
security import "$CERTIFICATE_PATH" \
	-k "$KEYCHAIN_PATH" \
	-P "$APPLE_CERTIFICATE_PASSWORD" \
	-T /usr/bin/codesign \
	-T /usr/bin/security
security set-key-partition-list \
	-S apple-tool:,apple: \
	-s \
	-k "$KEYCHAIN_PASSWORD" \
	"$KEYCHAIN_PATH"
security list-keychains -d user -s "$KEYCHAIN_PATH"
security find-identity -v -p codesigning "$KEYCHAIN_PATH" | grep -F "$APPLE_DEVELOPER_ID"

codesign --force --deep --strict --options runtime --timestamp \
	--sign "$APPLE_DEVELOPER_ID" \
	--keychain "$KEYCHAIN_PATH" \
	"$APP_PATH"
codesign --verify --deep --strict --verbose=2 "$APP_PATH"

ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$APP_ZIP_PATH"
xcrun notarytool submit "$APP_ZIP_PATH" \
	--key "$API_KEY_PATH" \
	--key-id "$APPLE_API_KEY_ID" \
	--issuer "$APPLE_API_ISSUER_ID" \
	--wait
xcrun stapler staple "$APP_PATH"

python scripts/package_macos.py \
	--app "$APP_PATH" \
	--version "$VERSION" \
	--output "$OUTPUT_DMG"
codesign --force --timestamp \
	--sign "$APPLE_DEVELOPER_ID" \
	--keychain "$KEYCHAIN_PATH" \
	"$OUTPUT_DMG"
xcrun notarytool submit "$OUTPUT_DMG" \
	--key "$API_KEY_PATH" \
	--key-id "$APPLE_API_KEY_ID" \
	--issuer "$APPLE_API_ISSUER_ID" \
	--wait
xcrun stapler staple "$OUTPUT_DMG"

codesign --verify --verbose=2 "$OUTPUT_DMG"
spctl --assess --type execute --verbose=4 "$APP_PATH"
xcrun stapler validate "$OUTPUT_DMG"
echo "Signed and notarized DMG: $OUTPUT_DMG"
