/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

extension api {
    public nonisolated(unsafe) internal(set) static var test = TestManagementAPI()
}

public class TestManagementAPI {
    var _home: (Database.Session, AuthenticatedUser) async throws -> TestHome
    var _search: (Database.Session, AuthenticatedUser, SearchTerm?) async throws -> [TestSearchResult]

    var _project: (Database.Session, AuthenticatedUser, TestProjectID?) async throws -> TestProject
    var _saveProject: (Database.Session, AuthenticatedUser, TestProjectID?, String?) async throws -> TestProject
    var _deleteProject: (Database.Session, AuthenticatedUser, TestProjectID) async throws -> Void
    var _projects: (Database.Session, AuthenticatedUser) async throws -> [TestProject]
    var _testSuites: (Database.Session, AuthenticatedUser, TestProjectID) async throws -> [TestSuite]
    var _projectTree: (Database.Session, AuthenticatedUser, TestProjectID?) async throws -> TestProjectTree

    var _testSuite: (Database.Session, AuthenticatedUser, TestSuiteID?) async throws -> TestSuite
    var _saveTestSuite: (Database.Session, AuthenticatedUser, TestSuiteID?, TestProjectID?, String? /* name */) async throws -> TestSuite
    var _saveTestSuiteText: (Database.Session, AuthenticatedUser, TestSuiteID, String? /* text */, [TestManagementAPI.TestSuiteTestCase]) async throws -> TestSuite
    var _testCases: (Database.Session, AuthenticatedUser, TestSuiteID) async throws -> [TestCase]
    
    var _deleteTestSuite: (Database.Session, AuthenticatedUser, TestSuiteID) async throws -> Void

    var _testCase: (Database.Session, AuthenticatedUser, TestCaseID?) async throws -> TestCase
    var _saveTestCase: (Database.Session, AuthenticatedUser, TestSuiteID?, TestCaseID?, String?, String?, Bool?) async throws -> TestCase
    var _deleteTestCase: (Database.Session, AuthenticatedUser, TestCaseID) async throws -> Void

    // NOTE: Uploading and adding links is done by saving the `TestCase`

    var _testRun: (Database.Session, AuthenticatedUser) async throws -> [TestProjectTree]
    var _findTestModels: (Database.Session, AuthenticatedUser, SearchTerm, Bool /* reverse lookup */) async throws -> [TestSearchResult]
    var _startTestRun: (Database.Session, AuthenticatedUser, String? /* name */, Bool? /* include automated tests */, [TestModelID]?) async throws -> TestRun
    var _activeTestRun: (Database.Session, AuthenticatedUser, TestRunID) async throws -> TestRun
    var _statusTestCase: (Database.Session, AuthenticatedUser, TestCaseResultID, TestRun.TestCaseStatus, String? /* Notes */) async throws -> TestRun.Status
    var _finishTestRun: (Database.Session, AuthenticatedUser, TestRunID, TestRunResults.Determination, String? /* Notes */) async throws -> TestRunResults
    var _testRunResults: (Database.Session, AuthenticatedUser, TestRunID) async throws -> TestRunResults
    var _testRuns: (Database.Session, AuthenticatedUser) async throws -> [TestRun]
    var _finishedTestRuns: (Database.Session, AuthenticatedUser) async throws -> [TestRun]

    var _createResource: (Database.Session, AuthenticatedUser, TestSuiteID) async throws -> TestSuiteResourceID
    var _updateResource: (Database.Session, AuthenticatedUser, TestSuiteResourceID, String /* name */, String /* MIME */, String /* path */) async throws -> TestSuiteResource
    var _deleteResource: (Database.Session, AuthenticatedUser, TestSuiteResourceID) async throws -> Void
    
    init() {
        self._home = ayslib.home(session:user:)
        self._search = ayslib.search(session:user:term:)

        self._project = ayslib.project(session:user:id:)
        self._saveProject = ayslib.saveProject(session:user:id:name:)
        self._deleteProject = ayslib.deleteProject(session:user:id:)
        self._projects = ayslib.projects(session:user:)
        self._testSuites = ayslib.testSuites(session:user:projectID:)
        self._projectTree = ayslib.projectTree(session:user:projectID:)

        self._testRun = ayslib.testRun(session:user:)
        self._findTestModels = ayslib.findTestModels(session:user:searchTerm:reverseLookup:)
        self._startTestRun = ayslib.startTestRun(session:user:name:includeAutomated:modelIDs:)
        self._activeTestRun = ayslib.activeTestRun(session:user:testRunID:)
        self._statusTestCase = ayslib.statusTestCase(session:user:testCaseResultID:status:notes:)
        self._finishTestRun = ayslib.finishTestRun(session:user:testRunID:determination:notes:)
        self._testRunResults = ayslib.testRunResults(session:user:id:)
        self._testRuns = ayslib.testRuns(session:user:)
        self._finishedTestRuns = ayslib.finishedTestRuns(session:user:)
        
        self._testSuite = ayslib.testSuite(session:user:id:)
        self._saveTestSuite = ayslib.saveTestSuite(session:user:id:projectID:name:)
        self._saveTestSuiteText = ayslib.saveTestSuite(session:user:id:text:testCases:)
        self._deleteTestSuite = ayslib.deleteTestSuite(session:user:id:)
        self._testCases = ayslib.testCases(session:user:testSuiteID:)
                
        self._testCase = ayslib.testCase(session:user:id:)
        self._saveTestCase = ayslib.saveTestCase(session:user:id:testSuiteID:name:notes:isAutomated:)
        self._deleteTestCase = ayslib.deleteTestCase(session:user:id:)
        
        self._createResource = ayslib.createResource(session:user:testSuiteID:)
        self._updateResource = ayslib.updateResource(session:user:id:name:mimeType:path:)
        self._deleteResource = ayslib.deleteResource(session:user:id:)
    }

    public func home(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser
    ) async throws -> TestHome {
        try await _home(session, user)
    }

    public func search(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        term: SearchTerm?
    ) async throws -> [TestSearchResult] {
        try await _search(session, user, term)
    }
    
    /// Create resource.
    ///
    /// A resource must be created before its name, MIME type, and path can be saved.
    ///
    /// - Parameter session: Database session
    /// - Parameter User: Signed in user
    /// - Parameter testSuiteID:
    public func createResource(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        testSuiteID: TestSuiteID
    ) async throws -> TestSuiteResourceID {
        try await _createResource(session, user, testSuiteID)
    }
    
    public func updateResource(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        id: TestSuiteResourceID,
        name: String,
        mimeType: String,
        path: String
    ) async throws -> TestSuiteResource {
        try await _updateResource(session, user, id, name, mimeType, path)
    }
    
    /// Delete a media resource from a test case.
    public func deleteResource(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        id: TestSuiteResourceID
    ) async throws -> Void {
        try await _deleteResource(session, user, id)
    }
}

private func home(session: Database.Session, user: AuthenticatedUser) async throws -> TestHome {
    let conn = try await session.conn()

    let projects = try await service.test.projects(conn: conn)
    let activeTestRuns = try await service.test.activeTestRuns(conn: conn)
    return .init(
        projects: projects,
        activeTestRuns: activeTestRuns
    )
}

private func search(
    session: Database.Session,
    user: AuthenticatedUser,
    term: SearchTerm?
) async throws -> [TestSearchResult] {
    guard let term, term.count > 0 else {
        return [TestSearchResult]()
    }
    let conn = try await session.conn()
    return try await service.test.search(conn: conn, term: term)
}

private func createResource(
    session: Database.Session,
    user: AuthenticatedUser,
    testSuiteID: TestSuiteID
) async throws -> TestSuiteResourceID {
    let conn = try await session.conn()
    return try await service.test.createResource(conn: conn, testSuiteID: testSuiteID).id
}

private func updateResource(
    session: Database.Session,
    user: AuthenticatedUser,
    id: TestSuiteResourceID,
    name: String,
    mimeType: String,
    path: String
) async throws -> TestSuiteResource {
    let conn = try await session.conn()
    var resource = try await service.test.resource(conn: conn, id: id)
    resource.name = name
    resource.mimeType = mimeType
    resource.path = path
    return try await service.test.updateResource(conn: conn, resource)
}

private func deleteResource(
    session: Database.Session,
    user: AuthenticatedUser,
    id: TestSuiteResourceID
) async throws -> Void {
    let conn = try await session.conn()
    try await service.test.deleteResource(conn: conn, id: id)
}
