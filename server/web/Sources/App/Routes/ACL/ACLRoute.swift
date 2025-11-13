/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import bosslib
import Foundation
import Vapor

/// Register the private `/acl/` routes.
///
/// These routes are not accessible to the public. Therefore, they do not need authorization.
public func registerACL(_ app: Application) {
    app.group("acl") { group in
        group.post("register") { req in
            let form = try req.content.decode(ACLForm.RegisterCatalog.self)
            let apps = form.apps.map { (app: ACLForm.RegisterCatalog.ACLApp) -> ACLApp in
                .init(bundleId: app.bundleId, features: Set(app.features))
            }
            let catalog = try await api.acl.createAclCatalog(for: form.name, apps: apps)
            boss.log.i("Registered ACL catalog (\(catalog))")
            let fragment = Fragment.RegisteredACL(catalog: catalog)
            return fragment
        }.openAPI(
            summary: "Register a BOSS service ACL catalog",
            description: "This allows a service to register the ACL associated to each of its endpoints.",
            body: .type(ACLForm.RegisterCatalog.self),
            contentType: .application(.json),
            response: .type(Fragment.RegisteredACL.self),
            responseContentType: .application(.json)
        )
        
        group.get("verify") { req in
            let form = try req.content.decode(ACLForm.VerifyACL.self)
            let user = try await verifyAccess(req, acl: .init(catalog: form.catalog, bundleId: form.bundleId, feature: form.feature))
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
