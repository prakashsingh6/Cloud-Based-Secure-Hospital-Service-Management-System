# ZetaTech Hospital Management System

Client-server prototype with a React dashboard frontend, FastAPI REST backend, and SQLite development database.

## Architecture

- Frontend: React, TypeScript, Vite, Tailwind CSS
- Backend: FastAPI REST APIs
- Database: SQLite for development, PostgreSQL planned through `DATABASE_URL`
- Authentication: JWT tokens with passlib `sha256_crypt` password hashing
- IoT simulation: Python script updates room status through API endpoints

## Frontend

```bash
npm install
npm run dev
```

Default frontend URL: `http://localhost:5173`

The frontend reads `VITE_API_URL` when present. If it is not set, it uses:

```text
http://127.0.0.1:8000
```

## Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Default API URL: `http://127.0.0.1:8000`

The backend creates and seeds `backend/zetatech.db` automatically on startup.

## Demo Users

```text
patient@example.com / password123
admin@zetatech.com / admin456
```

## IoT Simulation

Start the backend first, then run:

```bash
cd backend
python iot_simulator.py
```

The simulator sends room availability updates to:

```text
PATCH /iot/rooms/{room_id}
```
