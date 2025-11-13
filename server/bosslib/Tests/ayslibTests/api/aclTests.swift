/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import Foundation
import XCTest

@testable import bosslib

final class aclTests: XCTestCase {
    /// - Test creating service catalog
    /// - Test verifying access to resources
    func testAcl() async throws {
        try await boss.start(storage: .memory)
        
        let user = try await api.account.saveUser(user: superUser(), id: nil, email: "eric@example.com", password: "Password1!", fullName: "Eric", verified: true, enabled: true)
        var authUser = AuthenticatedUser(user: user, session: .fake(), peer: nil)
        
        // describe: invalid catalog name
        await XCTAssertError(
            try await api.acl.createAclCatalog(for: "", apps: []),
            api.error.InvalidParameter(name: "name")
        )
        // describe: invalid bundle ID
        await XCTAssertError(
            try await api.acl.createAclCatalog(for: "rust", apps:  [.init(bundleId: " ", features: [])]),
            api.error.InvalidParameter(name: "bundleId")
        )
        // describe: invalid feature
        await XCTAssertError(
            try await api.acl.createAclCatalog(for: "rust", apps: [.init(bundleId: "io.bithead", features: ["  "])]),
            api.error.InvalidParameter(name: "feature")
        )
        // describe: invalid feature first part
        await XCTAssertError(
            try await api.acl.createAclCatalog(for: "rust", apps: [.init(bundleId: "io.bithead", features: [".r"])]),
            api.error.InvalidParameter(name: "feature", expected: "A feature name must have at least one character")
        )
        // describe: invalid feature second part
        await XCTAssertError(
            try await api.acl.createAclCatalog(for: "rust", apps: [.init(bundleId: "io.bithead", features: ["Feature."])]),
            api.error.InvalidParameter(name: "feature", expected: "A permission name must have at least one character")
        )
        // describe: more than one dot is added
        await XCTAssertError(
            try await api.acl.createAclCatalog(for: "rust", apps: [.init(bundleId: "io.bithead", features: ["Feature.r.extra"])]),
            api.error.InvalidParameter(name: "feature", expected: "Only one dot is allowed")
        )
        
        var apps: [ACLApp] = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"])
        ]
        var catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        var expected: ACLPathMap = [
            "python": 1,
            "python,io.bithead.test": 2,
            "python,io.bithead.test,Test": 3,
            "python,io.bithead.test,Test,r": 4,
        ]
        XCTAssertEqual(catalog, expected)
        
        // describe: send same config
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"])
        ]
        // it: should return the same config
        catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        expected = [
            "python": 1,
            "python,io.bithead.test": 2,
            "python,io.bithead.test,Test": 3,
            "python,io.bithead.test,Test,r": 4,
        ]
        XCTAssertEqual(catalog, expected)
        
        // describe: user does not have license to use app (yet)
        await XCTAssertError(
            try await api.acl.appLicense(id: 2, user: user),
            service.error.RecordNotFound()
        )
        
        // describe: user requests license for app that does not exist
        await XCTAssertError(
            try await api.acl.appLicense(id: 42, user: user),
            service.error.RecordNotFound()
        )
        
        // describe: invalid catalog name
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(catalog: "  ", bundleId: "", feature: "")),
            api.error.InvalidParameter(name: "catalog")
        )
        // describe: invalid bundle ID
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(catalog: "python", bundleId: "  ", feature: "")),
            api.error.InvalidParameter(name: "bundleId")
        )
        // describe: invalid feature
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(catalog: "python", bundleId: "io.bithead.test", feature: "")),
            api.error.InvalidParameter(name: "feature")
        )
        // describe: invalid feature first part
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(catalog: "python", bundleId: "io.bithead.test", feature: ".r")),
            api.error.InvalidParameter(name: "feature", expected: "A feature name must have at least one character")
        )
        // describe: invalid feature second part
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(catalog: "python", bundleId: "io.bithead.test", feature: "Feature.")),
            api.error.InvalidParameter(name: "feature", expected: "A permission name must have at least one character")
        )
        // describe: more than one dot is added
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(catalog: "python", bundleId: "io.bithead.test", feature: "Feature.r.next")),
            api.error.InvalidParameter(name: "feature", expected: "Only one dot is allowed")
        )
        
        // describe: verify access to app that does not exist
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(catalog: "python", bundleId: "io.bithead.fake", feature: nil)),
            api.error.AppDoesNotExist()
        )
        
        // describe: verify user against feature that does not exist
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(catalog: "python", bundleId: "io.bithead.test", feature: "Fake.r")),
            api.error.AccessDenied()
        )
        
        // describe: provide license to app
        var expectedLicense = try await api.acl.issueAppLicense(id: 2, to: user)
        var license = try await api.acl.appLicense(id: 2, user: user)
        XCTAssertEqual(license, expectedLicense)
        
        // describe: provide access to feature; user still has an old session
        try await api.acl.assignAccessToAcl(id: 4, to: user)
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(catalog: "python", bundleId: "io.bithead.test", feature: "Test.r")),
            api.error.AccessDenied()
        )

        // describe: access to app; access to feature; user signs in
        authUser = AuthenticatedUser(user: user, session: .fake(jwt: .fake(apps: [2], acl: [4])), peer: nil)
        try await api.acl.verifyAccess(for: authUser, to: .init(catalog: "python", bundleId: "io.bithead.test", feature: "Test.r"))
        
        var aclIds: [ACLID] = try await api.acl.userAcl(for: user)
        var expectedAcls: [ACLID] = [4]
        XCTAssertEqual(aclIds, expectedAcls)
                
        // describe: user has access to all feature permissions
        try await api.acl.assignAccessToAcl(id: 3, to: user)
        try await api.acl.removeAccessToAcl(id: 4, from: user)
        authUser = AuthenticatedUser(user: user, session: .fake(jwt: .fake(apps: [2], acl: [3])), peer: nil)
        try await api.acl.verifyAccess(for: authUser, to: .init(catalog: "python", bundleId: "io.bithead.test", feature: "Test.r"))
        
        aclIds = try await api.acl.userAcl(for: user)
        expectedAcls = [3]
        XCTAssertEqual(aclIds, expectedAcls)

        // describe: user has access to the entire app
        try await api.acl.assignAccessToAcl(id: 2, to: user)
        try await api.acl.removeAccessToAcl(id: 3, from: user)
        authUser = AuthenticatedUser(user: user, session: .fake(jwt: .fake(apps: [2], acl: [2])), peer: nil)
        try await api.acl.verifyAccess(for: authUser, to: .init(catalog: "python", bundleId: "io.bithead.test", feature: "Test.r"))
        
        aclIds = try await api.acl.userAcl(for: user)
        expectedAcls = [2]
        XCTAssertEqual(aclIds, expectedAcls)
        
        // describe: new app is added
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Feature.w"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        expected = [
            "python": 1,
            "python,io.bithead.test": 2,
            "python,io.bithead.test,Test": 3,
            "python,io.bithead.test,Test,r": 4,
            "python,io.bithead.boss": 5,
            "python,io.bithead.boss,Feature": 6,
            "python,io.bithead.boss,Feature,w": 7,
        ]
        XCTAssertEqual(catalog, expected)
        
        // describe: a new feature is added
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Feature.w", "Person.r"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        expected = [
            "python": 1,
            "python,io.bithead.test": 2,
            "python,io.bithead.test,Test": 3,
            "python,io.bithead.test,Test,r": 4,
            "python,io.bithead.boss": 5,
            "python,io.bithead.boss,Feature": 6,
            "python,io.bithead.boss,Feature,w": 7,
            "python,io.bithead.boss,Person": 8,
            "python,io.bithead.boss,Person,r": 9,
        ]
        XCTAssertEqual(catalog, expected)

        // describe: a new feature permission is added
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Feature.w", "Feature.r", "Person.r"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        expected = [
            "python": 1,
            "python,io.bithead.test": 2,
            "python,io.bithead.test,Test": 3,
            "python,io.bithead.test,Test,r": 4,
            "python,io.bithead.boss": 5,
            "python,io.bithead.boss,Feature": 6,
            "python,io.bithead.boss,Feature,w": 7,
            "python,io.bithead.boss,Person": 8,
            "python,io.bithead.boss,Person,r": 9,
            "python,io.bithead.boss,Feature,r": 10,
        ]
        XCTAssertEqual(catalog, expected)
        
        // describe: create hierchical structure of ACL
        let tree = try await api.acl.aclTree()
        let expectedTree = ACLTree(catalogs: [
            .init(id: 1, name: "python", apps: [
                .init(id: 5, name: "io.bithead.boss", features: [
                    .init(id: 6, name: "Feature", permissions: [
                        .init(id: 10, name: "r"),
                        .init(id: 7, name: "w")
                    ]),
                    .init(id: 8, name: "Person", permissions: [
                        .init(id: 9, name: "r")
                    ])
                ]),
                .init(id: 2, name: "io.bithead.test", features: [
                    .init(id: 3, name: "Test", permissions: [
                        .init(id: 4, name: "r")
                    ])
                ])
            ])
        ])
        // it: should create a sorted tree structure
        XCTAssertEqual(tree, expectedTree)
        
        // describe: duplicate feature permission added
        let duplicateFeatures: [ACLApp] = [
            .init(bundleId: "io.bithead.test", features: ["Test.r", "Test.r"]), // <- Duplicate is here
            .init(bundleId: "io.bithead.boss", features: ["Feature.w", "Feature.r", "Person.r"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: duplicateFeatures)
        // it: should not contain duplicate feature
        XCTAssertEqual(catalog, expected) // Uses same `expected` as previous test
        
        // describe: a feature permission is removed
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Feature.r", "Person.r"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        expected = [
            "python": 1,
            "python,io.bithead.test": 2,
            "python,io.bithead.test,Test": 3,
            "python,io.bithead.test,Test,r": 4,
            "python,io.bithead.boss": 5,
            "python,io.bithead.boss,Feature": 6,
            "python,io.bithead.boss,Person": 8,
            "python,io.bithead.boss,Person,r": 9,
            "python,io.bithead.boss,Feature,r": 10,
        ]
        XCTAssertEqual(catalog, expected)
        
        // describe: a feature is removed
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Person.r"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        expected = [
            "python": 1,
            "python,io.bithead.test": 2,
            "python,io.bithead.test,Test": 3,
            "python,io.bithead.test,Test,r": 4,
            "python,io.bithead.boss": 5,
            "python,io.bithead.boss,Person": 8,
            "python,io.bithead.boss,Person,r": 9,
        ]
        XCTAssertEqual(catalog, expected)
        
        // describe: an app is removed
        apps = [
            .init(bundleId: "io.bithead.boss", features: ["Person.r"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        expected = [
            "python": 1,
            "python,io.bithead.boss": 5,
            "python,io.bithead.boss,Person": 8,
            "python,io.bithead.boss,Person,r": 9,
        ]
        XCTAssertEqual(catalog, expected)
        
        // describe: add a new catalog w/ some features
        apps = [
            .init(bundleId: "io.bithead.boss", features: ["Person.r"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "swift", apps: apps)
        expected = [
            "swift": 10,
            "swift,io.bithead.boss": 11,
            "swift,io.bithead.boss,Person": 12,
            "swift,io.bithead.boss,Person,r": 13,
        ]
        XCTAssertEqual(catalog, expected)
        
        // describe: verify access against same app in different catalog
        try await api.acl.assignAccessToAcl(id: 9, to: user) // 9 = python,io.bithead.boss,Person,r
        
        // describe: check if user has access to app
        expectedLicense = try await api.acl.issueAppLicense(id: 11, to: user)
        license = try await api.acl.appLicense(id: 11, user: user)
        XCTAssertEqual(license, expectedLicense)
        
        // describe: revoke app license
        try await api.acl.revokeAppLicense(id: 11, from: user)
        // it: should not return a license
        await XCTAssertError(
            try await api.acl.appLicense(id: 11, user: user),
            service.error.RecordNotFound()
        )
        
        // describe: re-issue license
        expectedLicense = try await api.acl.issueAppLicense(id: 11, to: user)
        license = try await api.acl.appLicense(id: 11, user: user)
        XCTAssertEqual(license, expectedLicense)
        
        authUser = AuthenticatedUser(user: user, session: .fake(jwt: .fake(apps: [11], acl: [9])), peer: nil)
        // sanity, to show that they have access to python, but not swift
        try await api.acl.verifyAccess(for: authUser, to: .init(catalog: "python", bundleId: "io.bithead.boss", feature: "Person.r"))
        // it: should deny access
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(catalog: "swift", bundleId: "io.bithead.boss", feature: "Person.r")),
            api.error.AccessDenied()
        )
    }
}
