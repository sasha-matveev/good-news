# План переезда на Firebase / Google Cloud (вариант A, cloud-only)

Цель: захостить Good News в облаке с фактической стоимостью $0/мес.
Облако становится **единственной** средой исполнения: локальный docker-режим,
Ollama и APScheduler удаляются, флагов совместимости нет.

Целевая архитектура:

| Компонент | Где | Тариф |
|---|---|---|
| Frontend (React/Vite) | Firebase Hosting | бесплатные квоты Blaze |
| Backend (FastAPI, монолит `app`) | Cloud Run (scale-to-zero) | бесплатные квоты Blaze |
| Postgres | Neon.tech | Free plan (0.5 GB) |
| LLM-анализ | Gemini API (вместо Ollama) | free tier AI Studio |
| Планировщик (sync + digest) | Cloud Scheduler → HTTP (вместо APScheduler) | 3 задания бесплатно |
| Email-дайджесты | Gmail SMTP (app password) или Brevo | бесплатно |

Что сознательно теряем: local-first приватность (статьи уходят в Gemini, данные в Neon),
Grafana-стек, мгновенный отклик (cold start ~2–4 с), локальный docker-режим целиком.

Что обязательно добавляем: аутентификацию (Firebase Auth, allowlist на email) —
без неё персональный фид и настройки SMTP открыты всему интернету.

Локальная разработка после переезда: `uvicorn app.main:app` + `npm run dev`
против dev-ветки Neon (Neon branches) с env-файлом. Без Docker.

---

## Фаза 1. Настройка Google Cloud / Firebase

Предусловия: Blaze-подписка уже есть, доступ к Gemini API уже есть.

- [ ] 1.1. Создать **отдельный** Firebase-проект `good-news` (не смешивать с существующим),
      привязать к существующему billing-аккаунту (Blaze).
- [ ] 1.2. Включить API в этом GCP-проекте:
      `run.googleapis.com`, `artifactregistry.googleapis.com`,
      `cloudscheduler.googleapis.com`, `secretmanager.googleapis.com`,
      `iamcredentials.googleapis.com` (для WIF из фазы 3).
- [ ] 1.3. Регион: `us-central1` (гарантированно поддерживается Hosting-rewrites → Cloud Run).
- [ ] 1.4. Создать Artifact Registry репозиторий `good-news` (Docker, тот же регион).
- [ ] 1.5. Сложить секреты в Secret Manager (бесплатно до 6 активных версий):
      - `good-news-db-url` — connection string Neon (появится в фазе 2)
      - `good-news-app-master-key` — текущий `GOOD_NEWS_APP_MASTER_KEY`
      - `good-news-gemini-api-key`
      - `good-news-smtp-password`
- [ ] 1.6. Получить/проверить Gemini API key (AI Studio), убедиться что free tier активен.
      Модель: актуальная flash-lite; дневных квот free tier достаточно
      для персонального объёма постов.
- [ ] 1.7. Включить Firebase Auth → провайдер Google Sign-In.
- [ ] 1.8. Поставить budget alert на $1 и $5 на billing-аккаунт (если ещё нет).

Критерий готовности: проект существует, API включены, секреты лежат в Secret Manager.

## Фаза 2. Настройка Neon

- [ ] 2.1. Зарегистрировать аккаунт на neon.tech (Free plan).
- [ ] 2.2. Создать проект `good-news`, Postgres 16+, регион ближе к региону Cloud Run
      (для `us-central1` → AWS us-east-*).
- [ ] 2.3. Создать базу `good_news` и роль приложения (не пользоваться owner-ролью).
- [ ] 2.4. Получить connection string с `sslmode=require`,
      записать в Secret Manager (`good-news-db-url`, см. 1.5).
- [ ] 2.5. Прогнать Alembic-миграции с локальной машины на Neon:
      `alembic upgrade head` с env-переменными, указывающими на Neon.
- [ ] 2.6. **До удаления локального postgres-волюма** решить судьбу данных:
      если история постов ценна — `pg_dump` из docker-контейнера →
      `pg_restore`/`psql` в Neon; иначе источники добавить заново через UI.
- [ ] 2.7. Создать dev-ветку Neon для локальной разработки.

Критерий готовности: `psql` к Neon ходит, `alembic current` показывает head.

## Фаза 3. CI/CD в GitHub Actions

Принцип: деплой только с `master`, аутентификация в GCP через
**Workload Identity Federation** (без JSON-ключей в секретах GitHub).

- [ ] 3.1. В GCP: создать service account `github-deployer@<project>.iam.gserviceaccount.com`
      с ролями: `run.admin`, `artifactregistry.writer`, `iam.serviceAccountUser`,
      `firebasehosting.admin`, `secretmanager.secretAccessor`.
- [ ] 3.2. Настроить Workload Identity Pool + Provider для GitHub OIDC,
      разрешить только репо `sasha-matveev/good-news`, ветку `master`.
- [ ] 3.3. GitHub repo variables/secrets: `GCP_PROJECT_ID`, `GCP_REGION`,
      `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`.
- [ ] 3.4. Workflow `.github/workflows/ci.yml` (deploy job on push в `master`,
      после успешных тестов):
      1. `google-github-actions/auth` (WIF)
      2. build backend image → push в Artifact Registry
      3. **миграции**: `gcloud run jobs execute db-migrate` (Cloud Run Job с тем же
         образом, command `python -m app.core.migration_runner`) — до деплоя сервиса
      4. `gcloud run deploy good-news-app` — новый образ, секреты из Secret Manager
         как env, `--min-instances=0 --max-instances=1 --memory=512Mi`
      5. build frontend (`npm ci && npm run build`) → `firebase deploy --only hosting`
- [ ] 3.5. Первый деплой: прогнать workflow, получить URL Cloud Run и URL Hosting.
- [ ] 3.6. Создать задания Cloud Scheduler (скриптом в `infra/`):
      - `source-sync`: каждые N минут → `POST <cloud-run-url>/internal/jobs/source-sync`,
        OIDC-токен от выделенного SA `scheduler-invoker`, attempt deadline ≤ 30 мин
      - `daily-digest`: cron по расписанию дайджеста →
        `POST <cloud-run-url>/internal/jobs/daily-digest`, тот же OIDC
      Cloud Run остаётся публичным (API для фронта), поэтому `/internal/*`
      защищаем проверкой OIDC-токена в коде (фаза 4).

Критерий готовности: push в master → тесты → образ → миграции → Cloud Run → Hosting,
всё зелёное; scheduler-задания созданы (пока могут бить в 404 — эндпоинты в фазе 4).

## Фаза 4. Изменения в коде

Порядок внутри фазы — от независимого к зависимому; каждая задача — отдельный PR.
Без флагов совместимости: Ollama и APScheduler не сохраняются.

- [ ] 4.1. **Конфиг БД**: единый `GOOD_NEWS_DATABASE_URL` (с `sslmode=require`)
      в `app/core/config.py` / `core/db.py`.
- [ ] 4.2. **GeminiClient**: новый класс в `backend/app/ai/` с тем же интерфейсом, что
      `OllamaClient` (`analyze_article`, `analyze_and_persist`); перенос промпта,
      httpx-вызов Gemini API (`generateContent`), JSON-mode.
      **`ollama_client.py` удаляется**, все ссылки переключаются на Gemini.
      Юнит-тесты с замоканным httpx.
- [ ] 4.3. **Джобы по HTTP**: эндпоинты `POST /internal/jobs/source-sync` и
      `POST /internal/jobs/daily-digest`, переиспользующие логику из
      `app/jobs/source_jobs.py` / `digest_jobs.py`.
      Защита: верификация Google OIDC-токена (issuer accounts.google.com,
      audience = URL сервиса, email = SA `scheduler-invoker`).
      **APScheduler и `app/jobs/scheduler.py` удаляются**, зависимость
      `apscheduler` убирается из pyproject.
- [ ] 4.4. **Auth**: фронт — Firebase Auth (Google Sign-In), токен в
      `Authorization: Bearer`; бэк — middleware, проверяющий Firebase ID token +
      allowlist email (`GOOD_NEWS_ALLOWED_EMAILS`). Без выключателя.
      Вне middleware только `/api/health` и `/internal/*` (своя OIDC-защита).
- [ ] 4.5. **Hosting-конфиг**: `firebase.json` + `.firebaserc` в корне:
      `public: frontend/dist`, rewrites `/api/**` → Cloud Run `good-news-app`,
      остальное → `/index.html`. Rewrite-таймаут Hosting ~60 с, поэтому
      ручной sync становится асинхронным: эндпоинт запускает работу и сразу
      отвечает 202, UI поллит статус.
- [ ] 4.6. **Email**: `email_service.py` → smtp.gmail.com:465 (app password)
      или Brevo; пароль из env/Secret Manager. Порт 25 в Cloud Run закрыт.
- [ ] 4.7. **CORS/origins**: `GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN` = домен Hosting
      (`https://<project>.web.app`); проверить ссылки в email-шаблонах.
- [ ] 4.8. **Monitoring-таб**: убрать ссылку на Grafana; блоки
      source health / LLM queue, которые читают своё API, оставить.

Критерий готовности: CI зелёный, новые тесты (GeminiClient, OIDC, auth) проходят.

## Фаза 5. Удаление локальной инфраструктуры (после успешного cutover)

- [ ] 5.1. Удалить: `docker-compose.yml`, `frontend/nginx.conf`,
      `frontend/Dockerfile`, `scripts/deploy.ps1`,
      `scripts/restart-runtime-service.ps1`, `scripts/pull-ollama-model.ps1`,
      `scripts/load-dev-secrets.ps1` и прочие compose-скрипты,
      `infra/observability/`.
- [ ] 5.2. Обновить README: облачная архитектура, деплой через GitHub Actions,
      секреты, локальная разработка через uvicorn + vite + Neon dev branch.

## Фаза 6. Cutover и проверка

- [ ] 6.1. Деплой через workflow из фазы 3.
- [ ] 6.2. Smoke: `GET https://<project>.web.app/` (логин), `GET /api/health`,
      добавить источник, дождаться sync от Scheduler, проверить посты и ранжирование
      (Gemini), форсировать дайджест, проверить письмо.
- [ ] 6.4. Проверить, что неавторизованный запрос к `/api/posts` получает 401,
      а `/internal/jobs/*` без OIDC — 401/403.
- [ ] 6.5. Неделю понаблюдать billing-отчёт: всё в пределах free tier, счёт $0.

## Риски и заметки

- **Квоты Gemini free tier** — дневной лимит запросов; при большом бэклоге постов
  анализ растянется на несколько дней. Митигировать: батчить, ранжировать только
  новые посты.
- **Neon free**: 0.5 GB и авто-suspend. Добавить retention-джоб (чистка старых
  постов) до того, как упрёмся в лимит.
- **Cold start**: первый запрос после простоя ~2–4 с; для одного пользователя приемлемо.
- **Долгий sync**: запрос Cloud Run ≤ 60 мин, Scheduler attempt deadline ≤ 30 мин —
  sync должен укладываться или стать инкрементальным.
- **Письма из Gmail**: лимит ~500/день — более чем достаточно.
- **Данные**: локальный postgres-волюм не удалять, пока не решён п. 2.6.
