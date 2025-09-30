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
ADMIN_PASSWORD = "admin123" # simple admin password

# Admin login check (super simple)
def check_admin(password):
  if password != ADMIN_PASSWORD:
    abort(401) # Unauthorized


@app.route('/admin/dashboard')
def admin_dashboard():
  return render_template("admin_dashboard.html")


# Generate random ticket ID
def generate_ticket_id():
  return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

@app.route('/admin/bookings')
def admin_bookings():
  password = request.args.get("password")
  check_admin(password)
  # Updated query to join through showtimes
  cursor.execute("""
    SELECT 
        b.ticket_id, b.username, b.email, 
        m.title, 
        s.seat_no,
        st.show_time
    FROM bookings b
    JOIN seats s ON b.seat_id = s.id
    JOIN showtimes st ON s.showtime_id = st.id
    JOIN movies m ON st.movie_id = m.id
  """)
  bookings = cursor.fetchall()
  # admin_bookings.html needs update to show show_time
  return render_template("admin_bookings.html", bookings=bookings)

@app.route('/admin/add_movie', methods=["GET", "POST"])
def add_movie():
  password = request.args.get("password")
  check_admin(password)
  if request.method == "POST":
    title = request.form["title"]
    cursor.execute("INSERT INTO movies (title) VALUES (%s)", (title,))
    db.commit()
    # Removed seat generation logic: seats are now generated per showtime
    flash(f"Movie '{title}' added successfully! Now add showtimes.")
    # Ensure password is passed back on redirect
    return redirect(f"/admin/add_movie?password=admin123")
  return render_template("add_movie.html")

@app.route('/admin/add_showtime', methods=["GET", "POST"])
def admin_add_showtime():
    password = request.args.get("password")
    check_admin(password)

    cursor.execute("SELECT id, title FROM movies")
    movies = cursor.fetchall()

    if request.method == "POST":
        movie_id = request.form["movie_id"]
        
        # --- CHANGES START HERE ---
        # Capture the two separate fields
        show_date = request.form["show_date"] 
        time_only = request.form["show_time_only"] 
        
        # Combine them into a DATETIME string format (YYYY-MM-DD HH:MM:00)
        show_time = f"{show_date} {time_only}:00" 
        # --- CHANGES END HERE ---


        # 1. Insert showtime
        # Assuming the 'showtimes' table structure (id, movie_id, show_time)
        cursor.execute("INSERT INTO showtimes (movie_id, show_time) VALUES (%s, %s)", (movie_id, show_time))
        db.commit()
        showtime_id = cursor.lastrowid

        # 2. Generate 25 seats for this specific showtime
        for n in range(25):
            seat_no = chr(65 + n // 5) + str(n % 5 + 1)
            cursor.execute("INSERT INTO seats (showtime_id, seat_no) VALUES (%s,%s)", (showtime_id, seat_no))
        db.commit()

        flash(f"Showtime '{show_time}' added successfully!")
        return redirect(f"/admin/add_showtime?password=admin123")

    return render_template("admin_add_showtime.html", movies=movies)


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

# New route to select showtimes for a movie
@app.route('/timings/<int:movie_id>')
def show_timings(movie_id):
    cursor.execute("SELECT title FROM movies WHERE id=%s", (movie_id,))
    movie = cursor.fetchone()
    if not movie:
        abort(404)

    # Fetch available showtimes for the movie
    cursor.execute("SELECT id, show_time FROM showtimes WHERE movie_id=%s ORDER BY show_time", (movie_id,))
    showtimes = cursor.fetchall()

    return render_template("timings.html", movie=movie, showtimes=showtimes)


# Seats now require showtime_id
@app.route('/seats/<int:showtime_id>')
def seats(showtime_id):
  # Fetch movie title and showtime details
  cursor.execute("""
      SELECT st.id, st.show_time, m.title 
      FROM showtimes st
      JOIN movies m ON st.movie_id = m.id
      WHERE st.id=%s
  """, (showtime_id,))
  showtime_data = cursor.fetchone()
  
  if not showtime_data:
      abort(404)
      
  # Fetch seats linked to this specific showtime
  cursor.execute("SELECT * FROM seats WHERE showtime_id=%s ORDER BY seat_no", (showtime_id,))
  seats = cursor.fetchall()
  
  # Note: passing showtime_data as 'showtime' to the template
  return render_template("seats.html", showtime=showtime_data, seats=seats)

# Booking now requires showtime_id and seat_id (from the showtime-specific seats table)
@app.route('/book/<int:showtime_id>/<int:seat_id>', methods=["GET", "POST"])
def book(showtime_id, seat_id):
  # 1. Check if seat is valid and booked
  cursor.execute("SELECT * FROM seats WHERE id=%s AND showtime_id=%s", (seat_id, showtime_id))
  seat = cursor.fetchone()
  
  if not seat:
      abort(404)

  if seat["is_booked"]:
    return "Seat already booked!"

  # 2. Fetch movie/showtime details for display
  cursor.execute("""
      SELECT st.id AS showtime_id, st.show_time, m.title, m.id AS movie_id
      FROM showtimes st
      JOIN movies m ON st.movie_id = m.id
      WHERE st.id=%s
  """, (showtime_id,))
  showtime_data = cursor.fetchone() # This variable now contains movie title and showtime

  if request.method == "POST":
    username = request.form["username"]
    email = request.form["email"]
    ticket_id = generate_ticket_id()

    # Mark seat as booked
    cursor.execute("UPDATE seats SET is_booked=TRUE WHERE id=%s", (seat_id,))
    
    # Save booking: Using showtime_id and the specific seat_id. 
    # NOTE: Assuming the 'bookings' table schema has been updated to use showtime_id.
    cursor.execute("INSERT INTO bookings (ticket_id, username, email, showtime_id, seat_id) VALUES (%s,%s,%s,%s,%s)",
             (ticket_id, username, email, showtime_id, seat_id))
    db.commit()

    return redirect(url_for("ticket", ticket_id=ticket_id))

  # Pass showtime_data as 'movie' to reuse book.html structure easily
  return render_template("book.html", movie=showtime_data, seat=seat)

@app.route('/ticket/<ticket_id>')
def ticket(ticket_id):
  # Updated query to join through seats, showtimes, and then movies
  cursor.execute("""
           SELECT 
               b.ticket_id, b.username, b.email, 
               m.title, 
               s.seat_no,
               st.show_time
           FROM bookings b
           JOIN seats s ON b.seat_id=s.id
           JOIN showtimes st ON s.showtime_id=st.id
           JOIN movies m ON st.movie_id=m.id
           WHERE b.ticket_id=%s
         """, (ticket_id,))
  booking = cursor.fetchone()
  # ticket.html needs update to show show_time
  return render_template("ticket.html", booking=booking)

if __name__ == "__main__":
  app.run(debug=True)