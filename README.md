# VERSUS — skeleton code

A starter scaffold for the VERSUS final project (CS460, Summer 2026). It
runs end to end with the core register, login, create-bracket, browse
and view pages working. You will extend it with the rest of the
features described in the project assignment.

## What is in here

- `app.py` — Flask app with register, login, logout, create bracket, browse, view
- `schema.sql` — the four core tables: Users, Brackets, Entrants, Matchups
- `templates/` — minimal HTML templates
- `requirements.txt` — Python dependencies

## What you will add

Everything in the project description that is not in the list above. At
a minimum:

- predictions table + the BEFORE INSERT trigger that enforces the
  prediction state
- votes table + the BEFORE INSERT trigger for the right round + the
  atomic vote-count update
- the close_round stored procedure that picks winners, scores
  predictions, promotes winners to the next round, and advances bracket
  status
- achievements + user_achievements tables + the AFTER INSERT triggers
  that award them
- follows table (with the CHECK that prevents self-follow)
- comments table + comment routes
- the global leaderboard using window functions (RANK, DENSE_RANK,
  PERCENT_RANK)
- the champion-path page using a recursive CTE
- indexes and the EXPLAIN ANALYZE writeup

## Setup

1. Install MySQL and start the server. Create the database from the
   skeleton schema:

   ```
   mysql -u root -p < schema.sql
   ```

2. Edit `app.py` and set `MYSQL_DATABASE_PASSWORD` to your MySQL root
   password.

3. Create a Python virtual environment and install the dependencies:

   ```
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. Run the app:

   ```
   python app.py
   ```

5. Open http://127.0.0.1:5000/ in your browser. Register an account,
   create a bracket, and view it. That is the part that already works.

## Notes

- The SQL is written with string interpolation (`'...{0}'.format(x)`)
  to match the style of the previous semester's skeleton. The same
  caveat applies: this is teaching code, not production code.
- The `Matchups` table holds three foreign keys to `Entrants`
  (entrant_a_id, entrant_b_id, winner_entrant_id). Each role plays a
  different part in the bracket lifecycle.
- Round 1 matchups are created with both entrants set. Later-round
  matchups are created with NULL entrants and are filled in by the
  close_round stored procedure as previous rounds end.
# versus
