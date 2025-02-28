/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import CustomDump
import Foundation
import XCTest

@testable import bosslib

final class TestManagementTests: XCTestCase {
    override func setUpWithError() throws {
        try super.setUpWithError()
        boss.reset()
    }

    func testHome() async throws {
        service.test._projects = { (conn) -> [TestProject] in
            [TestProject]()
        }
        service.test._activeTestRuns = { (conn) -> [TestRun] in
            [TestRun]()
        }
        // given: no projects or active test runs exist
        // and: user is signed in
        let home = try await api.test.home(user: superUser())
        // it: should return empty projects
        XCTAssertEqual(home, TestHome(projects: [], activeTestRuns: []))
    }
    
    func testProject() async throws {
        try await boss.start(storage: .memory)

        let c = try await api.test.saveProject(user: superUser(), id: nil, name: "Badge")
        XCTAssertEqual(TestProject(id: 1, name: "Badge", testSuiteIDs: []), c)
        
        let u = try await api.test.saveProject(user: superUser(), id: c.id, name: "BitBox")
        XCTAssertEqual(TestProject(id: 1, name: "BitBox", testSuiteIDs: []), u)
        
        let s = try await api.test.project(user: superUser(), id: 1)
        XCTAssertEqual(TestProject(id: 1, name: "BitBox", testSuiteIDs: []), s)
        try await api.test.deleteProject(user: superUser(), id: 1)
        
        await XCTAssertError(
            try await api.test.project(user: superUser(), id: 1),
            service.error.RecordNotFound()
        )
    }
    
    func testTestSuite() async throws {
        try await boss.start(storage: .memory)

        let project = try await api.test.saveProject(user: superUser(), id: nil, name: "Badge")
        
        let c = try await api.test.saveTestSuite(user: superUser(), id: nil, projectID: project.id, name: "User")
        XCTAssertEqual(TestSuite(id: 1, projectID: project.id, name: "User", text: nil), c)
        
        let u = try await api.test.saveTestSuite(user: superUser(), id: c.id, projectID: project.id, name: "Account")
        XCTAssertEqual(TestSuite(id: 1, projectID: project.id, name: "Account"), u)

        // TODO: describe: save test suite text and cases
        // it: should update existing test case; but keep ID at the end of name in text
        // it: should create new test case; add test case ID at end of name in text
        
        let s = try await api.test.testSuite(user: superUser(), id: 1)
        XCTAssertEqual(TestSuite(id: 1, projectID: project.id, name: "Account"), s)
        try await api.test.deleteTestSuite(user: superUser(), id: 1)
        
        await XCTAssertError(
            try await api.test.testSuite(user: superUser(), id: 1),
            service.error.RecordNotFound()
        )
        
        // TODO: describe: save test suite cases and text
        // it: should
        
        // TODO: describe: delete project
        // it: should cascade and delete all other models
    }
        
    func testTestCase() async throws {
        try await boss.start(storage: .memory)

        let project = try await api.test.saveProject(user: superUser(), id: nil, name: "Badge")
        let testSuite = try await api.test.saveTestSuite(user: superUser(), id: nil, projectID: project.id, name: "User")
        
        let c = try await api.test.saveTestCase(user: superUser(), id: nil, testSuiteID: testSuite.id, name: "User provides valid credentials", notes: "Notes", isAutomated: true)
        XCTAssertEqual(TestCase(id: 1, projectID: project.id, testSuiteID: testSuite.id, name: "User provides valid credentials", notes: "Notes", isAutomated: true), c)
        
        // TODO: describe: delete project
        // it: should delete test cases
        // TODO: describe: delete test suite
        // it: should delete test cases
    }
    
    func testMimeTypes() {
        let mt = mimeType(for: URL(string: "file:///image.png")!)
        XCTAssertEqual(mt, "image/png")
    }
    
    func testTestSuiteText() async throws {
        try await boss.start(storage: .memory)
        
        let project = try await api.test.saveProject(user: superUser(), id: nil, name: "Test Management")
        var testSuite = try await api.test.saveTestSuite(user: superUser(), id: nil, projectID: project.id, name: "Account")
        var testCases: [TestManagementAPI.TestSuiteTestCase] = [
            .init(id: nil, name: "User provides valid credentials", notes: nil, isAutomated: true, line: 5, delete: false),
            .init(id: nil, name: "User provides invalid credentials", notes: nil, isAutomated: false, line: 11, delete: false),
            .init(id: nil, name: "No credentials provided", notes: nil, isAutomated: false, line: 17, delete: false),
            .init(id: nil, name: "User signs out from account module", notes: nil, isAutomated: false, line: 26, delete: false),
            .init(id: nil, name: "User session times out", notes: nil, isAutomated: false, line: 32, delete: false),
        ]

        let text = """
Feature: Sign in
    Background:
        Given User is on the Sign In page
        And User IP is not blocked

    Scenario: User provides valid credentials
        When I enter "ec@ci.com" in Email field
        And I enter "Password" in Password field
        And I click Save
        Then I redirect to Home page

    Scenario: User provides invalid credentials
        When I enter "noreply@ci.com" in Email field
        And I enter "Password" in Password field
        And I click Save
        Then I see error message "No user found with those credentials"

    Scenario: No credentials provided
        When I click Save
        Then I see error message "Please enter email" under Email field
        And I see error message "Please enter password" under Password field

Feature: Sign out
    Background:
        Given User is signed in

    Scenario: User signs out from account module
        When I click Account button
        And I click Sign Out
        Then I redirect to the sign in page
        And I am signed out

    Scenario: User session times out
        Given my session has expired
        When I navigate to Home page
        Then I redirect to the sign in page
"""
        testSuite = try await api.test.saveTestSuite(user: superUser(), id: testSuite.id, text: text, testCases: testCases)
        
        var expectedText = """
Feature: Sign in
    Background:
        Given User is on the Sign In page
        And User IP is not blocked

    Scenario: User provides valid credentials {TC-1}
        When I enter "ec@ci.com" in Email field
        And I enter "Password" in Password field
        And I click Save
        Then I redirect to Home page

    Scenario: User provides invalid credentials {TC-2}
        When I enter "noreply@ci.com" in Email field
        And I enter "Password" in Password field
        And I click Save
        Then I see error message "No user found with those credentials"

    Scenario: No credentials provided {TC-3}
        When I click Save
        Then I see error message "Please enter email" under Email field
        And I see error message "Please enter password" under Password field

Feature: Sign out
    Background:
        Given User is signed in

    Scenario: User signs out from account module {TC-4}
        When I click Account button
        And I click Sign Out
        Then I redirect to the sign in page
        And I am signed out

    Scenario: User session times out {TC-5}
        Given my session has expired
        When I navigate to Home page
        Then I redirect to the sign in page
"""
        XCTAssertEqual(testSuite.text, expectedText)
        
        var expectedTestCases: [TestCase] = [
            .init(id: 1, projectID: project.id, testSuiteID: testSuite.id, name: "User provides valid credentials", isAutomated: true),
            .init(id: 2, projectID: project.id, testSuiteID: testSuite.id, name: "User provides invalid credentials"),
            .init(id: 3, projectID: project.id, testSuiteID: testSuite.id, name: "No credentials provided"),
            .init(id: 4, projectID: project.id, testSuiteID: testSuite.id, name: "User signs out from account module"),
            .init(id: 5, projectID: project.id, testSuiteID: testSuite.id, name: "User session times out"),
        ]
        var tcs = try await api.test.testCases(user: superUser(), testSuiteID: testSuite.id)
        XCTAssertEqual(tcs, expectedTestCases)
        
        // describe: update the name of a test case
        testCases[0].id = 1
        testCases[1].id = 2
        testCases[2].id = 3
        testCases[3].id = 4
        testCases[4].id = 5
        testCases[0].name = "User provides valid username and password"
        testSuite = try await api.test.saveTestSuite(user: superUser(), id: testSuite.id, text: testSuite.text, testCases: testCases)
        
        // it: should not change the text
        XCTAssertEqual(testSuite.text, expectedText)
        
        // it: should update the name of the test case
        // The name of the test case, even though not reflected in text, should accept the name provided in the list of test cases
        tcs = try await api.test.testCases(user: superUser(), testSuiteID: testSuite.id)
        XCTAssertEqual(tcs[0], .init(id: 1, projectID: project.id, testSuiteID: testSuite.id, name: "User provides valid username and password", isAutomated: true))

        // describe: remove a test case; do not update line numbers
        testCases[2].delete = true
        expectedText = """
Feature: Sign in
    Background:
        Given User is on the Sign In page
        And User IP is not blocked

    Scenario: User provides valid credentials {TC-1}
        When I enter "ec@ci.com" in Email field
        And I enter "Password" in Password field
        And I click Save
        Then I redirect to Home page

    Scenario: User provides invalid credentials {TC-2}
        When I enter "noreply@ci.com" in Email field
        And I enter "Password" in Password field
        And I click Save
        Then I see error message "No user found with those credentials"

Feature: Sign out
    Background:
        Given User is signed in

    Scenario: User signs out from account module {TC-4}
        When I click Account button
        And I click Sign Out
        Then I redirect to the sign in page
        And I am signed out

    Scenario: User session times out {TC-5}
        Given my session has expired
        When I navigate to Home page
        Then I redirect to the sign in page
"""
        // it: should error that line is not associated to scenario
        await XCTAssertError(
            testSuite = try await api.test.saveTestSuite(user: superUser(), id: testSuite.id, text: expectedText, testCases: testCases),
            api.error.InvalidParameter(name: "line", expected: "Test case (\(4)) name (\(testCases[3].name ?? "undefined")) line (\(testCases[3].line ?? -1)) does not map to line that has `Scenario:`")
        )
                
        // describe: remove test case; line exceeds document length
        testCases[3].line = 21;
        await XCTAssertError(
            testSuite = try await api.test.saveTestSuite(user: superUser(), id: testSuite.id, text: expectedText, testCases: testCases),
            api.error.InvalidParameter(name: "line", expected: "Test case (5) name (\(testCases[4].name ?? "undefined")) line (\(testCases[4].line ?? -1)) exceeds the number of lines in the document")
        )
        
        // describe: remove test case; all line numbers updated
        testCases[4].line = 27
        testSuite = try await api.test.saveTestSuite(user: superUser(), id: testSuite.id, text: expectedText, testCases: testCases)

        // it: should update the text
        XCTAssertEqual(testSuite.text, expectedText)
        
        // it: should remove the test case
        // it: should update the test case name provided in the list
        // The name of the test case, even though not reflected in text, should accept the name provided in the list of test cases
        tcs = try await api.test.testCases(user: superUser(), testSuiteID: testSuite.id)
        expectedTestCases[0].name = testCases[0].name ?? "undefined"
        expectedTestCases.remove(at: 2)
        XCTAssertEqual(tcs, expectedTestCases)
        
        // describe: create test run; include all cases from test suite
        let testRun = try await api.test.startTestRun(user: superUser(), name: "1.7", includeAutomated: false, modelIDs: ["TS-1"])
        
        // NOTE: TC-1 is automated, which is why it is removed
        expectedText = """
Feature: Sign in
    Background:
        Given User is on the Sign In page
        And User IP is not blocked

    Scenario: User provides invalid credentials {TC-2}
        When I enter "noreply@ci.com" in Email field
        And I enter "Password" in Password field
        And I click Save
        Then I see error message "No user found with those credentials"

Feature: Sign out
    Background:
        Given User is signed in

    Scenario: User signs out from account module {TC-4}
        When I click Account button
        And I click Sign Out
        Then I redirect to the sign in page
        And I am signed out

    Scenario: User session times out {TC-5}
        Given my session has expired
        When I navigate to Home page
        Then I redirect to the sign in page
"""
        // it: should include only non-automated tests
        XCTAssertEqual(testRun.text, expectedText)
        
        // it: should select first test case in run
        XCTAssertEqual(testRun.selectedTestCaseID, 2)
        
        // describe: status a test case
        var status = try await api.test.statusTestCase(
            user: superUser(),
            testCaseResultID: testRun.results[0].id,
            status: .passed,
            notes: "some notes"
        )

        // it: should return correct status results
        XCTAssertEqual(status.pending, 2)
        XCTAssertEqual(status.passed, 1)
        XCTAssertEqual(status.failed, 0)
        XCTAssertEqual(status.skipped, 0)
        
        // it: should save notes to respective test case
        let tc = try await api.test.testCase(user: superUser(), id: 2)
        XCTAssertEqual(tc.notes, "some notes")
        
        // it: should status test case
        var tr = try await api.test.activeTestRun(user: superUser(), testRunID: 1)
        XCTAssertEqual(tr.results[0].status, .passed)
        
        // describe: finish test run before all test cases have a status
        let results = try await api.test.finishTestRun(user: superUser(), testRunID: tr.id, determination: .passed, notes: "It passed!")
        
        // it: should mark remaining results as skipped
        XCTAssertEqual(results.status.pending, 0)
        XCTAssertEqual(results.status.passed, 1)
        XCTAssertEqual(results.status.failed, 0)
        XCTAssertEqual(results.status.skipped, 2)
        
        tr = try await api.test.activeTestRun(user: superUser(), testRunID: 1)
        XCTAssertEqual(tr.results[1].status, .skipped)
        XCTAssertEqual(tr.results[2].status, .skipped)
        
        // it: should be statused on correct date
        let now = Date.now
        guard let statused = tr.results[1].dateStatused else {
            XCTFail("Case must be statused")
            return
        }
        XCTAssertLessThan(statused, now)
        XCTAssertGreaterThan(statused, now - 2)
    }
}
