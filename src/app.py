"""FastAPI backend for activity management with auth, roles, and SQLite storage."""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field

app = FastAPI(
    title="Mergington High School API",
    description="API for extracurricular activities with authentication and roles",
)

current_dir = Path(__file__).parent
db_path = current_dir / "activities.db"

app.mount(
    "/static",
    StaticFiles(directory=os.path.join(current_dir, "static")),
    name="static",
)


seed_activities = [
    (
        "Chess Club",
        "Learn strategies and compete in chess tournaments",
        "Fridays, 3:30 PM - 5:00 PM",
        12,
    ),
    (
        "Programming Class",
        "Learn programming fundamentals and build software projects",
        "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        20,
    ),
    (
        "Gym Class",
        "Physical education and sports activities",
        "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        30,
    ),
    (
        "Soccer Team",
        "Join the school soccer team and compete in matches",
        "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        22,
    ),
    (
        "Basketball Team",
        "Practice and play basketball with the school team",
        "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        15,
    ),
    (
        "Art Club",
        "Explore your creativity through painting and drawing",
        "Thursdays, 3:30 PM - 5:00 PM",
        15,
    ),
    (
        "Drama Club",
        "Act, direct, and produce plays and performances",
        "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        20,
    ),
    (
        "Math Club",
        "Solve challenging problems and participate in math competitions",
        "Tuesdays, 3:30 PM - 4:30 PM",
        10,
    ),
    (
        "Debate Team",
        "Develop public speaking and argumentation skills",
        "Fridays, 4:00 PM - 5:30 PM",
        12,
    ),
]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_role(role: str) -> str:
    normalized = role.strip().lower().replace(" ", "_")
    aliases = {
        "clubrepresentative": "club_representative",
        "club-representative": "club_representative",
    }
    return aliases.get(normalized, normalized)


PASSWORD_HASH_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored_hash.split("$", 3)
    except ValueError:
        try:
            salt, digest = stored_hash.split("$", 1)
        except ValueError:
            return False
        computed = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
        return secrets.compare_digest(digest, computed)

    if algorithm != "pbkdf2_sha256":
        return False

    computed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations),
    ).hex()
    return secrets.compare_digest(digest, computed)


def init_db() -> None:
    conn = get_conn()
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('student', 'club_representative', 'admin')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                schedule TEXT NOT NULL,
                max_participants INTEGER NOT NULL CHECK(max_participants > 0)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                activity_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, activity_id),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(activity_id) REFERENCES activities(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        existing = conn.execute("SELECT COUNT(*) AS count FROM activities").fetchone()["count"]
        if existing == 0:
            conn.executemany(
                """
                INSERT INTO activities (name, description, schedule, max_participants)
                VALUES (?, ?, ?, ?)
                """,
                seed_activities,
            )
    conn.close()


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: Literal["student"] = "student"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1].strip()
    conn = get_conn()
    row = conn.execute(
        """
        SELECT u.id, u.email, u.role
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token = ?
        """,
        (token,),
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"id": row["id"], "email": row["email"], "role": row["role"], "token": token}


def require_roles(user: dict, allowed_roles: set[str]) -> None:
    if user["role"] not in allowed_roles:
        raise HTTPException(status_code=403, detail="You do not have permission for this action")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/static/index.html")


@app.post("/auth/signup")
def signup(payload: SignupRequest) -> dict:
    role = normalize_role(payload.role)
    if role not in {"student", "club_representative", "admin"}:
        raise HTTPException(status_code=400, detail="Invalid role")

    conn = get_conn()
    try:
        with conn:
            conn.execute(
                "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
                (payload.email.lower(), hash_password(payload.password), role),
            )
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=409, detail="User with this email already exists")

    conn.close()
    return {"message": "Account created", "email": payload.email.lower(), "role": role}


@app.post("/auth/login")
def login(payload: LoginRequest) -> dict:
    conn = get_conn()
    row = conn.execute(
        "SELECT id, email, role, password_hash FROM users WHERE email = ?",
        (payload.email.lower(),),
    ).fetchone()

    if not row or not verify_password(payload.password, row["password_hash"]):
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = secrets.token_urlsafe(32)
    with conn:
        conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, row["id"]))
    conn.close()

    return {
        "token": token,
        "user": {"id": row["id"], "email": row["email"], "role": row["role"]},
    }


@app.post("/auth/logout")
def logout(user: dict = Depends(get_current_user)) -> dict:
    conn = get_conn()
    with conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (user["token"],))
    conn.close()
    return {"message": "Logged out"}


@app.get("/me")
def me(user: dict = Depends(get_current_user)) -> dict:
    return {"id": user["id"], "email": user["email"], "role": user["role"]}


@app.get("/activities")
def get_activities() -> dict:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT a.name, a.description, a.schedule, a.max_participants, u.email AS participant_email
        FROM activities a
        LEFT JOIN registrations r ON r.activity_id = a.id
        LEFT JOIN users u ON u.id = r.user_id
        ORDER BY a.name, u.email
        """
    ).fetchall()
    conn.close()

    activities: dict = {}
    for row in rows:
        name = row["name"]
        if name not in activities:
            activities[name] = {
                "description": row["description"],
                "schedule": row["schedule"],
                "max_participants": row["max_participants"],
                "participants": [],
            }
        if row["participant_email"]:
            activities[name]["participants"].append(row["participant_email"])

    return activities


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, user: dict = Depends(get_current_user)) -> dict:
    conn = get_conn()
    activity = conn.execute(
        "SELECT id, max_participants, name FROM activities WHERE name = ?", (activity_name,)
    ).fetchone()
    if not activity:
        conn.close()
        raise HTTPException(status_code=404, detail="Activity not found")

    current_count = conn.execute(
        "SELECT COUNT(*) AS count FROM registrations WHERE activity_id = ?",
        (activity["id"],),
    ).fetchone()["count"]
    if current_count >= activity["max_participants"]:
        conn.close()
        raise HTTPException(status_code=400, detail="Activity is already full")

    try:
        with conn:
            conn.execute(
                "INSERT INTO registrations (user_id, activity_id) VALUES (?, ?)",
                (user["id"], activity["id"]),
            )
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Student is already signed up")

    conn.close()
    return {"message": f"Signed up {user['email']} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(
    activity_name: str,
    email: str | None = None,
    user: dict = Depends(get_current_user),
) -> dict:
    target_email = (email or user["email"]).lower()
    if target_email != user["email"]:
        require_roles(user, {"admin", "club_representative"})

    conn = get_conn()
    activity = conn.execute(
        "SELECT id FROM activities WHERE name = ?", (activity_name,)
    ).fetchone()
    if not activity:
        conn.close()
        raise HTTPException(status_code=404, detail="Activity not found")

    target_user = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        (target_email,),
    ).fetchone()
    if not target_user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    registration = conn.execute(
        "SELECT id FROM registrations WHERE activity_id = ? AND user_id = ?",
        (activity["id"], target_user["id"]),
    ).fetchone()
    if not registration:
        conn.close()
        raise HTTPException(status_code=400, detail="Student is not signed up for this activity")

    with conn:
        conn.execute("DELETE FROM registrations WHERE id = ?", (registration["id"],))
    conn.close()
    return {"message": f"Unregistered {target_email} from {activity_name}"}
