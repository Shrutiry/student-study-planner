from flask import (
    Flask, render_template, request, redirect,
    session, url_for
)
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import date
from functools import wraps

app = Flask(__name__)
app.secret_key = "change-this-to-a-long-random-secret"
def login_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_function(*args, **kwargs)
    return wrapped_view
DATABASE = "database.db"


# =========================================================
# DATABASE
# =========================================================

def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():

    connection = get_db()
    cursor = connection.cursor()

    # ---------------- TASKS ----------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            study_date TEXT NOT NULL,
            study_time TEXT,
            priority TEXT DEFAULT 'Medium',
            status TEXT DEFAULT 'Pending'
        )
    """)
     # ---------------- USERS ----------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)

    # ---------------- NOTES ----------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            content TEXT NOT NULL,
            important INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ---------------- GOALS ----------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            target_date TEXT NOT NULL,
            progress INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Active'
        )
    """)

    # ---------------- REMINDERS ----------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            reminder_date TEXT NOT NULL,
            reminder_time TEXT NOT NULL,
            status TEXT DEFAULT 'Pending'
        )
    """)

    # ---------------- STUDY SESSIONS ----------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            duration INTEGER NOT NULL,
            session_date TEXT NOT NULL
        )
    """)

    # ---------------- TIMETABLE ----------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_type TEXT NOT NULL,
            day TEXT NOT NULL,
            title TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            location TEXT DEFAULT '',
            teacher TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        )
    """)

    # ---------------- USER DATA OWNERSHIP ----------------
    # Add user_id to existing tables without deleting records.
    # Assign existing records to Shruti's account (ID 2).

    tables = [
        "tasks",
        "notes",
        "goals",
        "reminders",
        "study_sessions",
        "timetable"
    ]

    # Confirm the account exists before migrating records.
    owner = cursor.execute(
        "SELECT id FROM users WHERE id = ?", (2,)
    ).fetchone()

    if owner is None:
        connection.close()
        raise RuntimeError(
            "Account ID 2 was not found. Database migration stopped."
        )

    for table in tables:
        columns = [
            row["name"]
            for row in cursor.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        ]

        if "user_id" not in columns:
            cursor.execute(
                f"ALTER TABLE {table} ADD COLUMN user_id INTEGER"
            )

        # Existing records have no owner yet, so assign them to Shruti.
        cursor.execute(
            f"UPDATE {table} SET user_id = ? WHERE user_id IS NULL",
            (2,)
        )

    connection.commit()
    connection.close()


# =========================================================
# LOGIN AND REGISTRATION
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or len(password) < 8:
            return render_template(
                "register.html",
                error="Enter your name, email, and a password of at least 8 characters."
            )

        connection = get_db()

        try:
            connection.execute("""
                INSERT INTO users (name, email, password_hash)
                VALUES (?, ?, ?)
            """, (
                name,
                email,
                generate_password_hash(password)
            ))
            connection.commit()

            user = connection.execute(
                "SELECT id, name FROM users WHERE email = ?",
                (email,)
            ).fetchone()

            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return redirect(url_for("home"))

        except sqlite3.IntegrityError:
            return render_template(
                "register.html",
                error="This email is already registered. Please log in."
            )
        finally:
            connection.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        connection = get_db()
        try:
            user = connection.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,)
            ).fetchone()
        finally:
            connection.close()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("home"))

        return render_template(
            "login.html",
            error="Incorrect email or password."
        )

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))

# =========================================================
# DASHBOARD
# =========================================================

@app.route("/")
@login_required
def home():

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM tasks")
    total_tasks = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM tasks
        WHERE status = 'Completed'
    """)
    completed_tasks = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM notes")
    total_notes = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM goals
        WHERE status = 'Active'
    """)
    active_goals = cursor.fetchone()[0]

    cursor.execute("""
        SELECT *
        FROM tasks
        ORDER BY study_date, study_time
        LIMIT 5
    """)
    recent_tasks = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM goals
        ORDER BY target_date
        LIMIT 5
    """)
    goals = cursor.fetchall()

    connection.close()

    return render_template(
        "index.html",
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        total_notes=total_notes,
        active_goals=active_goals,
        recent_tasks=recent_tasks,
        goals=goals
    )


# =========================================================
# STUDY PLANNER
# =========================================================
@app.route("/planner")
@login_required
def planner():

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM tasks
        WHERE user_id = ?
        ORDER BY study_date, study_time
    """, (session["user_id"],))

    tasks = cursor.fetchall()

    connection.close()

    return render_template(
        "planner.html",
        tasks=tasks
    )



# =========================================================
# ADD TASK
# =========================================================

@app.route("/add-task", methods=["POST"])
def add_task():

    subject = request.form["subject"]
    topic = request.form["topic"]
    study_date = request.form["study_date"]
    study_time = request.form["study_time"]
    priority = request.form["priority"]

    connection = get_db()

    connection.execute("""
        INSERT INTO tasks
        (subject, topic, study_date, study_time, priority)
        VALUES (?, ?, ?, ?, ?)
    """, (
        subject,
        topic,
        study_date,
        study_time,
        priority
    ))

    connection.commit()
    connection.close()

    return redirect("/planner")

# =========================================================
# TIMETABLE
# =========================================================

@app.route("/timetable")
@login_required
def timetable():

    connection = get_db()

    entries = connection.execute("""
        SELECT *
        FROM timetable
        ORDER BY day, start_time
    """).fetchall()

    connection.close()

    days = [
        "Monday", "Tuesday", "Wednesday",
        "Thursday", "Friday", "Saturday", "Sunday"
    ]

    return render_template(
        "timetable.html",
        entries=entries,
        days=days
    )


# =========================================================
# ADD TIMETABLE ENTRY
# =========================================================

@app.route("/timetable/add", methods=["POST"])
def add_timetable_entry():

    entry_type = request.form["entry_type"]
    day = request.form["day"]
    title = request.form["title"]
    start_time = request.form["start_time"]
    end_time = request.form["end_time"]

    location = request.form.get("location", "")
    teacher = request.form.get("teacher", "")
    notes = request.form.get("notes", "")

    if start_time >= end_time:
        return redirect("/timetable")

    connection = get_db()

    connection.execute("""
        INSERT INTO timetable
        (entry_type, day, title, start_time, end_time,
         location, teacher, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        entry_type, day, title, start_time, end_time,
        location, teacher, notes
    ))

    connection.commit()
    connection.close()

    return redirect("/timetable")


# =========================================================
# DELETE TIMETABLE ENTRY
# =========================================================

@app.route("/timetable/delete/<int:entry_id>", methods=["POST"])
def delete_timetable_entry(entry_id):

    connection = get_db()

    connection.execute("""
        DELETE FROM timetable
        WHERE id = ?
    """, (entry_id,))

    connection.commit()
    connection.close()

    return redirect("/timetable")


  
# COMPLETE TASK
# =========================================================

@app.route("/complete-task/<int:task_id>", methods=["POST"])
@login_required
def complete_task(task_id):

    connection = get_db()

    connection.execute("""
        UPDATE tasks
        SET status = 'Completed'
        WHERE id = ? AND user_id = ?
    """, (task_id, session["user_id"]))

    connection.commit()
    connection.close()

    return redirect(url_for("planner"))


# =========================================================
# DELETE TASK
# =========================================================

@app.route("/delete-task/<int:task_id>", methods=["POST"])
@login_required
def delete_task(task_id):

    connection = get_db()

    connection.execute("""
        DELETE FROM tasks
        WHERE id = ? AND user_id = ?
    """, (task_id, session["user_id"]))

    connection.commit()
    connection.close()

    return redirect(url_for("planner"))


# =========================================================
# EDIT TASK
# =========================================================

@app.route("/edit-task/<int:task_id>")
@login_required
def edit_task(task_id):

    connection = get_db()

    task = connection.execute("""
        SELECT *
        FROM tasks
        WHERE id = ? AND user_id = ?
    """, (task_id, session["user_id"])).fetchone()

    connection.close()

    if task is None:
        return "Task not found or access denied.", 404

    return render_template(
        "edit_task.html",
        task=task
    )


# =========================================================
# UPDATE TASK
# =========================================================

@app.route("/update-task/<int:task_id>", methods=["POST"])
@login_required
def update_task(task_id):

    subject = request.form["subject"]
    topic = request.form["topic"]
    study_date = request.form["study_date"]
    study_time = request.form["study_time"]
    priority = request.form["priority"]

    connection = get_db()

    connection.execute("""
        UPDATE tasks
        SET subject = ?,
            topic = ?,
            study_date = ?,
            study_time = ?,
            priority = ?
        WHERE id = ? AND user_id = ?
    """, (
        subject,
        topic,
        study_date,
        study_time,
        priority,
        task_id,
        session["user_id"]
    ))

    connection.commit()
    connection.close()

    return redirect(url_for("planner"))



# =========================================================
# NOTES
# =========================================================

@app.route("/notes")
@login_required
def notes():

    search = request.args.get("search", "")
    important = request.args.get("important", "")

    connection = get_db()

    query = """
        SELECT *
        FROM notes
        WHERE 1=1
    """

    parameters = []

    if search:

        query += """
            AND (
                title LIKE ?
                OR subject LIKE ?
                OR content LIKE ?
            )
        """

        parameters.extend([
            "%" + search + "%",
            "%" + search + "%",
            "%" + search + "%"
        ])

    if important == "1":

        query += """
            AND important = 1
        """

    query += """
        ORDER BY created_at DESC
    """

    notes = connection.execute(
        query,
        parameters
    ).fetchall()

    connection.close()

    return render_template(
        "notes.html",
        notes=notes,
        search=search,
        important=important
    )


# =========================================================
# ADD NOTE
# =========================================================

@app.route("/add-note", methods=["POST"])
def add_note():

    title = request.form["title"]
    subject = request.form["subject"]
    content = request.form["content"]

    important = 1 if request.form.get("important") else 0

    connection = get_db()

    connection.execute("""
        INSERT INTO notes
        (title, subject, content, important)
        VALUES (?, ?, ?, ?)
    """, (
        title,
        subject,
        content,
        important
    ))

    connection.commit()
    connection.close()

    return redirect("/notes")


# =========================================================
# EDIT NOTE
# =========================================================

@app.route("/edit-note/<int:note_id>")
def edit_note(note_id):

    connection = get_db()

    note = connection.execute("""
        SELECT *
        FROM notes
        WHERE id = ?
    """, (note_id,)).fetchone()

    connection.close()

    return render_template(
        "edit_note.html",
        note=note
    )


# =========================================================
# UPDATE NOTE
# =========================================================

@app.route("/update-note/<int:note_id>", methods=["POST"])
def update_note(note_id):

    title = request.form["title"]
    subject = request.form["subject"]
    content = request.form["content"]

    important = 1 if request.form.get("important") else 0

    connection = get_db()

    connection.execute("""
        UPDATE notes
        SET title = ?,
            subject = ?,
            content = ?,
            important = ?
        WHERE id = ?
    """, (
        title,
        subject,
        content,
        important,
        note_id
    ))

    connection.commit()
    connection.close()

    return redirect("/notes")


# =========================================================
# DELETE NOTE
# =========================================================

@app.route("/delete-note/<int:note_id>")
def delete_note(note_id):

    connection = get_db()

    connection.execute("""
        DELETE FROM notes
        WHERE id = ?
    """, (note_id,))

    connection.commit()
    connection.close()

    return redirect("/notes")

# =========================================================
# NOTES
# =========================================================

@app.route("/notes")
@login_required
def notes():

    search = request.args.get("search", "")
    important = request.args.get("important", "")

    connection = get_db()

    query = """
        SELECT *
        FROM notes
        WHERE 1=1
    """

    parameters = []

    if search:

        query += """
            AND (
                title LIKE ?
                OR subject LIKE ?
                OR content LIKE ?
            )
        """

        parameters.extend([
            "%" + search + "%",
            "%" + search + "%",
            "%" + search + "%"
        ])

    if important == "1":

        query += """
            AND important = 1
        """

    query += """
        ORDER BY created_at DESC
    """

    notes = connection.execute(
        query,
        parameters
    ).fetchall()

    connection.close()

    return render_template(
        "notes.html",
        notes=notes,
        search=search,
        important=important
    )


# =========================================================
# ADD NOTE
# =========================================================

@app.route("/add-note", methods=["POST"])
def add_note():

    title = request.form["title"]
    subject = request.form["subject"]
    content = request.form["content"]

    important = 1 if request.form.get("important") else 0

    connection = get_db()

    connection.execute("""
        INSERT INTO notes
        (title, subject, content, important)
        VALUES (?, ?, ?, ?)
    """, (
        title,
        subject,
        content,
        important
    ))

    connection.commit()
    connection.close()

    return redirect("/notes")


# =========================================================
# EDIT NOTE
# =========================================================

@app.route("/edit-note/<int:note_id>")
def edit_note(note_id):

    connection = get_db()

    note = connection.execute("""
        SELECT *
        FROM notes
        WHERE id = ?
    """, (note_id,)).fetchone()

    connection.close()

    return render_template(
        "edit_note.html",
        note=note
    )


# =========================================================
# UPDATE NOTE
# =========================================================

@app.route("/update-note/<int:note_id>", methods=["POST"])
def update_note(note_id):

    title = request.form["title"]
    subject = request.form["subject"]
    content = request.form["content"]

    important = 1 if request.form.get("important") else 0

    connection = get_db()

    connection.execute("""
        UPDATE notes
        SET title = ?,
            subject = ?,
            content = ?,
            important = ?
        WHERE id = ?
    """, (
        title,
        subject,
        content,
        important,
        note_id
    ))

    connection.commit()
    connection.close()

    return redirect("/notes")


# =========================================================
# DELETE NOTE
# =========================================================

@app.route("/delete-note/<int:note_id>")
def delete_note(note_id):

    connection = get_db()

    connection.execute("""
        DELETE FROM notes
        WHERE id = ?
    """, (note_id,))

    connection.commit()
    connection.close()

    return redirect("/notes")


# =========================================================
# NOTES QUIZ
# =========================================================

@app.route("/notes-quiz")
@login_required
def notes_quiz():

    questions = [
        {
            "question": "What does CPU stand for?",
            "options": [
                "Central Processing Unit",
                "Computer Personal Unit",
                "Central Program Utility",
                "Control Processing User"
            ],
            "answer": 0
        },
        {
            "question": "Which language is commonly used with Flask?",
            "options": ["Java", "Python", "C++", "PHP"],
            "answer": 1
        },
        {
            "question": "Which of these is a database?",
            "options": ["HTML", "CSS", "SQLite", "Font Awesome"],
            "answer": 2
        },
        {
            "question": "What does HTML stand for?",
            "options": [
                "HyperText Markup Language",
                "HighText Machine Language",
                "HyperTool Multi Language",
                "Home Tool Markup Language"
            ],
            "answer": 0
        },
        {
            "question": "Which symbol starts a Python comment?",
            "options": ["//", "#", "/*", "<!--"],
            "answer": 1
        }
    ]

    return render_template(
        "notes_quiz.html",
        questions=questions
    )


# =========================================================
# GOALS
# =========================================================

@app.route("/goals")
@login_required
def goals():

    connection = get_db()

    goals = connection.execute("""
        SELECT *
        FROM goals
        ORDER BY target_date
    """).fetchall()

    connection.close()

    return render_template(
        "goals.html",
        goals=goals
    )


# =========================================================
# ADD GOAL
# =========================================================

@app.route("/add-goal", methods=["POST"])
def add_goal():

    title = request.form["title"]
    target_date = request.form["target_date"]

    connection = get_db()

    connection.execute("""
        INSERT INTO goals
        (title, target_date)
        VALUES (?, ?)
    """, (
        title,
        target_date
    ))

    connection.commit()
    connection.close()

    return redirect("/goals")


# =========================================================
# UPDATE GOAL PROGRESS
# =========================================================

@app.route("/update-goal/<int:goal_id>", methods=["POST"])
def update_goal(goal_id):

    progress = int(request.form["progress"])

    if progress < 0:
        progress = 0

    if progress > 100:
        progress = 100

    status = "Completed" if progress == 100 else "Active"

    connection = get_db()

    connection.execute("""
        UPDATE goals
        SET progress = ?,
            status = ?
        WHERE id = ?
    """, (
        progress,
        status,
        goal_id
    ))

    connection.commit()
    connection.close()

    return redirect("/goals")


# =========================================================
# DELETE GOAL
# =========================================================

@app.route("/delete-goal/<int:goal_id>")
def delete_goal(goal_id):

    connection = get_db()

    connection.execute("""
        DELETE FROM goals
        WHERE id = ?
    """, (goal_id,))

    connection.commit()
    connection.close()

    return redirect("/goals")


# =========================================================
# REMINDERS
# =========================================================

@app.route("/reminders")
@login_required
def reminders():

    connection = get_db()

    reminders = connection.execute("""
        SELECT *
        FROM reminders
        ORDER BY reminder_date, reminder_time
    """).fetchall()

    connection.close()

    return render_template(
        "reminders.html",
        reminders=reminders
    )


# =========================================================
# ADD REMINDER
# =========================================================

@app.route("/add-reminder", methods=["POST"])
def add_reminder():

    title = request.form["title"]
    reminder_date = request.form["reminder_date"]
    reminder_time = request.form["reminder_time"]

    connection = get_db()

    connection.execute("""
        INSERT INTO reminders
        (title, reminder_date, reminder_time)
        VALUES (?, ?, ?)
    """, (
        title,
        reminder_date,
        reminder_time
    ))

    connection.commit()
    connection.close()

    return redirect("/reminders")


# =========================================================
# COMPLETE REMINDER
# =========================================================

@app.route("/complete-reminder/<int:reminder_id>")
def complete_reminder(reminder_id):

    connection = get_db()

    connection.execute("""
        UPDATE reminders
        SET status = 'Completed'
        WHERE id = ?
    """, (reminder_id,))

    connection.commit()
    connection.close()

    return redirect("/reminders")


# =========================================================
# DELETE REMINDER
# =========================================================

@app.route("/delete-reminder/<int:reminder_id>")
def delete_reminder(reminder_id):

    connection = get_db()

    connection.execute("""
        DELETE FROM reminders
        WHERE id = ?
    """, (reminder_id,))

    connection.commit()
    connection.close()

    return redirect("/reminders")


# =========================================================
# STUDY TIMER
# =========================================================

@app.route("/timer")
@login_required
def timer():

    return render_template("timer.html")


# =========================================================
# SAVE STUDY SESSION
# =========================================================

@app.route("/save-session", methods=["POST"])
def save_session():

    subject = request.form["subject"]
    duration = int(request.form["duration"])

    today = date.today().isoformat()

    connection = get_db()

    connection.execute("""
        INSERT INTO study_sessions
        (subject, duration, session_date)
        VALUES (?, ?, ?)
    """, (
        subject,
        duration,
        today
    ))

    connection.commit()
    connection.close()

    return redirect("/timer")


# =========================================================
# ANALYTICS
# =========================================================

@app.route("/analytics")
@login_required
def analytics():

    connection = get_db()

    total_tasks = connection.execute("""
        SELECT COUNT(*)
        FROM tasks
    """).fetchone()[0]

    completed_tasks = connection.execute("""
        SELECT COUNT(*)
        FROM tasks
        WHERE status = 'Completed'
    """).fetchone()[0]

    total_notes = connection.execute("""
        SELECT COUNT(*)
        FROM notes
    """).fetchone()[0]

    total_goals = connection.execute("""
        SELECT COUNT(*)
        FROM goals
    """).fetchone()[0]

    completed_goals = connection.execute("""
        SELECT COUNT(*)
        FROM goals
        WHERE status = 'Completed'
    """).fetchone()[0]

    total_study_minutes = connection.execute("""
        SELECT COALESCE(SUM(duration), 0)
        FROM study_sessions
    """).fetchone()[0]

    connection.close()

    return render_template(
        "analytics.html",
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        total_notes=total_notes,
        total_goals=total_goals,
        completed_goals=completed_goals,
        total_study_minutes=total_study_minutes
    )


# =========================================================
# ACHIEVEMENTS
# =========================================================

@app.route("/achievements")
@login_required
def achievements():

    connection = get_db()

    completed_tasks = connection.execute("""
        SELECT COUNT(*)
        FROM tasks
        WHERE status = 'Completed'
    """).fetchone()[0]

    total_notes = connection.execute("""
        SELECT COUNT(*)
        FROM notes
    """).fetchone()[0]

    completed_goals = connection.execute("""
        SELECT COUNT(*)
        FROM goals
        WHERE status = 'Completed'
    """).fetchone()[0]

    total_sessions = connection.execute("""
        SELECT COUNT(*)
        FROM study_sessions
    """).fetchone()[0]

    connection.close()

    achievements_list = [
        {
            "title": "First Step",
            "description": "Complete your first study task.",
            "unlocked": completed_tasks >= 1
        },
        {
            "title": "Task Master",
            "description": "Complete 5 study tasks.",
            "unlocked": completed_tasks >= 5
        },
        {
            "title": "Note Taker",
            "description": "Create your first study note.",
            "unlocked": total_notes >= 1
        },
        {
            "title": "Goal Achiever",
            "description": "Complete your first goal.",
            "unlocked": completed_goals >= 1
        },
        {
            "title": "Study Starter",
            "description": "Complete your first study timer session.",
            "unlocked": total_sessions >= 1
        }
    ]

    return render_template(
        "achievements.html",
        achievements=achievements_list
    )


# =========================================================
# RUN
# =========================================================

# Initialize database when the application starts
init_db()

if __name__ == "__main__":
    app.run(debug=True)
