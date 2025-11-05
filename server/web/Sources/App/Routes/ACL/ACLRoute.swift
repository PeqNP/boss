/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import bosslib
import Foundation
import Smtp
import Vapor

/// Register the private `/acl/` routes.
///
/// These routes are not accessible to the public. Therefore, they do not need authorization.
public func registerACL(_ app: Application) {
    app.group("acl") { group in
        group.post("register") { req in
            let form = try req.content.decode(ACLForm.RegisterCatalog.self)
            boss.log.i("\(form)")
            // TODO: After registering ACL, it may be possible to return the catalog
            // TODO: Convert the ACLForm.ACLApp to the respective types
            _ = try await api.acl.createAclCatalog(for: form.catalog, apps: [])
            let fragment = Fragment.RegisteredACL(success: true)
            return fragment
        }.openAPI(
            summary: "Register BOSS service ACLs",
            body: .type(ACLForm.RegisterCatalog.self),
            contentType: .application(.json),
            response: .type(Fragment.RegisteredACL.self),
            responseContentType: .application(.json)
        )
        
        group.get("verify") { req in
            let form = try req.content.decode(ACLForm.VerifyACL.self)
            let feat: String? = if let permission = form.permission, let feature = form.feature {
                "\(feature).\(permission)"
            }
            else if let feature = form.feature {
                feature
            }
            else {
                nil
            }
            let user = try await verifyAccess(req, acl: .init(catalog: form.catalog, bundleId: form.bundleId, feature: feat))
            let fragment = user.user.makeUser()
            return fragment
        }.openAPI(
            summary: "Register BOSS service ACLs",
            description: "Verifies user's access to ACL resource. Returns user.",
            body: .type(ACLForm.VerifyACL.self),
            contentType: .application(.json),
            response: .type(Fragment.User.self),
            responseContentType: .application(.json)
        )
    }
}
