/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import bosslib
import LeafKit
import Vapor

/// Fragments are view models.
extension Fragment {
    // `TestHome` view model
    struct Home: Content {
        let projects: [TestProject]
        let activeTestRuns: [bosslib.TestRun]?
    }

    struct Search: Content {
        let results: [TestSearchResult]
    }

    struct TestSuites: Content {
        struct Focus: Content {
            let testSuiteID: TestSuiteID?
            let testCaseID: TestCaseID?
        }
        let project: TestProjectTree
        let host: String
        let focus: Focus
    }
    
    // MARK: Test Run

    struct TestRun: Content {
        // NOTE: All IDs are the model IDs to make the view less cumbersome with business logic
        struct Option: Content {
            let id: String
            let name: String
        }
        struct TestProject: Content {
            let id: String
            let name: String
            let testSuites: [Option]
        }
        struct TestSuite: Content {
            let id: String
            let testCases: [Option]
        }
        struct TestSuiteGroup: Content {
            let id: String
            let testCases: [Option]
        }
        struct Options: Content {
            /// `TestProject` to `TestSuite`s
            var projects: [TestProject]
            var testSuites: [TestRun.TestSuite]
        }
        
        var name: String?
        var includeAutomated: Bool?
        let options: TestRun.Options
        let selectedModelIDs: [TestModelID]?
        var error: String?
    }

    struct ActiveTestRun: Content {
        let testRun: bosslib.TestRun
    }
    
    struct TestSuiteEditor: Content {
        let testSuite: bosslib.TestSuite
        let testCases: [bosslib.TestCase]
    }

    struct FindTestModels: Content {
        let models: [TestSearchResult]
    }
    
    struct StartTestRun: Content {
        let testRunID: TestRunID
    }
    
    struct StatusTestCase: Content {
        let status: bosslib.TestRun.Status
    }
    
    struct FinishTestRun: Content {
        let testRunID: TestRunID
    }
    struct SaveTestRun: Content {
        let testRunID: TestRunID
    }
    
    struct TestRunResults: Content {
        let results: bosslib.TestRunResults
    }
    
    struct FinishedTestRuns: Content {
        let testRuns: [bosslib.TestRun]
    }
    
    // MARK: Models
    
    struct Project: Content {
        let project: bosslib.TestProject
    }
    struct SaveProject: Content {
        let project: bosslib.TestProject
    }
    struct DeleteProject: Content { }
    
    struct TestSuite: Content {
        let isNew: Bool
        var project: TestProject?
        var projects: [TestProject]?
        var id: TestSuiteID?
        var name: String?
    }
    
    struct SaveTestSuite: Content {
        let testSuite: bosslib.TestSuite
    }
    
    struct SaveTestSuiteEditor: Content { }
    struct DeleteTestSuite: Content { }
    
    struct TestSuiteResource: Content {
        let resource: bosslib.TestSuiteResource
    }
    
    struct UploadedFile: Content {
        let id: TestSuiteResourceID
        /// These are optional because when the resource is first created, the name, url, and type may not yet be known.
        let name: String?
        let url: String?
        let type: String? // string, link, pdf, etc.
    }
    
    struct DeleteResource: Content { }
}

extension Fragment.TestRun.Options {
    static func make(
        from projects: [TestProjectTree]
    ) -> Fragment.TestRun.Options {
        var suites = [Fragment.TestRun.TestSuite]()
        let projects = projects.map { (project: TestProjectTree) -> Fragment.TestRun.TestProject in
            var options = [Fragment.TestRun.Option]()
            for suite in project.testSuites {
                options.append(.init(id: "TS-\(suite.id)", name: suite.name))
                suites.append(.init(
                    id: "TS-\(suite.id)",
                    testCases: suite.testCases.map({ testCase in
                        .init(id: "TC-\(testCase.id)", name: testCase.name)
                    })
                ))
            }
            return .init(
                id: "P-\(project.id)",
                name: project.name,
                testSuites: options
            )
        }
        return .init(
            projects: projects,
            testSuites: suites
        )
    }
}
