#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG_DIR="$REPO_ROOT/packaging"
VERSION="$(sed -n 's/__version__ = "\(.*\)"/\1/p' "$REPO_ROOT/src/shss/__init__.py")"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "Construction de shss_${VERSION}_all.deb depuis $REPO_ROOT"

mkdir -p "$STAGE/DEBIAN"
sed "s/@VERSION@/$VERSION/" "$PKG_DIR/control" > "$STAGE/DEBIAN/control"
install -m 0755 "$PKG_DIR/postinst" "$STAGE/DEBIAN/postinst"
install -m 0755 "$PKG_DIR/postrm" "$STAGE/DEBIAN/postrm"

mkdir -p "$STAGE/opt/shss"
cp -r "$REPO_ROOT/src" "$STAGE/opt/shss/src"
cp -r "$REPO_ROOT/bin" "$STAGE/opt/shss/bin"
cp -r "$REPO_ROOT/shell-integration" "$STAGE/opt/shss/shell-integration"
cp -r "$REPO_ROOT/tests" "$STAGE/opt/shss/tests"
cp -r "$REPO_ROOT/docs" "$STAGE/opt/shss/docs"
cp "$REPO_ROOT/requirements.txt" "$STAGE/opt/shss/requirements.txt"
cp "$REPO_ROOT/README.md" "$STAGE/opt/shss/README.md"
cp "$REPO_ROOT/LISEZMOI.md" "$STAGE/opt/shss/LISEZMOI.md"
cp "$REPO_ROOT/LICENSE" "$STAGE/opt/shss/LICENSE"
mkdir -p "$STAGE/opt/shss/model"

find "$STAGE/opt/shss" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

mkdir -p "$STAGE/usr/bin"
install -m 0755 "$PKG_DIR/usr-bin-shss" "$STAGE/usr/bin/shss"
install -m 0755 "$PKG_DIR/usr-bin-shss-resolve-inline" "$STAGE/usr/bin/shss-resolve-inline"

mkdir -p "$STAGE/usr/share/man/man1"
gzip -9 -n -c "$PKG_DIR/shss.1" > "$STAGE/usr/share/man/man1/shss.1.gz"
gzip -9 -n -c "$PKG_DIR/shss-resolve-inline.1" > "$STAGE/usr/share/man/man1/shss-resolve-inline.1.gz"

mkdir -p "$STAGE/usr/share/doc/shss"
install -m 0644 "$PKG_DIR/copyright" "$STAGE/usr/share/doc/shss/copyright"
gzip -9 -n -c "$PKG_DIR/changelog" > "$STAGE/usr/share/doc/shss/changelog.gz"

# Permissions propres : dossiers 0755, fichiers 0644, executables 0755
# (le checkout git d'où on copie a des perms 0775/0664 liées à l'umask
# de dev, pas pertinentes pour le paquet).
find "$STAGE/opt" "$STAGE/usr" -type d -exec chmod 0755 {} +
find "$STAGE/opt" "$STAGE/usr" -type f -exec chmod 0644 {} +
chmod 0755 \
    "$STAGE/opt/shss/bin/shss" \
    "$STAGE/opt/shss/bin/shss-resolve-inline" \
    "$STAGE/usr/bin/shss" \
    "$STAGE/usr/bin/shss-resolve-inline"

OUT="$REPO_ROOT/shss_${VERSION}_all.deb"
dpkg-deb --root-owner-group --build "$STAGE" "$OUT"

echo "Paquet cree : $OUT"
echo "Installation : sudo apt install $OUT   (ou : sudo dpkg -i $OUT)"
