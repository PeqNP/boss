/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import bosslib
import Vapor

/// `TMForm` represents input data. It can either be from `POST` or `GET`.
enum TMForm {
    struct Search: Codable {
        let term: String?
    }

    /// Represents a `TestProject`
    struct Project: Codable {
        let id: TestProjectID?
        let name: String?
    }
    
    struct TestSuite: Codable {
        let id: TestSuiteID?
        /// Used only for creation
        let projectID: TestProjectID?
        let name: String?
    }
    
    /// Represents a `TestSuite`
    struct TestSuiteEditor: Codable {
        let id: TestSuiteID
        let text: String?
        let testCases: [TestManagementAPI.TestSuiteTestCase]
    }
    
    struct NewTestSuite: Codable {
        let projectID: TestProjectID?
    }

    struct DeleteTestSuite: Codable {
        let id: String?
    }

    struct TestSuiteResource: Content {
        let id: TestSuiteResourceID
        let name: String
    }
    
    struct UploadFile: Content {
        var file: File
    }

    struct TestSuites: Codable {
        let testSuiteID: TestSuiteID?
        let testCaseID: TestCaseID?
    }

    struct StartTestRun: Codable {
        let name: String?
        let includeAutomated: Bool?
        let selectedModelIDs: [String]?
    }
    
    struct FinishTestRun: Codable {
        let testRunID: Int
        let determination: TestRunResults.Determination
        let notes: String?
    }
    
    struct SaveTestRun: Codable {
        let testRunID: Int
        let determination: TestRunResults.Determination?
        let notes: String?
    }
    
    struct StatusTestCase: Codable {
        let testCaseResultID: TestCaseResultID
        let status: TestRun.TestCaseStatus
        let notes: String?
    }

    struct FindTestModels: Codable {
        let term: String
        let reverseLookup: Bool
    }
}
