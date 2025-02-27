/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation

/// The `TestProject`, `TestSuite`, and `TestSuiteGroup` manage the references to the children in the tree.
/// Children IDs are `nil` when first being created or when updating the respective model's properties. Its children are _not_ managed through CRUD forms. Only when performing changes on the project tree. By setting this value to `nil` it is obvious which context this model is being used and when it is appropriate to update the children IDs or not. This also provides a required level of control as we don't want an end-user mucking around with the tree outside of the tree context. Especially, the `TestSuite`s, as their `TestProject` can not change. A very limited API is provided to move a `TestCase` up, or down, within the tree. There is no way to modify the tree outside of this context.
/// However, read ops _always_ return a list of IDs, regardless of the context. This is necessary for debugging, and building the tree.

public typealias SearchTerm = String
public typealias TestProjectID = Int
public typealias TestSuiteID = Int
public typealias TestSuiteResourceID = Int
public typealias TestCaseID = Int
public typealias TestCaseResultID = Int
/// e.g. TS-45, TSG-3, TC-1
public typealias TestModelID = String
public typealias TestRunID = Int
public typealias TestRunResultsID = Int

public struct TestHome: Equatable, Codable {
    public let projects: [TestProject]
    public let activeTestRuns: [TestRun]
}

public struct TestProject: Equatable, Codable {
    public let id: TestProjectID
    public let name: String
    public var testSuiteIDs: [TestSuiteID]?

    public var numTestSuites: Int {
        testSuiteIDs?.count ?? 0
    }
}

/// Used when displaying all test suites for a given project.
public struct TestProjectTree: Equatable, Codable {
    public struct TestSuite: Equatable, Codable {
        public let id: TestSuiteID
        public let name: String
        public var testCases: [TestCase]
    }

    public let id: TestProjectID
    public let name: String
    public var testSuites: [TestProjectTree.TestSuite]
}

public struct TestSearchResult: Equatable, Codable {
    public struct Config: Equatable, Codable {
        let projectID: TestProjectID
        let testSuiteID: TestSuiteID?
        let testCaseID: TestCaseID?
    }
    public let id: String
    public let name: String
    public let config: TestSearchResult.Config
}

public struct TestSuiteResource: Equatable, Codable {
    public let id: TestSuiteResourceID
    public let testSuiteID: TestSuiteID
    public var mimeType: String?
    public var name: String?
    public var path: String?
    
    public var type: String {
        if mimeType?.starts(with: "image/") ?? false {
            "image"
        }
        else {
            "binary"
        }
    }
}

public struct TestSuite: Equatable, Codable {
    public let id: TestSuiteID
    public let projectID: TestProjectID
    public let name: String
    public var text: String? // Gherkin document
}

public struct TestCase: Equatable, Codable {
    public let id: TestCaseID
    public let projectID: TestProjectID
    public var testSuiteID: TestSuiteID
    public var name: String
    public var notes: String? // Share notes between test runs
    public var isAutomated: Bool = false
}

public struct TestRun: Equatable, Codable {
    public enum TestCaseStatus: Int, Equatable, Codable, Sendable {
        case pending = 0
        case passed = 1
        case failed = 2
        case skipped = 3
    }
    public struct TestSuite: Equatable, Codable {
        let id: String
        let name: String
        var testCases: [TestCaseResult]
    }
    public struct TestCaseResult: Equatable, Codable {
        public let id: TestCaseResultID
        public let testRunID: TestRunID
        public let user: User?
        public let dateStatused: Date?
        public let status: TestCaseStatus
        public let testCase: TestCase
    }
    public struct Status: Equatable, Codable {
        var pending: Int = 0
        var passed: Int = 0
        var failed: Int = 0
        var skipped: Int = 0
        var total: Int = 0
        var percentComplete: Int = 0
    }

    public let id: TestRunID
    public let dateCreated: Date
    /// The initial model IDs used to start the test run with
    public let modelIDs: [String]
    public let name: String
    public let includeAutomated: Bool
    /// Gherkin that contains only the test cases required for test run
    public let text: String
    public let status: Status
    /// Indicates the last test case that was selected. This is usually defined
    /// at the time a test case status was saved. The very first tests case should
    /// be seleted by default.
    public let selectedTestCaseID: TestCaseResultID
    public let results: [TestCaseResult]
    public let isFinished: Bool
}

public struct TestRunResults: Equatable, Codable {
    public enum Determination: Int, Equatable, Codable, Sendable {
        case passed = 0
        case failed = 1
    }

    /// This will always be a 1:1 with a test run. Therefore, these two records may share the same ID.
    public let id: TestRunID
    public let user: User
    public let dateCreated: Date
    public let name: String
    public let includeAutomated: Bool
    public let status: TestRun.Status
    public let determination: Determination
    public let notes: String?
    public let failedTestCases: [TestCase]?
}

/// TestNode is used to define the order of test suites, groups, and case.
struct TestNode {
    let id: String
    var children: [TestNode]

    init(id: String, children: [TestNode] = []) {
        self.id = id
        self.children = children
    }
}

public protocol TestObject {
    /// Returns model ID e.g. P-#, TS-#, TSG-#, TC-#
    var modelID: String { get }
}

extension TestProject: TestObject {
    public var modelID: String {
        "P-\(id)"
    }
}

extension TestSuite: TestObject {
    public var modelID: String {
        "TS-\(id)"
    }
}

extension TestCase: TestObject {
    public var modelID: String {
        "TC-\(id)"
    }
}

extension TestProjectTree: TestObject {
    public var modelID: String {
        "P-\(id)"
    }
}

extension TestProjectTree.TestSuite: TestObject {
    public var modelID: String {
        "TS-\(id)"
    }
}
