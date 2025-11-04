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
        var expected = ACLCatalog(paths: [
            "python": 1,
            "python,io.bithead.test": 2,
            "python,io.bithead.test,Test": 3,
            "python,io.bithead.test,Test,r": 4,
        ])
        XCTAssertEqual(catalog, expected)
        
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
        
        /** TODO: Add these tests
        // describe: verify access to app that does not exist
        await XCTAssertError(
            try await api.acl.verifyAccess(for: user, to: "io.bithead.test"),
            api.error.AccessDenied()
        )
        
        // describe: verify access to app that user does not have permission to
        await XCTAssertError(
            try await api.acl.verifyAccess(for: user, to: "io.bithead.test"),
            api.error.AccessDenied()
        )
        
        // describe: verify user against feature that does not exist not have ACL to feature within app
        await XCTAssertError(
            try await api.acl.verifyAccess(for: user, to: "io.bithead.test", feature: "Test.fake"),
            api.error.AccessDenied()
        )
        // describge: verify users against permission they have not been assigned
        await XCTAssertError(
            try await api.acl.verifyAccess(for: user, to: "io.bithead.test", feature: "Test.r"),
            api.error.AccessDenied()
        )
         */
        
        // describe: provide access to feature; user still has an old session
        try await api.acl.assignAccessToAcl(id: 4, to: user)
        await XCTAssertError(
            try await api.acl.verifyAccess(for: authUser, to: .init(catalog: "python", bundleId: "io.bithead.test", feature: "Test.r")),
            api.error.AccessDenied()
        )
        
        // describe: provide access to feature; user signs in
        authUser = AuthenticatedUser(user: user, session: .fake(jwt: .fake(acl: [4])), peer: nil)
        try await api.acl.verifyAccess(for: authUser, to: .init(catalog: "python", bundleId: "io.bithead.test", feature: "Test.r"))
        
        var aclIds: [ACLID] = try await api.acl.userAcl(for: user)
        var expectedAcls: [ACLID] = [4]
        XCTAssertEqual(aclIds, expectedAcls)
        
        // describe: user has access to app
//        try await api.acl.assignAccessToApp("io.bithead.test", to: user)
//        try await api.acl.verifyAccess(for: user, to: "io.bithead.test")
        
        // describe: user provides invalid feature name
//        await XCTAssertError(
//            try await api.acl.verifyAccess(for: user, to: "io.bithead.test", feature: "  "),
//            api.error.InvalidParameter(name: "feature")
//        )
        
        // describe: new app is added
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Feature.w"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        expected = ACLCatalog(paths: [
            "python": 1,
            "python,io.bithead.test": 2,
            "python,io.bithead.test,Test": 3,
            "python,io.bithead.test,Test,r": 4,
            "python,io.bithead.boss": 5,
            "python,io.bithead.boss,Feature": 6,
            "python,io.bithead.boss,Feature,w": 7,
        ])
        XCTAssertEqual(catalog, expected)
        
        // describe: a new feature is added
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Feature.w", "Person.r"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        // expected = ACLCatalog(id: 1, name: "python", apps: apps)
        XCTAssertEqual(catalog, expected)

        
        // describe: a new feature permission is added
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Feature.w", "Feature.r", "Person.r"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        // expected
        XCTAssertEqual(catalog, expected)
        
        // describe: duplicate feature permission added
        let duplicateFeatures: [ACLApp] = [
            .init(bundleId: "io.bithead.test", features: ["Test.r", "Test.r"]), // <- Duplicate is here
            .init(bundleId: "io.bithead.boss", features: ["Feature.w", "Feature.r", "Person.r"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: duplicateFeatures)
        // expected = ACLCatalog(id: 1, name: "python", apps: apps)
        // it: should not contain duplicate feature
        XCTAssertEqual(catalog, expected)
        
        // describe: a feature permission is removed
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Feature.r", "Person.r"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        // expected = ACLCatalog(id: 1, name: "python", apps: apps)
        XCTAssertEqual(catalog, expected)
        
        // describe: a feature is removed
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Person.r"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        // expected = ACLCatalog(id: 1, name: "python", apps: apps)
        XCTAssertEqual(catalog, expected)
        
        // describe: an app is removed
        apps = [
            .init(bundleId: "io.bithead.boss", features: ["Person.r"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        // expected = ACLCatalog(id: 1, name: "python", apps: apps)
        XCTAssertEqual(catalog, expected)
    }
}
