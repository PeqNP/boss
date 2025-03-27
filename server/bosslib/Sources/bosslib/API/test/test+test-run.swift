/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

extension TestManagementAPI {

    /// Begin the process of selecting test objects to include in a test run.
    ///
    /// - Returns: An object that represents the currently selected test objects to include a test run.
    public func testRun(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser
    ) async throws -> [TestProjectTree] {
        try await _testRun(session, user)
    }

    public func findTestModels(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        searchTerm: String,
        reverseLookup: Bool
    ) async throws -> [TestSearchResult] {
        try await _findTestModels(session, user, searchTerm, reverseLookup)
    }

    public func startTestRun(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        name: String?,
        includeAutomated: Bool?,
        modelIDs: [TestModelID]?
    ) async throws -> TestRun {
        try await _startTestRun(session, user, name, includeAutomated, modelIDs)
    }

    public func activeTestRun(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        testRunID: TestRunID
    ) async throws -> TestRun {
        try await _activeTestRun(session, user, testRunID)
    }

    public func statusTestCase(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        testCaseResultID: TestCaseResultID,
        status: TestRun.TestCaseStatus,
        notes: String?
    ) async throws -> TestRun.Status {
        try await _statusTestCase(session, user, testCaseResultID, status, notes)
    }

    public func finishTestRun(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        testRunID: TestRunID,
        determination: TestRunResults.Determination,
        notes: String?
    ) async throws -> TestRunResults {
        try await _finishTestRun(session, user, testRunID, determination, notes)
    }

    public func testRunResults(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        testRunID: TestRunID
    ) async throws -> TestRunResults {
        try await _testRunResults(session, user, testRunID)
    }
    
    public func testRuns(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser
    ) async throws -> [TestRun] {
        try await _testRuns(session, user)
    }
    
    public func finishedTestRuns(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser
    ) async throws -> [TestRun] {
        try await _finishedTestRuns(session, user)
    }
}

func testRun(
    session: Database.Session,
    user: AuthenticatedUser
) async throws -> [TestProjectTree] {
    let conn = try await session.conn()
    var trees = [TestProjectTree]()
    let projects = try await service.test.projects(conn: conn)
    for project in projects {
        let suites = try await service.test.testSuites(conn: conn, projectID: project.id)
        var testSuites = [TestProjectTree.TestSuite]()
        for ts in suites {
            testSuites.append(TestProjectTree.TestSuite(
                id: ts.id,
                name: ts.name,
                testCases: try await service.test.testCases(conn: conn, testSuiteID: ts.id),
                totalTestCases: ts.totalTestCases,
                automatedTestCases: ts.automatedTestCases
            ))
        }
        trees.append(.init(id: project.id, name: project.name, testSuites: testSuites))
    }
    return trees
}

func findTestModels(
    session: Database.Session,
    user: AuthenticatedUser,
    searchTerm: SearchTerm,
    reverseLookup: Bool
) async throws -> [TestSearchResult] {
    let conn = try await session.conn()
    if reverseLookup {
        return try await service.test.searchTestSuites(conn: conn, term: searchTerm)
    }
    return try await service.test.search(conn: conn, term: searchTerm)
}

func startTestRun(
    session: Database.Session,
    user: AuthenticatedUser,
    name: String?,
    includeAutomated: Bool?,
    modelIDs: [TestModelID]?
) async throws -> TestRun {
    guard let name = name?.cleaned() else {
        throw api.error.InvalidParameter(name: "name")
    }
    guard let modelIDs else {
        throw api.error.InvalidParameter(name: "modelIDs", expected: "One or more test models to be selected")
    }
    let cleanedModelIDs = modelIDs.compactMap { $0.cleaned() }
    guard cleanedModelIDs.count == modelIDs.count else {
        throw api.error.InvalidParameter(name: "modelIDs", expected: "One or more model IDs are invalid. IDs must start with `P-`, `TS-`, or `TC-` and end with respective model ID")
    }
    let validModelIDs = cleanedModelIDs.filter { modelID in
        modelID.starts(with: "P-") || modelID.starts(with: "TS-") || modelID.starts(with: "TC-")
    }
    guard validModelIDs.count == modelIDs.count else {
        throw api.error.InvalidParameter(name: "modelIDs", expected: "One or more model IDs are invalid. IDs must start with `P-`, `TS-`, or `TC-`")
    }

    return try await service.test.startTestRun(
        conn: session.conn(),
        name: name,
        includeAutomated: includeAutomated ?? false,
        modelIDs: modelIDs
    )
}

func activeTestRun(
    session: Database.Session,
    user: AuthenticatedUser,
    testRunID: TestRunID
) async throws -> TestRun {
    let conn = try await session.conn()
    return try await service.test.testRun(conn: conn, id: testRunID)
}

func statusTestCase(
    session: Database.Session,
    user: AuthenticatedUser,
    testCaseResultID: TestCaseResultID,
    status: TestRun.TestCaseStatus,
    notes: String?
) async throws -> TestRun.Status {
    let conn = try await session.conn()
    try await service.test.statusTestCase(conn: conn, id: testCaseResultID, userID: user.user.id, status: status, notes: notes)
    let result = try await service.test.testCaseResult(conn: conn, id: testCaseResultID)
    return try await service.test.testRunStatus(conn: conn, id: result.testRunID)
}

func finishTestRun(
    session: Database.Session,
    user: AuthenticatedUser,
    testRunID: TestRunID,
    determination: TestRunResults.Determination,
    notes: String?
) async throws -> TestRunResults {
    let conn = try await session.conn()
    _ = try await service.test.finishTestRun(conn: conn, id: testRunID, userID: user.user.id, determination: determination, notes: notes)
    return try await service.test.testRunResults(conn: conn, id: testRunID)
}

func testRunResults(
    session: Database.Session,
    user: AuthenticatedUser,
    id: TestRunID
) async throws -> TestRunResults {
    let conn = try await session.conn()
    return try await service.test.testRunResults(conn: conn, id: id)
}

func testRuns(
    session: Database.Session,
    user: AuthenticatedUser
) async throws -> [TestRun] {
    let conn = try await session.conn()
    return try await service.test.testRuns(conn: conn)
}

func finishedTestRuns(
    session: Database.Session,
    user: AuthenticatedUser
) async throws -> [TestRun] {
    let conn = try await session.conn()
    return try await service.test.finishedTestRuns(conn: conn)
}
