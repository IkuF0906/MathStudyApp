# 画面（static/）を配信し、/api/ をアプリに転送する nginx のイメージ。ビルドはリポジトリの直下から行う
FROM nginx:1.27-alpine

# 信頼できなくなったルート証明書を外す（理由はスクリプトに書いた）
COPY deploy/distrust-roots.sh /tmp/
RUN sh /tmp/distrust-roots.sh && rm /tmp/distrust-roots.sh

COPY deploy/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY static/ /usr/share/nginx/html/
