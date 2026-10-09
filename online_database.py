from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from typing import Any


class OnlineRentalDatabase:
    """Supabase REST-backed database with the same API as RentalDatabase."""

    def __init__(self, url: str | None = None, anon_key: str | None = None):
        self.url = (url or os.environ["SUPABASE_URL"]).rstrip("/")
        self.anon_key = anon_key or os.environ["SUPABASE_ANON_KEY"]
        self.headers = {
            "apikey": self.anon_key,
            "Authorization": f"Bearer {self.anon_key}",
            "Content-Type": "application/json",
        }

    def _request(self, table: str, method: str = "GET", query: str = "", body: Any = None, prefer: str | None = None):
        request = urllib.request.Request(
            f"{self.url}/rest/v1/{table}{query}",
            data=None if body is None else json.dumps(body).encode("utf-8"),
            headers={**self.headers, **({"Prefer": prefer} if prefer else {})},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                raw = response.read()
                return json.loads(raw.decode("utf-8")) if raw else []
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Supabase request failed ({error.code}): {details}") from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"Supabase is unreachable: {error.reason}") from error

    def authenticate(self, username: str, password: str) -> bool:
        params = urllib.parse.urlencode({"username": f"eq.{username.strip()}", "password": f"eq.{password}", "select": "id"})
        return bool(self._request("users", query=f"?{params}"))

    def _payments(self, month: str) -> dict[int, dict[str, Any]]:
        params = urllib.parse.urlencode({"month": f"eq.{month}", "select": "*"})
        return {row["flat_id"]: row for row in self._request("payments", query=f"?{params}")}

    def flats(self, month: str | None = None) -> list[dict[str, Any]]:
        month = month or date.today().strftime("%Y-%m")
        params = urllib.parse.urlencode({"select": "*", "order": "flat_number.asc"})
        payments = self._payments(month)
        result = []
        for item in self._request("flats", query=f"?{params}"):
            payment = payments.get(item["id"], {})
            for key, field in (("paid_rent", "rent"), ("paid_maintenance", "maintenance"), ("paid_parking", "parking"), ("paid_repair", "repair"), ("paid_bike_charge", "bike_charge"), ("paid_electricity", "electricity")):
                item[key] = float(payment.get(field, 0) or 0)
            item["electricity_arrears"] = float(item.get("electricity_arrears", 0) or 0)
            item["total_due"] = sum(float(item.get(key, 0) or 0) for key in ("monthly_rent", "maintenance", "parking", "repair", "bike_charge")) + float(item.get("electricity_due", 0) or 0) + float(item.get("electricity_arrears", 0) or 0)
            item["total_paid"] = sum(item[key] for key in ("paid_rent", "paid_maintenance", "paid_parking", "paid_repair", "paid_bike_charge", "paid_electricity"))
            item["balance"] = max(item["total_due"] - item["total_paid"], 0)
            result.append(item)
        return result

    def summary(self, month: str | None = None) -> dict[str, float]:
        rows = self.flats(month)
        return {"rent": sum(row["paid_rent"] for row in rows), "maintenance": sum(row["paid_maintenance"] for row in rows), "parking": sum(row["paid_parking"] for row in rows), "bike": sum(row["paid_bike_charge"] for row in rows), "electricity": sum(row["paid_electricity"] for row in rows), "due": sum(row["total_due"] for row in rows), "paid": sum(row["total_paid"] for row in rows), "balance": sum(row["balance"] for row in rows)}

    def record_payment(self, flat_id: int, month: str, values: dict[str, float]) -> None:
        params = urllib.parse.urlencode({"flat_id": f"eq.{flat_id}", "month": f"eq.{month}"})
        body = {"flat_id": flat_id, "month": month, "rent": values.get("rent", 0), "maintenance": values.get("maintenance", 0), "parking": values.get("parking", 0), "repair": values.get("repair", 0), "bike_charge": values.get("bike", 0), "paid_on": date.today().isoformat()}
        existing = self._request("payments", query=f"?{params}&select=id")
        if existing:
            self._request("payments", method="PATCH", query=f"?{params}", body=body, prefer="return=minimal")
        else:
            self._request("payments", method="POST", body=body, prefer="return=minimal")

    def update_electricity(self, flat_id: int, due: float, paid: float, arrears: float = 0) -> None:
        params = urllib.parse.urlencode({"id": f"eq.{flat_id}"})
        self._request("flats", method="PATCH", query=f"?{params}", body={"electricity_due": due, "electricity_paid": paid, "electricity_arrears": arrears}, prefer="return=minimal")

    def update_tenant(self, flat_id: int, name: str, phone: str, notes: str, vacating_date: str, advance_amount: float) -> None:
        params = urllib.parse.urlencode({"id": f"eq.{flat_id}"})
        body = {"tenant_name": name.strip(), "phone": phone.strip(), "tenant_notes": notes.strip(), "vacating_date": vacating_date.strip(), "advance_amount": advance_amount}
        self._request("flats", method="PATCH", query=f"?{params}", body=body, prefer="return=minimal")

    def vacating_flats(self, month: str | None = None) -> list[dict[str, Any]]:
        return sorted((flat for flat in self.flats(month) if flat.get("vacating_date")), key=lambda flat: flat["vacating_date"])

    def close(self) -> None:
        pass
