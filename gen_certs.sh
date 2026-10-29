#!/bin/bash
# Автор: A.Soroko, nerdsav@gmail.com, TG: @nerdsav
# Лицензия: MIT (см. файл LICENSE)

SERVICE_PATH='/opt/notify-service'
SERVICE_NAME='notify-service'

sudo openssl req -x509 -newkey rsa:4096 \
	-keyout "$SERVICE_PATH/certs/$SERVICE_NAME.key" \
        -out "$SERVICE_PATH/certs/$SERVICE_NAME.crt" -days 3650 -nodes \
        -subj "/CN=$SERVICE_NAME.local"
sudo chown -R 1001:1001 $SERVICE_PATH/certs/$SERVICE_NAME.crt
sudo chmod 644 $SERVICE_PATH/certs/$SERVICE_NAME.crt
sudo chmod 600 $SERVICE_PATH/certs/$SERVICE_NAME.key
