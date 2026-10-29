#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Автор: A.Soroko, nerdsav@gmail.com, TG: @nerdsav
# Лицензия: MIT (см. файл LICENSE)

"""
Сервис-прокси для отправки уведомлений в различные мессенджеры и системы.
Поддерживает Telegram, Пачка (Pachca) и другие каналы.
Авторизация по API-ключам, возможность использования прокси для каждого канала.
"""

import json
import logging
import requests
import sys
import os
import ssl
import yaml
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# ========== ПУТЬ К КОНФИГУ ==========
# Приоритет: переменная окружения CONFIG_PATH > значение по умолчанию
CONFIG_PATH = os.environ.get('CONFIG_PATH', '/app/config.yaml')
# ====================================

# Глобальные переменные для конфига
CONFIG = {}
CHANNELS = {}
API_KEYS = []
SERVER_CONFIG = {}
LOGGING_CONFIG = {}
TIMEOUT = 30
USE_SSL = True  # По умолчанию HTTPS


def load_config():
    """
    Загрузка конфигурации из YAML файла.
    
    Returns:
        bool: True если загрузка успешна, иначе False
    """
    global CONFIG, CHANNELS, API_KEYS, TIMEOUT, SERVER_CONFIG, LOGGING_CONFIG, USE_SSL

    try:
        if not os.path.exists(CONFIG_PATH):
            logging.error(f"Файл конфигурации не найден: {CONFIG_PATH}")
            logging.info(f"Попробуйте указать путь через переменную окружения CONFIG_PATH")
            return False

        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            CONFIG = yaml.safe_load(f)

        # Загружаем API ключи
        API_KEYS = CONFIG.get('api_keys', [])
        logging.info(f"Загружено {len(API_KEYS)} API ключей")

        # Загружаем каналы
        CHANNELS = CONFIG.get('channels', {})
        logging.info(f"Загружено {len(CHANNELS)} каналов")

        # Загружаем настройки сервера
        SERVER_CONFIG = CONFIG.get('server', {})
        
        # Определяем использовать ли SSL
        use_ssl_value = SERVER_CONFIG.get('use_ssl', True)
        # Приводим к bool: true/True/yes/1 -> True, false/False/no/0 -> False
        if isinstance(use_ssl_value, str):
            USE_SSL = use_ssl_value.lower() in ['true', 'yes', '1', 'on']
        else:
            USE_SSL = bool(use_ssl_value)

        if USE_SSL:
            logging.info("SSL включен (HTTPS)")
        else:
            logging.info("SSL отключен (HTTP)")

        # Загружаем настройки логирования
        LOGGING_CONFIG = CONFIG.get('logging', {})

        # Загружаем таймаут
        TIMEOUT = CONFIG.get('timeout', 30)

        # Устанавливаем уровень логирования
        log_level = LOGGING_CONFIG.get('level', 'INFO')
        logging.getLogger().setLevel(log_level)

        # Логируем загруженные каналы
        for channel_id, config in CHANNELS.items():
            channel_type = config.get('type', 'unknown')
            desc = config.get('description', '')
            has_proxy = 'proxy' in config and config['proxy'].get('host')
            proxy_info = f" (с прокси)" if has_proxy else " (без прокси)"
            logging.info(f"Канал '{channel_id}' [{channel_type}]: {desc}{proxy_info}")

        return True

    except yaml.YAMLError as e:
        logging.error(f"Ошибка парсинга YAML: {e}")
        return False
    except Exception as e:
        logging.error(f"Ошибка загрузки конфигурации: {e}")
        return False


def check_api_key(api_key):
    """
    Проверка API ключа на валидность.
    
    Args:
        api_key (str): API ключ для проверки
        
    Returns:
        bool: True если ключ валидный, иначе False
    """
    if not api_key:
        return False
    for key_data in API_KEYS:
        if key_data.get('key') == api_key:
            return True
    return False


def get_proxy_for_channel(channel_config):
    """
    Получение настроек прокси для канала.
    
    Args:
        channel_config (dict): Конфигурация канала
        
    Returns:
        dict: Конфигурация прокси для requests или None
    """
    if 'proxy' in channel_config:
        proxy_config = channel_config['proxy']
        if proxy_config.get('host'):
            return build_proxy_config(proxy_config)
    return None


def build_proxy_config(proxy_config):
    """
    Построение конфигурации прокси для библиотеки requests.
    
    Args:
        proxy_config (dict): Конфигурация прокси из YAML
        
    Returns:
        dict: Конфигурация для requests или None
    """
    if not proxy_config or not proxy_config.get('host'):
        return None

    proxy_url = f"{proxy_config.get('type', 'socks5')}://"

    if proxy_config.get('user') and proxy_config.get('password'):
        proxy_url += f"{proxy_config.get('user')}:{proxy_config.get('password')}@"

    proxy_url += f"{proxy_config.get('host')}:{proxy_config.get('port', 1080)}"

    return {
        "http": proxy_url,
        "https": proxy_url
    }


def send_to_telegram(token, chat_id, message, parse_mode, silent, proxy_config, channel_id):
    """
    Отправка сообщения в Telegram.
    
    Args:
        token (str): Токен бота Telegram
        chat_id (str): ID чата или пользователя
        message (str): Текст сообщения
        parse_mode (str): Режим форматирования (Markdown, HTML)
        silent (bool): Отправить без звука
        proxy_config (dict): Конфигурация прокси
        channel_id (str): ID канала для логирования
        
    Returns:
        dict: Результат отправки {ok: bool, result: ...}
    """
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode,
        "disable_notification": silent
    }

    try:
        if proxy_config:
            logging.debug(f"Используется прокси для канала {channel_id}: {proxy_config['http']}")
            response = requests.post(
                url,
                json=payload,
                proxies=proxy_config,
                timeout=TIMEOUT
            )
        else:
            response = requests.post(
                url,
                json=payload,
                timeout=TIMEOUT
            )

        if response.status_code == 200:
            logging.info(f"Telegram: сообщение отправлено в чат {chat_id} (channel: {channel_id})")
            return {"ok": True, "result": response.json()}
        else:
            logging.error(f"Telegram API error: {response.status_code} - {response.text}")
            return {"ok": False, "error": f"Telegram API error: {response.status_code}", "response": response.text}

    except requests.exceptions.ProxyError as e:
        logging.error(f"Ошибка прокси для канала {channel_id}: {e}")
        return {"ok": False, "error": f"Proxy error: {e}"}
    except requests.exceptions.Timeout:
        logging.error(f"Таймаут при отправке (timeout={TIMEOUT}s)")
        return {"ok": False, "error": "Timeout"}
    except Exception as e:
        logging.error(f"Ошибка отправки: {e}")
        return {"ok": False, "error": str(e)}


def send_to_pachca(token, entity_id, message, proxy_config, channel_id):
    """
    Отправка сообщения в Пачка (Pachca).
    
    Args:
        token (str): Токен доступа к API Пачка
        entity_id (int): ID сущности (чата) в Пачка
        message (str): Текст сообщения
        proxy_config (dict): Конфигурация прокси
        channel_id (str): ID канала для логирования
        
    Returns:
        dict: Результат отправки {ok: bool, result: ...}
    """
    url = "https://api.pachca.com/api/shared/v1/messages"

    payload = {
        "message": {
            "entity_id": entity_id,
            "content": message
        }
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        if proxy_config:
            logging.debug(f"Используется прокси для канала {channel_id}: {proxy_config['http']}")
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                proxies=proxy_config,
                timeout=TIMEOUT
            )
        else:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=TIMEOUT
            )

        if response.status_code in [200, 201]:
            logging.info(f"Pachca: сообщение отправлено в entity {entity_id} (channel: {channel_id})")
            return {"ok": True, "result": response.json()}
        else:
            logging.error(f"Pachca API error: {response.status_code} - {response.text}")
            return {"ok": False, "error": f"Pachca API error: {response.status_code}", "response": response.text}

    except requests.exceptions.ProxyError as e:
        logging.error(f"Ошибка прокси для канала {channel_id}: {e}")
        return {"ok": False, "error": f"Proxy error: {e}"}
    except requests.exceptions.Timeout:
        logging.error(f"Таймаут при отправке (timeout={TIMEOUT}s)")
        return {"ok": False, "error": "Timeout"}
    except Exception as e:
        logging.error(f"Ошибка отправки: {e}")
        return {"ok": False, "error": str(e)}


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Загружаем конфиг при старте
load_config()


def reconfigure_logging():
    """Перенастройка логирования - только в stdout."""
    log_level = LOGGING_CONFIG.get('level', 'INFO')

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True
    )

    logging.info(f"Логирование настроено: stdout, уровень {log_level}")


reconfigure_logging()


class TelegramProxyHandler(BaseHTTPRequestHandler):
    """Обработчик HTTP/HTTPS-запросов к прокси-сервису."""

    def do_GET(self):
        """Обработка GET-запросов."""
        parsed_path = urlparse(self.path)

        # Проверяем API ключ
        api_key = self.headers.get('X-API-Key')
        if not check_api_key(api_key):
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {"error": "Invalid or missing API key"}
            self.wfile.write(json.dumps(response).encode('utf-8'))
            return

        if parsed_path.path == "/health":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "status": "ok",
                "service": "notification_proxy",
                "channels": list(CHANNELS.keys()),
                "channels_count": len(CHANNELS)
            }
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
            return

        if parsed_path.path == "/channels":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            channels_info = {}
            for channel_id, config in CHANNELS.items():
                channels_info[channel_id] = {
                    "type": config.get('type', 'unknown'),
                    "description": config.get('description', ''),
                    "has_proxy": 'proxy' in config and config['proxy'].get('host')
                }
            response = {"channels": channels_info}
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
            return

        if parsed_path.path == "/":
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Notification Proxy Service is running.\n")
            self.wfile.write(f"Channels: {', '.join(CHANNELS.keys())}\n".encode('utf-8'))
            self.wfile.write(b"\nEndpoints:\n")
            self.wfile.write(b"  POST /send - Send message (requires X-API-Key header)\n")
            self.wfile.write(b"  GET /health - Health check\n")
            self.wfile.write(b"  GET /channels - List channels\n")
            return

        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not Found")

    def do_POST(self):
        """Обработка POST-запросов."""
        parsed_path = urlparse(self.path)

        if parsed_path.path != "/send":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        # Проверяем API ключ
        api_key = self.headers.get('X-API-Key')
        if not check_api_key(api_key):
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {"error": "Invalid or missing API key"}
            self.wfile.write(json.dumps(response).encode('utf-8'))
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)

            try:
                data = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                parsed = parse_qs(post_data.decode('utf-8'))
                data = {k: v[0] if v else '' for k, v in parsed.items()}

            channel_id = data.get('channel_id')
            message = data.get('message') or data.get('text')
            parse_mode = data.get('parse_mode', 'Markdown')
            silent = data.get('silent', False)

            logging.info(f"Получен запрос в канал: {channel_id} (API key: {api_key[:8]}...)")

            if not channel_id:
                self.send_error_response("channel_id is required")
                return

            if not message:
                self.send_error_response("message is required")
                return

            if channel_id not in CHANNELS:
                self.send_error_response(f"Unknown channel_id: {channel_id}")
                return

            channel_config = CHANNELS[channel_id]
            channel_type = channel_config.get('type', 'unknown')
            proxy_config = get_proxy_for_channel(channel_config)

            # Отправляем в зависимости от типа
            if channel_type == 'telegram':
                result = self.send_to_telegram(channel_config, message, parse_mode, silent, proxy_config, channel_id)
            elif channel_type == 'pachca':
                result = self.send_to_pachca(channel_config, message, proxy_config, channel_id)
            else:
                self.send_error_response(f"Unsupported channel type: {channel_type}")
                return

            # Отправляем ответ
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()

            response = {
                "status": "success" if result.get('ok') else "error",
                "channel_id": channel_id,
                "type": channel_type,
                "result": result
            }
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))

        except Exception as e:
            logging.error(f"Ошибка обработки запроса: {e}")
            self.send_error_response(str(e))

    def send_error_response(self, error_message):
        """
        Отправка ответа с ошибкой.
        
        Args:
            error_message (str): Текст ошибки
        """
        self.send_response(400)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = {
            "status": "error",
            "error": error_message
        }
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))

    def send_to_telegram(self, config, message, parse_mode, silent, proxy_config, channel_id):
        """
        Отправка сообщения в Telegram через внутреннюю функцию.
        
        Args:
            config (dict): Конфигурация канала
            message (str): Текст сообщения
            parse_mode (str): Режим форматирования
            silent (bool): Отправить без звука
            proxy_config (dict): Конфигурация прокси
            channel_id (str): ID канала
            
        Returns:
            dict: Результат отправки
        """
        token = config.get('token')
        chat_ids = config.get('chat_ids', [])

        if not token:
            return {"ok": False, "error": "Bot token not configured"}

        if not chat_ids:
            return {"ok": False, "error": "No chat_ids configured"}

        results = []
        for chat_id in chat_ids:
            result = send_to_telegram(token, chat_id, message, parse_mode, silent, proxy_config, channel_id)
            results.append({
                "chat_id": chat_id,
                "success": result.get('ok', False),
                "result": result
            })

        return {
            "ok": all(r.get('success') for r in results),
            "results": results
        }

    def send_to_pachca(self, config, message, proxy_config, channel_id):
        """
        Отправка сообщения в Пачка через внутреннюю функцию.
        
        Args:
            config (dict): Конфигурация канала
            message (str): Текст сообщения
            proxy_config (dict): Конфигурация прокси
            channel_id (str): ID канала
            
        Returns:
            dict: Результат отправки
        """
        token = config.get('token')
        entity_id = config.get('entity_id')

        if not token:
            return {"ok": False, "error": "Pachca token not configured"}

        if not entity_id:
            return {"ok": False, "error": "Pachca entity_id not configured"}

        result = send_to_pachca(token, entity_id, message, proxy_config, channel_id)

        return {
            "ok": result.get('ok', False),
            "entity_id": entity_id,
            "result": result
        }

    def log_message(self, format, *args):
        """Переопределение метода логирования."""
        logging.info(f"{self.address_string()} - {format % args}")


def run_server():
    """Запуск HTTP/HTTPS-сервера с учётом настроек use_ssl."""
    try:
        host = SERVER_CONFIG.get('host', '0.0.0.0')
        port_str = SERVER_CONFIG.get('port', 8443)
        try:
            port = int(port_str)
        except (ValueError, TypeError):
            port = 8443
            logging.warning(f"Неверный формат порта: {port_str}, используем 8443")
        
        ssl_cert = SERVER_CONFIG.get('ssl_cert', '/etc/ssl/certs/telegram-proxy.crt')
        ssl_key = SERVER_CONFIG.get('ssl_key', '/etc/ssl/private/telegram-proxy.key')

        # Если SSL включен — проверяем сертификаты
        if USE_SSL:
            # Проверяем существование файлов
            if not os.path.exists(ssl_cert):
                logging.error(f"Файл сертификата не найден: {ssl_cert}")
                logging.info("Решение: проверьте путь и наличие файла")
                logging.info(f"Ожидаемый путь: {ssl_cert}")
                sys.exit(1)
            
            if not os.path.exists(ssl_key):
                logging.error(f"Файл ключа не найден: {ssl_key}")
                logging.info("Решение: проверьте путь и наличие файла")
                logging.info(f"Ожидаемый путь: {ssl_key}")
                sys.exit(1)
            
            # Проверяем читаемость файлов
            try:
                with open(ssl_cert, 'r') as f:
                    f.read()
                logging.info(f"Сертификат доступен для чтения: {ssl_cert}")
            except PermissionError:
                logging.error(f"Нет прав на чтение сертификата: {ssl_cert}")
                logging.info("Решение: выполните chown 1001:1001 <путь_к_сертификату>")
                logging.info(f"Команда: chown 1001:1001 {ssl_cert}")
                sys.exit(1)
            except Exception as e:
                logging.error(f"Ошибка чтения сертификата: {e}")
                sys.exit(1)
            
            try:
                with open(ssl_key, 'r') as f:
                    f.read()
                logging.info(f"Ключ доступен для чтения: {ssl_key}")
            except PermissionError:
                logging.error(f"Нет прав на чтение ключа: {ssl_key}")
                logging.info("Решение: выполните chown 1001:1001 <путь_к_ключу>")
                logging.info(f"Команда: chown 1001:1001 {ssl_key}")
                sys.exit(1)
            except Exception as e:
                logging.error(f"Ошибка чтения ключа: {e}")
                sys.exit(1)

        server = HTTPServer((host, port), TelegramProxyHandler)

        # Если use_ssl = True, оборачиваем в SSL
        if USE_SSL:
            # Проверяем наличие сертификатов (повторно, для подстраховки)
            if os.path.exists(ssl_cert) and os.path.exists(ssl_key):
                try:
                    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                    context.load_cert_chain(ssl_cert, ssl_key)
                    server.socket = context.wrap_socket(server.socket, server_side=True)
                    protocol = "HTTPS"
                    logging.info(f"SSL сертификаты загружены успешно")
                except ssl.SSLError as e:
                    logging.error(f"Ошибка загрузки SSL сертификатов: {e}")
                    logging.info("Решение: проверьте, что сертификат и ключ корректны")
                    logging.info(f"Сертификат: {ssl_cert}")
                    logging.info(f"Ключ: {ssl_key}")
                    sys.exit(1)
            else:
                logging.warning("SSL включен, но сертификаты не найдены. Запускаем HTTP.")
                protocol = "HTTP"
        else:
            protocol = "HTTP"
            logging.info("SSL отключен, запускаем HTTP сервер")

        logging.info(f"Notification Proxy Service запущен на {protocol}://{host}:{port}")
        logging.info(f"Отправка сообщений: POST {protocol}://{host}:{port}/send (требуется X-API-Key)")
        logging.info(f"Проверка статуса: GET {protocol}://{host}:{port}/health")
        logging.info(f"Список каналов: GET {protocol}://{host}:{port}/channels")
        logging.info(f"Доступные channel_id: {list(CHANNELS.keys())}")

        server.serve_forever()

    except PermissionError as e:
        logging.error(f"Ошибка доступа: {e}")
        logging.info("Решение: проверьте права на файлы сертификатов")
        logging.info("Команда: chown -R 1001:1001 /путь/к/certs/")
        sys.exit(1)
    except KeyboardInterrupt:
        logging.info("Остановка сервера...")
        server.shutdown()
    except Exception as e:
        logging.error(f"Ошибка запуска сервера: {e}")
        sys.exit(1)

def reload_config():
    """
    Перезагрузка конфигурации без перезапуска сервера.
    
    Returns:
        bool: True если перезагрузка успешна, иначе False
    """
    logging.info("Перезагрузка конфигурации...")
    success = load_config()
    if success:
        reconfigure_logging()
        logging.info("Конфигурация перезагружена")
    else:
        logging.error("Ошибка перезагрузки конфигурации")
    return success


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--reload":
        reload_config()
        sys.exit(0)

    run_server()

