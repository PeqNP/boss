/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.
/// Potentially start using GRDB: https://github.com/groue/GRDB.swift. I'm not sure how well SQLite is supported and whether
/// it brings in more dependencies than it needs (is it an older vapor library?).

import Foundation
internal import SQLiteKit

protocol TestProvider {
    func homeProjects(conn: Database.Connection) async throws -> [TestHomeProject]
    func projects(conn: Database.Connection) async throws -> [TestProject]
    func search(conn: Database.Connection, term: SearchTerm) async throws -> [TestSearchResult]
    
    func project(conn: Database.Connection, id: TestProjectID) async throws -> TestProject
    func createProject(conn: Database.Connection, name: String) async throws ->TestProject
    func updateProject(conn: Database.Connection, _ project: TestProject) async throws -> TestProject
    func deleteProject(conn: Database.Connection, id: TestProjectID) async throws -> Void
    func testSuites(conn: Database.Connection, projectID: TestProjectID) async throws -> [TestSuite]
    
    func testSuite(conn: Database.Connection, id: TestSuiteID) async throws -> TestSuite
    func createTestSuite(conn: Database.Connection, projectID: TestProjectID, name: String, text: String?) async throws ->TestSuite
    func updateTestSuite(conn: Database.Connection, _ testSuite: TestSuite) async throws -> TestSuite
    func deleteTestSuite(conn: Database.Connection, id: TestSuiteID) async throws -> Void
    func testCases(conn: Database.Connection, testSuiteID: TestSuiteID) async throws -> [TestCase]
        
    func testCase(conn: Database.Connection, id: TestCaseID) async throws -> TestCase
    func createTestCase(conn: Database.Connection, projectID: TestProjectID, testSuiteID: TestSuiteID, name: String, notes: String?, isAutomated: Bool) async throws -> TestCase
    func updateTestCase(conn: Database.Connection, _ testCase: TestCase) async throws -> TestCase
    func deleteTestCase(conn: Database.Connection, id: TestCaseID) async throws -> Void
    func resources(conn: Database.Connection, testSuiteID: TestSuiteID) async throws -> [TestSuiteResource]
    func resource(conn: Database.Connection, id: TestSuiteResourceID) async throws -> TestSuiteResource
    func createResource(conn: Database.Connection, testSuiteID: TestSuiteID) async throws -> TestSuiteResource
    func updateResource(conn: Database.Connection, _ resource: TestSuiteResource) async throws -> TestSuiteResource
    func deleteResource(conn: Database.Connection, id: TestSuiteResourceID) async throws -> Void
    
    func activeTestRuns(conn: Database.Connection) async throws -> [TestRun]
    func testRun(conn: Database.Connection, id: TestRunID) async throws -> TestRun
    func searchTestSuites(conn: Database.Connection, term: SearchTerm) async throws -> [TestSearchResult]
    func startTestRun(conn: Database.Connection, name: String, includeAutomated: Bool, modelIDs: [String]) async throws -> TestRun
    func testRunStatus(conn: Database.Connection, id: TestRunID) async throws -> TestRun.Status
    func statusTestCase(conn: Database.Connection, id: TestCaseResultID, userID: UserID, status: TestRun.TestCaseStatus, notes: String?) async throws -> Void
    func finishTestRun(conn: Database.Connection, id: TestRunID, userID: UserID, determination: TestRunResults.Determination, notes: String?) async throws -> Void
    func testRunResults(conn: Database.Connection, id: TestRunID) async throws -> TestRunResults
    func testCaseResult(conn: Database.Connection, id: TestCaseResultID) async throws -> TestRun.TestCaseResult
    func testRuns(conn: Database.Connection) async throws -> [TestRun]
    func finishedTestRuns(conn: Database.Connection) async throws -> [TestRun]
}

class TestService {
    var _homeProjects: (Database.Connection) async throws -> [TestHomeProject] = { _ in fatalError("TestService.homeProjects()") }
    var _projects: (Database.Connection) async throws -> [TestProject] = { _ in fatalError("TestService.projects()") }
    var _search: (Database.Connection, SearchTerm) async throws -> [TestSearchResult] = { _, _ in fatalError("TestService.search()") }
    
    var _project: (Database.Connection, TestProjectID) async throws -> TestProject = { _, _ in fatalError("TestService.project") }
    var _createProject: (Database.Connection, String) async throws -> TestProject = { _, _ in fatalError("TestService.createProject") }
    var _updateProject: (Database.Connection, TestProject) async throws -> TestProject = { _, _ in fatalError("TestService.updateProject") }
    var _deleteProject: (Database.Connection, TestProjectID) async throws -> Void = { _, _ in fatalError("TestService.deleteProject") }
    var _testSuites: (Database.Connection, TestProjectID) async throws -> [TestSuite] = { _, _ in fatalError("TestService.testSuites") }
    
    var _testSuite: (Database.Connection, TestSuiteID) async throws -> TestSuite = { _, _ in fatalError("TestService.testSuite") }
    var _createTestSuite: (Database.Connection, TestProjectID, String, String?) async throws -> TestSuite = { _, _, _, _ in fatalError("TestService.createTestSuite") }
    var _updateTestSuite: (Database.Connection, TestSuite) async throws -> TestSuite = { _, _ in fatalError("TestService.updateTestSuite") }
    var _deleteTestSuite: (Database.Connection, TestSuiteID) async throws -> Void = { _, _ in fatalError("TestService.deleteTestSuite") }
    var _testCases: (Database.Connection, TestSuiteID) async throws -> [TestCase] = { _, _ in fatalError("TestService.testCases") }
        
    var _testCase: (Database.Connection, TestCaseID) async throws -> TestCase = { _, _ in fatalError("TestService.testCase") }
    var _createTestCase: (Database.Connection, TestProjectID, TestSuiteID, String, String?, Bool) async throws -> TestCase = { _, _, _, _, _, _ in fatalError("TestService.createTestCase") }
    var _updateTestCase: (Database.Connection, TestCase) async throws -> TestCase = { _, _ in fatalError("TestService.updateTestCase") }
    var _deleteTestCase: (Database.Connection, TestCaseID) async throws -> Void = { _, _ in fatalError("TestService.deleteTestCase") }
    var _resources: (Database.Connection, TestSuiteID) async throws -> [TestSuiteResource] = { _, _ in fatalError("TestService.resources") }
    var _resource: (Database.Connection, TestSuiteResourceID) async throws -> TestSuiteResource = { _, _ in fatalError("TestService.resource") }
    var _createResource: (Database.Connection, TestCaseID) async throws -> TestSuiteResource = { _, _ in fatalError("TestService.createResource") }
    var _updateResource: (Database.Connection, TestSuiteResource) async throws -> TestSuiteResource = { _, _ in fatalError("TestService.updateResource") }
    var _deleteResource: (Database.Connection, TestSuiteResourceID) async throws -> Void = { _, _ in fatalError("TestService.deleteResource") }
    
    var _activeTestRuns: (Database.Connection) async throws -> [TestRun] = { _ in fatalError("TestService.activeTestRuns()") }
    var _testRun: (Database.Connection, TestRunID) async throws -> TestRun = { _, _ in fatalError("TestService.testRun") }
    var _searchTestSuites: (Database.Connection, SearchTerm) async throws -> [TestSearchResult] = { _, _ in fatalError("TestService.searchTestSuites()") }
    var _startTestRun: (Database.Connection, String, Bool, [String]) async throws -> TestRun = { _, _, _, _ in fatalError("TestService.startTestRun()") }
    var _testRunStatus: (Database.Connection, TestRunID) async throws -> TestRun.Status = { _, _ in fatalError("TestService.startTestRun") }
    var _statusTestCase: (Database.Connection, TestCaseResultID, UserID, TestRun.TestCaseStatus, String?) async throws -> Void = { _, _, _, _, _ in fatalError("TestService.statusTestCase") }
    var _finishTestRun: (Database.Connection, TestRunID, UserID, TestRunResults.Determination, String?) async throws -> Void = { _, _, _, _, _ in fatalError("TestService.finishTestRun") }
    var _testRunResults: (Database.Connection, TestRunID) async throws -> TestRunResults = { _, _ in fatalError("TestService.finishTestRun") }
    var _testCaseResult: (Database.Connection, TestCaseResultID) async throws -> TestRun.TestCaseResult = { _, _ in fatalError("TestService.testCaseResult") }
    var _testRuns: (Database.Connection) async throws -> [TestRun] = { _ in fatalError("TestService.testRuns") }
    var _finishedTestRuns: (Database.Connection) async throws -> [TestRun] = { _ in fatalError("TestService.finishedTestRuns") }
    
    init() { }

    init(_ p: TestProvider) {
        self._homeProjects = p.homeProjects
        self._projects = p.projects
        self._search = p.search
        
        self._project = p.project
        self._createProject = p.createProject
        self._updateProject = p.updateProject
        self._deleteProject = p.deleteProject
        self._testSuites = p.testSuites
        
        self._testSuite = p.testSuite
        self._createTestSuite = p.createTestSuite
        self._updateTestSuite = p.updateTestSuite
        self._deleteTestSuite = p.deleteTestSuite
        self._testCases = p.testCases
                
        self._testCase = p.testCase
        self._createTestCase = p.createTestCase
        self._updateTestCase = p.updateTestCase
        self._deleteTestCase = p.deleteTestCase
        self._resources = p.resources
        self._resource = p.resource
        self._createResource = p.createResource
        self._updateResource = p.updateResource
        self._deleteResource = p.deleteResource
        
        self._activeTestRuns = p.activeTestRuns
        self._testRun = p.testRun
        self._searchTestSuites = p.searchTestSuites
        self._startTestRun = p.startTestRun
        self._testRunStatus = p.testRunStatus
        self._statusTestCase = p.statusTestCase
        self._finishTestRun = p.finishTestRun
        self._testRunResults = p.testRunResults
        self._testCaseResult = p.testCaseResult
        self._testRuns = p.testRuns
        self._finishedTestRuns = p.finishedTestRuns
    }

    func homeProjects(conn: Database.Connection) async throws -> [TestHomeProject] {
        try await _homeProjects(conn)
    }
    
    func projects(conn: Database.Connection) async throws -> [TestProject] {
        try await _projects(conn)
    }

    func search(conn: Database.Connection, term: SearchTerm) async throws -> [TestSearchResult] {
        try await _search(conn, term)
    }
    
    // MARK: Project
    
    func project(conn: Database.Connection, id: TestProjectID) async throws -> TestProject {
        try await _project(conn, id)
    }
    
    func createProject(conn: Database.Connection, name: String) async throws -> TestProject {
        try await _createProject(conn, name)
    }
    
    func updateProject(conn: Database.Connection, _ project: TestProject) async throws -> TestProject {
        try await _updateProject(conn, project)
    }
    
    func deleteProject(conn: Database.Connection, id: TestProjectID) async throws {
        try await _deleteProject(conn, id)
    }
    
    func testSuites(conn: Database.Connection, projectID: TestProjectID) async throws -> [TestSuite] {
        try await _testSuites(conn, projectID)
    }
    
    // MARK: TestSuite
    
    func testSuite(conn: Database.Connection, id: TestSuiteID) async throws -> TestSuite {
        try await _testSuite(conn, id)
    }
    
    func createTestSuite(conn: Database.Connection, projectID: TestProjectID, name: String, text: String?) async throws -> TestSuite {
        try await _createTestSuite(conn, projectID, name, text)
    }
    
    func updateTestSuite(conn: Database.Connection, _ testSuite: TestSuite) async throws -> TestSuite {
        try await _updateTestSuite(conn, testSuite)
    }
    
    func deleteTestSuite(conn: Database.Connection, id: TestSuiteID) async throws {
        try await _deleteTestSuite(conn, id)
    }
    
    func testCases(conn: Database.Connection, testSuiteID: TestSuiteID) async throws -> [TestCase] {
        try await _testCases(conn, testSuiteID)
    }
        
    // MARK: TestCase
    
    func testCase(conn: Database.Connection, id: TestCaseID) async throws -> TestCase {
        try await _testCase(conn, id)
    }
    
    func createTestCase(conn: Database.Connection, projectID: TestProjectID, testSuiteID: TestSuiteID, name: String, notes: String?, isAutomated: Bool) async throws -> TestCase {
        try await _createTestCase(conn, projectID, testSuiteID, name, notes, isAutomated)
    }
    
    func updateTestCase(conn: Database.Connection, _ testCase: TestCase) async throws -> TestCase {
        try await _updateTestCase(conn, testCase)
    }
    
    func deleteTestCase(conn: Database.Connection, id: TestCaseID) async throws {
        try await _deleteTestCase(conn, id)
    }
    
    func resources(conn: Database.Connection, testSuiteID: TestSuiteID) async throws -> [TestSuiteResource] {
        try await _resources(conn, testSuiteID)
    }
    
    func resource(conn: Database.Connection, id: TestSuiteResourceID) async throws -> TestSuiteResource {
        try await _resource(conn, id)
    }
    
    func createResource(conn: Database.Connection, testSuiteID: TestSuiteID) async throws -> TestSuiteResource {
        try await _createResource(conn, testSuiteID)
    }
    
    func updateResource(conn: Database.Connection, _ resource: TestSuiteResource) async throws -> TestSuiteResource {
        try await _updateResource(conn, resource)
    }
    
    func deleteResource(conn: Database.Connection, id: TestSuiteResourceID) async throws {
        try await _deleteResource(conn, id)
    }
    
    // MARK: Test Runs
    
    func activeTestRuns(conn: Database.Connection) async throws -> [TestRun] {
        try await _activeTestRuns(conn)
    }
    
    func testRun(conn: Database.Connection, id: TestRunID) async throws -> TestRun {
        try await _testRun(conn, id)
    }
    
    func searchTestSuites(conn: Database.Connection, term: SearchTerm) async throws -> [TestSearchResult] {
        try await _searchTestSuites(conn, term)
    }
    
    func startTestRun(conn: Database.Connection, name: String, includeAutomated: Bool, modelIDs: [String]) async throws -> TestRun {
        try await _startTestRun(conn, name, includeAutomated, modelIDs)
    }
    
    func testRunStatus(conn: Database.Connection, id: TestRunID) async throws -> TestRun.Status {
        try await _testRunStatus(conn, id)
    }
    
    func statusTestCase(conn: Database.Connection, id: TestCaseResultID, userID: UserID, status: TestRun.TestCaseStatus, notes: String?) async throws {
        try await _statusTestCase(conn, id, userID, status, notes)
    }
    
    func finishTestRun(conn: Database.Connection, id: TestRunID, userID: UserID, determination: TestRunResults.Determination, notes: String?) async throws -> Void {
        try await _finishTestRun(conn, id, userID, determination, notes)
    }
    
    func testRunResults(conn: Database.Connection, id: TestRunID) async throws -> TestRunResults {
        try await _testRunResults(conn, id)
    }

    func testCaseResult(conn: Database.Connection, id: TestCaseResultID) async throws -> TestRun.TestCaseResult {
        try await _testCaseResult(conn, id)
    }
    
    func testRuns(conn: Database.Connection) async throws -> [TestRun] {
        try await _testRuns(conn)
    }
    
    func finishedTestRuns(conn: Database.Connection) async throws -> [TestRun] {
        try await _finishedTestRuns(conn)
    }
}

class TestSQLiteService: TestProvider {
    func homeProjects(conn: Database.Connection) async throws -> [TestHomeProject] {
        let rows = try await conn.select()
            .column("*")
            .from("projects")
            .all()
        let projects = try rows.map { try makeProject(from: $0) }
        
        var homeProjects = [TestHomeProject]()
        for project in projects {
            let total = try await conn.query("SELECT COUNT(*) AS num_projects FROM test_cases WHERE project_id = ?", [.integer(project.id)])
            let totalTestCases = try total[0].sql().decode(column: "num_projects", as: Int.self)
            
            let automated = try await conn.query("SELECT COUNT(*) AS num_projects FROM test_cases WHERE project_id = ? AND is_automated = ?", [.integer(project.id), .integer(1)])
            let automatedTestCases = try automated[0].sql().decode(column: "num_projects", as: Int.self)
            
            let percentAutomated: Double = if automatedTestCases < 1 {
                0
            }
            else {
                Double(automatedTestCases) / Double(totalTestCases)
            }
            homeProjects.append(.init(
                id: project.id,
                name: "\(project.name), Automated (\(automatedTestCases)/\(totalTestCases)) \(Int(percentAutomated * 100.0))%",
                totalTestCases: totalTestCases,
                automatedTestCases: automatedTestCases,
                percentAutomated: percentAutomated
            ))
        }

        return  homeProjects
    }
    
    func projects(conn: Database.Connection) async throws -> [TestProject] {
        let rows = try await conn.select()
            .column("*")
            .from("projects")
            .all()
        return try rows.map { try makeProject(from: $0) }
    }
    
    func search(conn: Database.Connection, term: SearchTerm) async throws -> [TestSearchResult] {
        let terms = term.components(separatedBy: ",").map {
            $0.trimmingCharacters(in: .whitespacesAndNewlines)
        }
        
        var projects = try await searchForProjects(conn: conn, terms: terms)
        let testSuites = try await searchForTestSuites(conn: conn, terms: terms)
        let testCases = try await searchForTestCases(conn: conn, terms: terms)
        projects.append(contentsOf: testSuites)
        projects.append(contentsOf: testCases)
        return projects
    }
    
    /// Return unique set of model IDs
    ///
    /// - Returns: Unique set of model IDs
    private func idsForLabel(_ label: String, from terms: [SearchTerm]) -> [Int] {
        let ids = terms.compactMap { (term: String) -> Int? in
            if term.starts(with: label) {
                return Int(term
                    .replacingOccurrences(of: label, with: "")
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                )
            }
            return nil
        }
        
        return Array(Set(ids))
    }
    
    private func idsAndNames(for label: String, from terms: [SearchTerm]) -> ([Int], [String]) {
        let ids = idsForLabel(label, from: terms)
        let names = terms.compactMap { term in
            // Any term that starts with a model ID should not be considered a name
            if !term.starts(with: "P-") && !term.starts(with: "TS-") && !term.starts(with: "TC-") {
                return term.cleaned()
            }
            return nil
        }
        return (ids, names)
    }
    
    private func allRecords<T>(
        conn: Database.Connection,
        table: String,
        ids: [Int],
        make: (SQLRow) throws -> T
    ) async throws -> [T] {
        guard ids.count > 0 else {
            return [T]()
        }
        let rows = try await conn.select()
            .column("*")
            .from(table)
            .where("id", .in, ids)
            // Is there a way to use `OR`?
            .all()
        return try rows.map { try make($0) }
    }
    
    private func allRecords<T>(
        conn: Database.Connection,
        table: String,
        names: [String],
        make: @escaping (SQLiteRow) throws -> T
    ) async throws -> [T] {
        guard names.count > 0 else {
            return [T]()
        }
        
        let likes = names.map { _ in "name LIKE ?" }
        let stmt = "SELECT * FROM \(table) WHERE \(likes.joined(separator: " OR "))"
        let binds: [SQLiteData] = names.map { (name: String) -> SQLiteData in .text("%\(name)%") }
        let records = try await conn.query(stmt, binds).map {
            try make($0)
        }
        return records
    }
    
    private func searchForProjects(conn: Database.Connection, terms: [SearchTerm]) async throws -> [TestSearchResult] {
        let (projectIDs, names) = idsAndNames(for: "P-", from: terms)
        
        var projects = try await allRecords(conn: conn, table: "projects", ids: projectIDs, make: makeProject(from:))
        projects.append(contentsOf: try await allRecords(conn: conn, table: "projects", names: names, make: makeProject(from:)))
        
        return projects.map { (project: TestProject) -> TestSearchResult in
            .init(
                id: "P-\(project.id)",
                name: "P-\(project.id): \(project.name)",
                config: .init(projectID: project.id, testSuiteID: nil, testCaseID: nil)
            )
        }
    }
    
    private func searchForTestSuites(conn: Database.Connection, terms: [SearchTerm]) async throws -> [TestSearchResult] {
        let (testSuiteIDs, names) = idsAndNames(for: "TS-", from: terms)
        
        var testSuites = try await allRecords(conn: conn, table: "test_suites", ids: testSuiteIDs, make: makeTestSuite(from:))
        testSuites.append(contentsOf: try await allRecords(conn: conn, table: "test_suites", names: names, make: makeTestSuite(from:)))
        
        return testSuites.map { (testSuite: TestSuite) -> TestSearchResult in
            .init(
                id: "TS-\(testSuite.id)",
                name: "TS-\(testSuite.id): \(testSuite.name)",
                config: .init(projectID: testSuite.projectID, testSuiteID: testSuite.id, testCaseID: nil)
            )
        }
    }
    
    private func searchForTestCases(conn: Database.Connection, terms: [SearchTerm]) async throws -> [TestSearchResult] {
        let (testCaseIDs, names) = idsAndNames(for: "TC-", from: terms)
        
        var testCases = try await allRecords(conn: conn, table: "test_cases", ids: testCaseIDs, make: makeTestCase(from:))
        try await testCases.append(contentsOf: allRecords(conn: conn, table: "test_cases", names: names, make: makeTestCase(from:)))
        
        return testCases.map { (testCase: TestCase) -> TestSearchResult in
            .init(
                id: "TC-\(testCase.id)",
                name: "TC-\(testCase.id): \(testCase.name)",
                config: .init(projectID: testCase.projectID, testSuiteID: testCase.testSuiteID, testCaseID: testCase.id)
            )
        }
    }
    
    func project(conn: Database.Connection, id: TestProjectID) async throws -> TestProject {
        let rows = try await conn.select()
            .column("*")
            .from("projects")
            .where("id", .equal, id)
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        return try makeProject(from: row)
    }
    
    func testSuite(conn: Database.Connection, id: TestSuiteID) async throws -> TestSuite {
        let rows = try await conn.select()
            .column("*")
            .from("test_suites")
            .where("id", .equal, id)
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        return try await makeTestSuite(conn: conn, from: row)
    }
        
    func testCase(conn: Database.Connection, id: TestCaseID) async throws -> TestCase {
        let rows = try await conn.select()
            .column("*")
            .from("test_cases")
            .where("id", .equal, id)
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        return try makeTestCase(from: row)
    }
    
    func resources(conn: Database.Connection, testSuiteID: TestSuiteID) async throws -> [TestSuiteResource] {
        let rows = try await conn.select()
            .column("*")
            .from("test_suite_resources")
            .where("test_suite_id", .equal, testSuiteID)
            .all()
        var resources = [TestSuiteResource]()
        for row in rows {
            resources.append(try makeResource(from: row))
        }
        return resources
    }
    
    func resource(conn: Database.Connection, id: TestSuiteResourceID) async throws -> TestSuiteResource {
        let rows = try await conn.select()
            .column("*")
            .from("test_suite_resources")
            .where("id", .equal, id)
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        return try .init(
            id: row.decode(column: "id", as: TestSuiteResourceID.self),
            testSuiteID: row.decode(column: "test_suite_id", as: TestCaseID.self),
            mimeType: row.decode(column: "mime_type", as: String?.self),
            name: row.decode(column: "name", as: String?.self),
            path: row.decode(column: "path", as: String?.self)
        )
    }
    
    func createResource(
        conn: Database.Connection,
        testSuiteID: TestSuiteID
    ) async throws -> TestSuiteResource {
        let rows = try await conn.sql().insert(into: "test_suite_resources")
            .columns("id", "test_suite_id")
            .values(
                SQLLiteral.null,
                SQLBind(testSuiteID)
            )
            .returning("id")
            .all()

        return TestSuiteResource(
            id: try rows[0].decode(column: "id", as: TestProjectID.self),
            testSuiteID: testSuiteID,
            mimeType: "",
            name: "",
            path: ""
        )
    }
    
    func updateResource(conn: Database.Connection, _ resource: TestSuiteResource) async throws -> TestSuiteResource {
        try await conn.sql().update("test_suite_resources")
            .set("name", to: SQLBind(resource.name))
            .set("mime_type", to: SQLBind(resource.mimeType))
            .set("path", to: SQLBind(resource.path))
            .where("id", .equal, SQLBind(resource.id))
            .run()
        return resource
    }
    
    func deleteResource(conn: Database.Connection, id: TestSuiteResourceID) async throws {
        try await conn.sql().delete(from: "test_suite_resources")
            .where("id", .equal, SQLBind(id))
            .run()
    }
        
    func testRun(conn: Database.Connection, id: TestRunID, includeTestSuites: Bool) async throws -> TestRun {
        let rows = try await conn.select()
            .column("*")
            .from("test_runs")
            .where("id", .equal, id)
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        return try await makeTestRun(conn: conn, from: row)
    }
}

// MARK: - TestProject

extension TestSQLiteService {
    func createProject(conn: Database.Connection, name: String) async throws -> TestProject {
        let rows = try await conn.sql().insert(into: "projects")
            .columns("id", "name")
            .values(
                SQLLiteral.null,
                SQLBind(name)
            )
            .returning("id")
            .all()

        return TestProject(
            id: try rows[0].decode(column: "id", as: TestProjectID.self),
            name: name,
            testSuiteIDs: []
        )
    }
    
    func updateProject(conn: Database.Connection, _ project: TestProject) async throws -> TestProject {
        try await conn.sql().update("projects")
            .set("name", to: SQLBind(project.name))
            .where("id", .equal, SQLBind(project.id))
            .run()
        return try await self.project(conn: conn, id: project.id)
    }
    
    func deleteProject(conn: Database.Connection, id: TestProjectID) async throws {
        try await conn.sql().delete(from: "projects")
            .where("id", .equal, SQLBind(id))
            .run()
    }
    
    func testSuites(conn: Database.Connection, projectID: TestProjectID) async throws -> [TestSuite] {
        let rows = try await conn.select()
            .column("*")
            .from("test_suites")
            .where("project_id", .equal, projectID)
            .all()
        return try await rows.asyncMap { try await makeTestSuite(conn: conn, from: $0) }
    }
    
    func testSuites(conn: Database.Connection, ids: [TestSuiteID]) async throws -> [TestSuite] {
        let rows = try await conn.select()
            .column("*")
            .from("test_suites")
            .where("project_id", .in, ids)
            .all()
        return try await rows.asyncMap { try await makeTestSuite(conn: conn, from: $0) }
    }
}

// MARK: - TestSuite

extension TestSQLiteService {
    func createTestSuite(
        conn: Database.Connection,
        projectID: TestProjectID,
        name: String,
        text: String?
    ) async throws -> TestSuite {
        let rows = try await conn.sql().insert(into: "test_suites")
            .columns("id", "project_id", "name", "text")
            .values(
                SQLLiteral.null,
                SQLBind(projectID),
                SQLBind(name),
                SQLBind(text)
            )
            .returning("id")
            .all()
        
        let model = TestSuite(
            id: try rows[0].decode(column: "id", as: TestProjectID.self),
            projectID: projectID,
            name: name,
            text: text,
            totalTestCases: 0,
            automatedTestCases: 0
        )

        // Add to project's tree
        var project = try await project(conn: conn, id: projectID)
        project.testSuiteIDs?.append(model.id)
        try await conn.sql().update("projects")
            .set("test_suite_ids", to: SQLBind(project.testSuiteIDs ?? [TestSuiteID]()))
            .where("id", .equal, SQLBind(project.id))
            .run()
        
        return model
    }
    
    func updateTestSuite(conn: Database.Connection, _ testSuite: TestSuite) async throws -> TestSuite {
        try await conn.sql().update("test_suites")
            .set("name", to: SQLBind(testSuite.name))
            .set("text", to: SQLBind(testSuite.text))
            .where("id", .equal, SQLBind(testSuite.id))
            .run()
        return try await self.testSuite(conn: conn, id: testSuite.id)
    }
    
    func deleteTestSuite(conn: Database.Connection, id: TestSuiteID) async throws {
        let testSuite = try await testSuite(conn: conn, id: id)
        var project = try await project(conn: conn, id: testSuite.projectID)
        project.testSuiteIDs?.removeAll(where: { $0 == id })
        
        try await conn.sql().delete(from: "test_suites")
            .where("id", .equal, SQLBind(id))
            .run()
    }
    
    func testCases(conn: Database.Connection, testSuiteID: TestSuiteID) async throws -> [TestCase] {
        let rows = try await conn.select()
            .column("*")
            .from("test_cases")
            .where("test_suite_id", .equal, testSuiteID)
            .all()
        return try rows.map { try makeTestCase(from: $0) }
    }
    
    func testCases(conn: Database.Connection, testSuiteIDs: [TestSuiteID]) async throws -> [TestCase] {
        let rows = try await conn.select()
            .column("*")
            .from("test_cases")
            .where("test_suite_id", .in, testSuiteIDs)
            .all()
        return try rows.map { try makeTestCase(from: $0) }
    }
}

// MARK: - TestCase

extension TestSQLiteService {
    func createTestCase(
        conn: Database.Connection,
        projectID: TestProjectID,
        testSuiteID: TestSuiteID,
        name: String,
        notes: String?,
        isAutomated: Bool
    ) async throws -> TestCase {
        let rows = try await conn.sql().insert(into: "test_cases")
            .columns("id", "project_id", "test_suite_id", "name", "notes", "is_automated")
            .values(
                SQLLiteral.null,
                SQLBind(projectID),
                SQLBind(testSuiteID),
                SQLBind(name),
                SQLBind(notes),
                SQLBind(isAutomated)
            )
            .returning("id")
            .all()

        let model = TestCase(
            id: try rows[0].decode(column: "id", as: TestProjectID.self),
            projectID: projectID,
            testSuiteID: testSuiteID,
            name: name,
            notes: notes,
            isAutomated: isAutomated
        )
        
        return model
    }
    
    @discardableResult
    func updateTestCase(conn: Database.Connection, _ testCase: TestCase) async throws -> TestCase {
        try await conn.sql().update("test_cases")
            .set("test_suite_id", to: SQLBind(testCase.testSuiteID))
            .set("name", to: SQLBind(testCase.name))
            .set("notes", to: SQLBind(testCase.notes))
            .set("is_automated", to: SQLBind(testCase.isAutomated))
            .where("id", .equal, SQLBind(testCase.id))
            .run()
        return testCase
    }
    
    func deleteTestCase(conn: Database.Connection, id: TestCaseID) async throws {
        try await conn.sql().delete(from: "test_cases")
            .where("id", .equal, SQLBind(id))
            .run()
    }
}

// MARK: - Test Runs

extension TestSQLiteService {
    func activeTestRuns(conn: Database.Connection) async throws -> [TestRun] {
        let rows = try await conn.select()
            .column("*")
            .from("test_runs")
            .where("is_finished", .equal, false)
            .all()
        var records = [TestRun]()
        for row in rows {
            records.append(try await makeTestRun(conn: conn, from: row))
        }
        return records
    }
    
    func testRun(conn: Database.Connection, id: TestRunID) async throws -> TestRun {
        let rows = try await conn.select()
            .column("*")
            .from("test_runs")
            .where("id", .equal, id)
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        return try await makeTestRun(conn: conn, from: row)
    }
    
    func searchTestSuites(conn: Database.Connection, term: SearchTerm) async throws -> [TestSearchResult] {
        let terms = term.components(separatedBy: ",").map {
            $0.trimmingCharacters(in: .whitespacesAndNewlines)
        }
        let testCaseIDs = idsForLabel("TC-", from: terms)
        
        let testCases = try await allRecords(conn: conn, table: "test_cases", ids: testCaseIDs, make: makeTestCase(from:))
        let testSuiteIDs = Set(testCases.map { $0.testSuiteID })
        let testSuites = try await allRecords(
            conn: conn,
            table: "test_suites",
            ids: Array(testSuiteIDs),
            make: makeTestSuite(from:)
        )
        return testSuites.map { (testSuite: TestSuite) -> TestSearchResult in
            .init(
                id: "TS-\(testSuite.id)",
                name: "TS-\(testSuite.id): \(testSuite.name)",
                config: .init(projectID: testSuite.projectID, testSuiteID: testSuite.id, testCaseID: nil)
            )
        }
    }
    
    func startTestRun(conn: Database.Connection, name: String, includeAutomated: Bool, modelIDs: [String]) async throws -> TestRun {
        let rows = try await conn.sql().insert(into: "test_runs")
            .columns("id", "date_created", "name", "text", "model_ids", "include_automated", "selected_test_case_id", "is_finished")
            .values(
                SQLLiteral.null,
                SQLBind(Date.now),
                SQLBind(name),
                SQLBind(""),
                SQLBind(modelIDs.joined(separator: ",")),
                SQLBind(includeAutomated),
                SQLLiteral.null,
                SQLBind(false)
            )
            .returning("id")
            .all()
        let id = try rows[0].decode(column: "id", as: TestRunID.self)
        
        var cases = try await allRecords(
            conn: conn,
            table: "test_cases",
            ids: idsForLabel("TC-", from: modelIDs),
            make: makeTestCase(from:)
        )
        
        let projects = try await allRecords(
            conn: conn,
            table: "projects",
            ids: idsForLabel("P-", from: modelIDs),
            make: makeProject(from:)
        )
        var suites = [TestSuite]()
        for project in projects {
            suites.append(contentsOf: try await testSuites(conn: conn, projectID: project.id))
        }
        suites.append(contentsOf: try await allRecords(
            conn: conn,
            table: "test_suites",
            ids: idsForLabel("TS-", from: modelIDs),
            make: makeTestSuite(from:)
        ))
        
        // Add all tests cases that belong to test suites
        let allCasesForTestSuites = try await testCases(conn: conn, testSuiteIDs: suites.map { $0.id })
        
        // Only included cases that are not automated, if configured to do so
        let filteredCases = if includeAutomated {
            allCasesForTestSuites
        }
        else {
            allCasesForTestSuites.filter { testCase in
                !testCase.isAutomated
            }
        }
        cases.append(contentsOf: filteredCases)
        
        guard cases.count > 0 else {
            throw service.error.InvalidInput("In order to start a test run, at least one test case must be found given the search term.")
        }
        
        // Do not duplicate test cases
        var uniqueCases = [TestCase]()
        var testCaseIDs = [TestCaseID]()
        for testCase in cases {
            if testCaseIDs.contains(testCase.id) {
                continue
            }
            testCaseIDs.append(testCase.id)
            uniqueCases.append(testCase)
        }
        
        var firstTestCaseID: TestCaseID = 0
        // List of test suites we need to get text for
        var testSuiteIDs = Set<TestSuiteID>()
        // Used to find test case in string
        var modelIDs = [String]()
        for testCase in uniqueCases {
            try await conn.sql().insert(into: "test_case_results")
                .columns("id", "test_run_id", "test_case_id", "status")
                .values(
                    SQLLiteral.null,
                    SQLBind(id),
                    SQLBind(testCase.id),
                    SQLBind(TestRun.TestCaseStatus.pending)
                )
                .run()
            if firstTestCaseID == 0 {
                firstTestCaseID = testCase.id
            }
            testSuiteIDs.insert(testCase.testSuiteID)
            modelIDs.append("{TC-\(testCase.id)}")
        }
                
        // Compile test that will be used in test run
        suites = try await testSuites(conn: conn, ids: Array(testSuiteIDs))
        var text = [String]()
        for suite in suites {
            var bufferedLines = [String]()
            let lines = suite.text?.components(separatedBy: "\n") ?? [String]()
            var ignore = false
            var testCaseFound = false
            for line in lines {
                let trimmed = line.trimmingCharacters(in: .whitespaces)
                
                // Beginning of new feature
                if trimmed.starts(with: "Feature:") {
                    // Only add feature test cases if at least one test case was found
                    if testCaseFound {
                        text.append(contentsOf: bufferedLines)
                    }
                    
                    ignore = false
                    testCaseFound = false
                    bufferedLines = [line]
                    continue
                }

                if trimmed.starts(with: "Scenario:") {
                    // Ignore unless this test case is included. Otherwise, ignore everything until the next `Scenario` is found
                    ignore = true
                    for id in modelIDs {
                        if line.contains(id) {
                            testCaseFound = true
                            ignore = false
                            break
                        }
                    }
                }
                if !ignore {
                    bufferedLines.append(line)
                }
            }
            
            // Add last feature
            if testCaseFound {
                text.append(contentsOf: bufferedLines)
            }
        }
        
        try await conn.sql().update("test_runs")
            .set("text", to: SQLBind(text.joined(separator: "\n")))
            .set("selected_test_case_id", to: SQLBind(firstTestCaseID))
            .where("id", .equal, SQLBind(id))
            .run()

        return .init(
            id: id,
            dateCreated: .now,
            modelIDs: modelIDs,
            name: name,
            includeAutomated: includeAutomated,
            text: text.joined(separator: "\n"),
            status: .init(pending: uniqueCases.count, percentComplete: 0),
            selectedTestCaseID: firstTestCaseID,
            results: try await testCaseResults(conn: conn, testRunID: id),
            isFinished: false
        )
    }
    
    func testCaseResults(conn: Database.Connection, testRunID: TestRunID) async throws -> [TestRun.TestCaseResult] {
        let rows = try await conn.select()
            .column("*")
            .from("test_case_results")
            .where("test_run_id", .equal, testRunID)
            .all()
        var results = [TestRun.TestCaseResult]()
        for row in rows {
            let result = try await makeTestCaseResult(conn: conn, from: row)
            results.append(result)
        }
        return results
    }
    
    func testRunStatus(conn: Database.Connection, id: TestRunID) async throws -> TestRun.Status {
        var status = TestRun.Status()
        var total: Double = 0
        let statuses = try await testCaseStatuses(conn: conn, testRunID: id)
        statuses.forEach { result in
            total += 1
            switch result.status {
            case .failed:
                status.failed += 1
            case .passed:
                status.passed += 1
            case .pending:
                status.pending += 1
            case .skipped:
                status.skipped += 1
            }
        }
        status.percentComplete = Int((Double(status.passed + status.failed + status.skipped) / total) * 100)
        status.total = status.pending + status.passed + status.failed + status.skipped
        return status
    }
    
    func statusTestCase(conn: Database.Connection, id: TestCaseResultID, userID: UserID, status: TestRun.TestCaseStatus, notes: String?) async throws {
        try await conn.sql().update("test_case_results")
            .set("date_statused", to: SQLBind(Date.now))
            .set("status", to: SQLBind(status))
            .set("notes", to: SQLBind(notes))
            .where("id", .equal, SQLBind(id))
            .run()
        let result = try await testCaseResult(conn: conn, id: id)
        var testCase = try await testCase(conn: conn, id: result.testCase.id)
        testCase.notes = notes
        try await updateTestCase(conn: conn, testCase)
    }
    
    func finishTestRun(conn: Database.Connection, id: TestRunID, userID: UserID, determination: TestRunResults.Determination, notes: String?) async throws {
        try await conn.sql().insert(into: "test_run_results")
            .columns("test_run_id", "user_id", "date_created", "determination", "notes")
            .values(
                SQLBind(id),
                SQLBind(userID),
                SQLBind(Date.now),
                SQLBind(determination),
                SQLBind(notes)
            )
            .run()
        
        try await conn.sql().update("test_runs")
            .set("is_finished", to: SQLBind(true))
            .where("id", .equal, SQLBind(id))
            .run()
        
        // All `Pending` test cases are automatically set to `Skipped`
        let stmt = "UPDATE test_case_results SET status = 3, user_id = ?, date_statused = ? WHERE status = 0 AND test_run_id = ?"
        let binds: [SQLiteData] = [
            .integer(userID),
            .integer(Int(Date.now.timeIntervalSince1970)),
            .integer(id)
        ]
        // TODO: Make sure this updates the date correctly and all test cases that belong to test run
        let _ = try await conn.query(stmt, binds)
        boss.log.i("Finished test cases")
    }
    
    func testRunResults(conn: Database.Connection, id: TestRunID) async throws -> TestRunResults {
        let rows = try await conn.select()
            .column("*")
            .from("test_run_results")
            .where("test_run_id", .equal, id)
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        return try await makeTestRunResults(conn: conn, id: id, from: row)
    }
    
    func testCaseResult(conn: Database.Connection, id: TestCaseResultID) async throws -> TestRun.TestCaseResult {
        let rows = try await conn.select()
            .column("*")
            .from("test_case_results")
            .where("id", .equal, id)
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        return try await makeTestCaseResult(conn: conn, from: row)
    }
    
    func testRuns(conn: Database.Connection) async throws -> [TestRun] {
        let rows = try await conn.select()
            .column("*")
            .from("test_runs")
            .orderBy("date_created", .descending)
            .all()
        var runs = [TestRun]()
        for row in rows {
            try runs.append(await makeTestRun(conn: conn, from: row))
        }
        return runs
    }
    
    func finishedTestRuns(conn: Database.Connection) async throws -> [TestRun] {
        let rows = try await conn.select()
            .column("*")
            .from("test_runs")
            .where("is_finished", .equal, 1)
            .orderBy("date_created", .descending)
            .all()
        var runs = [TestRun]()
        for row in rows {
            try runs.append(await makeTestRun(conn: conn, from: row))
        }
        return runs
    }
    
    private func makeTestRunResults(conn: Database.Connection, id: TestRunID, from row: SQLRow) async throws -> TestRunResults {
        let userID = try row.decode(column: "user_id", as: UserID.self)
        let tr = try await testRun(conn: conn, id: id)
        return try .init(
            id: id,
            user: await service.user.user(conn: conn, id: userID),
            dateCreated: row.decode(column: "date_created", as: Date.self),
            name: tr.name,
            includeAutomated: tr.includeAutomated,
            status: await testRunStatus(conn: conn, id: id),
            determination: row.decode(column: "determination", as: TestRunResults.Determination.self),
            notes: row.decode(column: "notes", as: String?.self),
            failedTestCases: nil
        )

    }
    
    private func makeTestCaseResult(conn: Database.Connection, from row: SQLRow) async throws -> TestRun.TestCaseResult {
        let user: User? = if let userID = try row.decode(column: "user_id", as: UserID?.self) {
            try await service.user.user(conn: conn, id: userID)
        }
        else {
            nil
        }
        let testCaseID = try row.decode(column: "test_case_id", as: TestCaseID.self)
        let testCase = try await testCase(conn: conn, id: testCaseID)
        return try .init(
            id: row.decode(column: "id", as: TestCaseResultID.self),
            testRunID: row.decode(column: "test_run_id", as: TestRunID.self),
            user: user,
            dateStatused: row.decode(column: "date_statused", as: Date?.self),
            status: row.decode(column: "status", as: TestRun.TestCaseStatus.self),
            testCase: testCase
        )
    }

    private func testCaseStatuses(conn: Database.Connection, testRunID: TestRunID) async throws -> [TestCaseStatus] {
        let rows = try await conn.select()
            .column("*")
            .from("test_case_results")
            .where("test_run_id", .equal, testRunID)
            .all()
        return try rows.map { try makeTestCaseStatus(from: $0) }
    }
    
    private struct TestCaseStatus {
        let id: TestCaseResultID
        let status: TestRun.TestCaseStatus
    }
    
    private func makeTestCaseStatus(from row: SQLRow) throws -> TestCaseStatus {
        try .init(
            id: row.decode(column: "id", as: TestCaseResultID.self),
            status: row.decode(column: "status", as: TestRun.TestCaseStatus.self)
        )
    }
}

// MARK: - Factories

private extension TestSQLiteService {
    func makeProject(from row: SQLRow) throws -> TestProject {
        try TestProject(
            id: row.decode(column: "id", as: TestProjectID.self),
            name: row.decode(column: "name", as: String.self),
            testSuiteIDs: try row.decode(column: "test_suite_ids", as: [TestSuiteID]?.self) ?? []
        )
    }
    
    func makeTestSuite(conn: Database.Connection, from row: SQLRow) async throws -> TestSuite {
        let testSuiteId = try row.decode(column: "id", as: TestSuiteID.self)
        
        let total = try await conn.query("SELECT COUNT(*) AS num_projects FROM test_cases WHERE test_suite_id = ?", [.integer(testSuiteId)])
        let totalTestCases = try total[0].sql().decode(column: "num_projects", as: Int.self)
        
        let automated = try await conn.query("SELECT COUNT(*) AS num_projects FROM test_cases WHERE test_suite_id = ? AND is_automated = ?", [.integer(testSuiteId), .integer(1)])
        let automatedTestCases = try automated[0].sql().decode(column: "num_projects", as: Int.self)

        return try TestSuite(
            id: testSuiteId,
            projectID: row.decode(column: "project_id", as: TestProjectID.self),
            name: row.decode(column: "name", as: String.self),
            text: row.decode(column: "text", as: String?.self),
            totalTestCases: totalTestCases,
            automatedTestCases: automatedTestCases
        )
    }
    
    func makeTestSuite(from row: SQLRow) throws -> TestSuite {
        try TestSuite(
            id: row.decode(column: "id", as: TestSuiteID.self),
            projectID: row.decode(column: "project_id", as: TestProjectID.self),
            name: row.decode(column: "name", as: String.self),
            text: row.decode(column: "text", as: String?.self),
            totalTestCases: 0,
            automatedTestCases: 0
        )
    }
    
    func makeTestCase(from row: SQLRow) throws -> TestCase {
        try TestCase(
            id: try row.decode(column: "id", as: TestCaseID.self),
            projectID: row.decode(column: "project_id", as: TestProjectID.self),
            testSuiteID: row.decode(column: "test_suite_id", as: TestSuiteID.self),
            name: row.decode(column: "name", as: String.self),
            notes: row.decode(column: "notes", as: String?.self),
            isAutomated: row.decode(column: "is_automated", as: Bool.self)
        )
    }
    
    func makeLiteTestCase(from row: SQLRow) throws -> TestCase {
        try TestCase(
            id: try row.decode(column: "id", as: TestCaseID.self),
            projectID: row.decode(column: "project_id", as: TestProjectID.self),
            testSuiteID: row.decode(column: "test_suite_id", as: TestSuiteID.self),
            name: row.decode(column: "name", as: String.self),
            notes: row.decode(column: "notes", as: String?.self),
            isAutomated: row.decode(column: "is_automated", as: Bool.self)
        )
    }
    
    func makeResource(from row: SQLRow) throws -> TestSuiteResource {
        try TestSuiteResource(
            id: row.decode(column: "id", as: TestSuiteID.self),
            testSuiteID: row.decode(column: "test_suite_id", as: TestSuiteID.self),
            mimeType: row.decode(column: "mime_type", as: String?.self),
            name: row.decode(column: "name", as: String?.self),
            path: row.decode(column: "path", as: String?.self)
        )
    }
    
    func makeTestRun(conn: Database.Connection, from row: SQLRow) async throws -> TestRun {
        let id = try row.decode(column: "id", as: TestRunID.self)
        return try TestRun(
            id: id,
            dateCreated: row.decode(column: "date_created", as: Date.self),
            modelIDs: row.decode(column: "model_ids", as: String.self).components(separatedBy: ","),
            name: row.decode(column: "name", as: String.self),
            includeAutomated: row.decode(column: "include_automated", as: Bool.self),
            text: row.decode(column: "text", as: String.self),
            status: try await testRunStatus(conn: conn, id: id),
            selectedTestCaseID: row.decode(column: "selected_test_case_id", as: TestCaseID.self),
            results: try await testCaseResults(conn: conn, testRunID: id),
            isFinished: row.decode(column: "is_finished", as: Bool.self)
        )
    }
        
    struct TestModelIDs: Codable {
        var projects = [TestProjectID]()
        var testSuites = [TestSuiteID]()
        var testCases = [TestCaseID]()
        var testRuns = [TestRunID]()
    }
    struct TestModels {
        var projects = [TestProject]()
        var testSuites = [TestSuite]()
        var testCases = [TestCase]()
        var testRuns = [TestRun]()
    }

    func testModels(conn: Database.Connection, for modelIDs: TestModelIDs) async throws -> TestModels {
        var models = TestModels()
        for id in modelIDs.projects {
            let model = try await project(conn: conn, id: id)
            models.projects.append(model)
        }
        for id in modelIDs.testSuites {
            let model = try await testSuite(conn: conn, id: id)
            models.testSuites.append(model)
        }
        for id in modelIDs.testCases {
            let model = try await testCase(conn: conn, id: id)
            models.testCases.append(model)
        }
        for id in modelIDs.testRuns {
            let model = try await testRun(conn: conn, id: id, includeTestSuites: false)
            models.testRuns.append(model)
        }

        return models
    }
}
