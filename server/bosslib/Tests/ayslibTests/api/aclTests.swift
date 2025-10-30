/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import Foundation
import XCTest

@testable import bosslib

final class aclTests: XCTestCase {
    /// Tests access to an app and respective app's ACL permissions
    func testAcl() async throws {
        try await boss.start(storage: .memory)

        let user = try await api.account.saveUser(user: superUser(), id: nil, email: "eric@example.com", password: "Password1!", fullName: "Eric", verified: true, enabled: true)
        let app = try await api.acl.createApp("io.bithead.test")
        let acl = try await api.acl.createAcl(app: "io.bithead.test", feature: "Test.r")
        
        // describe: user has no access to app
        await XCTAssertError(
            try await api.acl.verifyAccess(user, to: "io.bithead.test"),
            api.error.AccessDenied()
        )
        
        // describe: user has access to app
        try await api.acl.assignAccessToApp("io.bithead.test", to: user)
        try await api.acl.verifyAccess(user, to: "io.bithead.test")
        
        // describe: user does not have ACL to feature within app
        await XCTAssertError(
            try await api.acl.verifyAccess(user, to: "io.bithead.test", feature: "Test.r"),
            api.error.AccessDenied()
        )
        
        // describe: user has acces to ACL feature
        try await api.acl.verifyAccess(user, to: "io.bithead.test", feature: "Test.r")
    }
    
    /// Services, such as the Python service, may provide a catalog of all apps and ACL. This tests the ACL catalog CRUD operations.
    func testAclCreation() async throws {
        /// describe: acl does not contain two parts
        let apps: [AppACL] = [
            .init(app: "io.bithead.test", features: ["Test"])
        ]
        try await api.acl.createCatalog(service: "python", apps: apps)
    }
}
