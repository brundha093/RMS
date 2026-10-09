from __future__ import annotations
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from appium.webdriver.extensions.android.nativekey import AndroidKey
import os


start_chat  = "//android.widget.Button[@content-desc='Start chat']"
enter_number = "//android.widget.EditText[@resource-id='ContactSearchField']"
send ="//android.view.View[@resource-id='ContactSuggestionList']/android.view.View"
compose_message="//android.widget.EditText[@resource-id='com.google.android.apps.messaging:id/compose_message_text']"
composed_msg_send="//android.view.View[@resource-id='Compose:Draft:Send']/android.widget.Button"
message ="Hi , Rent for this month is due. Please pay at your earliest convenience. Thank you, MR Towers Management"
message_modified = "Hi , Rent of 8500  is due from your side. Request you to pay at your earliest convenience. Thank you, MR Towers Management"


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


def send_due_sms(phone: str, flat_number: str, amount: float) -> tuple[bool, str]:

    try:
        driver = sms_driver()
        print("The driver created")
        package_name = "com.google.android.apps.messaging"
        driver.activate_app(package_name)
        time.sleep(5)
        ele = wait_for_xpath(driver, start_chat, timeout=100)
        ele.click()
        ele = wait_for_xpath(driver, enter_number, timeout=100)
        ele.click()
        print("The phone number is", phone)
        print(type(phone))
        time.sleep(5)
        ele.send_keys(phone)
        time.sleep(5)
        ele = wait_for_xpath(driver, send, timeout=100)
        ele.click() 
        ele= wait_for_xpath(driver, compose_message, timeout=100)
        ele.click() 
        ele.send_keys(message_modified)
        ele = wait_for_xpath(driver, composed_msg_send, timeout=100)
        ele.click()
    except Exception as e:
        print("Failed to send sms")
        print(e)
    finally:
        driver.press_keycode(AndroidKey.HOME)
        if driver is not None:
            driver.quit()


def sms_driver():    
    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.automation_name = "UiAutomator2"
    options.device_name ="00093348H001219"
    #options.udid = os.getenv("ANDROID_UDID")
    options.app_package = "com.google.android.apps.messaging"
    activity = "com.google.android.apps.messaging.MainActivity"
    if activity:
        options.app_activity = activity
    options.no_reset = True
    options.set_capability("appium:autoLaunch", False)
    server_url = os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723")
    return webdriver.Remote(server_url, options=options)

