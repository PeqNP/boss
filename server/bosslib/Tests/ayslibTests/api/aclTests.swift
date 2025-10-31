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
            api.error.AccessDenied()
        )
        
        // describe: create ACL with valid feature
        let acl = try await api.acl.createAcl(for: "io.bithead.test", feature: "Test.r")
        XCTAssertEqual(acl, ACLItem(id: 1, bundleId: "io.bithead.test", name: "Test", permission: "r"))
        
        // describe: user has no access to app
        await XCTAssertError(
            try await api.acl.verifyAccess(for: user, to: "io.bithead.test"),
            api.error.AccessDenied()
        )
        
        // describe: user has access to app
        try await api.acl.assignAccessToApp("io.bithead.test", to: user)
        try await api.acl.verifyAccess(for: user, to: "io.bithead.test")
        
        // describe: user does not have ACL to feature within app
        await XCTAssertError(
            try await api.acl.verifyAccess(for: user, to: "io.bithead.test", feature: "Test.r"),
            api.error.AccessDenied()
        )
        
        // describe: user has acces to ACL feature
        try await api.acl.verifyAccess(for: user, to: "io.bithead.test", feature: "Test.r")
    }
    
    /// Services, such as the Python service, may provide a catalog of all apps and ACL. This tests the ACL catalog CRUD operations.
    func testAclCatalog() async throws {
        try await boss.start(storage: .memory)
        
        /// describe: acl does not contain two parts
        let apps: [ACLApp] = [
            .init(bundleId: "io.bithead.test", features: ["Test.r"])
        ]
        let catalog = try await api.acl.createAclCatalog(for: "python", apps: apps)
        let expected = ACLCatalog(id: 1, name: "python", apps: apps)
        XCTAssertEqual(catalog, expected)
        
        // describe: a feature is removed
        // describe: an app is removed
        // describe: a new feature is added
        // describe: a new feature permission is added
        // describe: a feature permission is removed
    }
}
