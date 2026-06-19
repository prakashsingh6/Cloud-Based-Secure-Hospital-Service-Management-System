from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
import os
import sqlite3
import uuid

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{Path(__file__).with_name('zetatech.db')}")
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret-for-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
security = HTTPBearer()

app = FastAPI(title="ZetaTech Hospital Management API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://hospital-service-management-system.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UserRole = Literal["user", "admin"]
RequestStatus = Literal["pending", "approved", "rejected"]
ServiceType = Literal["consultation", "therapy", "followup"]
RoomStatus = Literal["available", "busy"]         
RoomType = Literal["therapy", "doctor", "equipment"]


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: UserRole


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ServiceRequestIn(BaseModel):
    userId: str
    userEmail: str
    serviceType: ServiceType


class ServiceRequestOut(ServiceRequestIn):
    id: str
    status: RequestStatus
    reason: str | None = None
    createdAt: str
    updatedAt: str


class RequestStatusIn(BaseModel):
    status: RequestStatus
    reason: str | None = None


class MedicalReportIn(BaseModel):
    userId: str
    userEmail: str
    title: str
    content: str
    diagnosis: str
    notes: str
    doctorName: str


class MedicalReportOut(MedicalReportIn):
    id: str
    createdAt: str


class RoomStatusIn(BaseModel):
    status: RoomStatus


class IoTRoomOut(BaseModel):
    id: str
    roomId: str
    roomType: RoomType
    status: RoomStatus
    timestamp: str
    location: str


class DashboardStatsOut(BaseModel):
    totalRequests: int
    pendingRequests: int
    approvedRequests: int
    rejectedRequests: int
    totalUsers: int
    activeRooms: int


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


def sqlite_path() -> str:
    if DATABASE_URL.startswith("sqlite:///"):
        return DATABASE_URL.replace("sqlite:///", "", 1)
    raise RuntimeError("Only SQLite is configured for development. Use DATABASE_URL for PostgreSQL later.")


def get_db():
    conn = sqlite3.connect(sqlite_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def row_to_user(row: sqlite3.Row) -> UserOut:
    return UserOut(id=row["id"], email=row["email"], name=row["name"], role=row["role"])


def row_to_request(row: sqlite3.Row) -> ServiceRequestOut:
    return ServiceRequestOut(
        id=row["id"],
        userId=row["user_id"],
        userEmail=row["user_email"],
        serviceType=row["service_type"],
        status=row["status"],
        reason=row["reason"],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def row_to_report(row: sqlite3.Row) -> MedicalReportOut:
    return MedicalReportOut(
        id=row["id"],
        userId=row["user_id"],
        userEmail=row["user_email"],
        title=row["title"],
        content=row["content"],
        diagnosis=row["diagnosis"],
        notes=row["notes"],
        createdAt=row["created_at"],
        doctorName=row["doctor_name"],
    )


def row_to_room(row: sqlite3.Row) -> IoTRoomOut:
    return IoTRoomOut(
        id=row["id"],
        roomId=row["room_id"],
        roomType=row["room_type"],
        status=row["status"],
        timestamp=row["timestamp"],
        location=row["location"],
    )


def create_access_token(user: UserOut) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRES_MINUTES)
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "exp": expires_at,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: sqlite3.Connection = Depends(get_db),
) -> UserOut:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return row_to_user(row)


def require_admin(user: UserOut = Depends(get_current_user)) -> UserOut:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def init_db() -> None:
    Path(sqlite_path()).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sqlite_path()) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                password_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS service_requests (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                user_email TEXT NOT NULL,
                service_type TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS medical_reports (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                user_email TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                diagnosis TEXT NOT NULL,
                notes TEXT NOT NULL,
                doctor_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rooms (
                id TEXT PRIMARY KEY,
                room_id TEXT UNIQUE NOT NULL,
                room_type TEXT NOT NULL,
                status TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                location TEXT NOT NULL
            );
            """
        )

        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count == 0:
            conn.executemany(
                "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                [
                    (new_id(), "patient@example.com", "John Patient", "user", pwd_context.hash("password123")),
                    (new_id(), "admin@zetatech.com", "Admin User", "admin", pwd_context.hash("admin456")),
                ],
            )

        conn.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (pwd_context.hash("password123"), "patient@example.com"),
        )
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (pwd_context.hash("admin456"), "admin@zetatech.com"),
        )

        patient = conn.execute("SELECT id, email FROM users WHERE email = ?", ("patient@example.com",)).fetchone()
        request_count = conn.execute("SELECT COUNT(*) FROM service_requests").fetchone()[0]
        if request_count == 0 and patient:
            created = now_iso()
            conn.executemany(
                "INSERT INTO service_requests VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (new_id(), patient[0], patient[1], "consultation", "approved", "Doctor available on requested date", created, created),
                    (new_id(), patient[0], patient[1], "therapy", "pending", None, created, created),
                ],
            )

        report_count = conn.execute("SELECT COUNT(*) FROM medical_reports").fetchone()[0]
        if report_count == 0 and patient:
            created = now_iso()
            conn.executemany(
                "INSERT INTO medical_reports VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        new_id(),
                        patient[0],
                        patient[1],
                        "General Consultation Report",
                        "Patient presented with mild symptoms. Physical examination completed.",
                        "Common cold - viral infection",
                        "Rest recommended. Stay hydrated. Follow up in 3 days if symptoms persist.",
                        "Dr. Emily Johnson",
                        created,
                    ),
                    (
                        new_id(),
                        patient[0],
                        patient[1],
                        "Annual Health Checkup",
                        "Complete blood work done. All vitals within normal range.",
                        "Healthy - no concerns",
                        "Continue current lifestyle. Next checkup in 12 months.",
                        "Dr. Michael Chen",
                        created,
                    ),
                ],
            )

        room_count = conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
        if room_count == 0:
            timestamp = now_iso()
            conn.executemany(
                "INSERT INTO rooms VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (new_id(), "DOC-101", "doctor", "available", timestamp, "First Floor - Wing A"),
                    (new_id(), "THR-201", "therapy", "busy", timestamp, "Second Floor - Wing B"),
                    (new_id(), "EQP-301", "equipment", "available", timestamp, "Third Floor - Radiology"),
                    (new_id(), "DOC-102", "doctor", "busy", timestamp, "First Floor - Wing A"),
                    (new_id(), "THR-202", "therapy", "available", timestamp, "Second Floor - Wing B"),
                ],
            )


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/login", response_model=LoginOut)
def login(payload: LoginIn, db: sqlite3.Connection = Depends(get_db)) -> LoginOut:
    row = db.execute("SELECT * FROM users WHERE email = ?", (payload.email,)).fetchone()
    if not row or not pwd_context.verify(payload.password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    user = row_to_user(row)
    return LoginOut(access_token=create_access_token(user), user=user)


@app.get("/auth/me", response_model=UserOut)
def me(user: UserOut = Depends(get_current_user)) -> UserOut:
    return user


@app.post("/requests", response_model=ServiceRequestOut)
def create_request(
    payload: ServiceRequestIn,
    user: UserOut = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> ServiceRequestOut:
    if user.role != "admin" and user.id != payload.userId:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create request for another user")

    request_id = new_id()
    created = now_iso()
    db.execute(
        "INSERT INTO service_requests VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (request_id, payload.userId, payload.userEmail, payload.serviceType, "pending", None, created, created),
    )
    db.commit()
    row = db.execute("SELECT * FROM service_requests WHERE id = ?", (request_id,)).fetchone()
    return row_to_request(row)


@app.get("/requests", response_model=list[ServiceRequestOut])
def list_requests(
    user: UserOut = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> list[ServiceRequestOut]:
    if user.role == "admin":
        rows = db.execute("SELECT * FROM service_requests ORDER BY created_at DESC").fetchall()
    else:
        rows = db.execute("SELECT * FROM service_requests WHERE user_id = ? ORDER BY created_at DESC", (user.id,)).fetchall()
    return [row_to_request(row) for row in rows]


@app.get("/users/{user_id}/requests", response_model=list[ServiceRequestOut])
def list_user_requests(
    user_id: str,
    user: UserOut = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> list[ServiceRequestOut]:
    if user.role != "admin" and user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot view another user's requests")
    rows = db.execute("SELECT * FROM service_requests WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    return [row_to_request(row) for row in rows]


@app.patch("/requests/{request_id}/status", response_model=ServiceRequestOut)
def update_request_status(
    request_id: str,
    payload: RequestStatusIn,
    _: UserOut = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> ServiceRequestOut:
    updated = now_iso()
    db.execute(
        "UPDATE service_requests SET status = ?, reason = ?, updated_at = ? WHERE id = ?",
        (payload.status, payload.reason, updated, request_id),
    )
    db.commit()
    row = db.execute("SELECT * FROM service_requests WHERE id = ?", (request_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return row_to_request(row)


@app.get("/users/{user_id}/reports", response_model=list[MedicalReportOut])
def list_user_reports(
    user_id: str,
    user: UserOut = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> list[MedicalReportOut]:
    if user.role != "admin" and user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot view another user's reports")
    rows = db.execute("SELECT * FROM medical_reports WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    return [row_to_report(row) for row in rows]


@app.post("/reports", response_model=MedicalReportOut)
def create_report(
    payload: MedicalReportIn,
    _: UserOut = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> MedicalReportOut:
    report_id = new_id()
    created = now_iso()
    db.execute(
        "INSERT INTO medical_reports VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            report_id,
            payload.userId,
            payload.userEmail,
            payload.title,
            payload.content,
            payload.diagnosis,
            payload.notes,
            payload.doctorName,
            created,
        ),
    )
    db.commit()
    row = db.execute("SELECT * FROM medical_reports WHERE id = ?", (report_id,)).fetchone()
    return row_to_report(row)


@app.get("/rooms", response_model=list[IoTRoomOut])
def list_rooms(
    _: UserOut = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> list[IoTRoomOut]:
    rows = db.execute("SELECT * FROM rooms ORDER BY room_id").fetchall()
    return [row_to_room(row) for row in rows]


def update_room(room_id: str, status_value: RoomStatus, db: sqlite3.Connection) -> IoTRoomOut:
    timestamp = now_iso()
    db.execute("UPDATE rooms SET status = ?, timestamp = ? WHERE room_id = ?", (status_value, timestamp, room_id))
    db.commit()
    row = db.execute("SELECT * FROM rooms WHERE room_id = ?", (room_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    return row_to_room(row)


@app.patch("/rooms/{room_id}", response_model=IoTRoomOut)
def update_room_status(
    room_id: str,
    payload: RoomStatusIn,
    _: UserOut = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> IoTRoomOut:
    return update_room(room_id, payload.status, db)


@app.patch("/iot/rooms/{room_id}", response_model=IoTRoomOut)
def iot_update_room_status(
    room_id: str,
    payload: RoomStatusIn,
    db: sqlite3.Connection = Depends(get_db),
) -> IoTRoomOut:
    return update_room(room_id, payload.status, db)


@app.get("/stats", response_model=DashboardStatsOut)
def dashboard_stats(
    _: UserOut = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> DashboardStatsOut:
    total_requests = db.execute("SELECT COUNT(*) FROM service_requests").fetchone()[0]
    pending = db.execute("SELECT COUNT(*) FROM service_requests WHERE status = 'pending'").fetchone()[0]
    approved = db.execute("SELECT COUNT(*) FROM service_requests WHERE status = 'approved'").fetchone()[0]
    rejected = db.execute("SELECT COUNT(*) FROM service_requests WHERE status = 'rejected'").fetchone()[0]
    total_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active_rooms = db.execute("SELECT COUNT(*) FROM rooms WHERE status = 'available'").fetchone()[0]
    return DashboardStatsOut(
        totalRequests=total_requests,
        pendingRequests=pending,
        approvedRequests=approved,
        rejectedRequests=rejected,
        totalUsers=total_users,
        activeRooms=active_rooms,
    )
