# AutoService CRM — Telegram Bot

CRM-система для автосервиса: запись клиентов, управление расписанием, рассылки.

## Быстрый старт

### 1. Клонировать / скачать проект

```bash
cd ~/Desktop/auto_service
```

### 2. Создать виртуальное окружение

```bash
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Настроить .env

```bash
cp .env.example .env
```

Открой `.env` и заполни:

```env
BOT_TOKEN=токен_от_@BotFather
ADMIN_PASSWORD=придумай_пароль
DATABASE_URL=sqlite+aiosqlite:///./autoservice.db
TZ=Europe/Moscow
```

### 5. Запустить

```bash
python3 bot.py
```

База данных `autoservice.db` создаётся автоматически при первом запуске.

---

## Первичная настройка

1. Найди бота в Telegram, нажми `/start`
2. Стань администратором: `/admin <твой_пароль>`
3. Готово — появится меню администратора

---

## Что умеет бот

### Для клиентов

- Запись на 6 типов услуг: ТО (1ч), Диагностика (1ч), Шиномонтаж (1ч), Кузовной ремонт (4ч), Электрика (2ч), Слесарка (2ч)
- Сохранение данных автомобиля (не вводить повторно)
- Выбор из ближайших свободных слотов
- Напоминания за 24ч и за 2ч до записи
- Отзыв после визита (оценка 1-5 + комментарий)
- Просмотр и отмена своих записей

### Для администратора

- Расписание на день / на неделю по 4 подъёмникам
- Добавление записи вручную (по Telegram ID клиента)
- Перенос и отмена записей
- Блокировка подъёмника на выбранное время
- Карточка клиента: история визитов, авто, средний рейтинг (`/client <ID>`)
- Рассылка с фильтрами: всем / не были 1+ месяц / не были 3+ месяца

---

## Команды

| Команда | Кто | Описание |
|---|---|---|
| `/start` | все | Главное меню |
| `/admin <пароль>` | любой | Стать администратором |
| `/unadmin` | admin | Выйти из роли администратора |
| `/client <ID>` | admin | Карточка клиента |

---

## Запуск на VPS (Ubuntu/Debian)

### Установка

```bash
# Python 3.11+
sudo apt update && sudo apt install python3.11 python3.11-venv git -y

# Копируем проект
git clone <repo> /opt/auto_service
cd /opt/auto_service
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # заполнить токен и пароль
```

### Systemd сервис

```bash
sudo nano /etc/systemd/system/autoservice.service
```

```ini
[Unit]
Description=AutoService Telegram Bot
After=network.target

[Service]
WorkingDirectory=/opt/auto_service
ExecStart=/opt/auto_service/.venv/bin/python3 bot.py
Restart=always
RestartSec=5
EnvironmentFile=/opt/auto_service/.env
User=ubuntu

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable autoservice
sudo systemctl start autoservice

# Проверить статус:
sudo systemctl status autoservice

# Просмотр логов:
sudo journalctl -u autoservice -f
```

### Обновление на VPS

```bash
cd /opt/auto_service
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart autoservice
```

---

## Архитектура

```
bot.py              # Точка входа
config.py           # Константы и настройки
db/
  models.py         # ORM-модели (SQLAlchemy)
  repository.py     # Весь CRUD — только здесь
services/
  availability.py   # Алгоритм поиска свободных слотов
  master_assign.py  # Авто-назначение мастера (least-busy)
  notifications.py  # Все уведомления через Telegram
  scheduler_jobs.py # APScheduler: напоминания, авто-завершение
handlers/
  client/           # start, booking (FSM), my_appointments, review
  admin/            # auth, schedule, appointments, clients, broadcast
```

---

## Настройка количества мастеров/подъёмников

В `config.py` изменить:
- `LIFT_COUNT` — количество подъёмников
- `MASTER_COUNT` — количество мастеров

В `db/repository.py` функция `seed_masters_and_lifts()` при первом запуске создаёт записи.
Если нужно изменить имена мастеров — отредактируйте их в файле `autoservice.db` через любой SQLite-браузер.

---

## Требования

- Python 3.11+
- Telegram Bot Token (получить у @BotFather)
- Дисковое место: ~50 MB (вместе с venv)
- RAM: ~100 MB
