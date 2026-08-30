#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG_DIR="$REPO_ROOT/packaging"
VERSION="$(sed -n 's/__version__ = "\(.*\)"/\1/p' "$REPO_ROOT/src/miniai/__init__.py")"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "Construction de miniai_${VERSION}_all.deb depuis $REPO_ROOT"

mkdir -p "$STAGE/DEBIAN"
sed "s/@VERSION@/$VERSION/" "$PKG_DIR/control" > "$STAGE/DEBIAN/control"
install -m 0755 "$PKG_DIR/postinst" "$STAGE/DEBIAN/postinst"
install -m 0755 "$PKG_DIR/postrm" "$STAGE/DEBIAN/postrm"

mkdir -p "$STAGE/opt/miniai"
cp -r "$REPO_ROOT/src" "$STAGE/opt/miniai/src"
cp -r "$REPO_ROOT/bin" "$STAGE/opt/miniai/bin"
cp -r "$REPO_ROOT/shell-integration" "$STAGE/opt/miniai/shell-integration"
cp -r "$REPO_ROOT/tests" "$STAGE/opt/miniai/tests"
cp -r "$REPO_ROOT/docs" "$STAGE/opt/miniai/docs"
cp "$REPO_ROOT/requirements.txt" "$STAGE/opt/miniai/requirements.txt"
cp "$REPO_ROOT/README.md" "$STAGE/opt/miniai/README.md"
cp "$REPO_ROOT/LICENSE" "$STAGE/opt/miniai/LICENSE"
mkdir -p "$STAGE/opt/miniai/model"

find "$STAGE/opt/miniai" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

mkdir -p "$STAGE/usr/bin"
install -m 0755 "$PKG_DIR/usr-bin-miniai" "$STAGE/usr/bin/miniai"
install -m 0755 "$PKG_DIR/usr-bin-miniai-resolve-inline" "$STAGE/usr/bin/miniai-resolve-inline"

mkdir -p "$STAGE/usr/share/man/man1"
gzip -9 -n -c "$PKG_DIR/miniai.1" > "$STAGE/usr/share/man/man1/miniai.1.gz"
gzip -9 -n -c "$PKG_DIR/miniai-resolve-inline.1" > "$STAGE/usr/share/man/man1/miniai-resolve-inline.1.gz"

mkdir -p "$STAGE/usr/share/doc/miniai"
install -m 0644 "$PKG_DIR/copyright" "$STAGE/usr/share/doc/miniai/copyright"
gzip -9 -n -c "$PKG_DIR/changelog" > "$STAGE/usr/share/doc/miniai/changelog.gz"

# Permissions propres : dossiers 0755, fichiers 0644, executables 0755
# (le checkout git d'où on copie a des perms 0775/0664 liées à l'umask
# de dev, pas pertinentes pour le paquet).
find "$STAGE/opt" "$STAGE/usr" -type d -exec chmod 0755 {} +
find "$STAGE/opt" "$STAGE/usr" -type f -exec chmod 0644 {} +
chmod 0755 \
    "$STAGE/opt/miniai/bin/miniai" \
    "$STAGE/opt/miniai/bin/miniai-resolve-inline" \
    "$STAGE/usr/bin/miniai" \
    "$STAGE/usr/bin/miniai-resolve-inline"

OUT="$REPO_ROOT/miniai_${VERSION}_all.deb"
dpkg-deb --root-owner-group --build "$STAGE" "$OUT"

echo "Paquet cree : $OUT"
echo "Installation : sudo apt install $OUT   (ou : sudo dpkg -i $OUT)"
