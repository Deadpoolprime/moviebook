from flask import Flask, render_template, request, redirect, url_for, abort,flash
import mysql.connector, random, string

app = Flask(__name__)

# MySQL connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="movie_booking"
)
cursor = db.cursor(dictionary=True)
app.secret_key = "supersecretkey"
ADMIN_PASSWORD = "admin123"  # simple admin password

# Admin login check (super simple)
def check_admin():
    password = request.args.get("password")
    if password != ADMIN_PASSWORD:
        abort(401)  # unauthorized

@app.route('/admin/dashboard')
def admin_dashboard():
    return render_template("admin_dashboard.html")


# Generate random ticket ID
def generate_ticket_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

@app.route('/', methods=["GET", "POST"])
def home():
    if request.method == "POST" and "admin_password" in request.form:
        password = request.form["admin_password"]
        if password == ADMIN_PASSWORD:
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Incorrect admin password!")
            return redirect(url_for("home"))

    cursor.execute("SELECT * FROM movies")
    movies = cursor.fetchall()
    return render_template("index.html", movies=movies)

@app.route('/seats/<int:movie_id>')
def seats(movie_id):
    cursor.execute("SELECT * FROM movies WHERE id=%s", (movie_id,))
    movie = cursor.fetchone()
    cursor.execute("SELECT * FROM seats WHERE movie_id=%s", (movie_id,))
    seats = cursor.fetchall()
    return render_template("seats.html", movie=movie, seats=seats)

@app.route('/book/<int:movie_id>/<int:seat_id>', methods=["GET", "POST"])
def book(movie_id, seat_id):
    cursor.execute("SELECT * FROM seats WHERE id=%s", (seat_id,))
    seat = cursor.fetchone()
    if seat["is_booked"]:
        return "Seat already booked!"

    cursor.execute("SELECT * FROM movies WHERE id=%s", (movie_id,))
    movie = cursor.fetchone()

    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        ticket_id = generate_ticket_id()

        # Mark seat as booked
        cursor.execute("UPDATE seats SET is_booked=TRUE WHERE id=%s", (seat_id,))
        # Save booking
        cursor.execute("INSERT INTO bookings (ticket_id, username, email, movie_id, seat_id) VALUES (%s,%s,%s,%s,%s)",
                       (ticket_id, username, email, movie_id, seat_id))
        db.commit()

        return redirect(url_for("ticket", ticket_id=ticket_id))

    return render_template("book.html", movie=movie, seat=seat)

@app.route('/ticket/<ticket_id>')
def ticket(ticket_id):
    cursor.execute("""SELECT b.ticket_id, b.username, b.email, m.title, s.seat_no 
                      FROM bookings b 
                      JOIN movies m ON b.movie_id=m.id 
                      JOIN seats s ON b.seat_id=s.id 
                      WHERE b.ticket_id=%s""", (ticket_id,))
    booking = cursor.fetchone()
    return render_template("ticket.html", booking=booking)

if __name__ == "__main__":
    app.run(debug=True)

@app.route('/admin/add_movie', methods=["GET", "POST"])
def add_movie():
    password = request.args.get("password")
    check_admin(password)
    if request.method == "POST":
        title = request.form["title"]
        cursor.execute("INSERT INTO movies (title) VALUES (%s)", (title,))
        db.commit()
        movie_id = cursor.lastrowid
        # Create 25 seats
        for n in range(25):
            seat_no = chr(65 + n // 5) + str(n % 5 + 1)
            cursor.execute("INSERT INTO seats (movie_id, seat_no) VALUES (%s,%s)", (movie_id, seat_no))
        db.commit()
        flash("Movie added successfully!")
        return redirect(url_for("add_movie", password=password))
    return render_template("add_movie.html")

@app.route('/admin/bookings')
def admin_bookings():
    password = request.args.get("password")
    check_admin(password)
    cursor.execute("""SELECT b.ticket_id, b.username, b.email, m.title, s.seat_no 
                      FROM bookings b 
                      JOIN movies m ON b.movie_id=m.id 
                      JOIN seats s ON b.seat_id=s.id""")
    bookings = cursor.fetchall()
    return render_template("admin_bookings.html", bookings=bookings)


