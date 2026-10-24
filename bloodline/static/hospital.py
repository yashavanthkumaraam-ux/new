"""Add a hospital login.  Usage:
   python add_hospital.py "Hospital Name" username password bank_id
Example:
   python add_hospital.py "Apollo Hospital" apollo MyStrongPass1 1
Run it from the project folder. bank_id is the id of the blood bank that hospital may edit."""
import os, sqlite3, sys
from werkzeug.security import generate_password_hash

if len(sys.argv) != 5:
    sys.exit(__doc__)
name, user, pw, bank = sys.argv[1], sys.argv[2].strip().lower(), sys.argv[3], sys.argv[4]
c = sqlite3.connect(os.environ.get("DB_PATH", "bloodline.db"))
if not c.execute("SELECT 1 FROM banks WHERE id=?", (bank,)).fetchone():
    sys.exit("No blood bank with that id. Banks: " + ", ".join(f"{r[0]}={r[1]}" for r in c.execute("SELECT id,name FROM banks")))
c.execute("INSERT INTO hospitals(name,username,password_hash,bank_id) VALUES(?,?,?,?)", (name, user, generate_password_hash(pw), int(bank)))
c.commit()
print("Hospital user created:", user)
