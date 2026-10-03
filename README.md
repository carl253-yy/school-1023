# School Management System

Flask-based CBC school management system with administrator, teacher, parent, and learner accounts; draft/submitted/approved results; attendance; fee statements/payments; audit logs; and CSV export.

## Install and run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `SECRET_KEY`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD` in `.env`, then initialize data:

```powershell
python seed.py
python app.py
```

Open `http://127.0.0.1:5000`. Sign in using the configured administrator email/password. Test accounts are `teacher@example.com / Teacher123!`, `parent@example.com / Parent123!`, and `learner@example.com / Learner123!`.

## Database and migrations

The default database is SQLite at `instance/school.db`. To use PostgreSQL/Supabase, set `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE` in `.env`; never place a Supabase API secret in this application. For migration-managed environments:

```powershell
flask --app app db init
flask --app app db migrate -m "initial school schema"
flask --app app db upgrade
python seed.py
```

## Security and workflow

All POST routes use CSRF protection. Roles are enforced server-side. Teachers can create only draft/submitted CBC results; administrators approve submitted records, after which teachers cannot change them. Fees are writable only by administrators. CBC levels remain `EE`, `ME`, `AE`, and `BE`—they are not converted to percentages.
