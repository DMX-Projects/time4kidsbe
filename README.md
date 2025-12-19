# Time4Kids Backend (Django REST Framework)

Production-ready backend powering the Time4Kids frontend. Includes JWT auth, RBAC, franchise isolation, events/media, enquiries, and careers.

## Quickstart

1. `cd time4kids-be`
2. Create venv: `python -m venv .venv` then activate it.
3. Install deps: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and adjust secrets (SendGrid-ready SMTP settings included).
5. Run migrations: `python manage.py migrate`
6. Create an admin user: `python manage.py createsuperuser` (role defaults to ADMIN via the manager).
7. Start API: `python manage.py runserver 8000`

## Key Settings

- `AUTH_USER_MODEL=accounts.User` with roles: ADMIN, FRANCHISE, PARENT.
- JWT via SimpleJWT (access/refresh lifetimes configurable via env).
- CORS/CSRF defaults to `http://localhost:3000`; override via env.
- Media served from `/media/` (stored under `media/`).

## Core API Map

Auth
- `POST /api/auth/login/` — universal login, returns access/refresh + role metadata.
- `POST /api/auth/refresh/`
- `GET /api/auth/me/`

Admin
- `GET/POST /api/franchises/admin/franchises/` — manage own franchises (creates franchise user).
- `GET/PUT/PATCH/DELETE /api/franchises/admin/franchises/{id}/`
- `GET /api/franchises/admin/parents/` — parents under admin’s franchises.
- `GET/POST /api/careers/admin/` and detail routes — manage careers.

Franchise
- `GET/PATCH /api/franchises/franchise/profile/` — manage franchise profile.
- `GET/POST /api/franchises/franchise/parents/` — manage parents (creates parent user); detail routes for update/delete.
- `GET/POST /api/events/franchise/` — manage events; detail routes for update/delete.
- `GET/POST /api/events/franchise/{event_id}/media/` — upload/list media for an event.
- `GET /api/enquiries/franchise/` — view enquiries for the franchise.

Parent
- `GET /api/events/parent/` — events for the parent’s franchise.

Public
- `GET /api/franchises/public/{slug}/` — public franchise profile (includes events/media).
- `GET /api/events/public/{slug}/` — public events by franchise slug.
- `GET /api/careers/public/` — public career listings.
- `POST /api/enquiries/submit/` — admission/franchise/contact forms (emails admin + franchise when applicable).

## Data Ownership Rules

- Admins only see franchises they created and associated parents/enquiries.
- Franchise users are limited to their own franchise data (profile, parents, events, media, enquiries).
- Parents can only read their profile’s franchise events.
- Public routes expose only whitelisted data.

## Notes for Frontend Integration

- Universal login response contains `user.role` for client-side routing.
- Use the franchise `slug` for dynamic `[franchise-name]` public routes.
- File uploads: send multipart form data to event media endpoints; media served under `/media/`.

## Maintenance

- Admin site available at `/admin/` (superusers only).
- Update env secrets before production. Enable real SMTP by switching `EMAIL_BACKEND`.
