/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import Foundation
import XCTest

@testable import bosslib

final class aclTests: XCTestCase {
    /// Tests access to an app and respective app's ACL permissions
    func testAcl() async throws {
        try await boss.start(storage: .memory)

        let user = try await api.account.saveUser(user: superUser(), id: nil, email: "eric@example.com", password: "Password1!", fullName: "Eric", verified: true, enabled: true)
        
        // describe: create app with invalid name
        await XCTAssertError(
            try await api.acl.createApp(" "),
            api.error.InvalidParameter(name: "bundleId")
        )
        
        // describe: create app with valid name
        let app = try await api.acl.createApp("io.bithead.test")
        
        XCTAssertEqual(app, ACLApp(id: 1, bundleId: "io.bithead.test", features: []))
        
        // describe: create ACL with invalid feature
        await XCTAssertError(
            try await api.acl.createAcl(for: "io.bithead.test", feature: "Test"),
            api.error.InvalidParameter(name: "feature", expected: "String with a dot separator")
        )
        await XCTAssertError(
            try await api.acl.createAcl(for: "io.bithead.test", feature: "Test."),
            api.error.InvalidParameter(name: "feature", expected: "Second part must be a permission name with at least one character")
        )
        await XCTAssertError(
            try await api.acl.createAcl(for: "io.bithead.test", feature: ".r"),
            api.error.InvalidParameter(name: "feature", expected: "First part must be a feature name with at least one character")
        )
        
        // describe: create ACL with valid feature
        let acl = try await api.acl.createAcl(for: "io.bithead.test", feature: "Test.r")
        XCTAssertEqual(acl, ACLItem(id: 1, bundleId: "io.bithead.test", name: "Test", permission: "r"))
        
        // describe: user provides invalid bundle ID
        await XCTAssertError(
            try await api.acl.verifyAccess(for: user, to: "  "),
            api.error.InvalidParameter(name: "bundleId")
        )
        
        // describe: user has no access to app
        await XCTAssertError(
            try await api.acl.verifyAccess(for: user, to: "io.bithead.test"),
            api.error.AccessDenied()
        )
        
        // describe: user has access to app
        try await api.acl.assignAccessToApp("io.bithead.test", to: user)
        try await api.acl.verifyAccess(for: user, to: "io.bithead.test")
        
        // describe: user provides invalid feature name
        await XCTAssertError(
            try await api.acl.verifyAccess(for: user, to: "io.bithead.test", feature: "  "),
            api.error.InvalidParameter(name: "feature")
        )
        
        // describe: user does not have ACL to feature within app
        await XCTAssertError(
            try await api.acl.verifyAccess(for: user, to: "io.bithead.test", feature: "Test.r"),
            api.error.AccessDenied()
        )
        
        // describe: provide access to feature
        try await api.acl.assignAccessToAppFeature("io.bithead.test", "Test.r", to: user)
        
        // describe: user has acces to ACL feature
        try await api.acl.verifyAccess(for: user, to: "io.bithead.test", feature: "Test.r")
        
        // describe: assign user access to unknown app
        await XCTAssertError(
            try await api.acl.verifyAccess(for: user, to: "io.bithead.unknown"),
            api.error.AccessDenied()
        )
        // describe: assign user access to unknown feature
        await XCTAssertError(
            try await api.acl.verifyAccess(for: user, to: "io.bithead.test", feature: "Feature.r"),
            api.error.AccessDenied()
        )
    }
    
    /// Services, such as the Python service, may provide a catalog of all apps and ACL. This tests the ACL catalog CRUD operations.
    func testAclCatalog() async throws {
        try await boss.start(storage: .memory)
        
        // describe: user does not have ACL to feature within app
        await XCTAssertError(
            try await api.acl.createAclCatalog(for: "", apps: []),
            api.error.InvalidParameter(name: "name")
        )
        
        var apps: [ACLApp] = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"])
        ]
        var catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        var expected = ACLCatalog(id: 1, name: "python", apps: apps)
        XCTAssertEqual(catalog, expected)
        
        // describe: new app is added
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Feature.w"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        expected = ACLCatalog(id: 1, name: "python", apps: apps)
        XCTAssertEqual(catalog, expected)
        
        // describe: a new feature is added
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Feature.w", "Person.r"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        expected = ACLCatalog(id: 1, name: "python", apps: apps)
        XCTAssertEqual(catalog, expected)

        
        // describe: a new feature permission is added
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Feature.w", "Feature.r", "Person.r"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        expected = ACLCatalog(id: 1, name: "python", apps: apps)
        XCTAssertEqual(catalog, expected)
        
        // describe: a feature permission is removed
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Feature.r", "Person.r"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        expected = ACLCatalog(id: 1, name: "python", apps: apps)
        XCTAssertEqual(catalog, expected)
        
        // describe: a feature is removed
        apps = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Person.r"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        expected = ACLCatalog(id: 1, name: "python", apps: apps)
        XCTAssertEqual(catalog, expected)
        
        // describe: an app is removed
        apps = [
            .init(bundleId: "io.bithead.boss", features: ["Person.r"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        expected = ACLCatalog(id: 1, name: "python", apps: apps)
        XCTAssertEqual(catalog, expected)
    }
}
