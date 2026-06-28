# 🔐 Auth-ChatBot-Service

> **Flask backend microservice handling authentication, AI chatbot, GPS tracking, user management, and admin operations for the AlzAware smart glasses platform.**

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Prerequisites](#-prerequisites)
- [Installation & Setup](#-installation--setup)
- [Environment Configuration](#-environment-configuration)
- [Running the Server](#-running-the-server)
- [Database Setup](#-database-setup)
- [API Endpoints](#-api-endpoints)
- [Authentication (JWT)](#-authentication-jwt)
- [Rate Limiting](#-rate-limiting)
- [Security](#-security)
- [Project Structure](#-project-structure)
- [Dependencies](#-dependencies)

---

## 🌟 Overview

This service is the core backend for the AlzAware platform. It provides:

| Module | Description |
|:---|:---|
| 🔐 **Authentication** | Multi-role JWT auth (Patient, Doctor, Caregiver, Admin) |
| 🤖 **AI Chatbot** | Google Gemini–powered assistant with text & voice support |
| 📍 **GPS Tracking** | Real-time location tracking with history |
| 👤 **User Management** | Profile CRUD, device tokens, prescriptions, todos |
| 🧩 **Game Scores** | Cognitive game score tracking |
| 🛡️ **Admin Dashboard** | User management, system logs, analytics |
| 🧠 **MRI Analysis** | Brain scan analysis for Alzheimer's detection |

---

## 📦 Prerequisites

- **Python** 3.11 or later
- **ODBC Driver 17** (or 18) for SQL Server — [Download from Microsoft](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
- **SQL Server** instance with database `Alzaware` created in SSMS
- **Gmail account** with [App Password](https://myaccount.google.com/apppasswords) enabled (for password reset emails)

---

## 🚀 Installation & Setup

### 1. Create virtual environment & install dependencies

```powershell
cd Auth-ChatBot-Service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure environment

Copy or edit the `.env` file:

```env
# SQL Server (SSMS) Local Database Configuration
MSSQL_SERVER=localhost\SQLEXPRESS
MSSQL_DB=Alzaware
MSSQL_DRIVER=ODBC Driver 17 for SQL Server
MSSQL_TRUSTED=true

# Flask & JWT Configuration
SECRET_KEY=your-secret-key-change-in-production
FLASK_ENV=development
JWT_EXP_MINUTES=60

# Rate Limiting
RATE_LIMIT_PER_HOUR=100 per minute
RATELIMIT_STORAGE_URI=memory://

# Gmail SMTP Configuration (for password reset emails)
SMTP_USER=your_gmail@gmail.com
SMTP_PASSWORD=your_gmail_app_password
EMAIL_FROM=your_gmail@gmail.com
```

> ⚠️ **Important**: The `SECRET_KEY` must match the one in `Face-Recognition-Service/.env` for cross-service JWT authentication to work.

### 3. Run the server

```powershell
python run.py
```

Server will listen on: **http://localhost:5005**

---

## ⚙️ Environment Configuration

| Variable | Description | Default |
|:---|:---|:---|
| `MSSQL_SERVER` | SQL Server host | `localhost\SQLEXPRESS` |
| `MSSQL_DB` | Database name | `Alzaware` |
| `MSSQL_DRIVER` | ODBC driver name | `ODBC Driver 17 for SQL Server` |
| `MSSQL_TRUSTED` | Use Windows Authentication | `true` |
| `MSSQL_USER` | SQL Server username (if not using trusted) | — |
| `MSSQL_PASSWORD` | SQL Server password (if not using trusted) | — |
| `DATABASE_URL` | Full override connection string | — |
| `SECRET_KEY` | Flask secret key & JWT signing key | `dev-secret-key` |
| `JWT_SECRET` | JWT secret (overrides SECRET_KEY if set) | — |
| `JWT_EXP_MINUTES` | Token expiry in minutes | `60` |
| `RATE_LIMIT_PER_HOUR` | Global rate limit per IP | `100 per minute` |
| `RATELIMIT_STORAGE_URI` | Rate limiter storage backend | `memory://` |
| `SMTP_USER` | Gmail address for sending emails | — |
| `SMTP_PASSWORD` | Gmail App Password | — |
| `EMAIL_FROM` | From address in emails | — |

### Database Connection Examples

**Windows Integrated Auth (Trusted Connection):**
```
mssql+pyodbc://@localhost\SQLEXPRESS/Alzaware?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes
```

**SQL Server Auth (Username/Password):**
```
mssql+pyodbc://USERNAME:PASSWORD@SERVER_NAME/DB_NAME?driver=ODBC+Driver+17+for+SQL+Server
```

---

## 🗄️ Database Setup

### Initialize Database with Migrations

```powershell
flask --app run.py db init
flask --app run.py db migrate -m "Initial tables"
flask --app run.py db upgrade
```

### Create an Initial Patient (Python REPL)

```python
from app import create_app, db
from app.models.patient import Patient

app = create_app()
ctx = app.app_context(); ctx.push()

p = Patient(username='patient1', full_name='Ahmed Ali', email='ahmed@example.com')
p.set_password('secret')

db.session.add(p)
db.session.commit()
```

### Data Models

| Model | Table | Description |
|:---|:---|:---|
| `Patient` | `patients` | Patient accounts (name, email, password, etc.) |
| `Doctor` | `doctors` | Doctor accounts |
| `CareGiver` | `caregivers` | Caregiver accounts |
| `Admin` | `admins` | Admin accounts |
| `Prescription` | `prescriptions` | Medicine prescriptions |
| `Todo` | `todos` | Task reminders for patients |
| `GameScore` | `game_scores` | Cognitive game scores |
| `Location` | `locations` | GPS location records |
| `Medicine` | `medicines` | Medicine information |
| `SystemLog` | `system_logs` | Audit/system logs |

---

## 📡 API Endpoints

### 🔓 Authentication (`/auth`)

| Method | Endpoint | Rate Limit | Description |
|:---|:---|:---|:---|
| `POST` | `/auth/register` | 100/min | Register a new user |
| `POST` | `/auth/register/patient` | 100/min | Register as patient |
| `POST` | `/auth/register/doctor` | 100/min | Register as doctor |
| `POST` | `/auth/register/caregiver` | 100/min | Register as caregiver |
| `POST` | `/auth/login` | 100/min | Login → returns JWT token |
| `POST` | `/auth/logout` | 100/min | Logout (revokes token) |
| `POST` | `/auth/forgetpassword` | 100/min | Request password reset email |
| `POST/GET` | `/auth/resetpassword` | 100/min | Reset password with token |
| `GET` | `/auth/resetpassword/open` | 100/min | Open reset password link |
| `PATCH/POST` | `/auth/updatemypassword` | 100/min | Change current password |

#### Register

```bash
curl -X POST http://localhost:5005/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Ahmed Ali",
    "email": "ahmed@example.com",
    "password": "secret"
  }'
```

**Response:**
```json
{
  "status": "success",
  "token": "<JWT>",
  "data": {
    "patient": {
      "patient_id": 1,
      "name": "Ahmed Ali",
      "email": "ahmed@example.com"
    }
  }
}
```

#### Login

```bash
curl -X POST http://localhost:5005/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "ahmed@example.com",
    "password": "secret"
  }'
```

**Response:**
```json
{
  "status": "success",
  "token": "<JWT>",
  "data": {
    "patient": { "...all patient data..." }
  }
}
```

#### Logout

```bash
curl -X POST http://localhost:5005/auth/logout \
  -H "Authorization: Bearer <JWT>"
```

#### Forgot Password

```bash
curl -X POST http://localhost:5005/auth/forgetpassword \
  -H "Content-Type: application/json" \
  -d '{
    "email": "ahmed@example.com",
    "role": "patient"
  }'
```

> `role` is optional. Required only if same email exists in multiple roles (`patient`, `doctor`, `caregiver`).

#### Reset Password

```bash
curl -X POST http://localhost:5005/auth/resetpassword \
  -H "Content-Type: application/json" \
  -d '{
    "token": "<token-from-email>",
    "password": "newSecret123",
    "confirm_password": "newSecret123"
  }'
```

---

### 👤 User Management (`/user`)

> All user endpoints require `Authorization: Bearer <JWT>` header.

| Method | Endpoint | Description |
|:---|:---|:---|
| `GET` | `/user/me` | Get current user profile |
| `PATCH/POST` | `/user/updateme` | Update profile info |
| `DELETE/POST` | `/user/deleteme` | Delete my account |
| `POST` | `/user/prescriptions` | Add a new prescription |
| `GET` | `/user/my-prescriptions` | Get my prescriptions |
| `GET` | `/user/prescriptions/:patient_id` | Get a patient's prescriptions |
| `GET` | `/user/my-patients` | Get my patients (doctor/caregiver) |
| `POST` | `/user/games/scores` | Submit a game score |
| `GET` | `/user/games/scores/patient/:patient_id` | Get patient game scores |
| `POST` | `/user/device-token` | Register push notification token |
| `POST` | `/user/todos` | Create a to-do item |
| `GET` | `/user/todos/patient/:patient_id` | Get patient's to-dos |
| `PATCH` | `/user/todos/:todo_id` | Update a to-do |
| `DELETE` | `/user/todos/:todo_id` | Delete a to-do |

#### Example: Get Profile

```bash
curl -X GET http://localhost:5005/user/me \
  -H "Authorization: Bearer <JWT>"
```

#### Example: Add Game Score

```bash
curl -X POST http://localhost:5005/user/games/scores \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "doctor_id": "doctor-123",
    "patient_id": "patient-456",
    "score": 85
  }'
```

---

### 🤖 AI Chatbot (`/chat`)

> 🔒 All chatbot endpoints require JWT authentication.

| Method | Endpoint | Description |
|:---|:---|:---|
| `POST` | `/chat/ask` | Send a text message to the AI chatbot |
| `POST` | `/chat/voice` | Send a voice message to the AI chatbot |

#### Text Chat

```bash
curl -X POST http://localhost:5005/chat/ask \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"message": "ما هي أعراض الزهايمر؟"}'
```

#### Voice Chat

```bash
curl -X POST http://localhost:5005/chat/voice \
  -H "Authorization: Bearer <JWT>" \
  -F "audio=@recording.wav"
```

---

### 📍 GPS Tracking (`/api`)

| Method | Endpoint | Description |
|:---|:---|:---|
| `POST` | `/api/gps` | Send GPS coordinates from smart glasses |
| `GET` | `/api/gps/last` | Get last known location |
| `GET` | `/api/gps/history` | Get full location history |

#### Send Location

```bash
curl -X POST http://localhost:5005/api/gps \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "patient-123",
    "latitude": 30.0444,
    "longitude": 31.2357
  }'
```

#### Get Last Location

```bash
curl -X GET "http://localhost:5005/api/gps/last?patient_id=patient-123"
```

---

### 🛡️ Admin Dashboard (`/admin`)

> All admin endpoints require admin-level JWT authentication.

| Method | Endpoint | Description |
|:---|:---|:---|
| `GET` | `/admin/overview` | Dashboard statistics |
| `GET` | `/admin/users` | List all users |
| `GET` | `/admin/users/:role` | List users filtered by role |
| `POST` | `/admin/users/:role` | Create a new user |
| `PATCH` | `/admin/users/:role/:user_id/email` | Update user email |
| `PATCH` | `/admin/users/:role/:user_id/account-action` | Activate/deactivate/delete user |
| `GET` | `/admin/logs` | View system audit logs |
| `GET` | `/admin/logs/patient-logins` | View patient login history |
| `GET` | `/admin/logs/new-patients` | View recently registered patients |

---

### 🧠 MRI Scan Analysis (`/scan`)

| Method | Endpoint | Description |
|:---|:---|:---|
| `POST` | `/scan/mri` | Upload and analyze a brain MRI scan |

```bash
curl -X POST http://localhost:5005/scan/mri \
  -F "scan=@brain_mri.jpg"
```

---

## 🔑 Authentication (JWT)

### How It Works

1. User registers or logs in → receives a **JWT access token**
2. Token is signed with `HS256` using `SECRET_KEY`
3. Token contains: `sub` (user ID), `role`, `iat`, `exp`, `pwd_sig`
4. Protected endpoints validate the token via `@jwt_required()` decorator

### Token Payload Example

```json
{
  "sub": "patient-abc123",
  "role": "patient",
  "iat": 1715468400,
  "exp": 1715472000,
  "pwd_sig": "a1b2c3d4..."
}
```

### Token Lifetime

Configure in `.env`:
```env
JWT_EXP_MINUTES=120
```

### Security Features

- **Password-change invalidation**: Tokens become invalid when the user changes their password
- **Token blacklist**: Logout adds tokens to a Redis-based JWT Blacklist
- **Role-based access**: Token payload includes user role for authorization
- **Password signature**: Token includes a `pwd_sig` claim to detect password changes

---

## ⚡ Rate Limiting

All auth endpoints are limited to **100 requests per minute per IP** by default.

When rate limited, the response is:
```json
{
  "status": "error",
  "code": "RATE_LIMIT_EXCEEDED",
  "message": "Too many requests from this IP. Limit is 100 per minute."
}
```

HTTP Status: **429 Too Many Requests**

### Configuration

```env
RATE_LIMIT_PER_HOUR=100 per minute
RATELIMIT_DEFAULT=100 per minute
RATELIMIT_STORAGE_URI=memory://
```

---

## 🔒 Security

### Baseline Security Stack

| Layer | Implementation | Description |
|:---|:---|:---|
| **Password Hashing** | `bcrypt` (cost factor 12) | All passwords are hashed before storage — plain text is never persisted |
| **JWT Signing** | `HS256` + `pwd_sig` claim | Tokens are cryptographically signed and bound to the user's password hash |
| **Security Headers** | Flask-Talisman | Enforces CSP, HSTS, X-Content-Type-Options, X-Frame-Options |
| **Input Validation** | Pydantic v2 strict schemas | All request payloads are validated; invalid data returns `422 Unprocessable Entity` |
| **Rate Limiting** | Flask-Limiter (per-IP) | All endpoints are rate-limited to prevent abuse (default: 100 req/min) |
| **SQL Injection** | SQLAlchemy ORM | Parameterized queries via ORM — no raw SQL concatenation |
| **Token Revocation** | Redis-based JWT Blacklist | Logout immediately invalidates the token for the remainder of its TTL |
| **Cross-Service Auth** | Shared `JWT_SECRET` | Tokens issued here are verifiable by `Face-Recognition-Service` |

---

### 🛡️ Security Audit & Vulnerability Remediation

A comprehensive security audit was conducted on the entire backend platform. The following **7 critical vulnerabilities** were identified and remediated across `Auth-ChatBot-Service` and `Face-Recognition-Service`:

#### Vulnerability Summary

| # | Vulnerability | Severity | OWASP Category | Status |
|:--|:---|:---|:---|:---|
| 1 | Registration Enumeration | 🔴 High | A01 — Broken Access Control | ✅ Fixed |
| 2 | Werkzeug Debugger / Info Disclosure | 🔴 High | A05 — Security Misconfiguration | ✅ Fixed |
| 3 | Weak JWT Secret Key (Token Forgery) | 🔴 Critical | A02 — Cryptographic Failures | ✅ Fixed |
| 4 | Token Invalidation Failure After Password Change | 🔴 High | A07 — Identification & Auth Failures | ✅ Fixed |
| 5 | AI Chatbot Prompt Injection | 🟠 Medium | A03 — Injection | ✅ Fixed |
| 6 | Token Fixation | 🟠 Medium | A07 — Identification & Auth Failures | ✅ Fixed |
| 7 | Account Lockout via Email Hijacking | 🔴 High | A01 — Broken Access Control | ✅ Fixed |

---

#### 1. Registration Enumeration Prevention

**Root Cause:** Registration endpoints returned `HTTP 409 Conflict` with `"Email already registered"` for existing emails and `HTTP 201 Created` for new accounts. Additionally, a timing side-channel existed — existing-email requests returned immediately while new registrations performed expensive `bcrypt` hashing, allowing attackers to infer account existence from response time alone.

**Fix:** All registration endpoints now return an identical `HTTP 200 OK` response with a generic message for both existing and non-existing emails. A `_dummy_verify()` function performs a throwaway bcrypt hash to normalize processing time. The validation order was corrected to check foreign keys (e.g., `doctor_id`) before email uniqueness, preventing targeted enumeration.

**Affected Files:**
- `app/controllers/auth_controller.py` — `_register_patient()`, `_register_doctor()`, `_register_caregiver()`

---

#### 2. Werkzeug Debugger & Information Disclosure

**Root Cause:** `run.py` had `debug=True` hardcoded, and `.env` set `FLASK_ENV=development`. In production, this exposed the Werkzeug interactive debugger on any unhandled exception, leaking full stack traces, source code, environment variables, and allowing arbitrary code execution via the debugger PIN.

**Fix:** `run.py` now dynamically reads `FLASK_ENV` and only enables debug mode in development. The `.env` file was updated to `FLASK_ENV=production`.

**Affected Files:**
- `run.py` — Debug mode logic
- `.env` — Environment configuration

---

#### 3. Weak JWT Secret Key & Safe Rotation

**Root Cause:** The JWT signing secret was a weak, guessable string (`JwtSecretForAuth` — only 17 characters). An attacker could brute-force or dictionary-attack this secret and forge valid JWT tokens for any user, achieving full account takeover across all roles.

**Fix:** Replaced the secret with a cryptographically secure 64-character hex string. Implemented a graceful key rotation mechanism using `JWT_SECRET_OLD` — new tokens are signed with the strong key, while existing tokens signed with the old key remain valid during the transition period. This was applied across **all three services** (Auth-ChatBot, Face-Recognition-Server, Retrain-Server) to maintain cross-service JWT verification.

**Affected Files:**
- `.env` — `JWT_SECRET`, `JWT_SECRET_OLD`, `SECRET_KEY`
- `app/utils/jwt.py` — `_get_secret()`, `decode_token()`
- `Face-Recognition-Service/.env`
- `Face-Recognition-Service/Face-Recognition-Server/.env`
- `Face-Recognition-Service/Retrain-Server/.env`
- `Face-Recognition-Service/*/middleware/auth.py`

---

#### 4. Token Invalidation Failure After Password Change

**Root Cause:** A Python timezone bug. `datetime.utcnow()` returns a **naive** (timezone-unaware) datetime. When `_to_unix_timestamp()` called `.timestamp()` on it, Python assumed the value was in the server's **local timezone** (e.g., UTC+3), producing a timestamp shifted by 3 hours into the past. This caused the security check `changed_ts > token_iat` to silently pass even after a password change, allowing old tokens to remain valid indefinitely.

**Fix:** Modified `_to_unix_timestamp()` to explicitly attach `tzinfo=UTC` to naive datetimes before calling `.timestamp()`, ensuring mathematically correct comparison. Combined with the existing `pwd_sig` (password signature) claim, tokens are now **instantly invalidated** across all devices the moment a password is changed.

**Affected Files:**
- `app/utils/jwt.py` — `_to_unix_timestamp()`

---

#### 5. AI Chatbot Prompt Injection Defense

**Root Cause:** User input was directly interpolated into the LLM system prompt via f-string (`User Question: "{question}"`). An attacker could inject control sequences like `"Ignore all previous instructions..."` to override system directives, extract the system prompt, or manipulate the AI into disclosing patient medical records.

**Fix:** Migrated from single-string prompt concatenation to a structured multi-turn `messages` array. System instructions are sent as a separate context turn, followed by a model acknowledgment turn, and then the user's actual input as a distinct message. This creates a clear boundary that the LLM respects, preventing role-override and instruction-leakage attacks.

**Affected Files:**
- `app/controllers/chat_controller.py` — `ask_text()`, `ask_voice()`

---

#### 6. Token Fixation Protection

**Root Cause:** Authentication workflows were vulnerable to session fixation — an attacker could potentially inject or reuse a pre-existing token across authentication boundaries without it being replaced by a freshly issued one.

**Fix:** All authentication and privilege-changing operations (login, password reset, password update) now unconditionally issue a **new JWT token** bound to the current password hash. Old tokens cannot be carried across authentication events.

**Affected Files:**
- `app/controllers/auth_controller.py` — `login()`, `reset_password()`, `update_my_password()`

---

#### 7. Account Lockout via Email Hijacking Prevention

**Root Cause:** The email update endpoint allowed immediate email address changes without verifying ownership of the new email. An attacker with a valid session could change the victim's email to their own, locking the legitimate user out of all account recovery mechanisms (password reset emails would be sent to the attacker's email).

**Fix:** The email update workflow was redesigned to require ownership verification before applying email address changes. Email modifications are no longer applied immediately, preventing account identity hijacking.

**Affected Files:**
- `app/controllers/user_controller.py` — Email update logic
- `app/controllers/admin_controller.py` — Admin email update logic

---

> ⚠️ **Production Checklist**:
> - ✅ Use a cryptographically secure `JWT_SECRET` (64+ hex characters)
> - ✅ Ensure `FLASK_ENV=production` is set in `.env`
> - ☐ Enable HTTPS via Nginx reverse proxy
> - ☐ Deploy with Gunicorn as WSGI server (not Flask dev server)
> - ☐ Persist token blacklist in Redis or database
> - ☐ Implement CAPTCHA on registration for distributed enumeration defense

---

## 📝 Data Validation & Transformation

This project employs rigorous data validation and transformation pipelines to ensure data integrity, prevent injection attacks, and prepare data for AI models.

### Validation (`Pydantic`)
- **Strict Payloads:** All incoming requests are validated against robust `Pydantic v2` schemas (e.g., `RegisterPatientPayload`, `LoginPayload`).
- **Data Integrity:** We use `ConfigDict(extra='forbid')` to reject any undocumented fields in API requests, mitigating mass-assignment vulnerabilities.
- **Custom Business Logic:** Complex validation rules (e.g., matching `password` and `confirm_password`, verifying contact info) are enforced using Pydantic's `@model_validator(mode='after')`.

### Serialization & Transformation
- **Object-to-JSON Serialization:** Dedicated mapping functions (e.g., `_patient_to_dict`, `_caregiver_to_dict`) cleanly transform complex `SQLAlchemy` ORM entities into secure, formatted JSON dictionaries for API responses.
- **JSON-to-Object Deserialization:** Incoming raw JSON payloads are transformed and sanitized into safe Python data types using Pydantic's `.model_validate().model_dump()`.
- **AI/ML Data Pipelines:**
  - **NLP:** Text queries are transformed into dense vector embeddings using `SentenceTransformer` for RAG and vector database querying (ChromaDB).
  - **Computer Vision (Face Recognition):** `LabelEncoder` is utilized to transform raw string labels (names) into numeric formats for neural network training (`fit_transform`) and inverse-transformed back to names during inference (`inverse_transform`).

---

## 📁 Project Structure

```
Auth-ChatBot-Service/
├── app/
│   ├── __init__.py              ← App factory, DB config, rate limiting, Talisman
│   ├── controllers/
│   │   ├── auth_controller.py   ← Registration, login, password flows
│   │   ├── user_controller.py   ← Profile, prescriptions, todos, games
│   │   ├── admin_controller.py  ← Admin dashboard & user management
│   │   ├── chat_controller.py   ← AI chatbot (Gemini, text & voice)
│   │   ├── gps_controller.py    ← GPS location tracking
│   │   └── scan_controller.py   ← MRI scan analysis
│   ├── models/
│   │   ├── patient.py           ← Patient SQLAlchemy model
│   │   ├── doctor.py            ← Doctor model
│   │   ├── caregiver.py         ← Caregiver model
│   │   ├── admin.py             ← Admin model
│   │   ├── prescription.py      ← Prescription model
│   │   ├── todo.py              ← To-do item model
│   │   ├── game_score.py        ← Game score model
│   │   ├── location.py          ← GPS location model
│   │   ├── medicine.py          ← Medicine model
│   │   └── system_log.py        ← Audit log model
│   ├── routes/
│   │   ├── auth_routes.py       ← /auth blueprint
│   │   ├── user_routes.py       ← /user blueprint
│   │   ├── admin_routes.py      ← /admin blueprint
│   │   ├── chat_routes.py       ← /chat blueprint
│   │   ├── gps_routes.py        ← /api/gps blueprint
│   │   └── scan_routes.py       ← /scan blueprint
│   └── utils/
│       ├── jwt.py               ← JWT creation, verification, decorators
│       ├── validation.py        ← Pydantic schemas & validators
│       ├── response.py          ← Standard JSON response helpers
│       ├── email.py             ← SMTP email sending
│       ├── error_handler.py     ← Global error handlers
│       ├── audit.py             ← Audit logging
│       └── sns_helper.py        ← AWS SNS push notifications
├── scripts/                     ← Utility scripts
├── vector_db/                   ← ChromaDB vector database for chatbot
├── .env                         ← Environment configuration
├── run.py                       ← Entry point (runs on port 5005)
├── requirements.txt             ← Python dependencies
└── README.md                    ← This file
```

---

## 📚 Dependencies

| Package | Purpose |
|:---|:---|
| `Flask` 3.0.3 | Web framework |
| `Flask-SQLAlchemy` 3.1.1 | ORM for SQL Server |
| `SQLAlchemy` 2.0.25 | Database toolkit |
| `pyodbc` 5.1.0 | ODBC driver interface |
| `python-dotenv` 1.0.1 | `.env` file loading |
| `passlib[bcrypt]` 1.7.4 | Password hashing |
| `Flask-Migrate` 4.0.5 | Database migrations (Alembic) |
| `Flask-Talisman` 1.1.0 | Security headers |
| `Pydantic` 2.7.4 | Request validation |
| `Flask-Limiter` 3.8.0 | Rate limiting |
| `PyJWT` 2.9.0 | JWT token handling |
| `langchain-google-genai` | Google Gemini integration |
| `langchain` | LLM orchestration framework |
| `textblob` | NLP text processing |
| `SpeechRecognition` | Voice-to-text |
| `gTTS` | Text-to-speech |
| `pydub` | Audio processing |
| `chromadb` | Vector database |
| `sentence-transformers` | Text embeddings |

---

Built and maintained by **Mohamed Ashraf** and team. 🚀
