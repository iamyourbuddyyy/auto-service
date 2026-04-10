# AutoService CRM — Telegram Bot

## Описание проекта

CRM-система для автосервиса в Telegram. 4 подъёмника, 6 мастеров, Пн-Сб 09:00-21:00.

## Tech Stack

- Python 3.11+
- **aiogram 3.x** — async Telegram bot framework, FSM
- **SQLAlchemy (async) + aiosqlite** — ORM + SQLite
- **APScheduler** — напоминания, авто-завершение записей
- **python-dotenv** — конфиг из .env

## Запуск

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить BOT_TOKEN и ADMIN_PASSWORD
python3 bot.py
```

## Структура проекта

```
bot.py                    # точка входа
config.py                 # константы (типы услуг, часы работы)
db/
  engine.py               # async_engine, session factory
  models.py               # все ORM-модели
  repository.py           # единственный слой доступа к БД (весь CRUD здесь)
handlers/
  client/                 # /start, booking FSM, my_appointments, review
  admin/                  # auth, schedule, appointments, clients, broadcast
keyboards/
  client_kb.py / admin_kb.py
states/
  booking_states.py       # BookingStates, ReviewStates
  admin_states.py         # AdminAddAppointment, AdminReschedule, AdminBroadcast, AdminBlockSlot
services/
  availability.py         # алгоритм свободных слотов (ЯДРО ЛОГИКИ)
  master_assign.py        # авто-назначение мастера + подъёмника (least-busy)
  scheduler_jobs.py       # APScheduler jobs
  notifications.py        # все типы уведомлений через bot.send_message
filters/
  is_admin.py             # IsAdmin() кастомный фильтр
middlewares/
  db_session.py           # DbSessionMiddleware — передаёт session в handlers
utils/
  datetime_utils.py       # generate_day_slots(), get_week_start()
  formatters.py           # format_day_schedule(), format_client_card()
```

## Ключевые правила

- **Весь доступ к БД — только через `db/repository.py`**. Никаких прямых запросов в handlers.
- Рабочие дни: Пн-Сб (воскресенье пропускается при поиске слотов).
- Длительности услуг: ТО=1ч, Диагностика=1ч, Шиномонтаж=1ч, Кузовной=4ч, Электрика=2ч, Слесарка=2ч.
- Мастер и подъёмник назначаются **автоматически** при подтверждении записи (least-busy за неделю).
- Статусы записей: `scheduled` → `completed` / `cancelled` / `no_show`.
- Авторизация админа: `/admin <пароль>` (пароль из `ADMIN_PASSWORD` в .env).

## База данных

Таблицы: `clients`, `vehicles`, `masters`, `lifts`, `service_types`, `appointments`, `blocked_slots`, `reviews`, `broadcasts`.

SQLite-файл: `autoservice.db` в корне проекта (создаётся автоматически при старте).

## Scheduler jobs (APScheduler, timezone=Europe/Moscow)

| Job | Интервал | Что делает |
|---|---|---|
| send_reminders_job | 15 мин | Напоминания за 24ч и за 2ч до записи |
| send_review_requests_job | 30 мин | Запрос отзыва через 30-90 мин после завершения |
| auto_complete_job | 30 мин | scheduled → completed если end_dt прошёл >15 мин |

## .env переменные

```
BOT_TOKEN=           # токен от @BotFather
ADMIN_PASSWORD=      # секретный пароль для /admin
DATABASE_URL=sqlite+aiosqlite:///./autoservice.db
TZ=Europe/Moscow
```

## Проверки после изменений

- `.py` файл → `python3 -m py_compile <файл>`
- Запуск бота → `python3 bot.py`
- Синтаксис всего проекта → `python3 -m py_compile bot.py db/models.py services/availability.py`
