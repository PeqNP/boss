/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation

extension TestManagementAPI {
    public struct Link: Equatable, Codable {
        public let name: String
        public let url: String
    }
    
    public func testCase(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        id: TestCaseID?
    ) async throws -> TestCase {
        try await _testCase(session, user, id)
    }

    /// Save a test case
    ///
    /// - Parameter resourceIDs: List of resource IDs, where the ID is the name of the file in the test media directory (e.g. `<uuidvalue>.png`)
    public func saveTestCase(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        id: TestCaseID?,
        testSuiteID: TestSuiteID?,
        name: String?,
        notes: String?,
        isAutomated: Bool?
    ) async throws -> TestCase {
        try await _saveTestCase(session, user, id, testSuiteID,name, notes, isAutomated)
    }

    /// Delete test case.
    public func deleteTestCase(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        id: TestCaseID
    ) async throws -> Void {
        try await _deleteTestCase(session, user, id)
    }
}

func testCase(
    session: Database.Session,
    user: AuthenticatedUser,
    id: TestCaseID?
) async throws -> TestCase {
    guard let id else {
        throw api.error.RequiredParameter("id")
    }
    let conn = try await session.conn()
    return try await service.test.testCase(conn: conn, id: id)
}

func saveTestCase(
    session: Database.Session,
    user: AuthenticatedUser,
    id: TestCaseID?,
    testSuiteID: TestSuiteID?,
    name: String?,
    notes: String?,
    isAutomated: Bool?
) async throws -> TestCase {
    guard let testSuiteID else {
        throw api.error.InvalidParameter(name: "testSuiteID")
    }
    guard let name = name?.trimmingCharacters(in: .whitespacesAndNewlines) else {
        throw api.error.InvalidParameter(name: "name")
    }
    let notes = notes?.trimmingCharacters(in: .whitespacesAndNewlines)
    
    let isAutomated = isAutomated ?? false
        
    let conn = try await session.conn()
    
    if let id {
        let old = try await service.test.testCase(conn: conn, id: id)
        
        let model = TestCase(
            id: id,
            // The parent models may NOT be changed in this context (for now).
            // Changes must be performed within the project tree.
            projectID: old.projectID,
            testSuiteID: old.testSuiteID,
            name: name,
            notes: notes,
            isAutomated: isAutomated
        )
        
        return try await service.test.updateTestCase(conn: conn, model)
    }
    else {
        let testSuite = try await service.test.testSuite(conn: conn, id: testSuiteID)
        
        return try await service.test.createTestCase(
            conn: conn,
            projectID: testSuite.projectID,
            testSuiteID: testSuite.id,
            name: name,
            notes: notes,
            isAutomated: isAutomated
        )
    }
}

func deleteTestCase(
    session: Database.Session,
    user: AuthenticatedUser,
    id: TestCaseID
) async throws -> Void {
    let conn = try await session.conn()
    return try await service.test.deleteTestCase(conn: conn, id: id)
}
