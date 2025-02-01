#!/usr/bin/env python3
#
# Test Managemer
#
# Don't ever mix explicit and implicit waits as it causes unpredictable results.
# e.g. driver.implicitly_wait(0.5)
#

import logging
import os
import pytest
import requests
import time

from tests import *

logging.basicConfig(filename="selenium.log", encoding="utf-8", level=logging.INFO)

def get_test_directory():
    #home_path = os.path.expanduser("~")
    #config_dir = os.path.join(home_path, ".boss")
    path = os.path.abspath(__file__)
    return os.path.dirname(path)

# Returns the full path to a file in the `tests/media` directory.
def get_media_file(name):
    d = get_test_directory()
    return os.path.join(d, "media", name)

def sign_in(browser):
    # it: should show Welcome screen when signed in as user
    window = browser.find_window("Welcome")
    window.click_button("Sign in")

    # describe: sign in with valid credentials
    signin = browser.find_modal()
    signin.type_in("email", "bitheadrl@protonmail.com")
    signin.type_in("password", "Password1!")
    signin.click_button("Sign in")

    # Required as the page refreshes
    signin.is_hidden()

def test_setup(driver):
    # given: database is clean
    response = requests.get(make_path("uitests/automatic"))
    assert response.status_code == 200, "Failed to prepare environent for UI testing. Is the server up?"

    logging.info("TC-1: Sign in with valid credentials")

    # when: user loads home page
    driver.get(make_path("/"))
    assert driver.title == "Bithead OS"

    # NOTE: This illustrates how you can query a parent element to further
    # refine your query to a specific element.
    # and: user provides valid credentials
    browser = Element(driver)

    logging.info("TC-#: User provides valid credentials")

    sign_in(browser)

    # describe: open Test Manager application
    system_menu = browser.click_menu("system-menu")
    system_menu.click_menu_option("Applications")

    apps = browser.find_window("Applications")
    app_list = apps.find_list("applications")
    app_list.click_list_option("Test Manager")
    apps.click_button("Open")

    # describe: add new project
    tm = browser.find_window("Test Management")
    tm.click_button("Add Project")

    project_win = browser.find_window("Project")
    project_win.type_in("name", "Test Management System")
    project_win.click_button("Save")
    project_win.is_hidden()

    # it: should show new project in list
    tm.click_list_option("Test Management System")
    tm.click_button("Edit")

    # describe: update a project name
    project_win = browser.find_window("Project")
    project_win.type_in("name", "Test Manager")
    project_win.click_button("Save")
    project_win.is_hidden()

    # it: should save project name
    tm.click_list_option("Test Manager")
    tm.click_button("Open")

    # it: should show test suites
    ts = browser.find_window("Test Suites")
    ts.click_button("Add Suite")

    # describe: create test suite
    ts_win = browser.find_window("Test Suite")
    ts_win.type_in("name", "Account")
    ts_win.click_button("Save")

    # it: should save test case
    ts.find_list_option("TS-1: Account")

    response = requests.put(make_path("uitests/snapshot/basic_objects"))
    assert response.status_code == 200, "Failed to create snapshot"

def test_editor(driver):
    response = requests.get(make_path("uitests/snapshot/basic_objects"))
    assert response.status_code == 200, "Failed to load snapshot: basic_objects"

    driver.get(make_path("/"))
    assert driver.title == "Bithead OS"
    browser = Element(driver)

    sign_in(browser)

    # describe: open Test Manager application
    system_menu = browser.click_menu("system-menu")
    system_menu.click_menu_option("Applications")

    apps = browser.find_window("Applications")
    app_list = apps.find_list("applications")
    app_list.click_list_option("Test Manager")
    apps.click_button("Open")

    tm = browser.find_window("Test Management")
    tm.type_in("term", "TS-1")
    tm.click_button("Search")

    search = browser.find_window("Search results")
    search.click_button("Editor")

    # describe: create test case
    editor = browser.find_window("Test Suite Editor")
    editor.type_in_editor("""Feature: Sign In
    Scenario: User provides valid credentials
        When I enter "ec@bithead.io" in Email field
        And I enter "Password" in Password field
        And I click Save
        Then I redirect to desktop
    """)
    editor.click_button("Save")
    editor.click_button("Close")

    search.close_window()

    tm.click_button("Open")

    suites = browser.find_window("Test Suites")
    suites.find_list_option("TC-1: User provides valid credentials")

    suites.close_window()
    tm.close_window()
    apps.close_window()

    driver.quit()
