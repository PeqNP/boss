/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation

extension TestManagementAPI {
    public struct TestSuiteTestCase: Codable {
        public var id: TestCaseID?
        public var name: String?
        public let notes: String?
        public let isAutomated: Bool?
        public var line: Int?
        public var delete: Bool
    }
    
    public func testSuite(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        id: TestSuiteID?
    ) async throws -> TestSuite {
        try await _testSuite(session, user, id)
    }

    public func saveTestSuite(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        id: TestSuiteID?,
        projectID: TestProjectID?,
        name: String?
    ) async throws -> TestSuite {
        try await _saveTestSuite(session, user, id, projectID, name)
    }
    
    public func saveTestSuite(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        id: TestSuiteID,
        text: String?,
        testCases: [TestSuiteTestCase]
    ) async throws -> TestSuite {
        try await _saveTestSuiteText(session, user, id, text, testCases)
    }

    public func deleteTestSuite(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        id: TestSuiteID
    ) async throws -> Void {
        try await _deleteTestSuite(session, user, id)
    }
    
    public func testCases(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        testSuiteID: TestSuiteID
    ) async throws -> [TestCase] {
        try await _testCases(session, user, testSuiteID)
    }
}

func testSuite(
    session: Database.Session,
    user: AuthenticatedUser,
    id: TestSuiteID?
) async throws -> TestSuite {
    guard let id else {
        throw api.error.RequiredParameter("id")
    }
    let conn = try await session.conn()
    return try await service.test.testSuite(conn: conn, id: id)
}

func saveTestSuite(
    session: Database.Session,
    user: AuthenticatedUser,
    id: TestSuiteID?,
    projectID: TestProjectID?,
    name: String?
) async throws -> TestSuite {
    guard let projectID else {
        throw api.error.InvalidParameter(name: "projectID")
    }
    guard let name else {
        throw api.error.InvalidParameter(name: "name")
    }
    
    // NOTE: Replace tabs (\t) with 4 spaces if `text` is ever saved in this context
    let conn = try await session.conn()
    if let id {
        let old = try await service.test.testSuite(conn: conn, id: id)
        let model = TestSuite(id: id, projectID: projectID, name: name, text: old.text)
        return try await service.test.updateTestSuite(conn: conn, model)
    }
    else {
        return try await service.test.createTestSuite(
            conn: conn,
            projectID: projectID,
            name: name,
            text: nil
        )
    }
}

func saveTestSuite(
    session: Database.Session,
    user: AuthenticatedUser,
    id: TestSuiteID,
    text: String?,
    testCases: [TestManagementAPI.TestSuiteTestCase]
) async throws -> TestSuite {
    let conn = try await session.conn()
    var testSuite = try await service.test.testSuite(conn: conn, id: id)
    
    var lines: [String] = text?.components(separatedBy: "\n") ?? [String]()
    guard let regex = try? NSRegularExpression(pattern: "\\{TC-(\\d+)\\}", options: []) else {
        boss.log.e("Regular expression failed to initialize")
        throw api.error.ServerError()
    }

    for testCase in testCases {
        if testCase.delete {
            if let id = testCase.id {
                try await service.test.deleteTestCase(conn: conn, id: id)
                boss.log.i("Deleted test case (\(id)) name (\(testCase.name ?? ""))")
            }
            else {
                boss.log.w("Attempting to delete a test case that has no ID (\(testCase.name ?? ""))")
            }
            continue
        }
        
        guard let line = testCase.line else {
            throw api.error.InvalidParameter(name: "line", expected: "Test case (\(testCase.id ?? 0)) must indicate which line in the document it is located.")
        }
        
        let testCaseName = testCase.name ?? ""
        
        // Replace all matches with an empty string
        let range = NSRange(location: 0, length: testCaseName.utf16.count)
        let name = regex
            .stringByReplacingMatches(in: testCaseName, options: [], range: range, withTemplate: "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        
        let tc = try await api.test.saveTestCase(
            session: session,
            user: user,
            id: testCase.id,
            testSuiteID: testSuite.id,
            name: name,
            notes: testCase.notes,
            isAutomated: testCase.isAutomated
        )
        
        if line >= lines.count {
            throw api.error.InvalidParameter(name: "line", expected: "Test case (\(testCase.id ?? 0)) name (\(testCase.name ?? "")) line (\(line)) exceeds the number of lines in the document")
        }
        
        let content = lines[line]
        // Only associate test cases to lines that have a scenario
        guard content.trimmingCharacters(in: .whitespacesAndNewlines).starts(with: "Scenario:") else {
            throw api.error.InvalidParameter(name: "line", expected: "Test case (\(testCase.id ?? 0)) name (\(testCase.name ?? "")) line (\(line)) does not map to line that has `Scenario:`")
        }
        if !content.contains("{TC-") {
            lines[line] = content.appending(" {TC-\(tc.id)}")
        }
    }
    
    // All tabs must be removed so that all tab types are the same. This is necessary for test runs as it is the only way the test cases can be torn out of a document which aren't part of the test.
    testSuite.text = lines
        .joined(separator: "\n")
        .replacingOccurrences(of: "\t", with: "    ")
    
    return try await service.test.updateTestSuite(conn: conn, testSuite)
}

func deleteTestSuite(
    session: Database.Session,
    user: AuthenticatedUser,
    id: TestSuiteID
) async throws -> Void {
    let conn = try await session.conn()
    return try await service.test.deleteTestSuite(conn: conn, id: id)
}

func testCases(
    session: Database.Session,
    user: AuthenticatedUser,
    testSuiteID: TestSuiteID
) async throws -> [TestCase] {
    let conn = try await session.conn()
    return try await service.test.testCases(conn: conn, testSuiteID: testSuiteID)
}
