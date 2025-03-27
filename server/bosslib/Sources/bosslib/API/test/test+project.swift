/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

extension TestManagementAPI {
    public func project(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        id: TestProjectID?
    ) async throws -> TestProject {
        try await _project(session, user, id)
    }
    
    public func saveProject(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        id: TestProjectID?,
        name: String?
    ) async throws -> TestProject {
        try await _saveProject(session, user, id, name)
    }
    
    public func deleteProject(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        id: TestProjectID
    ) async throws -> Void {
        try await _deleteProject(session, user, id)
    }
    
    public func projects(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser
    ) async throws -> [TestProject] {
        try await _projects(session, user)
    }
    
    public func projectTree(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        projectID: TestProjectID?
    ) async throws -> TestProjectTree {
        try await _projectTree(session, user, projectID)
    }
    
    public func testSuites(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        projectID: TestProjectID
    ) async throws -> [TestSuite] {
        try await _testSuites(session, user, projectID)
    }
}

func project(
    session: Database.Session,
    user: AuthenticatedUser,
    id: TestProjectID?
) async throws -> TestProject {
    guard let id else {
        throw api.error.InvalidParameter(name: "id")
    }
    
    let conn = try await session.conn()
    return try await service.test.project(conn: conn, id: id)
}

func saveProject(
    session: Database.Session,
    user: AuthenticatedUser,
    id: TestProjectID?,
    name: String?
) async throws -> TestProject {
    guard let name else {
        throw api.error.InvalidParameter(name: "name")
    }
    
    let conn = try await session.conn()
    if let id {
        let project = TestProject(id: id, name: name)
        return try await service.test.updateProject(conn: conn, project)
    }
    else {
        return try await service.test.createProject(conn: conn, name: name)
    }
}

func deleteProject(
    session: Database.Session,
    user: AuthenticatedUser,
    id: TestProjectID
) async throws -> Void {
    let conn = try await session.conn()
    return try await service.test.deleteProject(conn: conn, id: id)
}

func projects(session: Database.Session, user: AuthenticatedUser) async throws -> [TestProject] {
    let conn = try await session.conn()
    return try await service.test.projects(conn: conn)
}

func testSuites(
    session: Database.Session,
    user: AuthenticatedUser,
    projectID: TestProjectID
) async throws -> [TestSuite] {
    let conn = try await session.conn()
    return try await service.test.testSuites(conn: conn, projectID: projectID)
}

func projectTree(
    session: Database.Session,
    user: AuthenticatedUser,
    projectID: TestProjectID?
) async throws -> TestProjectTree {
    guard let projectID else {
        throw api.error.InvalidParameter(name: "projectID")
    }
    
    let conn = try await session.conn()
    
    let project = try await service.test.project(conn: conn, id: projectID)
    let testSuites = try await service.test.testSuites(conn: conn, projectID: projectID)
    
    var branches = [TestProjectTree.TestSuite]()
    for suite in testSuites {
        let branch = TestProjectTree.TestSuite(
            id: suite.id,
            name: suite.name,
            testCases: try await service.test.testCases(conn: conn, testSuiteID: suite.id),
            totalTestCases: suite.totalTestCases,
            automatedTestCases: suite.automatedTestCases
        )
        branches.append(branch)
    }
    
    return TestProjectTree(
        id: project.id,
        name: project.name,
        testSuites: branches
    )
}
