/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation
import XCTest

@testable import ayslib

final class aclTests: XCTestCase {
    override func setUpWithError() throws {
        try super.setUpWithError()
        api.reset()
    }

    func testAcl() throws {
        // when: user is super admin; acl has no access
        // it: should grant access
        var node = Node.fake()
        try api.acl.checkAccess(authUser: superUser(), object: node, op: .read)

        // when: user is guest; acl has no access
        // it: should NOT grant access
        XCTThrowsError(
            try api.acl.checkAccess(authUser: guestUser(), object: node, op: .read),
            api.error.AccessDenied()
        )

        // when: acl is all; valid op
        // it: should grant access
        node.acl = [.fake(operations: [.read], type: .all)]
        try api.acl.checkAccess(authUser: guestUser(), object: node, op: .read)

        // when: acl is all; invalid op
        // it: should NOT grant access
        node.acl = [.fake(operations: [.read], type: .all)]
        XCTThrowsError(
            try api.acl.checkAccess(authUser: guestUser(), object: node, op: .write),
            api.error.AccessDenied()
        )

        // when: acl is individual; user has access
        // it: should grant access
        node.acl = [.fake(operations: [.read], type: .individual(Global.guestUserId))]
        try api.acl.checkAccess(authUser: guestUser(), object: node, op: .read)

        // when: acl is individual; user does not have access
        // it: should NOT grant access
        node.acl = [.fake(operations: [.read], type: .individual(Global.guestUserId))]
        XCTThrowsError(
            try api.acl.checkAccess(authUser: guestUser(), object: node, op: .write),
            api.error.AccessDenied()
        )

        // when: acl is group: user has access
        // it: should grant access
        node.acl = [.fake(operations: [.read], type: .group([Global.guestUserId]))]
        try api.acl.checkAccess(authUser: guestUser(), object: node, op: .read)

        // when: acl is group: user does NOT have access
        // it: should NOT grant access
        node.acl = [.fake(operations: [.read], type: .individual(Global.guestUserId))]
        XCTThrowsError(
            try api.acl.checkAccess(authUser: guestUser(), object: node, op: .write),
            api.error.AccessDenied()
        )

        // when: acl is entity: user has access
        // it: should grant access
        node.acl = [.fake(operations: [.read], type: .entities([.fake(type: .all)]))]
        try api.acl.checkAccess(authUser: guestUser(), object: node, op: .read)

        // when: acl is entity: user does NOT have access
        // it: should NOT grant access
        node.acl = [.fake(operations: [.read], type: .entities([.fake(type: .all)]))]
        XCTThrowsError(
            try api.acl.checkAccess(authUser: guestUser(), object: node, op: .write),
            api.error.AccessDenied()
        )
    }
}
