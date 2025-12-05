/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import bosslib
import Foundation
import Vapor

/// Register private routes at `/private/`.
///
/// These routes are not accessible to the public. Therefore, they do not need authorization.
public func registerPrivate(_ app: Application) {
    app.group("private") { group in
        group.group("acl") { acl in
            acl.post("register") { req in
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
            
            acl.get("verify") { req in
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
        }
        
        group.group("send") { notification in
            group.post("notifications") { req in
                let form = try req.content.decode(PrivateForm.SendNotifications.self)
                // TODO: Save to DB if notification must be persisted
                await ConnectionManager.shared.sendNotifications(form.notifications)
                return Fragment.OK()
            }.openAPI(
                summary: "Send notification(s) to user(s)",
                body: .type(PrivateForm.SendNotifications.self),
                contentType: .application(.json),
                response: .type(Fragment.OK.self),
                responseContentType: .application(.json)
            )
            .addScope(.user)
            
            group.post("events") { req in
                // TODO: Send to signed in users
                return Fragment.OK()
            }.openAPI(
                summary: "Send event(s) to user(s)",
                body: .type(PrivateForm.SendEvents.self),
                contentType: .application(.json),
                response: .type(Fragment.OK.self),
                responseContentType: .application(.json)
            )
            .addScope(.user)
        }
    }
}
