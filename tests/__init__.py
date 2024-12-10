#
# Provides web testing abstraction for Bithead OS
#
# The best way to troubleshoot if your CSS selectors are accurate is to use
# your browser's console and log using `querySelector`.
#
# ```
# console.log(document.querySelector("div.modal div.exclamation > p.message"));
# ```
#

import pytest

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

SERVER = "http://localhost:8080/"

class ElementNotVisible(Exception):
    def __init__(self, _type, value):
        self.value = value
        message = f"Element with {_type} not found using ({value})"
        super().__init__(message)

def make_path(path):
    """ Returns full url to the server under test, appending the
    provided resource path. """
    return SERVER + path

class WaitForChange(object):
    def __init__(self, locator, text_):
        self.locator = locator
        self.text = text_

    def __call__(self, driver):
        try:
            element = driver.find_element(*self.locator)
            return element.text == self.text
        except StaleElementReferenceException:
            return False

class Element(object):
    def __init__(self, element):
        self.element = element

    def is_displayed(self):
        return self.element.is_displayed()

    @property
    def text(self):
        return self.element.text

    def find_by_class(self, selector):
        element = Element(WebDriverWait(self.element, timeout=2).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        ))
        if not element.is_displayed():
            raise ElementNotVisible("class", selector)
        return element

    def find_by_id(self, _id):
        element = Element(WebDriverWait(self.element, timeout=2).until(
            EC.presence_of_element_located((By.ID, _id))
        ))
        if not element.is_displayed():
            raise ElementNotVisible("id", _id)
        return element

    def find_by_name(self, name):
        return Element(WebDriverWait(self.element, timeout=2).until(
            EC.presence_of_element_located((By.NAME, name))
        ))
        if not element.is_displayed():
            raise ElementNotVisible("name", name)
        return element

    def find_by_xpath(self, xpath):
        element = Element(WebDriverWait(self.element, timeout=2).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        ))
        if not element.is_displayed():
            raise ElementNotVisible("xpath", value)
        return element

    def find_button(self, value):
        return self.find_by_value("button", value)

    def find_div(self, value):
        return self.find_by_value("div", value)

    def find_span(self, value):
        return self.find_by_value("span", value)

    def find_summary(self, value):
        return self.find_by_value("summary", value)

    def find_by_value(self, _type, value):
        element = Element(WebDriverWait(self.element, timeout=2).until(
            EC.presence_of_element_located((By.XPATH, f".//{_type}[contains(text(), '{value}')]"))
        ))
        if not element.is_displayed():
            raise ElementNotVisible("span", value)
        return element

    def wait_for_class(self, selector, value):
        WebDriverWait(self.element, timeout=2).until(
            WaitForChange((By.CSS_SELECTOR, selector), value)
        )

    def click_div(self, value):
        self.find_div(value).click()

    def click_button(self, value):
        self.find_button(value).click()

    # Clear text field
    def clear(self):
        self.element.clear()

    # Clear field and then type new value in input
    def type(self, text):
        self.clear()
        self.element.send_keys(text)

    def type_in(self, name, text):
        self.find_by_name(name).type(text)

    # Adds text to the end of an input's value
    def type_add(self, text):
        self.element.send_keys(text)

    # Click on an element
    def click(self):
        self.element.click()

    ## Bithead OS

    def wait_for_window(self, value):
        return self.wait_for_class("div.title > span", value)

    # Component: Modal

    def wait_for_delete_modal(self, value):
        return self.wait_for_class("div.modal div.exclamation > p.message", value)

    # Component: OS / Popup Menu

    def find_menu(self, value):
        return self.find_div(value)

    def click_menu(self, value):
        self.click_div(value)

    # Component: Folder

    # Find a folder within a Folder component hierarchy
    def find_folder(self, value):
        return self.find_span(value)

    # Represents a file within a folder
    def find_file(self, value):
        return self.find_span(value)

    # Returns `True` when file exists
    def file_exists(self, value):
        try:
            self.find_span(value)
            return True
        except Exception:
            return False

@pytest.fixture(scope="function")
def driver():
    options = Options()

    # Opera
    #options.binary_location = "/Applications/Opera.app/Contents/MacOS/Opera"
    #options.add_argument("--enable-automation")
    #driver = webdriver.Chrome(options=options)

    # Chrome
    # Keeps the browser open after test is finished
    #options.add_experimental_option("detach", True)
    driver = webdriver.Chrome(options=options)

    # Firefox doesn't immediately close making it easier to diagnose issues.
    #driver = webdriver.Firefox()

    yield driver
    driver.quit()
