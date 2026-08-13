#!/bin/sh
set -eu

PROJECT="M_Bamboo_SV08Max_Mods"
REPO="${M_BAMBOO_REPO:-kuratsunade/M_Bamboo_SV08Max_Mods}"
REF="${M_BAMBOO_REF:-main}"
KEEP_TEMP="${M_BAMBOO_KEEP_TEMP:-0}"

say() { printf '%s\n' "$*"; }
die() { say "ERROR: $*" >&2; exit 1; }

command -v python3 >/dev/null 2>&1 || die "python3 is required"
command -v tar >/dev/null 2>&1 || die "tar is required"

TMPDIR=$(mktemp -d "/tmp/M_Bamboo_SV08MAX.XXXXXX") || die "unable to create temporary directory"
ARCHIVE="$TMPDIR/source.tar.gz"

cleanup() {
    rc=$?
    trap - EXIT HUP INT TERM
    if [ "$KEEP_TEMP" = "1" ]; then
        say "Temporary files kept at: $TMPDIR"
    else
        rm -rf -- "$TMPDIR"
    fi
    exit "$rc"
}
trap cleanup EXIT HUP INT TERM

URL="https://github.com/$REPO/archive/$REF.tar.gz"
say "M_Bamboo bootstrap: $REPO @ $REF"
say "Downloading release snapshot..."
if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 --connect-timeout 15 -o "$ARCHIVE" "$URL"
elif command -v wget >/dev/null 2>&1; then
    wget -O "$ARCHIVE" "$URL"
else
    die "curl or wget is required"
fi

TOP=$(tar -tzf "$ARCHIVE" | sed -n '1{s,/.*,,;p;}')
[ -n "$TOP" ] || die "unable to determine archive root"
tar -xzf "$ARCHIVE" -C "$TMPDIR"
ROOT="$TMPDIR/$TOP"
[ -d "$ROOT" ] || die "archive root is missing"
[ -f "$ROOT/SHA256SUMS" ] || die "SHA256SUMS is missing"
[ -f "$ROOT/install.sh" ] || die "install.sh is missing"

say "Verifying release payload checksums..."
if command -v sha256sum >/dev/null 2>&1; then
    (cd "$ROOT" && sha256sum -c SHA256SUMS)
else
    python3 - "$ROOT" <<'PY'
import hashlib
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
for raw in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
    raw = raw.strip()
    if not raw:
        continue
    expected, rel = raw.split(None, 1)
    path = root / rel.strip()
    if not path.is_file():
        raise SystemExit("Missing checksum target: %s" % rel)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit("Checksum mismatch: %s" % rel)
    print("%s: OK" % rel)
PY
fi

say "Checksum verification passed."
say "Launching installer..."
cd "$ROOT"
sh ./install.sh "$@"
