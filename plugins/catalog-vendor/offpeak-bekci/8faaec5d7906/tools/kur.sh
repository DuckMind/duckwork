#!/usr/bin/env bash
# offpeak-bekci — sunucu tarafı kurulum (idempotent).
#
# Repo kökünü Duckwork eklenti dizinine kopyalar (kaynak = bu checkout, uzak indirme YOK),
# sonra kurulumu `duckwork plugins validate` ile doğrular.
#
# Kullanım:
#   tools/kur.sh                 # varsayılan profil evi (~/.duckwork)
#   DUCKWORK_HOME=~/.duckwork/profiles/<profil> tools/kur.sh
#
# Not: eklentinin DEVREYE girmesi için config'de `plugins.enabled` içinde adı geçmelidir:
#   duckwork plugins enable offpeak-bekci
set -euo pipefail

KOK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EV="${DUCKWORK_HOME:-$HOME/.duckwork}"
HEDEF="$EV/plugins/offpeak-bekci"

echo "kaynak : $KOK"
echo "hedef  : $HEDEF"

mkdir -p "$HEDEF"

# .git ve türetilmiş dizinler taşınmaz; gerisi birebir (manifest girdileri eksiksiz kalsın).
rsync -a --delete \
  --exclude '.git/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  --exclude 'node_modules/' \
  "$KOK/" "$HEDEF/"

echo "--- kurulan dosyalar ---"
find "$HEDEF" -maxdepth 2 -type f | sed "s|$HEDEF/|  |" | sort

echo "--- yükleme yüzeyi (sha256) ---"
for f in plugin.yaml __init__.py bekci_core.py bekci_kurulum.py metinler.py; do
  printf '  %s  %s\n' "$(shasum -a 256 "$KOK/$f" | cut -d' ' -f1)" "$f"
done

if command -v duckwork >/dev/null 2>&1; then
  echo "--- doğrulama: duckwork plugins validate ---"
  duckwork plugins validate "$HEDEF"
else
  echo "UYARI: 'duckwork' PATH'te yok — validate atlandı." >&2
fi

echo "KURULUM TAMAM (EXIT=0)"
