print("STEP 0 - script started")  # TEMP

"""School Results Portal Flask application (Supabase Auth version)."""

import os
print("STEP 1 - imported os")  # TEMP

import secrets
print("STEP 2 - imported secrets")  # TEMP

from datetime import datetime
print("STEP 3 - imported datetime")  # TEMP

from dotenv import load_dotenv
print("STEP 4 - imported dotenv")  # TEMP

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
print("STEP 5 - imported flask")  # TEMP

from supabase import create_client, Client
print("STEP 6 - imported supabase")  # TEMP


load_dotenv()
print("STEP 7 - load_dotenv() done")  # TEMP

app = Flask(__name__)
print("STEP 8 - Flask app object created")  # TEMP

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    secrets.token_hex(32)
)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

print("About to create Supabase client...")  # TEMP
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
print("Supabase client created OK.")  # TEMP


# =========================================================
# SCHOOL INFORMATION
# =========================================================

SCHOOL = {
    "name": "School Results Portal",
    "location": "Kenya",
    "logo_url": "",
    "tagline": "Kenyan CBC assessment tracking",
    "hero_blurb": "Secure access to learner assessment results.",
}


VALID_ROLES = {"parent", "teacher", "admin"}

# Every possible spelling/casing a role tab or hidden input could
# send, all normalized down to exactly one of VALID_ROLES.
ROLE_ALIASES = {
    "parent": "parent",
    "teacher": "teacher",
    "admin": "admin",
    "administrator": "admin",
}


def resolve_role(raw_role):
    """Normalize whatever the form sent (any case/whitespace) down
    to one of 'parent' / 'teacher' / 'admin', or None if it doesn't
    match anything recognized.

    This is the ONLY place role strings get interpreted -- both
    /register and /signin call this, so there is no way for the
    two routes to disagree on what a given role string means.
    """

    if not raw_role:
        return None

    cleaned = raw_role.strip().lower()

    return ROLE_ALIASES.get(cleaned)


# =========================================================
# SUPABASE HELPERS
# =========================================================

def sign_up_user(email, password, full_name, role):
    """Create a Supabase Auth user. The `profiles` row is created
    automatically by the on_auth_user_created trigger, seeded from
    the metadata we pass here.

    Returns (success: bool, error_message: str | None).
    """

    if role not in VALID_ROLES:
        return False, "Please choose a valid role."

    if not full_name:
        return False, "Please enter your full name."

    print(f"REGISTER DEBUG - email={email!r} role_saved={role!r}")  # TEMP

    try:
        supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "full_name": full_name,
                    "role": role,
                }
            },
        })

    except Exception as exc:
        # Supabase raises AuthApiError with a human-readable message
        # for things like "already registered" or weak passwords.
        print("REGISTER DEBUG - signup error:", repr(exc))  # TEMP
        return False, str(exc)

    return True, None


def sign_in_user(email, password, expected_role):
    """Authenticate against Supabase Auth, then look up the role
    from `profiles` and confirm it matches the tab the user signed
    in from.

    Returns (success: bool, error_message: str | None).
    """

    print(f"SIGN-IN DEBUG - email={email!r} expected_role={expected_role!r}")  # TEMP

    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })

    except Exception as exc:
        print("SIGN-IN DEBUG - auth error:", repr(exc))  # TEMP
        return False, "Invalid sign-in details."

    user = auth_response.user

    if not user:
        print("SIGN-IN DEBUG - no user returned")  # TEMP
        return False, "Invalid sign-in details."

    profile = (
        supabase
        .table("profiles")
        .select("full_name, role")
        .eq("id", user.id)
        .single()
        .execute()
    )

    if not profile.data:
        print("SIGN-IN DEBUG - no profile row for user id:", user.id)  # TEMP
        return False, "No profile found for this account."

    # Normalize the stored role too, in case older rows were saved
    # with different casing before this fix.
    # Run the stored value through the SAME normalizer used for form
    # input. This means a legacy row saved as "administrator" (from
    # before role handling was unified) is still recognized as
    # "admin" here, instead of silently failing to match.
    raw_stored_role = profile.data.get("role")
    stored_role = resolve_role(raw_stored_role)

    print(
        f"SIGN-IN DEBUG - raw_stored_role={raw_stored_role!r} "
        f"resolved_stored_role={stored_role!r} "
        f"vs expected_role={expected_role!r}"
    )  # TEMP

    if stored_role is None:
        print(
            "SIGN-IN DEBUG - stored role did not match any known "
            "alias -- check the 'role' column in profiles for this "
            "user."
        )  # TEMP
        return False, "Invalid sign-in details."

    if stored_role != expected_role:
        return False, "Invalid sign-in details."

    session["user"] = {
        "id": user.id,
        "email": email,
        "name": profile.data["full_name"],
        "role": stored_role,
        # Supabase's access/refresh tokens, kept so we can act as
        # this user for RLS-protected queries later in the request
        # lifecycle if needed.
        "access_token": auth_response.session.access_token,
        "refresh_token": auth_response.session.refresh_token,
    }

    return True, None


# =========================================================
# ROLE DESTINATIONS
# =========================================================

def destination(role):

    return {
        "parent": "dashboard",
        "teacher": "teacher_dashboard",
        "admin": "admin_dashboard",
    }[role]


# =========================================================
# GLOBAL SCHOOL CONTEXT
# =========================================================

@app.context_processor
def school_context():

    return {
        "school": SCHOOL,
        "current_year": datetime.now().year,
    }


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# GENERAL SIGN IN  (login page: templates/login.html)
# =========================================================

@app.route(
    "/signin",
    methods=["GET", "POST"]
)
@app.route(
    "/login",
    methods=["GET", "POST"]
)
@app.route(
    "/login.html",
    methods=["GET", "POST"]
)
def signin():

    if request.method == "POST":

        role = resolve_role(
            request.form.get("role")
        )

        identifier = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get(
            "password", ""
        )

        if role:

            success, error = sign_in_user(
                identifier, password, role
            )

            if success:

                return redirect(
                    url_for(destination(role))
                )

        else:
            print(
                "SIGN-IN DEBUG - unrecognized role from form:",
                repr(request.form.get("role"))
            )  # TEMP

        flash(
            "Invalid sign-in details.",
            "error"
        )

    return render_template(
        "login.html"
    )


# =========================================================
# FORGOT PASSWORD
# =========================================================

@app.route(
    "/forgot-password",
    methods=["GET", "POST"]
)
def forgot_password():

    if request.method == "POST":

        identifier = request.form.get(
            "email", ""
        ).strip().lower()

        if identifier:

            try:
                supabase.auth.reset_password_for_email(
                    identifier,
                    {
                        "redirect_to": url_for(
                            "signin", _external=True
                        )
                    },
                )
            except Exception:
                # Don't reveal whether the email exists.
                pass

        flash(
            "If that email is registered, a reset link has "
            "been sent.",
            "success"
        )

        return redirect(url_for("signin"))

    return render_template(
        "forgot_password.html"
    )


# =========================================================
# GENERAL REGISTER / SIGN UP
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        role = resolve_role(
            request.form.get("role")
        )

        if role is None:
            print(
                "REGISTER DEBUG - unrecognized role from form:",
                repr(request.form.get("role"))
            )  # TEMP
            role = "parent"

        identifier = request.form.get(
            "email", ""
        ).strip().lower()

        full_name = request.form.get(
            "full_name", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        confirm_password = request.form.get(
            "confirm_password", ""
        )

        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "error"
            )

            return render_template("signin.html")

        success, error = sign_up_user(
            identifier, password, full_name, role
        )

        if success:

            flash(
                "Account created. Check your email to confirm, "
                "then sign in.",
                "success"
            )

            return redirect(url_for("signin"))

        flash(
            error or "Could not create account.",
            "error"
        )

    return render_template(
        "signin.html"
    )


# =========================================================
# PARENT DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if session.get("user", {}).get("role") != "parent":

        return redirect(url_for("signin"))

    return render_template(
        "results.html",
        user=session["user"]
    )


# =========================================================
# TEACHER DASHBOARD
# =========================================================

@app.route("/teacher/dashboard")
def teacher_dashboard():

    if session.get("user", {}).get("role") != "teacher":

        return redirect(url_for("signin"))

    teacher_id = session["user"]["id"]

    # ---- Profile (gender, avatar) ----
    # Base name/email already in session; pull the extra fields
    # that only live in the database.
    profile_row = (
        supabase
        .table("profiles")
        .select("gender, avatar_url")
        .eq("id", teacher_id)
        .single()
        .execute()
    )
    profile_extra = profile_row.data or {}

    # ---- Assigned classes / subjects (for counts + "My Classes") ----
    assignments = (
        supabase
        .table("teacher_assignments")
        .select("class_id, subject_id, room, classes(name), subjects(name)")
        .eq("teacher_id", teacher_id)
        .execute()
    )
    assignment_rows = assignments.data or []

    class_ids = {row["class_id"] for row in assignment_rows}
    subject_ids = {row["subject_id"] for row in assignment_rows}

    # ---- Learner count across assigned classes ----
    learner_count = 0
    if class_ids:
        learners = (
            supabase
            .table("learners")
            .select("id", count="exact")
            .in_("class_id", list(class_ids))
            .execute()
        )
        learner_count = learners.count or 0

    # ---- Recent assessments (drafts + submitted) ----
    recent_results = (
        supabase
        .table("assessments")
        .select(
            "id, status, rubric, learners(full_name), subjects(name)"
        )
        .eq("teacher_id", teacher_id)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
    )

    # ---- Pending (draft) count ----
    pending = (
        supabase
        .table("assessments")
        .select("id", count="exact")
        .eq("teacher_id", teacher_id)
        .eq("status", "draft")
        .execute()
    )
    pending_count = pending.count or 0

    # ---- Today's timetable ----
    today_index = datetime.now().weekday()  # 0=Mon .. 6=Sun

    timetable = (
        supabase
        .table("timetable_slots")
        .select("start_time, room, classes(name), subjects(name)")
        .eq("teacher_id", teacher_id)
        .eq("day_of_week", today_index)
        .order("start_time")
        .execute()
    )

    return render_template(
        "teacher_dashboard.html",
        user=session["user"],
        teacher_name=session["user"]["name"],
        teacher_email=session["user"]["email"],
        teacher_gender=profile_extra.get("gender"),
        teacher_image=profile_extra.get("avatar_url"),
        active_page="dashboard",
        class_count=len(class_ids),
        subject_count=len(subject_ids),
        learner_count=learner_count,
        pending_count=pending_count,
        recent_results=recent_results.data or [],
        timetable=timetable.data or [],
    )


# =========================================================
# TEACHER - ENTER RESULTS
# =========================================================

@app.route(
    "/teacher/results",
    methods=["GET", "POST"]
)
def teacher_results():

    if session.get("user", {}).get("role") != "teacher":

        return redirect(url_for("signin"))

    teacher_id = session["user"]["id"]

    # ---- Profile (for sidebar) ----
    profile_row = (
        supabase
        .table("profiles")
        .select("gender, avatar_url")
        .eq("id", teacher_id)
        .single()
        .execute()
    )
    profile_extra = profile_row.data or {}

    # ---- This teacher's class/subject assignments (filter dropdowns) ----
    assignments = (
        supabase
        .table("teacher_assignments")
        .select("class_id, subject_id, classes(name), subjects(name)")
        .eq("teacher_id", teacher_id)
        .execute()
    )
    assignment_rows = assignments.data or []

    # De-duplicated dropdown options
    classes_seen = {}
    subjects_seen = {}
    for row in assignment_rows:
        if row["classes"]:
            classes_seen[row["class_id"]] = row["classes"]["name"]
        if row["subjects"]:
            subjects_seen[row["subject_id"]] = row["subjects"]["name"]

    class_options = [
        {"id": cid, "name": name} for cid, name in classes_seen.items()
    ]
    subject_options = [
        {"id": sid, "name": name} for sid, name in subjects_seen.items()
    ]

    # ---- Handle saving a result ----
    if request.method == "POST":

        learner_id = request.form.get("learner_id")
        subject_id = request.form.get("subject_id")
        rubric = request.form.get("rubric", "").strip()
        remarks = request.form.get("remarks", "").strip()
        status = request.form.get("status", "draft")

        if status not in ("draft", "submitted"):
            status = "draft"

        if learner_id and subject_id and rubric:

            supabase.table("assessments").insert({
                "learner_id": learner_id,
                "subject_id": subject_id,
                "teacher_id": teacher_id,
                "status": status,
                "rubric": rubric,
                "remarks": remarks,
            }).execute()

            flash(
                f"Result saved as {status}.",
                "success"
            )

        else:

            flash(
                "Please select a rubric before saving.",
                "error"
            )

        # Redirect back preserving the selected class/subject filter
        return redirect(
            url_for(
                "teacher_results",
                class_id=request.form.get("class_id", ""),
                subject_id=subject_id or "",
            )
        )

    # ---- GET: show learners for the selected class ----
    selected_class_id = request.args.get("class_id", "")
    selected_subject_id = request.args.get("subject_id", "")

    learners = []

    if selected_class_id:

        learner_rows = (
            supabase
            .table("learners")
            .select("id, full_name, admission_number")
            .eq("class_id", selected_class_id)
            .order("full_name")
            .execute()
        )
        learners = learner_rows.data or []

        # Pull each learner's most recent assessment for this
        # subject, so the form can show current status/rubric.
        if selected_subject_id and learners:

            learner_ids = [row["id"] for row in learners]

            existing = (
                supabase
                .table("assessments")
                .select("learner_id, status, rubric, remarks, created_at")
                .in_("learner_id", learner_ids)
                .eq("subject_id", selected_subject_id)
                .eq("teacher_id", teacher_id)
                .order("created_at", desc=True)
                .execute()
            )

            # Keep only the most recent row per learner
            latest_by_learner = {}
            for row in (existing.data or []):
                if row["learner_id"] not in latest_by_learner:
                    latest_by_learner[row["learner_id"]] = row

            for learner in learners:
                learner["existing"] = latest_by_learner.get(learner["id"])

    return render_template(
        "teacher_results.html",
        user=session["user"],
        teacher_name=session["user"]["name"],
        teacher_email=session["user"]["email"],
        teacher_gender=profile_extra.get("gender"),
        teacher_image=profile_extra.get("avatar_url"),
        active_page="results",
        class_options=class_options,
        subject_options=subject_options,
        selected_class_id=selected_class_id,
        selected_subject_id=selected_subject_id,
        learners=learners,
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin/dashboard")
def admin_dashboard():

    if session.get("user", {}).get("role") != "admin":

        return redirect(url_for("signin"))

    return render_template(
        "admin_dashboard.html",
        user=session["user"],
        teacher_count=0,
        admin_count=0,
        student_count=0,
        pending_records=[],
        announcements=[],
        message=None,
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    session.clear()

    return redirect(url_for("home"))


# =========================================================
# DEVELOPMENT SERVER
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )