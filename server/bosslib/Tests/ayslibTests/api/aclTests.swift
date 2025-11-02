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
        
        // describe: user provides invalid bundle ID
        await XCTAssertError(
            try await api.acl.verifyAccess(for: user, to: "  "),
            api.error.InvalidParameter(name: "bundleId")
        )
        
        // describe: verify access to app that does not exist
        await XCTAssertError(
            try await api.acl.verifyAccess(for: user, to: "io.bithead.test"),
            api.error.AccessDenied()
        )
        
        // describe: invalid service name
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
        
        // describe: provide access to feature
        try await api.acl.assignAccessToAppFeature("io.bithead.test", "Test.r", to: user)
        try await api.acl.verifyAccess(for: user, to: "io.bithead.test", feature: "Test.r")
        
        // describe: user has access to app
        try await api.acl.assignAccessToApp("io.bithead.test", to: user)
        try await api.acl.verifyAccess(for: user, to: "io.bithead.test")
        
        // describe: user provides invalid feature name
        await XCTAssertError(
            try await api.acl.verifyAccess(for: user, to: "io.bithead.test", feature: "  "),
            api.error.InvalidParameter(name: "feature")
        )
        
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
        
        // describe: duplicate feature permission added
        let duplicateFeatures: [ACLApp] = [
            .init(bundleId: "io.bithead.test", features: ["Test.r", "Test.r"]),
            .init(bundleId: "io.bithead.boss", features: ["Feature.w", "Feature.r", "Person.r"]),
        ]
        catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        expected = ACLCatalog(id: 1, name: "python", apps: apps)
        // it: should not contain duplicate feature
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
