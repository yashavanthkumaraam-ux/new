# Bloodline: Blood Donor and Emergency Blood Availability Portal

Stack: Flask (Python) + SQLite backend, HTML/CSS/JavaScript frontend.

## Run locally
    python -m venv venv
    source venv/bin/activate        # Windows: venv\Scripts\activate
    pip install -r requirements.txt
    python app.py
Open http://localhost:5000

## Project structure
    app.py            Flask app, REST API and SQLite database
    static/index.html Frontend (served at /)
    requirements.txt  Dependencies
    Procfile          Start command for hosting platforms

## REST API
    GET/POST   /api/donors            DELETE /api/donors/<id>
    GET        /api/banks             POST   /api/banks/<id>/stock   {group, delta: 1|-1}
    GET/POST   /api/requests          POST   /api/requests/<id>/fulfil   DELETE /api/requests/<id>
    POST       /api/reset             restore demo data

## Deploy on PythonAnywhere (free, SQLite data persists)
1. Create an account at pythonanywhere.com and open a Bash console.
2. Upload or `git clone` this project, then:
       python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
3. Web tab > Add a new web app > Manual configuration > Python 3.10+.
4. Set Virtualenv to the venv path and edit the WSGI file:
       import sys
       sys.path.insert(0, "/home/YOURNAME/bloodline")
       from app import app as application
5. Click Reload. Your site is at YOURNAME.pythonanywhere.com

## Deploy on Render (free, but SQLite resets on restart)
1. Push the project to GitHub.
2. Render > New > Web Service > connect the repo.
3. Build command: `pip install -r requirements.txt`  Start command: `gunicorn app:app`
4. Deploy. For permanent data, add a Render PostgreSQL database or a paid persistent disk.
