######################################
# VERSUS skeleton app.py
# CS460 Final Project
######################################
# Covers the core: register/login, create bracket, browse, view.
# Students extend with: predictions, voting, round-closing (stored
# procedure), triggers, leaderboard (window functions), recursive CTE,
# follows, comments, indexes.
###################################################

import flask
from flask import Flask, request, render_template, redirect, url_for
import mysql.connector
import flask_login
import datetime

app = Flask(__name__)
app.secret_key = 'IloveCS460S'  # Change this!

# These will need to be changed according to your credentials.
DB_USER     = 'root'
DB_PASSWORD = 'IloveCS460S'
DB_NAME     = 'versus'
DB_HOST     = 'localhost'

def get_conn():
	return mysql.connector.connect(
		host=DB_HOST,
		user=DB_USER,
		password=DB_PASSWORD,
		database=DB_NAME,
		autocommit=False,
	)

conn = get_conn()


# begin code used for login
login_manager = flask_login.LoginManager()
login_manager.init_app(app)


def getUserList():
	cursor = conn.cursor()
	cursor.execute("SELECT username from Users")
	rows = cursor.fetchall()
	cursor.close()
	return rows


class User(flask_login.UserMixin):
	pass


@login_manager.user_loader
def user_loader(username):
	users = getUserList()
	if not(username) or username not in str(users):
		return
	user = User()
	user.id = username
	return user


@login_manager.request_loader
def request_loader(request):
	users = getUserList()
	username = request.form.get('username')
	if not(username) or username not in str(users):
		return
	user = User()
	user.id = username
	cursor = conn.cursor()
	cursor.execute("SELECT password FROM Users WHERE username = '{0}'".format(username))
	data = cursor.fetchall()
	cursor.close()
	pwd = str(data[0][0])
	user.is_authenticated = request.form['password'] == pwd
	return user


'''
A new page looks like this:
@app.route('new_page_name')
def new_page_function():
	return new_page_html
'''

@app.route('/login', methods=['GET', 'POST'])
def login():
	if request.method == 'GET':
		return '''
			<form action='login' method='POST'>
				<input type='text' name='username' id='username' placeholder='username' />
				<input type='password' name='password' id='password' placeholder='password' />
				<input type='submit' name='submit' />
			</form><br />
			<a href='/'>Home</a>
		'''
	# The request method is POST (page is receiving data)
	username = request.form['username']
	cursor = conn.cursor()
	# check if username is registered
	cursor.execute("SELECT password FROM Users WHERE username = '{0}'".format(username))
	data = cursor.fetchall()
	cursor.close()
	if data:
		pwd = str(data[0][0])
		if request.form['password'] == pwd:
			user = User()
			user.id = username
			flask_login.login_user(user)
			return redirect(url_for('home'))
	# information did not match
	return "<a href='/login'>Try again</a><br />\
			<a href='/register'>or make an account</a>"


@login_manager.unauthorized_handler
def unauthorized_handler():
	return render_template('unauth.html')


# you can specify specific methods (GET/POST) in the function header instead
# of inside the function body
@app.route("/register", methods=['GET'])
def register():
	return render_template('register.html')


@app.route("/register", methods=['POST'])
def register_user():
	try:
		username = request.form.get('username')
		email    = request.form.get('email')
		password = request.form.get('password')
		bio      = request.form.get('bio')
	except:
		print("couldn't find all tokens")
		return redirect(url_for('register'))
	cursor = conn.cursor()
	if isUsernameUnique(username):
		cursor.execute(
			"INSERT INTO Users (username, email, password, bio) VALUES ('{0}', '{1}', '{2}', '{3}')".format(
				username, email, password, bio or ""))
		conn.commit()
		cursor.close()
		# log user in
		user = User()
		user.id = username
		flask_login.login_user(user)
		return render_template('hello.html', name=username, message='account created')
	else:
		cursor.close()
		print("username already in use")
		return redirect(url_for('register'))


def isUsernameUnique(username):
	# use this to check if a username has already been registered
	cursor = conn.cursor()
	cursor.execute("SELECT username FROM Users WHERE username = '{0}'".format(username))
	rows = cursor.fetchall()
	cursor.close()
	return len(rows) == 0


def getUserIdFromUsername(username):
	cursor = conn.cursor()
	cursor.execute("SELECT user_id FROM Users WHERE username = '{0}'".format(username))
	row = cursor.fetchone()
	cursor.close()
	return row[0] if row else None


def getUsernameFromUserId(uid):
	cursor = conn.cursor()
	cursor.execute("SELECT username FROM Users WHERE user_id = '{0}'".format(uid))
	row = cursor.fetchone()
	cursor.close()
	return row[0] if row else None

# end login code


# begin bracket creation code
@app.route('/create', methods=['GET', 'POST'])
@flask_login.login_required
def create_bracket():
	if request.method == 'POST':
		uid           = getUserIdFromUsername(flask_login.current_user.id)
		title         = request.form.get('title')
		description   = request.form.get('description')
		entrant_count = int(request.form.get('entrant_count'))
		cursor = conn.cursor()

		# 1. insert the bracket row
		cursor.execute(
			"INSERT INTO Brackets (host_id, title, description, entrant_count) VALUES ('{0}', '{1}', '{2}', '{3}')".format(
				uid, title, description or "", entrant_count))
		cursor.execute("SELECT LAST_INSERT_ID()")
		bracket_id = cursor.fetchone()[0]

		# 2. insert all entrants in seed order
		entrant_ids = []
		for seed in range(1, entrant_count + 1):
			entrant_name = request.form.get('entrant_' + str(seed))
			cursor.execute(
				"INSERT INTO Entrants (bracket_id, seed, name) VALUES ('{0}', '{1}', '{2}')".format(
					bracket_id, seed, entrant_name))
			cursor.execute("SELECT LAST_INSERT_ID()")
			entrant_ids.append(cursor.fetchone()[0])

		# 3. create Round 1 matchups (seed pairs: 1v2, 3v4, ...)
		round_1_slots = entrant_count // 2
		for slot in range(1, round_1_slots + 1):
			a = entrant_ids[(slot - 1) * 2]
			b = entrant_ids[(slot - 1) * 2 + 1]
			cursor.execute(
				"INSERT INTO Matchups (bracket_id, round, slot, entrant_a_id, entrant_b_id) VALUES ('{0}', 1, '{1}', '{2}', '{3}')".format(
					bracket_id, slot, a, b))

		# 4. create empty shells for later rounds
		slots = round_1_slots // 2
		round_num = 2
		while slots >= 1:
			for slot in range(1, slots + 1):
				cursor.execute(
					"INSERT INTO Matchups (bracket_id, round, slot) VALUES ('{0}', '{1}', '{2}')".format(
						bracket_id, round_num, slot))
			slots //= 2
			round_num += 1

		conn.commit()
		cursor.close()
		return redirect(url_for('view_bracket', bracket_id=bracket_id))
	else:
		return render_template('create.html')
# end bracket creation code


# begin browse code
def getAllBrackets():
	cursor = conn.cursor()
	cursor.execute(
		"SELECT b.bracket_id, b.title, b.status, b.entrant_count, b.created_at, u.username "
		"FROM Brackets b JOIN Users u ON b.host_id = u.user_id "
		"ORDER BY b.created_at DESC")
	rows = cursor.fetchall()
	cursor.close()
	return rows


@app.route('/browse', methods=['GET'])
def browse():
	brackets = getAllBrackets()
	return render_template('browse.html', brackets=brackets)
# end browse code


# begin bracket view code
def getBracketInfo(bracket_id):
	cursor = conn.cursor()
	cursor.execute(
		"SELECT b.bracket_id, b.title, b.description, b.status, b.entrant_count, u.username "
		"FROM Brackets b JOIN Users u ON b.host_id = u.user_id "
		"WHERE b.bracket_id = '{0}'".format(bracket_id))
	row = cursor.fetchone()
	cursor.close()
	return row


def getMatchupsForBracket(bracket_id):
	cursor = conn.cursor()
	uid = None
	if flask_login.current_user.is_authenticated:
		uid = getUserIdFromUsername(flask_login.current_user.id)
	query = """
        SELECT m.matchup_id, m.round, m.slot, ea.name, eb.name, ew.name, m.votes_a, m.votes_b,
               ea.entrant_id, eb.entrant_id, p.entrant_id AS predicted_entrant_id
        FROM Matchups m
        LEFT JOIN Entrants ea ON ea.entrant_id = m.entrant_a_id
        LEFT JOIN Entrants eb ON eb.entrant_id = m.entrant_b_id
        LEFT JOIN Entrants ew ON ew.entrant_id = m.winner_entrant_id
        LEFT JOIN Predictions p ON p.matchup_id = m.matchup_id AND p.user_id = %s
        WHERE m.bracket_id = %s
        ORDER BY m.round, m.slot
    """
	cursor.execute(query, (uid, bracket_id))
	rows = cursor.fetchall()
	cursor.close()
	return rows


@app.route('/bracket<bracket_id>', methods=['GET'])
def view_bracket(bracket_id):
	bracket  = getBracketInfo(bracket_id)
	matchups = getMatchupsForBracket(bracket_id)
	return render_template('bracket.html', bracket=bracket, matchups=matchups)
# end bracket view code

# begin extended features (Predictions, Votes, Leaderboard, Comments, Admin)

@app.route('/predict', methods=['POST'])
@flask_login.login_required
def submit_prediction():

    uid = getUserIdFromUsername(flask_login.current_user.id)

    bracket_id = request.form.get('bracket_id')
    matchup_id = request.form.get('matchup_id')
    selected_name = request.form.get('entrant_name')

    cursor = conn.cursor()

    try:

        cursor.execute(
            "SELECT entrant_id FROM Entrants WHERE name = %s",
            (selected_name,)
        )

        result = cursor.fetchone()

        if result:

            entrant_id = result[0]

            cursor.execute("""
                INSERT INTO Predictions (user_id, matchup_id, entrant_id)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE entrant_id = %s
            """, (uid, matchup_id, entrant_id, entrant_id))

            conn.commit()

    except Exception as e:
        conn.rollback()
        print(e)

    finally:
        cursor.close()

    return redirect(url_for('view_bracket', bracket_id=bracket_id))
@app.route('/start_voting/<bracket_id>', methods=['POST'])
@flask_login.login_required
def start_voting(bracket_id):

    cursor = conn.cursor()

    try:
        cursor.execute(
            "UPDATE Brackets SET status = 'round_1' WHERE bracket_id = %s",
            (bracket_id,)
        )

        conn.commit()

    except Exception as e:
        conn.rollback()
        print(e)

    finally:
        cursor.close()

    return redirect(url_for('view_bracket', bracket_id=bracket_id))
@app.route('/vote', methods=['POST'])
@flask_login.login_required
def submit_vote():

    uid = getUserIdFromUsername(flask_login.current_user.id)

    matchup_id = request.form.get('matchup_id')
    bracket_id = request.form.get('bracket_id')
    entrant_id = request.form.get('entrant_id')

    cursor = conn.cursor()

    try:

        cursor.execute(
            "INSERT INTO Votes (user_id, matchup_id, entrant_id) VALUES (%s, %s, %s)",
            (uid, matchup_id, entrant_id)
        )

        cursor.execute(
            "SELECT entrant_a_id, entrant_b_id FROM Matchups WHERE matchup_id = %s",
            (matchup_id,)
        )

        entrant_a_id, entrant_b_id = cursor.fetchone()

        if int(entrant_id) == entrant_a_id:
            cursor.execute(
                "UPDATE Matchups SET votes_a = votes_a + 1 WHERE matchup_id = %s",
                (matchup_id,)
            )

        elif int(entrant_id) == entrant_b_id:
            cursor.execute(
                "UPDATE Matchups SET votes_b = votes_b + 1 WHERE matchup_id = %s",
                (matchup_id,)
            )

        conn.commit()

    except Exception as e:
        conn.rollback()
        print(e)

    finally:
        cursor.close()

    return redirect(url_for('view_bracket', bracket_id=bracket_id))

@app.route('/close_round/<bracket_id>/<round_num>', methods=['POST'])
@flask_login.login_required
def call_close_round(bracket_id, round_num):
    cursor = conn.cursor()
    try:
        cursor.callproc('close_round', [bracket_id, round_num])
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(e)
    finally:
        cursor.close()
    return redirect(url_for('view_bracket', bracket_id=bracket_id))


@app.route('/comment', methods=['POST'])
@flask_login.login_required
def post_comment():

    uid = getUserIdFromUsername(flask_login.current_user.id)
    
   
    bracket_id = request.form.get('bracket_id')
    matchup_id = request.form.get('matchup_id')
    selected_name = request.form.get('entrant_name')

    cursor = conn.cursor()
    
    
    cursor.execute("SELECT entrant_id FROM Entrants WHERE name = %s", (selected_name,))
    result = cursor.fetchone()
    
    if result:
        entrant_id = result[0]
        
        cursor.execute("INSERT INTO Predictions (user_id, matchup_id, entrant_id) VALUES (%s, %s, %s)", 
                       (uid, matchup_id, entrant_id))
        conn.commit()
    
    cursor.close()
    return redirect(url_for('view_bracket', bracket_id=bracket_id))


@app.route('/leaderboard', methods=['GET'])
def leaderboard():
    cursor = conn.cursor()
    # Using window functions as specified in assignment
    query = """
        SELECT u.username, 
               COALESCE(SUM(p.points), 0) AS total_points,
               RANK() OVER (ORDER BY COALESCE(SUM(p.points), 0) DESC) as user_rank,
               DENSE_RANK() OVER (ORDER BY COALESCE(SUM(p.points), 0) DESC) as user_dense_rank,
               PERCENT_RANK() OVER (ORDER BY COALESCE(SUM(p.points), 0) DESC) as user_percent_rank
        FROM Users u
        LEFT JOIN Predictions p ON u.user_id = p.user_id
        GROUP BY u.user_id, u.username
        ORDER BY total_points DESC
    """
    cursor.execute(query)
    board = cursor.fetchall()
    cursor.close()
    return render_template('leaderboard.html', leaderboard=board)


@app.route('/champion_path/<bracket_id>', methods=['GET'])
def champion_path(bracket_id):
    cursor = conn.cursor()
    # Recursive CTE 
    query = """
        WITH RECURSIVE ChampPath AS (
            SELECT matchup_id, round, slot, entrant_a_id, entrant_b_id, winner_entrant_id
            FROM Matchups
            WHERE bracket_id = '{0}' AND round = (SELECT MAX(round) FROM Matchups WHERE bracket_id = '{0}')
            
            UNION ALL
            
            SELECT m.matchup_id, m.round, m.slot, m.entrant_a_id, m.entrant_b_id, m.winner_entrant_id
            FROM Matchups m
            INNER JOIN ChampPath cp ON m.bracket_id = '{0}' 
                AND m.round = cp.round - 1
                AND m.winner_entrant_id = cp.winner_entrant_id
        )
        SELECT * FROM ChampPath ORDER BY round ASC;
    """.format(bracket_id)
    cursor.execute(query)
    path = cursor.fetchall()
    cursor.close()
    return render_template('champion_path.html', path=path)


@app.route('/follow/<username>', methods=['POST'])
@flask_login.login_required
def follow_user(username):
    follower_id = getUserIdFromUsername(flask_login.current_user.id)
    followed_id = getUserIdFromUsername(username)
    
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Follows (follower_id, followed_id) VALUES ('{0}', '{1}')".format(follower_id, followed_id))
        conn.commit()
    except Exception as e:
        print(e)
    finally:
        cursor.close()
    return redirect(url_for('home'))




# end of my added code for features

# default page
@app.route('/', methods=['GET', 'POST'])
def home():
	if request.method == 'POST':
		flask_login.logout_user()
	try:
		username = flask_login.current_user.id
		return render_template('hello.html', name=username, message='welcome to VERSUS')
	except AttributeError:  # not logged in
		return render_template('hello.html', message=None)


if __name__ == "__main__":
	# this is invoked when in the shell you run
	# $ python app.py
	app.debug = True
	app.run(port=5000, debug=True)
