
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session
import sqlite3
from pathlib import Path

app = Flask(__name__)
app.secret_key = "e-governance-lab-secret-key"

# Database file stored in the project folder
DATABASE = Path(__file__).parent / "portal.db"


def get_db_connection():
    """Connect to the SQLite database."""
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    """Create the database tables if they do not exist."""
    connection = get_db_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            service_name TEXT NOT NULL,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Submitted',
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    connection.commit()
    connection.close()


@app.route("/")
def home():
    """Display the portal homepage."""
    return render_template("index.html")

@app.route("/services")
def services():
    """Display available government services."""
    return render_template("services.html")

@app.route("/apply/<service_name>", methods=["GET", "POST"])
def apply_for_service(service_name):
    """Display and submit a government service application."""

    allowed_services = [
        "Income Certificate",
        "Residence Certificate",
        "Birth Certificate"
    ]

    if service_name not in allowed_services:
        return "Service not found", 404

    if "user_id" not in session:
        flash("Please log in before applying for a service.")
        return redirect(url_for("login"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        if not full_name or not phone or not address:
            flash("Please fill in all fields.")
            return redirect(url_for(
                "apply_for_service",
                service_name=service_name
            ))

        connection = get_db_connection()

        cursor = connection.execute(
            """
            INSERT INTO applications
                (user_id, service_name, full_name, phone, address)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                service_name,
                full_name,
                phone,
                address
            )
        )

        connection.commit()
        application_id = cursor.lastrowid
        connection.close()

        flash(f"Application submitted! Your Application ID is APP-{application_id:05d}.")
        return redirect(url_for("track"))

    return render_template("apply.html", service_name=service_name)

@app.route("/register", methods=["GET", "POST"])
def register():
    """Display the form and register a new user."""

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Please fill in all fields.")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)

        connection = get_db_connection()

        try:
            connection.execute(
                """
                INSERT INTO users (name, email, password_hash)
                VALUES (?, ?, ?)
                """,
                (name, email, password_hash)
            )
            connection.commit()

        except sqlite3.IntegrityError:
            flash("This email is already registered.")

        else:
            connection.close()
            flash("Registration successful! You can now log in.")
            return redirect(url_for("login"))

        finally:
            connection.close()

        return redirect(url_for("register"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log in a registered user."""

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        connection = get_db_connection()

        user = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        connection.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            flash("Login successful!")
            return redirect(url_for("home"))

        flash("Invalid email or password.")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/track", methods=["GET", "POST"])
def track():
    """Find an application and display its status."""

    application = None

    if request.method == "POST":
        entered_id = request.form.get("application_id", "").strip().upper()

        if entered_id.startswith("APP-"):
            entered_id = entered_id[4:]

        if not entered_id.isdigit():
            flash("Please enter a valid Application ID, such as APP-00001.")
            return render_template("track.html", application=None)

        connection = get_db_connection()

        application = connection.execute(
            """
            SELECT *
            FROM applications
            WHERE id = ? AND user_id = ?
            """,
            (int(entered_id), session.get("user_id", -1))
        ).fetchone()

        connection.close()

        if application is None:
            flash("Application not found for your account.")

    return render_template("track.html", application=application)

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.")
    return redirect(url_for("home"))

@app.route("/my-applications")
def my_applications():
    if "user_id" not in session:
        flash("Please log in to view your applications.")
        return redirect(url_for("login"))

    connection = get_db_connection()
    applications = connection.execute(
        """SELECT * FROM applications
           WHERE user_id = ?
           ORDER BY id DESC""",
        (session["user_id"],)
    ).fetchall()
    connection.close()

    return render_template(
        "my_applications.html",
        applications=applications
    )

if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)
