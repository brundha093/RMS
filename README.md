# మన ఇల్లు · Rental Manager

Telugu-first Python/Kivy rental management app for an owner managing 17 flats.

## Features

- Owner login backed by SQLite (`owner` / `owner123` for the initial demo).
- 17 flat records seeded on first run.
- Monthly rent, maintenance, parking, repair, electric-bike, and electricity payment fields.
- Clear total due, paid, and balance summaries.
- Manual SMS reminder button for each flat; Android opens the SMS composer for confirmation.
- `integrations.py` provides the APSPDCL automation insertion point.
- The Electricity screen can launch `fetch_apspdcl_bill.py` after confirmation.
- `import_excel.py` imports common English/Telugu workbook headers into SQLite.
- The bundled Noto Sans Telugu font is used consistently on desktop and Android.
- Supabase/PostgreSQL support is available through `online_database.py`.

## Run on desktop

```powershell
python -m pip install -r requirements.txt
python app.py
```

If Kivy is not available for the selected Python version, use a Python 3.11 virtual environment before installing requirements.

## Load Excel flat data

Run this once after installing the requirements:

```powershell
python import_excel.py Excel.xlsx
```

The importer updates matching flat numbers and leaves the payment history intact.

## Fetch APSPDCL bills

The Electricity screen's **FETCH APSPDCL BILLS** button runs
`fetch_apspdcl_bill.py`. It requires a running Appium server, a connected
Android device with the APSPDCL app installed, `Excel.xlsx` beside the script,
and the `OPENROUTER_API_KEY` environment variable. Copy `.env.example` to
`.env` and fill in the required values. The script writes
`electricity_bills.json`; email reporting also needs the email settings in
`.env`.

## Use shared online data

1. Create a Supabase project.
2. Run `supabase_schema.sql` in the Supabase SQL Editor.
3. Copy `supabase_config.py.example` to `supabase_config.py` and add the project URL and public anon key.
4. Migrate the existing local data:

```powershell
python migrate_to_supabase.py
```

When the two Supabase values are configured, the app fetches flats and monthly
payments from PostgreSQL on load and writes payment, tenant, and electricity
updates back to the shared database. Without them, it continues to use local
SQLite.

The included SQL policies are suitable for initial testing only. Before
production, replace the demo username/password table and open anon policies
with Supabase Auth and row-level security policies.

## Build the Android APK

Buildozer is normally run in Linux, WSL2, or CI:

```bash
buildozer android debug
```

The resulting debug APK is placed in `bin/`. The Android build requests `INTERNET` and `SEND_SMS` permissions. The owner still confirms each SMS in the device messaging app.

The APK is standalone: on first launch it copies the bundled populated
`rental_manager.db` into Android's writable private app directory. Subsequent
payments and tenant edits are stored there and survive app restarts. This is
local storage per phone; using the same records across multiple phones still
requires the hosted PostgreSQL/Supabase backend described below.

The Android dependency chain includes Pillow, FreeType, and HarfBuzz for font
loading and complex-script shaping. The current upstream python-for-android
recipe set does not provide a `libraqm` recipe; adding `libraqm` directly to
`requirements` would stop the build with an unknown-recipe error. If Pillow
features that specifically require Raqm are later needed, add a custom
python-for-android Raqm recipe together with its FriBidi dependency.

## Production checklist

- Replace the demo password with a salted password hash and add remote authentication.
- Move SQLite to a hosted API/database for access from multiple devices.
- Build the Android APK from WSL2/Linux with `buildozer android debug`.
- Implement `fetch_apspdcl_bill()` with the owner’s APSPDCL automation adapter.
- Add encrypted backups and role-based users before deployment.
