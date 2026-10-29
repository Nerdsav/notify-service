# notify-service

Сервис-прокси для отправки уведомлений в мессенджеры через единый HTTP(S)-API.
Сейчас поддерживаются каналы **Telegram** и **Пачка (Pachca)**. Доступ к `/send` защищён API-ключами; для каждого канала можно задать HTTP-прокси.

**Автор:** A.Soroko, 07-2026
**Почта:** nerdsav@gmail.com
**Telegram:** [@nerdsav](https://t.me/nerdsav)

**Лицензия:** [MIT](LICENSE) — свободное использование, изменение и распространение, в том числе в коммерческих целях, при сохранении уведомления об авторстве.

## Структура

| Файл | Назначение |
| --- | --- |
| `notify_service.py` | Основной сервис (HTTP/HTTPS-сервер на стандартной библиотеке + `requests`) |
| `config.yaml.example` | Шаблон конфигурации (ключи, каналы, прокси, сервер) |
| `Dockerfile` | Сборка образа на `python:3.11-slim` |
| `docker-compose.yml` | Запуск контейнера (порт `8448`, монтирование конфига, сертификатов и логов) |
| `requirements.txt` | Зависимости Python |
| `gen_certs.sh` | Генерация самоподписанного сертификата для HTTPS |

## Быстрый старт

1. Создайте конфиг из шаблона и заполните его:

   ```bash
   cp config.yaml.example config.yaml
   ```

2. Если нужен HTTPS, сгенерируйте сертификат (по умолчанию в `/opt/notify-service/certs`, см. `SERVICE_PATH` в `gen_certs.sh`) и в `config.yaml` установите `server.use_ssl: true`:

   ```bash
   ./gen_certs.sh
   ```

3. Соберите и запустите:

   ```bash
   docker compose up -d --build
   ```

> `Dockerfile` копирует `config.yaml` в образ, поэтому файл должен существовать до сборки. Не публикуйте образ с реальным конфигом.

## Переменные окружения

- `CONFIG_PATH` — путь к конфигу внутри контейнера (по умолчанию `/app/config.yaml`).
- `TZ` — часовой пояс (в compose задан `Europe/Moscow`).

## API

Все запросы, кроме `GET /`, требуют заголовок `X-API-Key`.

| Метод | Путь | Описание |
| --- | --- | --- |
| `GET` | `/` | Текстовая справка |
| `GET` | `/health` | Статус сервиса и список каналов |
| `GET` | `/channels` | Каналы, их тип, описание и наличие прокси |
| `POST` | `/send` | Отправка сообщения |

Пример отправки:

```bash
curl -X POST http://localhost:8448/send \
  -H "X-API-Key: <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"channel_id": "telegram_my_notify", "message": "Привет", "parse_mode": "Markdown", "silent": false}'
```

Тело запроса также принимается как `application/x-www-form-urlencoded`. Поля:

- `channel_id` (обязательно) — ключ из секции `channels`;
- `message` или `text` (обязательно) — текст сообщения;
- `parse_mode` — для Telegram, по умолчанию `Markdown`;
- `silent` — отправить без звука (Telegram).

## Конфигурация

См. `config.yaml.example`. Основные секции:

- `api_keys` — список допустимых ключей с описанием;
- `channels` — каналы; для `telegram` нужны `token` и `chat_ids`, для `pachca` — `token` и `entity_id`;
- `proxy` — необязательный прокси канала (`http`/`socks5`, `host`, `port`, `user`, `password`);
- `server` — `host`, `port`, `use_ssl`, пути к `ssl_cert` и `ssl_key`;
- `timeout` — таймаут исходящих запросов, сек.

Перечитать конфиг без перезапуска сервера:

```bash
python notify_service.py --reload
```

## Логи

Логи пишутся в stdout контейнера (`docker logs notify-service`). В compose также смонтирована директория `logs/` и включена ротация json-file.

## Безопасность

- Не коммитьте `config.yaml`, ключи и сертификаты — они исключены через `.gitignore`.
- Если секреты когда-либо попали в git, их нужно перевыпустить (токены ботов, ключи API, пароли прокси).
