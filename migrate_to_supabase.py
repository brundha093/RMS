from __future__ import annotations

import sqlite3

from online_database import OnlineRentalDatabase


def migrate(database_path: str = "rental_manager.db") -> None:
    cloud = OnlineRentalDatabase()
    local = sqlite3.connect(database_path)
    local.row_factory = sqlite3.Row
    flats = [dict(row) for row in local.execute("SELECT * FROM flats").fetchall()]
    payments = [dict(row) for row in local.execute("SELECT * FROM payments").fetchall()]
    users = [dict(row) for row in local.execute("SELECT username, password, display_name FROM users").fetchall()]

    cloud._request("users", method="POST", query="?on_conflict=username", body=users, prefer="resolution=merge-duplicates,return=minimal")
    cloud._request("flats", method="POST", query="?on_conflict=flat_number", body=flats, prefer="resolution=merge-duplicates,return=minimal")
    cloud._request("payments", method="POST", query="?on_conflict=flat_id%2Cmonth", body=payments, prefer="resolution=merge-duplicates,return=minimal")
    local.close()
    print(f"Migrated {len(flats)} flats, {len(payments)} payments, and {len(users)} users.")


if __name__ == "__main__":
    migrate()
