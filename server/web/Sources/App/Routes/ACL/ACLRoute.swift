/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import bosslib
import Foundation
import Smtp
import Vapor

/// Register the private `/acl/` routes.
///
/// These routes are not accessible to the public.
public func registerACL(_ app: Application) {
    app.group("acl") { group in
        group.post("register") { req in
            let form = try req.content.decode(ACLForm.RegisterACL.self)
            boss.log.i("\(form)")
            let fragment = Fragment.RegisteredACL(success: true)
            return fragment
        }.openAPI(
            summary: "Register BOSS service ACLs",
            body: .type(ACLForm.RegisterACL.self),
            contentType: .application(.urlEncoded),
            response: .type(Fragment.RegisteredACL.self),
            responseContentType: .application(.json)
        )
        
        group.get("verify") { req in
            // There also needs to be a "source" (Swift | Python) of the ACL so that ACL can be removed. Such that, if the Python service no longer provides ACL for a given service, it needs to be removed because it means the app was removed.
            guard let bundleId = req.headers["ACL-Bundle-ID"].first else {
                throw Abort(.badRequest, reason: "ACL-Bundle-ID is required")
            }
            guard let name = req.headers["ACL-Name"].first else {
                throw Abort(.badRequest, reason: "ACL-Name is required")
            }
            guard let permission = req.headers["ACL-Permission"].first else {
                throw Abort(.badRequest, reason: "ACL-Permission is required")
            }
            let user = try await verifyAccess(req)
            let acl = ACLItem(bundleId: bundleId, name: name, permission: permission)
            // TODO: Check ACL against user, if any
            // throw Abort(.forbidden, reason: "You do not have the required permissions to access this resource.")
            let fragment = user.user.makeUser()
            return fragment
        }.openAPI(
            summary: "Register BOSS service ACLs",
            description: "Verify that a user has access to a ACL resource. Use /account/user to get your own user information.",
            response: .type(Fragment.User.self),
            responseContentType: .application(.json)
        )
    }
}
