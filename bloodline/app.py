import os, re, sqlite3
from flask import Flask, jsonify, request, g, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, static_folder="static", static_url_path="")
# On a real server, set a long random SECRET_KEY environment variable.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
DB = os.environ.get("DB_PATH", "bloodline.db")
GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
PHONE = re.compile(r"^[0-9+\- ]{7,15}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS donors(id INTEGER PRIMARY KEY, name TEXT, grp TEXT, city TEXT, phone TEXT, last TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS banks(id INTEGER PRIMARY KEY, name TEXT, city TEXT, phone TEXT);
CREATE TABLE IF NOT EXISTS stock(bank_id INTEGER, grp TEXT, units INTEGER DEFAULT 0, PRIMARY KEY(bank_id, grp));
CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY, patient TEXT, grp TEXT, units INTEGER, hospital TEXT,
  city TEXT, phone TEXT, level TEXT, done INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS hospitals(id INTEGER PRIMARY KEY, name TEXT, username TEXT UNIQUE, password_hash TEXT, bank_id INTEGER);
"""

def seed(c):
    c.executescript("DELETE FROM donors; DELETE FROM banks; DELETE FROM stock; DELETE FROM requests;")
    c.executemany("INSERT INTO donors(name,grp,city,phone,last) VALUES(?,?,?,?,?)", [
        ("Asha Rao", "O-", "Bengaluru", "9800000001", ""),
        ("Imran Khan", "B+", "Bengaluru", "9800000002", "2026-09-20"),
        ("Meera Nair", "A+", "Mysuru", "9800000003", "2026-03-02"),
        ("Karthik S", "AB+", "Chennai", "9800000004", ""),
        ("Divya P", "O+", "Bengaluru", "9800000005", "2026-05-14"),
        ("Rohit Verma", "A-", "Chennai", "9800000006", "")])
    banks = [("City Central Blood Bank", "Bengaluru", "8040000001", [12, 2, 9, 1, 4, 0, 15, 3]),
             ("Lakeside Hospital Blood Centre", "Mysuru", "8210000002", [5, 1, 6, 0, 2, 1, 8, 1]),
             ("Marina Red Cross Bank", "Chennai", "4420000003", [7, 0, 4, 2, 1, 0, 10, 2])]
    for i, (n, city, ph, units) in enumerate(banks, 1):
        c.execute("INSERT INTO banks(id,name,city,phone) VALUES(?,?,?,?)", (i, n, city, ph))
        c.executemany("INSERT INTO stock VALUES(?,?,?)", [(i, g, u) for g, u in zip(GROUPS, units)])
    c.execute("INSERT INTO requests(patient,grp,units,hospital,city,phone,level) VALUES(?,?,?,?,?,?,?)",
              ("Surgery patient", "B-", 2, "St. Mary's Hospital", "Bengaluru", "9800000010", "Critical (within hours)"))
    c.commit()

def init():
    c = sqlite3.connect(DB)
    c.executescript(SCHEMA)
    if not c.execute("SELECT 1 FROM banks").fetchone():
        seed(c)
    if not c.execute("SELECT 1 FROM hospitals").fetchone():
        demo = [("City Central Hospital", "citycentral", 1), ("Lakeside Hospital", "Yash", 2), ]
        for name, user, bank in demo:  # demo password: hospital123 (change it!)
            c.execute("INSERT OR IGNORE INTO hospitals(name,username,password_hash,bank_id) VALUES(?,?,?,?)",
                      (name, user, generate_password_hash("Yash123"), bank))
        c.commit()
    c.close()

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d:
        d.close()

def err(msg, code=400):
    return jsonify(error=msg), code

def clean(data, fields):
    out = {}
    for f in fields:
        v = str(data.get(f, "")).strip()
        if not v:
            return None
        out[f] = v[:120]
    return out

@app.get("/")
def index():
    return app.send_static_file("index.html")

# ---------- Hospital login ----------
def hospital():
    hid = session.get("hid")
    if not hid:
        return None
    return db().execute("SELECT * FROM hospitals WHERE id=?", (hid,)).fetchone()

def need_hospital(bank_id=None):
    """Returns (hospital, error_response). Pass bank_id to limit access to that hospital's own bank."""
    h = hospital()
    if not h:
        return None, err("Please log in as a hospital user.", 401)
    if bank_id is not None and h["bank_id"] != bank_id:
        return None, err("You can only edit your own blood bank.", 403)
    return h, None

def user_json(h):
    return dict(name=h["name"], username=h["username"], bank_id=h["bank_id"])

@app.post("/api/login")
def login():
    d = request.get_json(silent=True) or {}
    h = db().execute("SELECT * FROM hospitals WHERE username=?", (str(d.get("username", "")).strip().lower(),)).fetchone()
    if not h or not check_password_hash(h["password_hash"], str(d.get("password", ""))):
        return err("Wrong username or password.", 401)
    session.clear()
    session["hid"] = h["id"]
    return jsonify(user=user_json(h))

@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)

@app.get("/api/me")
def me():
    h = hospital()
    return jsonify(user=user_json(h) if h else None)

# ---------- Donors ----------
@app.get("/api/donors")
def donors():
    rows = db().execute("SELECT * FROM donors ORDER BY id DESC").fetchall()
    return jsonify([dict(id=r["id"], name=r["name"], group=r["grp"], city=r["city"], phone=r["phone"], last=r["last"]) for r in rows])

@app.post("/api/donors")
def add_donor():
    d = request.get_json(silent=True) or {}
    v = clean(d, ["name", "group", "city", "phone"])
    if not v or v["group"] not in GROUPS or not PHONE.match(v["phone"]):
        return err("Enter a name, blood group, city and valid phone number.")
    last = str(d.get("last", ""))[:10]
    db().execute("INSERT INTO donors(name,grp,city,phone,last) VALUES(?,?,?,?,?)",
                 (v["name"], v["group"], v["city"], v["phone"], last))
    db().commit()
    return jsonify(ok=True), 201

@app.delete("/api/donors/<int:i>")
def del_donor(i):
    db().execute("DELETE FROM donors WHERE id=?", (i,))
    db().commit()
    return jsonify(ok=True)

# ---------- Blood banks and stock ----------
@app.get("/api/banks")
def banks():
    out = []
    for b in db().execute("SELECT * FROM banks ORDER BY id"):
        st = {g: 0 for g in GROUPS}
        for s in db().execute("SELECT grp, units FROM stock WHERE bank_id=?", (b["id"],)):
            st[s["grp"]] = s["units"]
        out.append(dict(id=b["id"], name=b["name"], city=b["city"], phone=b["phone"], stock=st))
    return jsonify(out)

@app.put("/api/banks/<int:i>")
def edit_bank(i):
    _, bad = need_hospital(i)
    if bad:
        return bad
    v = clean(request.get_json(silent=True) or {}, ["name", "city", "phone"])
    if not v or not PHONE.match(v["phone"]):
        return err("Enter a name, city and valid phone number.")
    db().execute("UPDATE banks SET name=?, city=?, phone=? WHERE id=?", (v["name"], v["city"], v["phone"], i))
    db().commit()
    return jsonify(ok=True)

@app.post("/api/banks/<int:i>/stock")
def stock(i):
    _, bad = need_hospital(i)
    if bad:
        return bad
    d = request.get_json(silent=True) or {}
    grp, delta = d.get("group"), d.get("delta")
    if grp not in GROUPS or delta not in (1, -1):
        return err("Invalid stock change.")
    c = db()
    c.execute("INSERT OR IGNORE INTO stock VALUES(?,?,0)", (i, grp))
    c.execute("UPDATE stock SET units=MAX(0, units+?) WHERE bank_id=? AND grp=?", (delta, i, grp))
    c.commit()
    return jsonify(ok=True)

# ---------- Emergency requests ----------
@app.get("/api/requests")
def requests_list():
    rows = db().execute("SELECT * FROM requests ORDER BY id DESC").fetchall()
    return jsonify([dict(id=r["id"], patient=r["patient"], group=r["grp"], units=r["units"], hospital=r["hospital"],
                         city=r["city"], phone=r["phone"], level=r["level"], done=bool(r["done"])) for r in rows])

@app.post("/api/requests")
def add_request():
    d = request.get_json(silent=True) or {}
    v = clean(d, ["group", "hospital", "city", "phone", "level"])
    if not v or v["group"] not in GROUPS or not PHONE.match(v["phone"]):
        return err("Enter the hospital, city and a valid contact phone.")
    try:
        units = max(1, min(50, int(d.get("units", 1))))
    except (TypeError, ValueError):
        units = 1
    db().execute("INSERT INTO requests(patient,grp,units,hospital,city,phone,level) VALUES(?,?,?,?,?,?,?)",
                 (str(d.get("patient", ""))[:120], v["group"], units, v["hospital"], v["city"], v["phone"], v["level"]))
    db().commit()
    return jsonify(ok=True), 201

@app.post("/api/requests/<int:i>/fulfil")
def fulfil(i):
    db().execute("UPDATE requests SET done=1 WHERE id=?", (i,))
    db().commit()
    return jsonify(ok=True)

@app.delete("/api/requests/<int:i>")
def del_request(i):
    db().execute("DELETE FROM requests WHERE id=?", (i,))
    db().commit()
    return jsonify(ok=True)

@app.post("/api/reset")
def reset():
    _, bad = need_hospital()
    if bad:
        return bad
    seed(db())
    return jsonify(ok=True)

init()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))