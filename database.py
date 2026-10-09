from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any


class RentalDatabase:
    """SQLite persistence for the owner dashboard."""

    def __init__(self, database_path: str | None = None) -> None:
        self.path = Path(database_path or "rental_manager.db")
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self._create_schema()
        self._seed_flats()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                display_name TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS flats (
                id INTEGER PRIMARY KEY,
                flat_number TEXT UNIQUE NOT NULL,
                flat_type TEXT NOT NULL DEFAULT '',
                tenant_name TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                electricity_number TEXT NOT NULL DEFAULT '',
                monthly_rent REAL NOT NULL DEFAULT 0,
                maintenance REAL NOT NULL DEFAULT 0,
                parking REAL NOT NULL DEFAULT 0,
                repair REAL NOT NULL DEFAULT 0,
                bike_charge REAL NOT NULL DEFAULT 0,
                electricity_due REAL NOT NULL DEFAULT 0,
                electricity_paid REAL NOT NULL DEFAULT 0,
                electricity_arrears REAL NOT NULL DEFAULT 0,
                joining_date TEXT NOT NULL DEFAULT '',
                vacating_date TEXT NOT NULL DEFAULT '',
                tenant_notes TEXT NOT NULL DEFAULT '',
                advance_amount REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY,
                flat_id INTEGER NOT NULL REFERENCES flats(id),
                month TEXT NOT NULL,
                rent REAL NOT NULL DEFAULT 0,
                maintenance REAL NOT NULL DEFAULT 0,
                parking REAL NOT NULL DEFAULT 0,
                repair REAL NOT NULL DEFAULT 0,
                bike_charge REAL NOT NULL DEFAULT 0,
                electricity REAL NOT NULL DEFAULT 0,
                paid_on TEXT NOT NULL,
                UNIQUE(flat_id, month)
            );
            """
        )
        self.connection.execute(
            "INSERT OR IGNORE INTO users VALUES (1, 'owner', 'owner123', 'ఇంటి యజమాని')"
        )
        self._add_column_if_missing("flats", "vacating_date", "TEXT NOT NULL DEFAULT ''")
        self._add_column_if_missing("flats", "tenant_notes", "TEXT NOT NULL DEFAULT ''")
        self._add_column_if_missing("flats", "flat_type", "TEXT NOT NULL DEFAULT ''")
        self._add_column_if_missing("flats", "joining_date", "TEXT NOT NULL DEFAULT ''")
        self._add_column_if_missing("flats", "electricity_arrears", "REAL NOT NULL DEFAULT 0")
        self._add_column_if_missing("flats", "advance_amount", "REAL NOT NULL DEFAULT 0")
        self.connection.commit()

    def _add_column_if_missing(self, table: str, column: str, definition: str) -> None:
        columns = {row[1] for row in self.connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _seed_flats(self) -> None:
        count = self.connection.execute("SELECT COUNT(*) FROM flats").fetchone()[0]
        if count:
            return
        rows = [
            (f"{floor}{position:02d}", "", "", f"APSPDCL-{floor}{position:02d}", 12500, 1800, 1000, 0, 0, 0, 0)
            for floor in range(1, 5)
            for position in range(1, 6)
        ][:17]
        self.connection.executemany(
            """INSERT INTO flats (
                flat_number, tenant_name, phone, electricity_number, monthly_rent,
                maintenance, parking, repair, bike_charge, electricity_due, electricity_paid
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self.connection.commit()

    def authenticate(self, username: str, password: str) -> bool:
        return self.connection.execute(
            "SELECT 1 FROM users WHERE username = ? AND password = ?",
            (username.strip(), password),
        ).fetchone() is not None

    def flats(self, month: str | None = None) -> list[dict[str, Any]]:
        month = month or date.today().strftime("%Y-%m")
        rows = self.connection.execute(
            """
            SELECT f.*, p.rent AS paid_rent, p.maintenance AS paid_maintenance,
                   p.parking AS paid_parking, p.repair AS paid_repair,
                   p.bike_charge AS paid_bike_charge, p.electricity AS paid_electricity
            FROM flats f LEFT JOIN payments p ON p.flat_id = f.id AND p.month = ?
            ORDER BY f.flat_number
            """,
            (month,),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            for field in ("paid_rent", "paid_maintenance", "paid_parking", "paid_repair", "paid_bike_charge", "paid_electricity"):
                item[field] = float(item[field] or 0)
            item["electricity_arrears"] = float(item.get("electricity_arrears") or 0)
            item["total_due"] = sum(float(item[key]) for key in ("monthly_rent", "maintenance", "parking", "repair", "bike_charge")) + float(item["electricity_due"]) + float(item["electricity_arrears"])
            item["total_paid"] = sum(item[field] for field in ("paid_rent", "paid_maintenance", "paid_parking", "paid_repair", "paid_bike_charge", "paid_electricity"))
            item["balance"] = max(item["total_due"] - item["total_paid"], 0)
            result.append(item)
        return result

    def summary(self, month: str | None = None) -> dict[str, float]:
        rows = self.flats(month)
        fields = {
            "rent": "paid_rent", "maintenance": "paid_maintenance", "parking": "paid_parking",
            "bike": "paid_bike_charge", "electricity": "paid_electricity",
        }
        return {key: sum(row[field] for row in rows) for key, field in fields.items()} | {
            "due": sum(row["total_due"] for row in rows),
            "paid": sum(row["total_paid"] for row in rows),
            "balance": sum(row["balance"] for row in rows),
        }

    def record_payment(self, flat_id: int, month: str, values: dict[str, float]) -> None:
        self.connection.execute(
            """INSERT INTO payments (flat_id, month, rent, maintenance, parking, repair, bike_charge, electricity, paid_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(flat_id, month) DO UPDATE SET rent=excluded.rent, maintenance=excluded.maintenance,
            parking=excluded.parking, repair=excluded.repair, bike_charge=excluded.bike_charge,
            electricity=payments.electricity, paid_on=excluded.paid_on""",
            (flat_id, month, values.get("rent", 0), values.get("maintenance", 0), values.get("parking", 0),
             values.get("repair", 0), values.get("bike", 0), values.get("electricity", 0), date.today().isoformat()),
        )
        self.connection.commit()

    def record_payment(self, flat_id: int, month: str, values: dict[str, float]) -> None:
        self.connection.execute(
            """INSERT INTO payments (flat_id, month, rent, maintenance, parking, repair, bike_charge, electricity, paid_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(flat_id, month) DO UPDATE SET rent=excluded.rent, maintenance=excluded.maintenance,
            parking=excluded.parking, repair=excluded.repair, bike_charge=excluded.bike_charge,
            electricity=payments.electricity, paid_on=excluded.paid_on""",
            (flat_id, month, values.get("rent", 0), values.get("maintenance", 0), values.get("parking", 0),
             values.get("repair", 0), values.get("bike", 0), values.get("electricity", 0), date.today().isoformat()),
        )
        self.connection.commit()

    def record_electricity(self, flat_id: int, month: str, values: dict[str, float]) -> None:
        self.connection.execute(
            """INSERT INTO payments (flat_id, month, rent, maintenance, parking, repair, bike_charge, electricity, paid_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(flat_id, month) DO UPDATE SET rent=excluded.rent, maintenance=excluded.maintenance,
            parking=excluded.parking, repair=excluded.repair, bike_charge=excluded.bike_charge,
            electricity=payments.electricity, paid_on=excluded.paid_on""",
            (flat_id, month, values.get("rent", 0), values.get("maintenance", 0), values.get("parking", 0),
             values.get("repair", 0), values.get("bike", 0), values.get("electricity", 0), date.today().isoformat()),
        )
        self.connection.commit()

    def update_tenant(self, flat_id: int, name: str, phone: str, notes: str, vacating_date: str, advance_amount: float) -> None:
        self.connection.execute(
            "UPDATE flats SET tenant_name = ?, phone = ?, tenant_notes = ?, vacating_date = ?, advance_amount = ? WHERE id = ?",
            (name.strip(), phone.strip(), notes.strip(), vacating_date.strip(), advance_amount, flat_id),
        )
        self.connection.commit()

    def vacating_flats(self, month: str | None = None) -> list[dict[str, Any]]:
        rows = [flat for flat in self.flats(month) if flat.get("vacating_date")]
        return sorted(rows, key=lambda flat: flat["vacating_date"])

    def close(self) -> None:
        self.connection.close()
