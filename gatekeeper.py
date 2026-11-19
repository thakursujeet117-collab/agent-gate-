"""
Agent Gatekeeper - prototype for an online store (Amazon India).
Decides ALLOW / ASK CUSTOMER / BLOCK for requests from a customer's AI agent.

Usage:
  python gatekeeper.py register  <agent> <customer>
  python gatekeeper.py revoke    <agent>
  python gatekeeper.py request   <customer> <agent> <action> [amount]
  python gatekeeper.py log
  python gatekeeper.py agents
"""
import sqlite3
import sys
from datetime import datetime, timezone, timedelta

# ---- CHANGE THIS to your real enrolment number before you record the video ----
ENROLMENT_NUMBER = "YOUR_ENROLMENT_NUMBER"
COMPANY = "Amazon India (online store)"
DB_FILE = "gatekeeper.db"

SPEND_LIMIT = 5000  # rupees. Money actions above this need customer confirmation.

IST = timezone(timedelta(hours=5, minutes=30))
VALID_ACTIONS = {"view_order", "place_order", "return", "refund"}

RULES = {
    1: "Revoked agent is always blocked",
    2: "Unknown (unregistered) agent is blocked",
    3: "Agent registered for a different customer is blocked",
    4: "Unsupported action or invalid amount is blocked",
    5: "View order (read-only) is allowed",
    6: "Place order or return up to the limit is allowed",
    7: "Place order or return above the limit needs customer confirmation",
    8: "Refund always needs customer confirmation",
}


def now():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def connect(db=DB_FILE):
    con = sqlite3.connect(db)
    con.execute(
        """CREATE TABLE IF NOT EXISTS agents (
               agent TEXT PRIMARY KEY,
               customer TEXT NOT NULL,
               registered_at TEXT NOT NULL,
               revoked_at TEXT)"""
    )
    con.execute(
        """CREATE TABLE IF NOT EXISTS audit (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               time TEXT, customer TEXT, agent TEXT, action TEXT,
               amount REAL, decision TEXT, rule INTEGER, reason TEXT)"""
    )
    return con


def register_agent(con, agent, customer):
    con.execute(
        "INSERT OR REPLACE INTO agents VALUES (?,?,?,NULL)", (agent, customer, now())
    )
    con.commit()


def revoke_agent(con, agent):
    """Save the exact date and time of revocation (the Wells Fargo problem)."""
    row = con.execute("SELECT 1 FROM agents WHERE agent=?", (agent,)).fetchone()
    if not row:
        return None
    t = now()
    con.execute("UPDATE agents SET revoked_at=? WHERE agent=?", (t, agent))
    con.commit()
    return t


def decide(con, customer, agent, action, amount=0):
    """Return (decision, rule_number). Rules are checked in order."""
    row = con.execute(
        "SELECT customer, revoked_at FROM agents WHERE agent=?", (agent,)
    ).fetchone()

    if row and row[1]:
        return "BLOCK", 1
    if not row:
        return "BLOCK", 2
    if row[0] != customer:
        return "BLOCK", 3
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return "BLOCK", 4
    if action not in VALID_ACTIONS or amount < 0:
        return "BLOCK", 4
    if action == "view_order":
        return "ALLOW", 5
    if action == "refund":
        return "ASK CUSTOMER", 8
    # place_order or return
    if amount <= SPEND_LIMIT:
        return "ALLOW", 6
    return "ASK CUSTOMER", 7


def handle_request(con, customer, agent, action, amount=0):
    decision, rule = decide(con, customer, agent, action, amount)
    reason = RULES[rule]
    try:
        amt = float(amount)
    except (TypeError, ValueError):
        amt = None
    con.execute(
        "INSERT INTO audit (time,customer,agent,action,amount,decision,rule,reason) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (now(), customer, agent, action, amt, decision, rule, reason),
    )
    con.commit()
    return decision, rule, reason


def banner():
    print("=" * 60)
    print(f" AGENT GATEKEEPER  |  {COMPANY}")
    print(f" Enrolment number: {ENROLMENT_NUMBER}")
    print(f" Spending limit: Rs {SPEND_LIMIT}")
    print("=" * 60)


def main(argv):
    banner()
    if len(argv) < 2:
        print(__doc__)
        return
    con = connect()
    cmd = argv[1]
    if cmd == "register" and len(argv) == 4:
        register_agent(con, argv[2], argv[3])
        print(f"Registered agent '{argv[2]}' for customer '{argv[3]}' at {now()}")
    elif cmd == "revoke" and len(argv) == 3:
        t = revoke_agent(con, argv[2])
        print(f"Revoked '{argv[2]}' at {t}" if t else "No such agent.")
    elif cmd == "request" and len(argv) in (5, 6):
        amount = argv[5] if len(argv) == 6 else 0
        d, r, why = handle_request(con, argv[2], argv[3], argv[4], amount)
        print(f"Decision: {d}  |  Rule {r}: {why}")
    elif cmd == "log":
        for r in con.execute("SELECT time,customer,agent,action,amount,decision,rule FROM audit"):
            print(r)
    elif cmd == "agents":
        for r in con.execute("SELECT * FROM agents"):
            print(r)
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)
