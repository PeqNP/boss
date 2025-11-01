/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import bosslib
import Foundation
import LeafKit
import Vapor
import VaporToOpenAPI

private enum Constant {
    static let homeRoute = "/test/home/"
}

/// Register the `/time/` routes.
public func registerTestManagement(_ app: Application) {
    app.group("test") { group in
        group.get("home") { req in
            let home = try await api.test.home(user: req.authUser)
            return Fragment.Home(
                projects: home.projects,
                activeTestRuns: home.activeTestRuns.isEmpty ? nil : home.activeTestRuns
            )
        }.openAPI(
            summary: "Returns all test projects",
            response: .type(Fragment.Home.self),
            responseContentType: .application(.json)
        )
        .addScope(.app("io.bithead.test-manager"))
        
        group.post("search") { req in
            let form = try req.content.decode(TMForm.Search.self)
            let results = try await api.test.search(user: req.authUser, term: form.term)
            let fragment = Fragment.Search(
                results: results
            )
            return fragment
        }.openAPI(
            summary: "Displays test models that match search term",
            response: .type(Fragment.Search.self),
            responseContentType: .application(.json)
        )
        .addScope(.app("io.bithead.test-manager"))

        group.get("test-run") { req async throws -> View in
            // TODO: Plumb finding business objects given a search term. It should return {id:"TC-1", name: "Name of test case"} and add to `selectedModelIDs`.
            let testRun = try await api.test.testRun(user: req.authUser)
            let fragment = Fragment.TestRun(
                options: .make(from: testRun),
                selectedModelIDs: []
            )
            return try await req.view.render("test/test-run", fragment)
        }.openAPI(
            summary: "Create a new test run",
            description: "Select the test suites, groups, and cases to run and then start the test run."
        )
        .addScope(.app("io.bithead.test-manager"))
        
        group.post("test-run") { req in
            let form = try req.content.decode(TMForm.StartTestRun.self)
            let testRun = try await api.test.startTestRun(
                user: req.authUser,
                name: form.name,
                includeAutomated: form.includeAutomated,
                modelIDs: form.selectedModelIDs
            )
            return Fragment.StartTestRun(
                testRunID: testRun.id
            )
        }.openAPI(
            summary: "Start a test run",
            body: .type(TMForm.StartTestRun.self),
            contentType: .application(.json),
            response: .type(Fragment.StartTestRun.self),
            responseContentType: .application(.json)
        )
        .addScope(.app("io.bithead.test-manager"))
        
        group.get("test-run", ":testRunID") { req in
            let testRunID = req.parameters.get("testRunID")
            let testRun = try await api.test.activeTestRun(user: req.authUser, testRunID: .require(testRunID))
            // TODO: If test run is over, go directly to results.
            return Fragment.ActiveTestRun(testRun: testRun)
        }.openAPI(
            summary: "Query active test run",
            response: .type(Fragment.ActiveTestRun.self),
            responseContentType: .application(.json)
        )
        .addScope(.app("io.bithead.test-manager"))
        
        group.post("finish-test-run") { req in
            let form = try req.content.decode(TMForm.FinishTestRun.self)
            let results = try await api.test.finishTestRun(
                user: req.authUser,
                testRunID: form.testRunID,
                determination: form.determination,
                notes: form.notes
            )
            return Fragment.FinishTestRun(
                testRunID: results.id
            )
        }.openAPI(
            summary: "Finish a test run",
            body: .type(TMForm.FinishTestRun.self),
            contentType: .application(.json),
            response: .type(Fragment.FinishTestRun.self),
            responseContentType: .application(.json)
        )
        .addScope(.app("io.bithead.test-manager"))
        
        group.post("status-test-case") { req in
            let form = try req.content.decode(TMForm.StatusTestCase.self)
            let status = try await api.test.statusTestCase(
                user: req.authUser,
                testCaseResultID: form.testCaseResultID,
                status: form.status,
                notes: form.notes
            )
            return Fragment.StatusTestCase(status: status)
        }.openAPI(
            summary: "Status a test case",
            description: "Status a test case for an active test run. Returns totals.",
            response: .type(Fragment.FindTestModels.self),
            responseContentType: .application(.json)
        )
        .addScope(.app("io.bithead.test-manager"))

        group.post("find-test-models") { req in
            let form = try req.content.decode(TMForm.FindTestModels.self)
            let models = try await api.test.findTestModels(
                user: req.authUser,
                searchTerm: form.term,
                reverseLookup: form.reverseLookup
            )
            return Fragment.FindTestModels(models: models)
        }.openAPI(
            summary: "Find test models given a search term",
            description: "Returns a set of test models that match the search term",
            response: .type(Fragment.FindTestModels.self),
            responseContentType: .application(.json)
        )
        .addScope(.app("io.bithead.test-manager"))
        
        group.get("test-run-results", ":testRunID") { req async throws -> View in
            let testRunID = req.parameters.get("testRunID")
            let results = try await api.test.testRunResults(user: req.authUser, testRunID: .require(testRunID))
            let fragment = Fragment.TestRunResults(results: results)
            return try await req.view.render("test/test-run-results", fragment)
        }.openAPI(
            summary: "View results for a test run"
        )
        .addScope(.app("io.bithead.test-manager"))

        group.get("finished-test-runs") { req in
            let testRuns = try await api.test.finishedTestRuns(user: req.authUser)
            return Fragment.FinishedTestRuns(testRuns: testRuns)
        }.openAPI(
            summary: "View historical test runs",
            response: .type(Fragment.FinishedTestRuns.self),
            responseContentType: .application(.json)
        )
        .addScope(.app("io.bithead.test-manager"))
        
        group.get("project", ":projectID") { req in
            let projectID = req.parameters.get("projectID")
            let project = try await api.test.project(user: req.authUser, id: .make(projectID))
            return Fragment.Project(project: project)
        }.openAPI(
            summary: "Query existing project",
            response: .type(Fragment.Project.self),
            responseContentType: .application(.json)
        )
        .addScope(.app("io.bithead.test-manager"))
        
        group.post("project") { req in
            let form = try req.content.decode(TMForm.Project.self)
            let project = try await api.test.saveProject(
                user: req.authUser,
                id: .make(form.id),
                name: form.name
            )
            return Fragment.SaveProject(project: project)
        }.openAPI(
            summary: "Save a project",
            response: .type(Fragment.SaveProject.self),
            responseContentType: .application(.json)
        )
        .addScope(.app("io.bithead.test-manager"))

        group.delete("project", ":projectID") { req in
            let projectID = req.parameters.get("projectID")
            _ = try await api.test.deleteProject(
                user: req.authUser,
                id: .require(projectID)
            )
            return Fragment.DeleteProject()
        }.openAPI(
            summary: "Delete a project",
            response: .type(Fragment.DeleteProject.self),
            responseContentType: .application(.json)
        )
        .addScope(.app("io.bithead.test-manager"))

        group.get("test-suites", ":projectID") { req in
            let projectID = req.parameters.get("projectID")
            /// Automatically open a test suite, group, etc for a given focused business object (test suite,
            /// group, or test case) This is the ID of the respective object TS-#, TSG-#, or TC-#.
            let form = try req.query.decode(TMForm.TestSuites.self)
            // TODO: The `focus` value needs to be translated into something that can be selected within the form.
            // Possibly use an `id` on each of the `li`s. Or maybe it is determined while iterating over parents?
            // Whatever it is, this needs to be done in order to open the respective test case. It should also be
            // selected and automatically navigated to. Indeed, it would be better if this was a #hash, because
            // a browser will automatically navigate to that hashed value.
            let project = try await api.test.projectTree(user: req.authUser, projectID: .make(projectID))
            return Fragment.TestSuites(
                project: project,
                host: boss.config.host,
                focus: .init(testSuiteID: form.testSuiteID, testCaseID: form.testCaseID)
            )
        }.openAPI(
            summary: "Manage a project's test suites",
            query: .type(TMForm.TestSuites.self),
            response: .type(Fragment.TestSuites.self),
            responseContentType: .application(.json)
        )
        .addScope(.app("io.bithead.test-manager"))
        
        // MARK: Test Suite

        group.get("test-suite") { req async throws -> View in
            let auth = try req.authUser
            let form = try req.query.decode(TMForm.NewTestSuite.self)
            var project: TestProject?
            var projects: [TestProject]?
            if let projectID = form.projectID {
                project = try await api.test.project(user: auth, id: projectID)
            }
            else {
                projects = try await api.test.projects(user: auth)
            }
            let fragment = Fragment.TestSuite(
                isNew: true,
                project: project,
                projects: projects
            )
            return try await req.view.render("test/test-suite", fragment)
        }.openAPI(
            summary: "Create a new test suite"
        )
        .addScope(.app("io.bithead.test-manager"))
        
        group.get("test-suite", ":testSuiteID") { req async throws -> View in
            let auth = try req.authUser
            let testSuiteID = req.parameters.get("testSuiteID")
            let suite = try await api.test.testSuite(user: auth, id: .make(testSuiteID))
            let project = try await api.test.project(user: auth, id: suite.projectID)
            let fragment = Fragment.TestSuite(
                isNew: false,
                project: project,
                id: suite.id,
                name: suite.name
            )
            return try await req.view.render("test/test-suite", fragment)
        }.openAPI(
            summary: "Modify a test suite"
        )
        .addScope(.app("io.bithead.test-manager"))
        
        group.post("test-suite") { req in
            let form = try req.content.decode(TMForm.TestSuite.self)
            let testSuite = try await api.test.saveTestSuite(
                user: req.authUser,
                id: .make(form.id),
                projectID: .make(form.projectID),
                name: form.name
            )
            return Fragment.SaveTestSuite(testSuite: testSuite)
        }.openAPI(
            summary: "Save a test suite",
            response: .type(Fragment.SaveTestSuite.self),
            responseContentType: .application(.json)
        )
        .addScope(.app("io.bithead.test-manager"))

        group.delete("test-suite", ":testSuiteID") { req in
            let testSuiteID = req.parameters.get("testSuiteID")
            _ = try await api.test.deleteTestSuite(
                user: req.authUser,
                id: .require(testSuiteID)
            )
            return Fragment.DeleteTestSuite()
        }.openAPI(
            summary: "Delete a test suite",
            response: .type(Fragment.DeleteTestSuite.self),
            responseContentType: .application(.json)
        )
        .addScope(.app("io.bithead.test-manager"))
        
        group.get("test-suite-editor", ":testSuiteID") { req in
            let auth = try req.authUser
            let testSuiteID = req.parameters.get("testSuiteID")
            let testSuite = try await api.test.testSuite(user: auth, id: .require(testSuiteID))
            let testCases = try await api.test.testCases(user: auth, testSuiteID: testSuite.id)
            return Fragment.TestSuiteEditor(
                testSuite: testSuite,
                testCases: testCases
            )
        }.openAPI(
            summary: "View a test run that is in progress"
        )
        .addScope(.app("io.bithead.test-manager"))
        
        group.post("test-suite-editor") { req in
            let auth = try req.authUser
            let form = try req.content.decode(TMForm.TestSuiteEditor.self)
            let testSuite = try await api.test.saveTestSuite(
                user: auth,
                id: form.id,
                text: form.text,
                testCases: form.testCases
            )
            let testCases = try await api.test.testCases(user: auth, testSuiteID: testSuite.id)
            return Fragment.TestSuiteEditor(
                testSuite: testSuite,
                testCases: testCases
            )
        }.openAPI(
            summary: "Save a test suite's Gherkin document",
            response: .type(Fragment.TestSuiteEditor.self),
            responseContentType: .application(.json)
        )
        .addScope(.app("io.bithead.test-manager"))
        
        group.post("upload-file", ":testSuiteID") { req in
            let auth = try req.authUser
            let id = req.parameters.get("testSuiteID")
            let form = try req.content.decode(TMForm.UploadFile.self)
            
            let session = Database.session()
            let resourceID = try await api.test.createResource(
                session: session,
                user: auth,
                testSuiteID: .require(id)
            )
            
            let fileName = "\(resourceID).\(form.file.extension ?? "binary")"
            let directoryURL = boss.config.testMediaDirectory
            let fileURL = directoryURL.appending(component: fileName)
            let fileManager = FileManager.default
            if !fileManager.fileExists(atPath: directoryURL.path) {
                try fileManager.createDirectory(
                    at: directoryURL,
                    withIntermediateDirectories: true,
                    attributes: nil
                )
            }
            
            try await req.fileio.writeFile(form.file.data, at: fileURL.path)
            
            let resource = try await api.test.updateResource(
                session: session,
                user: auth,
                id: resourceID,
                name: form.file.filename,
                mimeType: mimeType(for: fileURL),
                path: "\(boss.config.testMediaResourcePath)/\(fileName)"
            )
            
            return Fragment.UploadedFile(
                id: resource.id,
                name: resource.name,
                url: resource.path,
                type: resource.type
            )
        }.openAPI(
            summary: "Upload a file",
            response: .type(Fragment.UploadedFile.self),
            responseContentType: .application(.json)
        )
        .addScope(.app("io.bithead.test-manager"))

        group.delete("resource", ":resourceID") { req in
            let id = req.parameters.get("resourceID")
            _ = try await api.test.deleteResource(
                user: req.authUser,
                id: .require(id)
            )
            return Fragment.DeleteResource()
        }.openAPI(
            summary: "Delete a resource from a test case",
            response: .type(Fragment.DeleteResource.self),
            responseContentType: .application(.json)
        )
        .addScope(.app("io.bithead.test-manager"))
    }
}

extension TestProjectID {
    static func make(_ id: String?) -> TestProjectID? {
        guard let id else {
            return nil
        }
        return TestProjectID(id)
    }
    
    static func make(_ id: Int?) -> TestProjectID? {
        guard let id else {
            return nil
        }
        return TestProjectID(id)
    }

    static func require(_ id: String?) throws -> TestProjectID {
        guard let id else {
            throw api.error.InvalidParameter(name: "id", expected: "Integer")
        }
        guard let id = TestProjectID(id) else {
            throw api.error.InvalidParameter(name: "id", expected: "Integer")
        }
        return TestProjectID(id)
    }
}
