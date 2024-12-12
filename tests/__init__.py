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

import logging
import pytest
import time

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

SERVER = "http://localhost:8080/"
TIMEOUT = 3

class InvalidOperation(Exception):
    def __init__(self, message):
        super().__init__(message)

class TransitionFailed(Exception):
    def __init__(self, url):
        message = "Failed to transition from url ({url}) - Expected the page to change"
        logging.error(f"About to emit error ({message}). Waiting 10 seconds...")
        time.sleep(10)
        super().__init__(message)

class ElementNotFound(Exception):
    def __init__(self, locator, log_error=None):
        message = f"Element located with ({locator}) not found"
        if log_error in [None, True]:
            logging.error(f"About to emit error ({message}). Waiting 10 seconds...")
            time.sleep(10)
        super().__init__(message)

class ElementNotHidden(Exception):
    def __init__(self, locator):
        message = f"Element located with ({locator}) is still visible"
        logging.error(f"About to emit error ({message}). Waiting 10 seconds...")
        time.sleep(10)
        super().__init__(message)

class ElementNotVisible(Exception):
    def __init__(self, locator):
        self.value = value
        message = f"Element located with ({locator}) is not visible"
        logging.error(f"About to emit error ({message}). Waiting 10 seconds...")
        time.sleep(10)
        super().__init__(message)

class ElementIsVisible(Exception):
    def __init__(self, locator):
        message = f"Element located with ({locator}) is visible"
        logging.error(f"About to emit error ({message}). Waiting 10 seconds...")
        time.sleep(10)
        super().__init__(message)

class WindowNotFound(Exception):
    def __init__(self, title):
        message = f"Window not found with title ({title})"
        logging.error(f"About to emit error ({message}). Waiting 10 seconds...")
        time.sleep(10)
        super().__init__(message)

def make_path(path):
    """ Returns full url to the server under test, appending the
    provided resource path. """
    return SERVER + path

class check_element_value(object):
    """ Waits for a change in the DOM to occur before failing. This checks the
    start of the element's text value. The reason being is that a component
    _may_ have multiple text components. Imagine an `<li>Text <button>Hi</button></li>`.
    The text values of `Text Hi` will be returned from `text`. In most cases
    we only care about the actual text value. Therefore, this matches only the
    first part of the `li`'s text value, `Text`.
    """
    def __init__(self, locator, text_):
        self.locator = locator
        self.text = text_

    def __call__(self, driver):
        try:
            logging.debug(f"Checking for locator ({self.locator}) at ({time.time()})")
            elements = driver.find_elements(*self.locator)
            for element in elements:
                # Text is not provided.
                # NOTE: This always returns the first element found -- which may
                # or may not be the desired behavior.
                if self.text is None:
                    return element
                if element.text.strip().startswith(self.text.strip()):
                    return element
            return None # Not found
        except StaleElementReferenceException:
            return None

class Element(object):
    def __init__(self, driver, element=None):
        self.driver = driver
        self.element = element or driver

        # This is temporary until the Bithead OS does not transition between different pages.
        # It is expected that this will only be used on the _root_ element!
        self.current_url = element is None

    def cache_url(self):
        self.current_url = self.driver.current_url

    def is_displayed(self):
        return self.element.is_displayed()

    @property
    def text(self):
        return self.element.text

    def get_attribute(self, name):
        return self.element.get_attribute(name)

    def log_html(self):
        if self.driver == self.element:
            logging.error("If you are getting this error, and believe you should not, you may need to wait for a page to transition to another. Use `driver.transition()` to do this.")
            logging.error("Printing out the entire DOM")
            # This does not print "shadow" DOM
            #logging.error(self.driver.page_source)

            # This should print everything in the DOM, including elements created by Javasript
            logging.error(self.driver.execute_script("return document.documentElement.outerHTML"))

            # I found this to be much easier to scan all elements when testing
            # for a specific class name.
            #elements = self.driver.find_elements(By.XPATH, "//*")
            #for element in elements:
            #    logging.error(f"{element.tag_name}: {element.get_attribute('class')}")
            return
        logging.error(self.driver.execute_script("return arguments[0].shadowRoot.innerHTML;", self.element))

    def find_element(self, locator):
        try:
            element = Element(self.driver, WebDriverWait(self.element, timeout=TIMEOUT).until(
                EC.presence_of_element_located(locator)
            ))
        except:
            self.log_html()
            raise ElementNotFound(locator)
        if not element.is_displayed():
            raise ElementNotVisible(locator)
        return element

    def find_element_with_value(self, locator, value, timeout=None, log_error=None):
        """ In addition to finding the element, this also queries the
        element that contains the respective text value.

        This is designed for CSS selectors. It's not clear if XPATH can be used
        for this. XPATH is still used when checking the text for elements with
        specific types.
        """
        try:
            element = Element(self.driver, WebDriverWait(self.element, timeout=timeout or TIMEOUT).until(
                check_element_value(locator, value)
            ))
        except Exception as error:
            if log_error in [None, True]:
                self.log_html()
            raise ElementNotFound(locator, log_error=log_error)
        if not element.is_displayed():
            raise ElementNotVisible(locator)
        return element

    def find_all_by_class_name(self, class_name):
        elements = []
        found = self.element.find_elements(By.XPATH, f"//*[contains(@class, '{class_name}')]")
        for element in found:
            elements.append(Element(self.driver, element))
        return elements

    def find_by_class(self, selector):
        return self.find_element((By.CSS_SELECTOR, selector))

    def find_by_id(self, _id):
        return self.find_element((By.ID, _id))

    def find_by_name(self, name):
        return self.find_element((By.NAME, name))

    def find_by_xpath(self, xpath):
        return self.find_element((By.XPATH, xpath))

    # Find by specific element types

    def find_button(self, value):
        return self.find_by_value("button", value)

    def find_div(self, value):
        return self.find_by_value("div", value)

    def find_span(self, value):
        return self.find_by_value("span", value)

    def find_summary(self, value):
        return self.find_by_value("summary", value)

    def find_by_value(self, _type, value):
        return self.find_element((By.XPATH, f".//{_type}[contains(text(), '{value}')]"))

    def find_class_with_value(self, selector, value=None, timeout=None, log_error=None):
        return self.find_element_with_value((By.CSS_SELECTOR, selector), value, timeout=timeout, log_error=log_error)

    # Assert element visibility is hidden (or non-existing in DOM)

    def hide_element(self, locator):
        """ Waits for element to be hidden. """
        try:
            Element(self.driver, WebDriverWait(self.element, timeout=TIMEOUT).until(
                EC.invisibility_of_element_located(locator)
            ))
        except:
            raise ElementIsVisible(locator)

    def hide_by_value(self, _type, value):
        return self.hide_element((By.XPATH, f".//{_type}[contains(text(), '{value}')]"))

    def hide_span(self, value):
        return self.hide_by_value("span", value)

    def click_div(self, value):
        self.find_div(value).click()

    def click_button(self, value):
        # All operations that take user from one page to the next is done via button taps.
        # This is temporary to cache what the current URL is so that we can test if a page
        # transitions after certain behaviors.
        self.cache_url()
        self.find_button(value).click()

    def clear(self):
        """ Clear text field contents. """
        self.element.clear()

    def type(self, text):
        """ Clear field and then type new value in input. """
        self.clear()
        self.element.send_keys(text)

    def type_in(self, name, text):
        """ Type in text into a given input field. """
        self.find_by_name(name).type(text)

    def type_append(self, text):
        """ Append text to the current element's input field. """
        self.element.send_keys(text)

    def click(self):
        """ Click the current element. """
        self.element.click()

    ## Bithead OS

    def transition(self):
        """ Waits for transition from current page to next page. """
        ts = time.time()
        while True:
            if self.current_url != self.driver.current_url:
                self.current_url = self.driver.current_url
                return
            time.sleep(0.25)
            if time.time() - ts > TIMEOUT:
                raise FailedTransition(self.current_url)

    def is_hidden(self):
        """ Waits for the current element to be hidden. """
        ts = time.time()
        while True:
            try:
                if not self.element.is_displayed():
                    return
            except StaleElementReferenceException:
                return # No longer in DOM
            if time.time() - ts > TIMEOUT:
                raise ElementNotHidden(self.element.tag_name)
            time.time(0.25)

    def find_window(self, value, transition=None):
        """ Returns the respective window where its title matches `value`. """
        # Wait for page to transition before searching for windows
        if transition is True:
            self.transition()
        # Almost all issues are caused by the DOM not rendering up-to-date info.
        # This ensures the DOM has time to settle down between page transitions
        # or displaying new windows. Waiting .33 seconds will ensure that most
        # checks will succeed on first iteration.
        time.sleep(0.33)
        ts = time.time()
        while True:
            windows = self.find_all_by_class_name("ui-window")
            logging.debug(f"Number of windows ({len(windows)})")
            for win in windows:
                try:
                    win.find_class_with_value("div.title > span", value, timeout=0.25, log_error=False)
                    return win
                except ElementNotFound:
                    pass
            if time.time() - ts > TIMEOUT:
                raise WindowNotFound(value)
            time.sleep(0.25)

    # Component: Modal

    def find_modal(self):
        modal = self.find_by_class("div.modal")
        # The OS is responsible for showing only one modal at a time. Therefore,
        # there should only be one modal visible at a time. Unless a modal has
        # an instance ID, it won't be possible to determine when one modal transitions
        # to another. Selenium will be too fast to wait for the change to occur.
        # Therefore, eventually the OS should assign an ID instance to a modal AND
        # this function will look for the modal's respective ID instance when determining
        # if it is hidden (is removed from DOM).
        return modal

    def find_delete_modal(self, value):
        modal = self.find_by_class("div.modal")
        modal.find_class_with_value("div.exclamation > p.message", value)
        return modal

    # Component: Bullet list

    def find_list(self, value):
        return self.find_class_with_value("ul.bullet-list > li", value)

    # Component: Image Carousel

    def image_viewer(self):
        return self.find_class_with_value("div.image-viewer")

    # Component: OS / Popup Menu

    def find_menu(self, value):
        return self.find_div(value)

    def click_menu(self, value):
        self.click_div(value)

    # Component: Folder

    def find_folder(self, value):
        """ Find a folder within a Folder component hierarchy. """
        return self.find_span(value)

    def find_file(self, value):
        """ Represents a file within a folder. """
        return self.find_span(value)

    def hide_file(self, value):
        self.hide_span(value)

    ## Test Management Components

    def find_resource_image(self, value):
        """ Find an image resource with a given caption. """
        for element in self.find_all_by_class_name("image"):
            try:
                # TODO: Can XPATH be used here?
                element.find_class_with_value("figcaption", value, log_error=False)
                return element
            except:
                pass
        raise ElementNotFound(f"resource_image w/ value ({value})")

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
