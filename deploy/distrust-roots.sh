#!/bin/sh
# 信頼できなくなったルート証明書を、イメージの CA バンドルから外す。Debian（アプリ）と Alpine（nginx）の両方で使う
#
# 2026-10 に eMudhra の中間 CA の秘密鍵が漏れた（https://bugzilla.mozilla.org/show_bug.cgi?id=2083449）。
# その中間 CA に届く次のルートを外す。OpenSSL は失効を確かめないので、ルートごと外さないと、
# 漏れた鍵で作った証明書を信頼してしまう
# - emSign ECC Root CA - G3：Mozilla が緊急で外した
# - AAA Certificate Services（Sectigo）：漏れた中間 CA をクロス署名している。Mozilla・Chrome はすでに外している
set -eu

names="Comodo_AAA_Services_root emSign_ECC_Root_CA_-_G3"

for name in $names; do
  sed -i "s#^mozilla/$name\.crt\$#!mozilla/$name.crt#" /etc/ca-certificates.conf
done
update-ca-certificates

# 外れたことを証明書の中身で確かめる。ファイル名が変わって外し損ねたら、ビルドを失敗させる
for name in $names; do
  crt="/usr/share/ca-certificates/mozilla/$name.crt"
  [ -f "$crt" ] || continue
  if grep -qxF "$(sed -n 10p "$crt")" /etc/ssl/certs/ca-certificates.crt; then
    echo "distrust-roots: $name が CA バンドルに残っている" >&2
    exit 1
  fi
done
