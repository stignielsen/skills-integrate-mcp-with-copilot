# Mergington High School Activities API

FastAPI application for extracurricular activity registration with SQLite persistence, authentication, and role-based authorization.

## Features

- Persistent SQLite storage for users, activities, registrations, and sessions
- Sign up, log in, log out, and session-based token auth
- Role model: `student`, `club_representative`, `admin`
- Activity browsing and protected registration/unregistration flows

## Getting Started

1. Install dependencies:

   ```bash
   pip install -r ../requirements.txt
   ```

2. Run the app from the `src` directory:

   ```bash
   uvicorn app:app --reload
   ```

3. Open:

- App: http://localhost:8000/static/index.html
- OpenAPI docs: http://localhost:8000/docs

## Database

On startup, the app creates `activities.db` in the `src` folder and seeds default activities when empty.

Tables:

- `users`
- `activities`
- `registrations`
- `sessions`

## API Endpoints

| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| POST | `/auth/signup` | Create user account (`email`, `password`, `role`) |
| POST | `/auth/login` | Return auth token for valid credentials |
| POST | `/auth/logout` | Invalidate current bearer token |
| GET | `/me` | Return current authenticated user |
| GET | `/activities` | List activities with registered participant emails |
| POST | `/activities/{activity_name}/signup` | Register authenticated user into activity |
| DELETE | `/activities/{activity_name}/unregister?email=<target>` | Unregister self, or others for admin/club representative |

## Authorization Rules

- Any authenticated user can register themselves for activities.
- Any authenticated user can unregister themselves.
- Only `admin` and `club_representative` can unregister another user.
