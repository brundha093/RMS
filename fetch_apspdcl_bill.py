########################################################################
# before start of this file please run "appium" in the command prompt to start the appium server and then run this script

"""
The Requirement here is earlier to manage the tenant rents we need to maintain a ledger and manually enter each month rent details

also the electricity bills get due every month and we need to check the electricity bills for each flat and then update the ledger with the details

so to solve this manual process an app was developed this app

"""

##############################################################################
import os
import json
import smtplib
from email.message import EmailMessage
from pathlib import Path
from datetime import datetime, timezone
import requests
import openpyxl
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from openai import OpenAI
from dotenv import load_dotenv
from appium.webdriver.extensions.android.nativekey import AndroidKey

# Load variables from .env file into environment
load_dotenv()

username = os.getenv("APP_USERNAME")
password = os.getenv("APP_PASSWORD")
email = os.getenv("APP_EMAIL")

def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value

def is_non_empty_json(data) -> tuple[bool, str]:
    """
    Checks if input is valid JSON/dict/list and non-empty.
    Returns (True, "Success message") or (False, "Error message").
    """
    # 1. If input is a raw JSON string
    if isinstance(data, str):
        if not data.strip():
            return False, "Input is an empty or whitespace-only string."
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON syntax: {e.msg} at line {e.lineno}, column {e.colno}"

    # 2. Check for None
    if data is None:
        return False, "Data is None."

    # 3. Check for empty collection structures ({}, [], "", set)
    if isinstance(data, (dict, list, str, set)) and len(data) == 0:
        return False, f"JSON data structure is empty ({type(data).__name__})."

    # 4. Ensure data is a valid JSON object or array top-level structure
    if not isinstance(data, (dict, list)):
        return False, f"Expected a JSON object (dict) or array (list), but got {type(data).__name__}."

    return True, "JSON data is valid and non-empty."

def send_summary_json_by_email(bill_records: list[dict[str, object]]) -> None:
    # if os.getenv("SEND_BILL_EMAIL", "false").lower() != "true":
    #     print("Email disabled; set SEND_BILL_EMAIL=true to send the JSON report.")
    #     return
    
 
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=required("OPENROUTER_API_KEY"),
    )
    # Your sample JSON data
    json_data = json.dumps(bill_records, ensure_ascii=False, indent=2)
    print("The statementis**************")
    print(is_non_empty_json(json_data))
    if is_non_empty_json(json_data) == False:
        assert False, "The JSON data is empty or invalid. Please check the input."

    # Convert JSON data to a string
        
    
    # Formulate the prompt combining the JSON and your query
   

    prompt = f"Here is the JSON data:\n{json_data}\n\n"
    system_prompt= """You are a professional Telugu translator and data analyst.

            Analyze the JSON data provided below and generate a clear, accurate summary.

            Your tasks:

            1. Identify all tenants whose bill is currently DUE/UNPAID.
            2. For each tenant with a due/unpaid bill, provide:
            - Flat Number
            - Tenant Name
            - Phone Number
            - Due Amount (if available)
            3. Separately identify all tenants whose bill has already been PAID.
            4. For paid tenants, provide:
            - Flat Number
            - Tenant Name
            - Phone Number
            - Paid Amount (if available)
            5. Do not assume or invent any information that is not present in the JSON.
            6. If a field is missing, write "Not available".
            7. Treat payment status carefully:
            - PAID = bill has been paid
            - DUE/UNPAID/PENDING = bill has not been paid
            - If the status is unclear, put the tenant under "Status unclear" rather than guessing.
            8. Give the final response entirely in fluent, natural Telugu.
            9. Keep names, flat numbers, and phone numbers exactly as they appear in the JSON.
            10. Present the result in clearly separated sections.

            Use this format:

            బిల్లు చెల్లించాల్సిన వారు:
            1. ఫ్లాట్ నంబర్: ___
            పేరు: ___
            ఫోన్ నంబర్: ___
            బకాయి మొత్తం: ___

            చెల్లించిన వారు:
            1. ఫ్లాట్ నంబర్: ___
            పేరు: ___
            ఫోన్ నంబర్: ___
            చెల్లించిన మొత్తం: ___

            స్థితి స్పష్టంగా లేని వారు:
            1. ఫ్లాట్ నంబర్: ___
            పేరు: ___
            ఫోన్ నంబర్: ___
            వివరాలు: ___

            చివరగా:
            మొత్తం బకాయి ఉన్నవారు: ___
            మొత్తం చెల్లించినవారు: ___
            స్థితి స్పష్టంగా లేనివారు: ___

            JSON Data:
            {{JSON_DATA}}
                """
    response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
            ],
    )

    chatgpt_output = response.choices[0].message.content
        
    
    # Print the result
    output =response.choices[0].message.content
    print("ChatGPT Output:\n", output)
    
  

# Set up email details from environment variables
    sender= os.getenv("SENDER_EMAIL")
    app_password = os.getenv("EMAIL_PASSWORD")
    smtp_server = "smtp.gmail.com"
    smtp_port = 587


    recipient = os.getenv("RECEPIENT_EMAIL")
  

    current_date = datetime.now()

# 2. Format it to "bb yyyy" (e.g., "Sep 2026")
    formatted_date = current_date.strftime("%b %Y")

    print(formatted_date)
    
    message = EmailMessage()
    message["Subject"] = "హాయ్ స్వర్ణ, ఈ నెల బాకీ ఉన్న అద్దెదారుల వివరాలు"+" (" + formatted_date + ")"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(output)
    message.add_attachment(
         json_data.encode("utf-8"),
         maintype="application",
         subtype="json",
         filename="electricity_bills.json",
     )

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(sender, app_password)
        smtp.send_message(message)
    print(f"JSON report emailed to {recipient}")
    #client = OpenAI()
    


# Initialize the client (assumes OPENAI_API_KEY is set in your environment variables)






def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def create_driver() -> webdriver.Remote:
    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.automation_name = "UiAutomator2"
    options.device_name ="00093348H001219"
    #options.udid = os.getenv("ANDROID_UDID")
    options.app_package = "com.apspdcl.consumerapp"
    activity = "com.apspdcl.consumerapp.MainActivity"
    if activity:
        options.app_activity = activity
    options.no_reset = True
    options.set_capability("appium:autoLaunch", False)
    server_url = os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723")
    return webdriver.Remote(server_url, options=options)



def read_xpath(driver: webdriver.Remote, xpath: str) -> str:
    return wait_for_xpath(driver, xpath).text.strip()

import time
def wait_for_xpath(
    driver: webdriver.Remote, xpath: str, timeout: int = 60
):
    #time.sleep(1)
    return WebDriverWait(driver, timeout).until(
        lambda current_driver: current_driver.find_element(AppiumBy.XPATH, xpath)
    )


def swipe_up(driver: webdriver.Remote, percent: float = 0.75) -> None:
    window_size = driver.get_window_size()
    driver.execute_script(
        "mobile: swipeGesture",
        {
            "left": 0,
            "top": 0,
            "width": window_size["width"],
            "height": window_size["height"],
            "direction": "up",
            "percent": percent,
        },
    )


SELECTORS = {
    "quickpay": '//android.widget.ImageView[@resource-id="com.apspdcl.consumerapp:id/img_quickpaylogin"]',
    "billpay":'//android.widget.ImageView[@resource-id="com.apspdcl.consumerapp:id/billpay"]',
    "enter_number": '//android.widget.EditText[@resource-id="com.apspdcl.consumerapp:id/scnotxt"]',
    "captcha": '//android.widget.EditText[@resource-id="com.apspdcl.consumerapp:id/edittxt_captcha"]',
    "edit_Captcha":'//android.widget.EditText[@resource-id="com.apspdcl.consumerapp:id/et_captcha"]',
    "proceed": '//android.widget.Button[@resource-id="com.apspdcl.consumerapp:id/proceedbtn"]',
    "arrears": '//android.widget.TextView[@resource-id="com.apspdcl.consumerapp:id/data1" and @text="Arrears:"]/parent::android.widget.LinearLayout/android.widget.TextView[@resource-id="com.apspdcl.consumerapp:id/data2"]',
    "total_amount": '//android.widget.TextView[@resource-id="com.apspdcl.consumerapp:id/data1" and @text="Total Amount:"]/parent::android.widget.LinearLayout/android.widget.TextView[@resource-id="com.apspdcl.consumerapp:id/data2"]',
    "cancel": '//android.widget.Button[@resource-id="com.apspdcl.consumerapp:id/qpcanel"]',
    "click_number":'//android.widget.TextView[@resource-id="com.apspdcl.consumerapp:id/regscnovalue" and @text="{number}"]',
    "back_button":'//android.widget.Button[@resource-id="com.apspdcl.consumerapp:id/back"]'
}


def save_to_supabase(record: dict[str, str]) -> None:
    supabase_url = required("SUPABASE_URL").rstrip("/")
    supabase_key = required("SUPABASE_SERVICE_ROLE_KEY")
    table = os.getenv("SUPABASE_BILL_TABLE", "electricity_bills")
    response = requests.post(
        f"{supabase_url}/rest/v1/{table}",
        headers={
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json=record,
        timeout=30,
    )
    response.raise_for_status()


def send_bill_json_by_email(bill_records: list[dict[str, object]]) -> None:
    if os.getenv("SEND_BILL_EMAIL", "false").lower() != "true":
        print("Email disabled; set SEND_BILL_EMAIL=true to send the JSON report.")
        return

    sender = required("EMAIL_SENDER")
    app_password = required("EMAIL_APP_PASSWORD")
    recipient = required("EMAIL_RECIPIENT")
    json_data = json.dumps(bill_records, ensure_ascii=False, indent=2)

    message = EmailMessage()
    message["Subject"] = "APSPDCL electricity bill details"
    message["From"] = sender
    message["To"] = recipient
    message.set_content("Attached is the latest APSPDCL electricity bill report.")
    message.add_attachment(
        json_data.encode("utf-8"),
        maintype="application",
        subtype="json",
        filename="electricity_bills.json",
    )

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(sender, app_password)
        smtp.send_message(message)
    print(f"JSON report emailed to {recipient}")


def normalize_electricity_number(value: object) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def load_flat_numbers(path: str = "Excel.xlsx") -> dict[str, dict[str, str | None]]:
    workbook_path = Path(path)
    if not workbook_path.is_absolute():
        workbook_path = Path(__file__).resolve().parent / workbook_path
    workbook = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
    sheet = workbook.active
    mapping: dict[str, dict[str, str | None]] = {}
    for row in sheet.iter_rows(min_row=2, values_only=True):
        flat_number = row[0]
        tenant_name = row[3]
        phone_number = row[4]
        electricity_number = row[11]
        if flat_number is not None and electricity_number is not None:
            mapping[normalize_electricity_number(electricity_number)] = {
                "flat_number": str(flat_number),
                "tenant_name": str(tenant_name) if tenant_name is not None else None,
                "phone_number": str(phone_number) if phone_number is not None else None,
            }
    workbook.close()
    return mapping

import time
def main() -> None:
    driver = None
    bill_dict: dict[str, dict[str, object]] = {}
    try:
        prefix =required("prefix")
        #num1 = ["4557", "4558", "4559", "4560", "4568", "4567", "4564", "4565", "4561", "4566"]
        flat_numbers = load_flat_numbers()
        driver = create_driver()
        print("The driver created")
        package_name = "com.apspdcl.consumerapp"
        driver.activate_app(package_name)
        time.sleep(10)
        prefix = os.getenv("prefix")
        data = os.getenv("ELECTRICITY_NUMBERS", "").split(",")
        num2 = [item.strip() for item in data]
        print(num2)
        time.sleep(10)
        for i in range(0, len(num2)):
            if True:
                output  = ()
                ele = wait_for_xpath(driver, SELECTORS["quickpay"])
                ele.click()
                number = SELECTORS["click_number"].format(number=prefix+num2[i])
                ele = wait_for_xpath(driver, SELECTORS["enter_number"])
                ele.send_keys(prefix+num2[i])
                ele = wait_for_xpath(driver, SELECTORS["captcha"])
                captcha = ele.get_attribute("text")
                print(captcha)
                ele = wait_for_xpath(driver, SELECTORS["edit_Captcha"])
                ele.send_keys(captcha)
                ele = wait_for_xpath(driver, SELECTORS["proceed"])
                ele.click()
                ele = wait_for_xpath(driver, SELECTORS["total_amount"], timeout=50)
                total_amount = ele.get_attribute("text")
                ele = wait_for_xpath(driver, SELECTORS["arrears"])
                arrears= ele.get_attribute("text")
                output  = (total_amount, arrears)
                electricity_number = prefix + num2[i]
                tenant = flat_numbers.get(normalize_electricity_number(num2[i]), {})
                bill_dict[electricity_number] = {
                    "ఫ్లాట్_నంబర్": tenant.get("flat_number", "Unknown"),
                    "అద్దెదారు పేరు": tenant.get("tenant_name"),
                    "ఫోన్ నంబర్": tenant.get("phone_number"),
                    "చెల్లించబడాలి": total_amount,
                    "బకాయిలు": arrears,
                }
                #print(bill_dict)
                ele = wait_for_xpath(driver, SELECTORS["cancel"])
                ele.click()
    except Exception as e:
        print("Failed to fetch bill details")
        print(e)
 
    finally:
        try:
            bill_records = [
                {"విద్యుత్ సంఖ్య": electricity_number, **details}
                for electricity_number, details in bill_dict.items()
            ]
            report_path = Path(__file__).resolve().parent / "electricity_bills.json"
            report_path.write_text(
                json.dumps(bill_records, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"JSON report saved to {report_path}")
            try:
                send_summary_json_by_email(bill_records)
            except Exception as email_error:
                print(f"Could not send email report: {email_error}")
        finally:
            driver.press_keycode(AndroidKey.HOME)
            if driver is not None:
                driver.quit()


if __name__ == "__main__":
    main()