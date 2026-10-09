from __future__ import annotations

from datetime import date
from functools import partial
from pathlib import Path
import os
import shutil
import subprocess
import sys
import threading

os.environ.setdefault("KIVY_TEXT", "pil")
import time
from kivy.app import App
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import platform

from database import RentalDatabase
from integrations import send_due_sms
from online_database import OnlineRentalDatabase

try:
    from supabase_config import SUPABASE_URL, SUPABASE_ANON_KEY
except ImportError:
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

Window.clearcolor = (0.95, 0.96, 0.94, 1)
TELUGU_FONT = "TeluguFont"
FONT_NAME = TELUGU_FONT
FONT_PATH = Path(__file__).resolve().parent / "fonts" / "NotoSansTelugu-Regular.ttf"
if not FONT_PATH.exists():
    raise FileNotFoundError(f"Telugu font not found: {FONT_PATH}")
LabelBase.register(name=TELUGU_FONT, fn_regular=str(FONT_PATH))

# Use the bundled font for standard Kivy text widgets as well.
Label.font_name = TELUGU_FONT
Button.font_name = TELUGU_FONT


class TeluguLabel(Label):
    def __init__(self, **kwargs):
        kwargs.setdefault("font_name", TELUGU_FONT)
        super().__init__(**kwargs)


class TeluguButton(Button):
    def __init__(self, **kwargs):
        kwargs.setdefault("font_name", FONT_NAME)
        super().__init__(**kwargs)


class TeluguInput(TextInput):
    def __init__(self, **kwargs):
        kwargs.setdefault("font_name", FONT_NAME)
        super().__init__(**kwargs)


def apply_font_to_tree(widget):
    """Keep all current and newly composed Kivy text widgets consistent."""
    if hasattr(widget, "font_name"):
        widget.font_name = FONT_NAME
    for child in widget.children:
        apply_font_to_tree(child)


UiLabel = TeluguLabel
UiButton = TeluguButton
UiInput = TeluguInput

INK = (0.08, 0.18, 0.16, 1)
MUTED = (0.34, 0.4, 0.37, 1)
GREEN = (0.12, 0.42, 0.34, 1)
RED = (0.78, 0.3, 0.14, 1)


class PaymentView(ModalView):
    def __init__(self, flat: dict, save_callback, **kwargs):
        super().__init__(size_hint=(0.94, 0.84), background_color=(1, 1, 1, 1), **kwargs)
        self.flat = flat
        self.save_callback = save_callback
        self.inputs: dict[str, TextInput] = {}
        layout = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(8))
        layout.add_widget(Label(text=f"Flat {flat['flat_number']} · Payment", font_size=dp(20), color=INK, size_hint_y=None, height=dp(44)))
        scroll = ScrollView(do_scroll_x=False)
        grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, padding=(0, 0, 0, dp(10)))
        grid.bind(minimum_height=grid.setter("height"))
        fields = {"rent": ("Rent", "paid_rent"), "maintenance": ("Maintenance", "paid_maintenance"), "parking": ("Parking", "paid_parking"), "repair": ("Repairs", "paid_repair"), "bike": ("Electric Bike", "paid_bike_charge")}
        for key, (title, paid_field) in fields.items():
            grid.add_widget(Label(text=title, color=MUTED, size_hint_y=None, height=dp(42), halign="left"))
            field = TextInput(text=str(int(flat[paid_field])), input_filter="float", multiline=False, size_hint_y=None, height=dp(42))
            self.inputs[key] = field
            grid.add_widget(field)
        scroll.add_widget(grid)
        layout.add_widget(scroll)
        message = Label(text="", color=RED, size_hint_y=None, height=dp(32))
        layout.add_widget(message)
        actions = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        cancel = Button(text="Cancel", background_color=(0.84, 0.86, 0.83, 1), color=INK)
        save = Button(text="Save Payment", background_color=GREEN)
        cancel.bind(on_release=self.dismiss)
        save.bind(on_release=lambda *_: self._save(message))
        actions.add_widget(cancel)
        actions.add_widget(save)
        layout.add_widget(actions)
        self.add_widget(layout)
        apply_font_to_tree(self)


    def _save(self, message: Label) -> None:
        try:
            values = {key: float(field.text or 0) for key, field in self.inputs.items()}
        except ValueError:
            message.text = "Enter valid amounts."
            return
        self.save_callback(self.flat["id"], values)
        self.dismiss()

class ElectricityView(ModalView):
    def __init__(self, flat: dict, save_callback, **kwargs):
        super().__init__(size_hint=(0.94, 0.84), background_color=(1, 1, 1, 1), **kwargs)
        self.flat = flat
        self.save_callback = save_callback
        self.inputs: dict[str, TextInput] = {}
        layout = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(8))
        layout.add_widget(Label(text=f"Flat {flat['flat_number']} · Electricity Bill", font_size=dp(20), color=INK, size_hint_y=None, height=dp(44)))
        scroll = ScrollView(do_scroll_x=False)
        grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, padding=(0, 0, 0, dp(10)))
        grid.bind(minimum_height=grid.setter("height"))
        fields = {"elect": ("Electricity", "paid_electricity")}
        for key, (title, paid_field) in fields.items():
            grid.add_widget(Label(text=title, color=MUTED, size_hint_y=None, height=dp(42), halign="left"))
            field = TextInput(text=str(int(flat[paid_field])), input_filter="float", multiline=False, size_hint_y=None, height=dp(42))
            self.inputs[key] = field
            grid.add_widget(field)
        scroll.add_widget(grid)
        layout.add_widget(scroll)
        message = Label(text="", color=RED, size_hint_y=None, height=dp(32))
        layout.add_widget(message)
        actions = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        cancel = Button(text="Cancel", background_color=(0.84, 0.86, 0.83, 1), color=INK)
        save = Button(text="Save Bill", background_color=GREEN)
        cancel.bind(on_release=self.dismiss)
        save.bind(on_release=lambda *_: self._save(message))
        actions.add_widget(cancel)
        actions.add_widget(save)
        layout.add_widget(actions)
        self.add_widget(layout)
        apply_font_to_tree(self)


    def _save(self, message: Label) -> None:
        try:
            values = {key: float(field.text or 0) for key, field in self.inputs.items()}
        except ValueError:
            message.text = "Enter valid amounts."
            return
        self.save_callback(self.flat["id"], values)
        self.dismiss()



class TenantView(ModalView):
    def __init__(self, flat: dict, save_callback, **kwargs):
        super().__init__(size_hint=(0.94, 0.78), background_color=(1, 1, 1, 1), **kwargs)
        self.flat = flat
        self.save_callback = save_callback
        self.validation_message = Label(text="", color=RED, size_hint_y=None, height=dp(32))
        form = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(9))
        form.add_widget(Label(text=f"Flat {flat['flat_number']} · Tenant details", font_size=dp(20), color=INK, size_hint_y=None, height=dp(44)))
        form.add_widget(Label(text="Tenant name and mobile number are required.", color=MUTED, size_hint_y=None, height=dp(38)))
        self.fields = {}
        for key, hint, value in (("name", "Tenant name", flat["tenant_name"]), ("phone", "Mobile number", flat["phone"]), ("advance_amount", "Advance amount", str(flat.get("advance_amount", 0))), ("notes", "Notes", flat.get("tenant_notes", "")), ("vacating_date", "Vacating date (YYYY-MM-DD)", flat.get("vacating_date", ""))):
            field = TextInput(text=value, hint_text=hint, input_filter="float" if key == "advance_amount" else None, multiline=False, size_hint_y=None, height=dp(44))
            self.fields[key] = field
            form.add_widget(field)
        form.add_widget(self.validation_message)
        actions = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(48))
        close = Button(text="Cancel", background_color=(0.84, 0.86, 0.83, 1), color=INK)
        save = Button(text="Save tenant details", background_color=GREEN)
        close.bind(on_release=self.dismiss)
        save.bind(on_release=self._save)
        actions.add_widget(close)
        actions.add_widget(save)
        form.add_widget(actions)
        self.add_widget(form)
        apply_font_to_tree(self)

    def _save(self, *_):
        name = self.fields["name"].text.strip()
        phone = self.fields["phone"].text.strip()
        if not name or not phone:
            self.validation_message.text = "Enter the tenant name and mobile number."
            return
        try:
            advance_amount = float(self.fields["advance_amount"].text or 0)
        except ValueError:
            self.validation_message.text = "Enter a valid advance amount."
            return
        values = {key: field.text for key, field in self.fields.items()}
        values["advance_amount"] = advance_amount
        self.save_callback(self.flat["id"], values)
        self.dismiss()


class RentalApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.database: RentalDatabase | None = None
        self.month = date.today().strftime("%Y-%m")
        self.content = None
        self.missing_details_prompted = False
        self.bill_fetch_running = False
        self.bill_fetch_button: Button | None = None
        self.bill_fetch_status: Label | None = None
        self.bill_fetch_status_text = "Ready."

    def build(self):
        self.title = "మన ఇల్లు · అద్దె నిర్వహణ"
        if SUPABASE_URL and SUPABASE_ANON_KEY:
            self.database = OnlineRentalDatabase(SUPABASE_URL, SUPABASE_ANON_KEY)
            self.database_backend = "supabase"
        elif platform == "android":
            data_dir = Path(self.user_data_dir)
            data_dir.mkdir(parents=True, exist_ok=True)
            database_path = data_dir / "rental_manager.db"
            bundled_database = Path(__file__).resolve().parent / "rental_manager.db"
            if not database_path.exists() and bundled_database.exists():
                shutil.copy2(bundled_database, database_path)
            self.database = RentalDatabase(str(database_path))
            self.database_backend = "sqlite-local"
        else:
            self.database = RentalDatabase()
            self.database_backend = "sqlite-local"
        login = self.login_screen()
        apply_font_to_tree(login)
        return login

    def login_screen(self):
        root = BoxLayout(orientation="vertical", padding=dp(28), spacing=dp(16))
        root.add_widget(TeluguLabel(text="Mana Illu", font_size=dp(30), bold=True, color=GREEN, size_hint_y=None, height=dp(84), valign="middle", padding_y=dp(8)))
        root.add_widget(TeluguLabel(text="Tenant Management", font_size=dp(20), color=INK, size_hint_y=None, height=dp(54), valign="middle", padding_y=dp(6)))
        root.add_widget(TeluguLabel(text="Login", font_size=dp(18), color=MUTED, size_hint_y=None, height=dp(52), valign="middle", padding_y=dp(6)))
        username = TextInput(hint_text="Username", multiline=False, size_hint_y=None, height=dp(48))
        password = TextInput(hint_text="Password", password=True, multiline=False, size_hint_y=None, height=dp(48))
        status = Label(text="", color=RED, size_hint_y=None, height=dp(38))
        login = Button(text="Log in", size_hint_y=None, height=dp(52), background_color=GREEN)
        login.bind(on_release=lambda *_: self._login(username.text, password.text, status))
        for widget in (username, password, login, status):
            root.add_widget(widget)
        root.add_widget(Label(text="Demo: owner / owner123", color=MUTED, size_hint_y=None, height=dp(42), valign="middle", padding_y=dp(5)))
        return root

    def _login(self, username: str, password: str, status: Label) -> None:
        if self.database.authenticate(username, password):
            self.show_app()
        else:
            status.text = "Incorrect username or password."

    def show_app(self):
        self.content = BoxLayout(orientation="vertical")
        self.root.clear_widgets()
        self.root.add_widget(self.content)
        apply_font_to_tree(self.root)
        self.navigate("dashboard")
        Clock.schedule_once(self.prompt_missing_tenant_details, 0.3)

    def prompt_missing_tenant_details(self, *_):
        if self.missing_details_prompted:
            return
        missing = next(
            (flat for flat in self.database.flats(self.month) if not flat["tenant_name"] or not flat["phone"]),
            None,
        )
        if missing:
            self.missing_details_prompted = True
            TenantView(missing, self.save_tenant).open()

    def navigate(self, menu: str, *_):
        self.content.clear_widgets()
        self.content.add_widget(self.menu_screen(menu))
        nav = BoxLayout(size_hint_y=None, height=dp(68), spacing=dp(3), padding=(dp(3), dp(4)))
        items = (("dashboard", "హోమ్"), ("tenants", "టెనెంట్లు"), ("pending", "బకాయిలు"), ("electricity", "కరెంట్"), ("vacating", "ఖాళీ"))
        for key, title in items:
            button = Button(text=title, font_size=dp(13), background_color=GREEN if key == menu else (0.83, 0.87, 0.83, 1), color=(1, 1, 1, 1) if key == menu else INK)
            button.bind(on_release=partial(self.navigate, key))
            nav.add_widget(button)
        self.content.add_widget(nav)
        apply_font_to_tree(self.content)

    def menu_screen(self, menu: str):
        root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(9))
        titles = {"dashboard": "Dashboard", "tenants": "Tenant Details", "pending": "Pending Amounts", "electricity": "Electricity", "vacating": "Vacating"}
        root.add_widget(Label(text=titles[menu], font_size=dp(24), bold=True, color=INK, size_hint_y=None, height=dp(48), halign="left"))
        root.add_widget(Label(text=f"Month: {self.month} · Total flats: 17", color=MUTED, size_hint_y=None, height=dp(28), halign="left"))
        if menu == "dashboard":
            root.add_widget(self.dashboard_body())
        elif menu == "tenants":
            root.add_widget(self.list_body(self.tenant_card, self.database.flats(self.month)))
        elif menu == "pending":
            root.add_widget(self.list_body(self.pending_card, [flat for flat in self.database.flats(self.month) if flat["balance"] > 0]))
        elif menu == "electricity":
            self.bill_fetch_button = Button(
                text="FETCH APSPDCL BILLS",
                size_hint_y=None,
                height=dp(44),
                background_color=(0.25, 0.52, 0.72, 1),
                disabled=self.bill_fetch_running,
            )
            self.bill_fetch_button.bind(on_release=self.confirm_bill_fetch)
            root.add_widget(self.bill_fetch_button)
            self.bill_fetch_status = Label(
                text=self.bill_fetch_status_text,
                color=MUTED,
                size_hint_y=None,
                height=dp(54),
                halign="left",
                valign="middle",
                text_size=(Window.width - dp(28), None),
            )
            root.add_widget(self.bill_fetch_status)
            root.add_widget(self.list_body(self.electricity_card, self.database.flats(self.month)))
        else:
            root.add_widget(self.list_body(self.vacating_card, self.database.vacating_flats(self.month), empty="No tenants are marked as moving out."))
        return root

    def confirm_bill_fetch(self, *_):
        confirmation = ModalView(size_hint=(0.9, 0.42), auto_dismiss=False)
        layout = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        layout.add_widget(Label(
            text="This will use Appium to check bills, save a JSON report, and send bill details to an AI service and by email. Continue?",
            color=INK,
            halign="center",
        ))
        actions = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        cancel = Button(text="Cancel", background_color=(0.84, 0.86, 0.83, 1), color=INK)
        run = Button(text="Continue", background_color=GREEN)
        cancel.bind(on_release=confirmation.dismiss)
        run.bind(on_release=lambda *_: self.start_bill_fetch(confirmation))
        actions.add_widget(cancel)
        actions.add_widget(run)
        layout.add_widget(actions)
        confirmation.add_widget(layout)
        apply_font_to_tree(confirmation)
        confirmation.open()

    def start_bill_fetch(self, confirmation: ModalView):
        confirmation.dismiss()
        if self.bill_fetch_running:
            return
        self.bill_fetch_running = True
        self.bill_fetch_status_text = "Fetching APSPDCL bills..."
        if self.bill_fetch_button is not None:
            self.bill_fetch_button.disabled = True
        if self.bill_fetch_status is not None:
            self.bill_fetch_status.text = self.bill_fetch_status_text
        threading.Thread(target=self._run_bill_fetch, daemon=True).start()

    def _run_bill_fetch(self):
        script_path = Path(__file__).resolve().parent / "fetch_apspdcl_bill.py"
        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(script_path.parent),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            return_code = result.returncode
            output = (result.stdout + "\n" + result.stderr).strip()
        except OSError as error:
            return_code = None
            output = str(error)
        Clock.schedule_once(
            partial(self._bill_fetch_completed, return_code, output),
            0,
        )

    def _bill_fetch_completed(self, return_code: int | None, output: str, *_):
        self.bill_fetch_running = False
        email_error = next(
            (line for line in output.splitlines() if "Could not send email report:" in line),
            None,
        )
        if return_code == 0 and email_error is None:
            self.bill_fetch_status_text = "Bill fetch completed."
        elif return_code == 0:
            self.bill_fetch_status_text = f"Bill fetch completed, but email reporting failed:\n{email_error}"
        else:
            details = output[-800:] or "The script exited without additional output."
            self.bill_fetch_status_text = f"Bill fetch failed (exit code {return_code}).\n{details}"
        if self.bill_fetch_button is not None:
            self.bill_fetch_button.disabled = False
        if self.bill_fetch_status is not None:
            self.bill_fetch_status.text = self.bill_fetch_status_text

    def list_body(self, builder, records, empty="No records found."):
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(8))
        stack = GridLayout(cols=1, spacing=dp(9), size_hint_y=None, padding=(0, 0, 0, dp(22)))
        stack.bind(minimum_height=stack.setter("height"))
        if not records:
            stack.add_widget(Label(text=empty, color=MUTED, size_hint_y=None, height=dp(70)))
        for record in records:
            stack.add_widget(builder(record))
        scroll.add_widget(stack)
        return scroll

    def dashboard_body(self):
        box = BoxLayout(orientation="vertical", spacing=dp(10))
        summary = self.database.summary(self.month)
        grid = GridLayout(cols=2, spacing=dp(6), size_hint_y=None, height=dp(118))
        for title, amount, color in (("Total due", summary["due"], (0.82, 0.55, 0.12, 1)), ("Total paid", summary["paid"], (0.12, 0.5, 0.31, 1)), ("Balance", summary["balance"], RED), ("Electricity paid", summary["electricity"], (0.2, 0.45, 0.7, 1))):
            card = BoxLayout(orientation="vertical", padding=dp(7))
            card.add_widget(Label(text=title, font_size=dp(12), color=MUTED, halign="left"))
            card.add_widget(Label(text=f"₹{amount:,.0f}", font_size=dp(16), bold=True, color=color, halign="left"))
            grid.add_widget(card)
        box.add_widget(grid)
        box.add_widget(self.list_body(self.dashboard_card, self.database.flats(self.month)))
        return box

    def base_card(self, height=dp(100)):
        return BoxLayout(orientation="vertical", padding=dp(11), spacing=dp(4), size_hint_y=None, height=height)

    def dashboard_card(self, flat):
        card = self.base_card(dp(128))
        status = "Paid in full" if flat["balance"] == 0 else "Balance pending"
        status_color = GREEN if flat["balance"] == 0 else RED
        card.add_widget(Label(text=f"Flat {flat['flat_number']}  ·  {flat['tenant_name'] or 'Tenant details not entered'}", bold=True, color=INK, halign="left", size_hint_y=None, height=dp(28)))
        card.add_widget(Label(text=f"Mobile: {flat['phone'] or 'Not available'}  |  Electricity no: {flat['electricity_number']}", color=MUTED, halign="left", size_hint_y=None, height=dp(26)))
        card.add_widget(Label(text=f"Rent ₹{flat['monthly_rent']:,.0f}  |  Maintenance ₹{flat['maintenance']:,.0f}  |  Parking ₹{flat['parking']:,.0f}", color=MUTED, halign="left", size_hint_y=None, height=dp(26)))
        card.add_widget(Label(text=f"Due ₹{flat['total_due']:,.0f}  |  Paid ₹{flat['total_paid']:,.0f}  |  Balance ₹{flat['balance']:,.0f}  ·  {status}", color=status_color, halign="left", size_hint_y=None, height=dp(28)))
        card.add_widget(Label(text="────────────────────────────────", color=(0.72, 0.75, 0.72, 1), size_hint_y=None, height=dp(20), halign="center"))
        return card

    def tenant_card(self, flat):
        card = self.base_card(dp(108))
        card.add_widget(Label(text=f"FLAT {flat['flat_number']} · {flat['tenant_name'] or 'NAME NOT REGISTERED'}", bold=True, color=INK, halign="left"))
        card.add_widget(Label(text=f"Mobile: {flat['phone'] or 'NOT AVAILABLE'} | Advance: ₹{flat.get('advance_amount', 0):,.0f} | Electricity number: {flat['electricity_number']}", color=MUTED, halign="left"))
        edit = Button(text="UPDATE TENANT DETAILS", size_hint_y=None, height=dp(36), background_color=GREEN)
        edit.bind(on_release=partial(self.open_tenant, flat))
        card.add_widget(edit)
        return card

    def pending_card(self, flat):
        card = self.base_card(dp(116))
        card.add_widget(Label(text=f"FLAT {flat['flat_number']} · {flat['tenant_name'] or 'ఖాళీ'}", bold=True, color=INK, halign="left"))
        card.add_widget(Label(text=f"DUE ₹{flat['total_due']:,.0f} | DONE ₹{flat['total_paid']:,.0f} | Balance ₹{flat['balance']:,.0f}", color=RED, halign="left"))
        actions = BoxLayout(spacing=dp(6), size_hint_y=None, height=dp(36))
        sms = Button(text="Send SMS", background_color=(0.25, 0.52, 0.72, 1))
        sms.bind(on_release=partial(self.send_reminder, flat))
        payment = Button(text="UPDATE PAYMENT DETAILS", background_color=GREEN)
        payment.bind(on_release=partial(self.open_payment, flat))
        actions.add_widget(sms)
        actions.add_widget(payment)
        card.add_widget(actions)
        return card

    def electricity_card(self, flat):
        card = self.base_card(dp(112))
        paid = flat["paid_electricity"]
        due = flat["electricity_due"]
        card.add_widget(Label(text=f"FLAT {flat['flat_number']} · METER: {flat['electricity_number']}", bold=True, color=INK, halign="left"))
        card.add_widget(Label(text=f"BILL ₹{due:,.0f} | PAID ₹{paid:,.0f} | DUE ₹{max(due - paid, 0):,.0f}", color=MUTED, halign="left"))
        sync = Button(text="SYNC ELECTRICITY BILL", size_hint_y=None, height=dp(36), background_color=(0.25, 0.52, 0.72, 1))
        sync.bind(on_release=partial(self.open_electricity, flat))
        card.add_widget(sync)
        return card

    def vacating_card(self, flat):
        card = self.base_card(dp(94))
        card.add_widget(Label(text=f"FLAT {flat['flat_number']} · {flat['tenant_name'] or 'NAME NOT REGISTERED'}", bold=True, color=INK, halign="left"))
        card.add_widget(Label(text=f"VACATING DATE: {flat['vacating_date']} | PHONE: {flat['phone'] or 'NOT REGISTERED'}", color=RED, halign="left"))
        return card

    def open_payment(self, flat, *_):
        PaymentView(flat, self.save_payment).open()

    def open_tenant(self, flat, *_):
        TenantView(flat, self.save_tenant).open()

    def open_electricity(self, flat, *_):
        ElectricityView(flat, self.save_electricity).open()

    def save_payment(self, flat_id: int, values: dict[str, float]):
        self.database.record_payment(flat_id, self.month, values)
        self.navigate("pending")

    def save_electricity(self, flat_id: int, values: dict[str, float]):
        self.database.record_electricity(flat_id, self.month, values)
        self.navigate("electricity")

    def save_tenant(self, flat_id: int, values: dict[str, str]):
        self.database.update_tenant(flat_id, values["name"], values["phone"], values["notes"], values["vacating_date"], values["advance_amount"])
        self.navigate("tenants")

    def send_reminder(self, flat: dict, *_):
        print("Sending SMS reminder to flat", flat["flat_number"], "at", flat["phone"])
        time.sleep(5)
        send_due_sms(flat["phone"], flat["flat_number"], flat["balance"])

    def on_stop(self):
        self.database.close()


if __name__ == "__main__":
    RentalApp().run()
