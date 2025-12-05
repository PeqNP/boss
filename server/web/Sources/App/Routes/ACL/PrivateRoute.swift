/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import bosslib
import Foundation
import Vapor

/// Register private routes at `/private/`.
///
/// These routes are not accessible to the public. Therefore, they do not need authorization.
public func registerPrivate(_ app: Application) {
    app.group("private") { group in
        group.post("register-acl") { req in
            let form = try req.content.decode(PrivateForm.RegisterCatalog.self)
            let apps = form.apps.map { (app: PrivateForm.RegisterCatalog.ACLApp) -> ACLApp in
                .init(bundleId: app.bundleId, features: Set(app.features))
            }
            let catalog = try await api.acl.createAclCatalog(for: form.name, apps: apps)
            boss.log.i("Registered ACL catalog (\(catalog))")
            let fragment = Fragment.RegisteredACL(catalog: catalog)
            return fragment
        }.openAPI(
            summary: "Register a BOSS service ACL catalog",
            description: "This allows a service to register the ACL associated to each of its endpoints.",
            body: .type(PrivateForm.RegisterCatalog.self),
            contentType: .application(.json),
            response: .type(Fragment.RegisteredACL.self),
            responseContentType: .application(.json)
        )
        
        group.get("verify-acl") { req in
            let form = try req.content.decode(PrivateForm.VerifyACL.self)
            let user = try await verifyAccess(req, acl: .init(catalog: form.catalog, bundleId: form.bundleId, feature: form.feature))
            let fragment = user.user.makeUser()
            return fragment
        }.openAPI(
            summary: "Register BOSS service ACLs",
            description: "Verifies user's access to ACL resource. Returns user.",
            body: .type(PrivateForm.VerifyACL.self),
            contentType: .application(.json),
            response: .type(Fragment.User.self),
            responseContentType: .application(.json)
        )
        
        group.post("send-notifications") { req in
            let fragment = Fragment.Notifications(notifications: [])
            return fragment
        }.openAPI(
            summary: "Send notification(s) to user(s)",
            body: .type(PrivateForm.SendNotifications.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)
    }
}
