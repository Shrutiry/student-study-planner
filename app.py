import random
import re
from flask import (
    Flask, render_template, request, redirect,
    session, url_for, session , flash
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
            user_id INTEGER NOT NULL,
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
            user_id INTEGER NOT NULL,
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
            user_id INTEGER NOT NULL,
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
            user_id INTEGER NOT NULL,
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
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            duration INTEGER NOT NULL,
            session_date TEXT NOT NULL
        )
    """)

    # ---------------- TIMETABLE ----------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
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

    tables = [
        "tasks",
        "notes",
        "goals",
        "reminders",
        "study_sessions",
        "timetable"
    ]
    owner = cursor.execute(
        "SELECT id FROM users ORDER BY id ASC LIMIT 1"
    ).fetchone()
    
    fallback_user_id = owner["id"] if owner else 1

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

        cursor.execute(
            f"UPDATE {table} SET user_id = ? WHERE user_id IS NULL",
            (fallback_user_id,)
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


@app.route("/logout", methods=["GET","POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/")
@login_required
def home():
    user_id = session["user_id"]
    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ?", (user_id,))
    total_tasks = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM tasks
        WHERE user_id = ? AND status = 'Completed'
    """, (user_id,))
    completed_tasks = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM notes WHERE user_id = ?", (user_id,))
    total_notes = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM goals
        WHERE user_id = ? AND status = 'Active'
    """, (user_id,))
    active_goals = cursor.fetchone()[0]

    cursor.execute("""
        SELECT *
        FROM tasks
        WHERE user_id = ?
        ORDER BY study_date, study_time
        LIMIT 5
    """, (user_id,))
    recent_tasks = cursor.fetchall()

    cursor.execute("""
        SELECT *
        FROM goals
        WHERE user_id = ?
        ORDER BY target_date
        LIMIT 5
    """, (user_id,))
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
    user_id = session["user_id"]
    today_str = date.today().isoformat()
    
    connection = get_db()
    cursor = connection.cursor()

    # 1. Get all tasks for the user
    cursor.execute("""
        SELECT *
        FROM tasks
        WHERE user_id = ?
        ORDER BY study_date, study_time
    """, (user_id,))
    tasks = cursor.fetchall()
    
    # 2. Get tasks scheduled specifically for TODAY (acting as reminders)
    cursor.execute("""
        SELECT *
        FROM tasks
        WHERE user_id = ? AND study_date = ?
        ORDER BY study_time
    """, (user_id, today_str))
    
    today_tasks = cursor.fetchall()  # 👈 Added missing parentheses ()

    connection.close()  # 👈 Always close connection

    # 3. Render the template and send both lists of tasks
    return render_template("planner.html", tasks=tasks, today_tasks=today_tasks)
    
# =========================================================
# ADD TASK
# =========================================================

@app.route("/add-task", methods=["POST"])
@login_required
def add_task():
    user_id = session["user_id"]
    subject = request.form["subject"]
    topic = request.form["topic"]
    study_date = request.form["study_date"]
    study_time = request.form["study_time"]
    priority = request.form["priority"]   

    # Check if the date is in the past
    today_str = date.today().isoformat()
    if study_date < today_str:
        connection = get_db()
        tasks = connection.execute("""
            SELECT * FROM tasks WHERE user_id = ? ORDER BY study_date, study_time
        """, (user_id,)).fetchall()
        connection.close()
        
        return render_template(
            "planner.html",
            tasks=tasks,
            error="❌ You cannot schedule a study task for a past date!"
        )

    
    connection = get_db()
    connection.execute("""
        INSERT INTO tasks
        (user_id, subject, topic, study_date, study_time, priority)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_id,
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
    user_id = session["user_id"]
    connection = get_db()

    entries = connection.execute("""
        SELECT *
        FROM timetable
        WHERE user_id = ?
        ORDER BY day, start_time
    """, (user_id,)).fetchall()

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
@login_required
def add_timetable_entry():
    user_id = session["user_id"]
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
        (user_id, entry_type, day, title, start_time, end_time,
         location, teacher, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, entry_type, day, title, start_time, end_time,
        location, teacher, notes
    ))

    connection.commit()
    connection.close()

    return redirect("/timetable")


# =========================================================
# DELETE TIMETABLE ENTRY
# =========================================================

@app.route("/timetable/delete/<int:entry_id>", methods=["POST"])
@login_required
def delete_timetable_entry(entry_id):
    user_id = session["user_id"]
    connection = get_db()

    connection.execute("""
        DELETE FROM timetable
        WHERE id = ? AND user_id = ?
    """, (entry_id, user_id))

    connection.commit()
    connection.close()

    return redirect("/timetable")


# =========================================================
# COMPLETE TASK
# =========================================================

@app.route("/complete-task/<int:task_id>")
@login_required
def complete_task(task_id):
    user_id = session["user_id"]
    connection = get_db()

    connection.execute("""
        UPDATE tasks
        SET status = 'Completed'
        WHERE id = ? AND user_id = ?
    """, (task_id, user_id))

    connection.commit()
    connection.close()

    return redirect("/planner")


# =========================================================
# DELETE TASK
# =========================================================

@app.route("/delete-task/<int:task_id>")
@login_required
def delete_task(task_id):
    user_id = session["user_id"]
    connection = get_db()

    connection.execute("""
        DELETE FROM tasks
        WHERE id = ? AND user_id = ?
    """, (task_id, user_id))

    connection.commit()
    connection.close()

    return redirect("/planner")


# =========================================================
# EDIT TASK
# =========================================================

@app.route("/edit-task/<int:task_id>")
@login_required
def edit_task(task_id):
    user_id = session["user_id"]
    connection = get_db()

    task = connection.execute("""
        SELECT *
        FROM tasks
        WHERE id = ? AND user_id = ?
    """, (task_id, user_id)).fetchone()

    connection.close()

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
    user_id = session["user_id"]
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
        user_id
    ))

    connection.commit()
    connection.close()

    return redirect("/planner")


# =========================================================
# NOTES
# =========================================================

@app.route("/notes")
@login_required
def notes():
    user_id = session["user_id"]
    search = request.args.get("search", "")
    important = request.args.get("important", "")

    connection = get_db()

    query = """
        SELECT *
        FROM notes
        WHERE user_id = ?
    """
    parameters = [user_id]

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
        query += " AND important = 1"

    query += " ORDER BY created_at DESC"

    notes = connection.execute(query, parameters).fetchall()
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
@login_required
def add_note():
    user_id = session["user_id"]
    title = request.form["title"]
    subject = request.form["subject"]
    content = request.form["content"]
    important = 1 if request.form.get("important") else 0

    connection = get_db()
    connection.execute("""
        INSERT INTO notes
        (user_id, title, subject, content, important)
        VALUES (?, ?, ?, ?, ?)
    """, (
        user_id,
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
@login_required
def edit_note(note_id):
    user_id = session["user_id"]
    connection = get_db()

    note = connection.execute("""
        SELECT *
        FROM notes
        WHERE id = ? AND user_id = ?
    """, (note_id, user_id)).fetchone()

    connection.close()

    return render_template(
        "edit_note.html",
        note=note
    )


# =========================================================
# UPDATE NOTE
# =========================================================

@app.route("/update-note/<int:note_id>", methods=["POST"])
@login_required
def update_note(note_id):
    user_id = session["user_id"]
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
        WHERE id = ? AND user_id = ?
    """, (
        title,
        subject,
        content,
        important,
        note_id,
        user_id
    ))

    connection.commit()
    connection.close()

    return redirect("/notes")


# =========================================================
# DELETE NOTE
# =========================================================

@app.route("/delete-note/<int:note_id>")
@login_required
def delete_note(note_id):
    user_id = session["user_id"]
    connection = get_db()

    connection.execute("""
        DELETE FROM notes
        WHERE id = ? AND user_id = ?
    """, (note_id, user_id))

    connection.commit()
    connection.close()

    return redirect("/notes")
 

# =========================================================
# NOTE QUIZ (NO AI OR API KEY)
# =========================================================

@app.route("/notes/<int:note_id>/quiz", methods=["GET", "POST"])
@login_required
def note_quiz(note_id):
    user_id = session.get("user_id")

    conn = get_db()
    note = conn.execute("""
        SELECT *
        FROM notes
        WHERE id = ? AND user_id = ?
    """, (note_id, user_id)).fetchone()
    conn.close()

    if not note:
        flash("Note not found.", "danger")
        return redirect(url_for("notes"))

    content = note["content"] or ""

    # Split note content into sentences
    sentences = [
        s.strip()
        for s in re.split(r'(?<=[.!?])\s+', content)
        if len(s.strip()) > 15
    ]

    questions = []

    # Create fill-in-the-blank questions
    for sentence in sentences:
        words = re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{3,}\b", sentence)

        if not words:
            continue

        answer = random.choice(words)

        question_text = re.sub(
            r"\b" + re.escape(answer) + r"\b",
            "______",
            sentence,
            count=1
        )

        # Create answer choices from words in the note
        other_words = [
            word for word in re.findall(
                r"\b[A-Za-z][A-Za-z0-9_-]{3,}\b",
                content
            )
            if word.lower() != answer.lower()
        ]

        choices = list(dict.fromkeys([answer] + other_words))

        if len(choices) < 4:
            continue

        random.shuffle(choices)
        choices = choices[:4]

        # Ensure the correct answer is included
        if answer not in choices:
            choices[-1] = answer

        random.shuffle(choices)

        questions.append({
            "question": question_text,
            "options": choices,
            "answer": answer
        })

        if len(questions) >= 5:
            break

    # Calculate score when answers are submitted
    score = None

    if request.method == "POST":
        score = 0

        for i, question in enumerate(questions):
            selected = request.form.get(f"question_{i}", "")

            if selected == question["answer"]:
                score += 1

    return render_template(
        "note_quiz.html",
        note=note,
        questions=questions,
        score=score
    )

# =========================================================
# quize achievements
# =========================================================
@app.route("/notes/quiz/complete", methods=["POST"])
@login_required
def complete_quiz():
    user_id = session.get("user_id")
    # Here you can mark an achievement as unlocked or increment user quiz stats
    conn = get_db()
    # Example: Check if an achievement for completing a quiz exists, or add a flash/log
    conn.close()
    return {"status": "success", "message": "Quiz completed and achievement recorded!"}



# ================= TASK QUIZ =================

@app.route("/generate-quiz")
@login_required
def generate_quiz():
    user_id = session["user_id"]
    task_id = request.args.get("task_id", type=int)

    if not task_id:
        flash("Task not found.", "danger")
        return redirect(url_for("planner"))

    connection = get_db()

    task = connection.execute("""
        SELECT *
        FROM tasks
        WHERE id = ? AND user_id = ?
    """, (task_id, user_id)).fetchone()

    connection.close()

    if task is None:
        flash("Task not found.", "danger")
        return redirect(url_for("planner"))

    return render_template("task_quiz.html", task=task)



# =========================================================
# GOALS
# =========================================================

@app.route("/goals")
@login_required
def goals():
    user_id = session["user_id"]
    connection = get_db()

    goals = connection.execute("""
        SELECT *
        FROM goals
        WHERE user_id = ?
        ORDER BY target_date
    """, (user_id,)).fetchall()

    connection.close()

    return render_template(
        "goals.html",
        goals=goals
    )


# =========================================================
# ADD GOAL
# =========================================================

@app.route("/add-goal", methods=["POST"])
@login_required
def add_goal():
    user_id = session["user_id"]
    title = request.form["title"]
    target_date = request.form["target_date"]

    # Check if target date is in the past
    today_str = date.today().isoformat()
    if target_date < today_str:
        connection = get_db()
        goals = connection.execute("""
            SELECT * FROM goals WHERE user_id = ? ORDER BY target_date
        """, (user_id,)).fetchall()
        connection.close()

        return render_template(
            "goals.html",
            goals=goals,
            error="❌ Goal target date cannot be in the past!"
        )


    connection = get_db()
    connection.execute("""
        INSERT INTO goals
        (user_id, title, target_date)
        VALUES (?, ?, ?)
    """, (
        user_id,
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
@login_required
def update_goal(goal_id):
    user_id = session["user_id"]
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
        WHERE id = ? AND user_id = ?
    """, (
        progress,
        status,
        goal_id,
        user_id
    ))

    connection.commit()
    connection.close()

    return redirect("/goals")


# =========================================================
# DELETE GOAL
# =========================================================

@app.route("/delete-goal/<int:goal_id>")
@login_required
def delete_goal(goal_id):
    user_id = session["user_id"]
    connection = get_db()

    connection.execute("""
        DELETE FROM goals
        WHERE id = ? AND user_id = ?
    """, (goal_id, user_id))

    connection.commit()
    connection.close()

    return redirect("/goals")


# =========================================================
# REMINDERS
# =========================================================

@app.route("/reminders")
@login_required
def reminders():
    user_id = session["user_id"]
    connection = get_db()

    reminders = connection.execute("""
        SELECT *
        FROM reminders
        WHERE user_id = ?
        ORDER BY reminder_date, reminder_time
    """, (user_id,)).fetchall()

    connection.close()

    return render_template(
        "reminders.html",
        reminders=reminders
    )


# =========================================================
# ADD REMINDER
# =========================================================

@app.route("/add-reminder", methods=["POST"])
@login_required
def add_reminder():
    user_id = session["user_id"]
    title = request.form["title"]
    reminder_date = request.form["reminder_date"]
    reminder_time = request.form["reminder_time"]

    # Check if reminder date is in the past
    today_str = date.today().isoformat()
    if reminder_date < today_str:
        connection = get_db()
        reminders = connection.execute("""
            SELECT * FROM reminders WHERE user_id = ? ORDER BY reminder_date, reminder_time
        """, (user_id,)).fetchall()
        connection.close()

        return render_template(
            "reminders.html",
            reminders=reminders,
            error="❌ Reminder date cannot be in the past!"
        )

    

    connection = get_db()
    connection.execute("""
        INSERT INTO reminders
        (user_id, title, reminder_date, reminder_time)
        VALUES (?, ?, ?, ?)
    """, (
        user_id,
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
@login_required
def complete_reminder(reminder_id):
    user_id = session["user_id"]
    connection = get_db()

    connection.execute("""
        UPDATE reminders
        SET status = 'Completed'
        WHERE id = ? AND user_id = ?
    """, (reminder_id, user_id))

    connection.commit()
    connection.close()

    return redirect("/reminders")


# =========================================================
# DELETE REMINDER
# =========================================================

@app.route("/delete-reminder/<int:reminder_id>")
@login_required
def delete_reminder(reminder_id):
    user_id = session["user_id"]
    connection = get_db()

    connection.execute("""
        DELETE FROM reminders
        WHERE id = ? AND user_id = ?
    """, (reminder_id, user_id))

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
@login_required
def save_session():
    # If someone visits the URL directly (GET request), just send them back to the timer
    if request.method == "GET":
        return redirect(url_for("timer"))

    # If it's a form submission (POST request), save the data
    user_id = session["user_id"]
    subject = request.form["subject"]
    duration = int(request.form["duration"])
    today = date.today().isoformat()

    connection = get_db()
    connection.execute("""
        INSERT INTO study_sessions
        (user_id, subject, duration, session_date)
        VALUES (?, ?, ?, ?)
    """, (
        user_id,
        subject,
        duration,
        today
    ))

    connection.commit()
    connection.close()

    return redirect(url_for("timer"))


 #===========================================================
# ANALYTICS
# =========================================================

@app.route("/analytics")
@login_required
def analytics():
    user_id = session["user_id"]
    connection = get_db()

    total_tasks = connection.execute("""
        SELECT COUNT(*)
        FROM tasks
        WHERE user_id = ?
    """, (user_id,)).fetchone()[0]

    completed_tasks = connection.execute("""
        SELECT COUNT(*)
        FROM tasks
        WHERE user_id = ? AND status = 'Completed'
    """, (user_id,)).fetchone()[0]

    total_notes = connection.execute("""
        SELECT COUNT(*)
        FROM notes
        WHERE user_id = ?
    """, (user_id,)).fetchone()[0]

    total_goals = connection.execute("""
        SELECT COUNT(*)
        FROM goals
        WHERE user_id = ?
    """, (user_id,)).fetchone()[0]

    completed_goals = connection.execute("""
        SELECT COUNT(*)
        FROM goals
        WHERE user_id = ? AND status = 'Completed'
    """, (user_id,)).fetchone()[0]

    total_study_minutes = connection.execute("""
        SELECT COALESCE(SUM(duration), 0)
        FROM study_sessions
        WHERE user_id = ?
    """, (user_id,)).fetchone()[0]

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
    user_id = session["user_id"]
    connection = get_db()

    completed_tasks = connection.execute("""
        SELECT COUNT(*)
        FROM tasks
        WHERE user_id = ? AND status = 'Completed'
    """, (user_id,)).fetchone()[0]

    total_notes = connection.execute("""
        SELECT COUNT(*)
        FROM notes
        WHERE user_id = ?
    """, (user_id,)).fetchone()[0]

    completed_goals = connection.execute("""
        SELECT COUNT(*)
        FROM goals
        WHERE user_id = ? AND status = 'Completed'
    """, (user_id,)).fetchone()[0]

    total_sessions = connection.execute("""
        SELECT COUNT(*)
        FROM study_sessions
        WHERE user_id = ?
    """, (user_id,)).fetchone()[0]

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

init_db()

if __name__ == "__main__":
    app.run(debug=True)
