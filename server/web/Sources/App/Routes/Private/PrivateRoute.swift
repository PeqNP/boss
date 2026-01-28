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
                summary: "Register a private BOSS service ACL catalog",
                description: "Refer to the private Python services for examples. An endpoint may indicate that a permission is required to access the respective resource. `/private/acl/register` must be called directly after all routes have been registered in the private service. Once the ACL is registered, the private service can call `/private/acl/verify` to check if the signed in user has access to the resource. * Only available to private services.",
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
                description: "Verify a user's access to an ACL resource. * Only available to private services.",
                body: .type(PrivateForm.VerifyACL.self),
                contentType: .application(.json),
                response: .type(Fragment.User.self),
                responseContentType: .application(.json)
            )
        }
        
        group.group("send") { notification in
            notification.post("notifications") { req in
                try await sendNotifications(request: req)
            }.openAPI(
                summary: "Send BOSS notification(s) to user(s)",
                description: "* Only available to private services.",
                body: .type(PrivateForm.SendNotifications.self),
                contentType: .application(.json),
                response: .type(Fragment.OK.self),
                responseContentType: .application(.json)
            )
            .addScope(.user)
            
            notification.post("events") { req in
                try await sendEvents(request: req)
            }.openAPI(
                summary: "Send BOSS event(s) to user(s)",
                description: "* Only available to private services.",
                body: .type(PrivateForm.SendEvents.self),
                contentType: .application(.json),
                response: .type(Fragment.OK.self),
                responseContentType: .application(.json)
            )
            .addScope(.user)
        }
    }
}

func sendNotifications(request: Request) async throws -> some Content {
    let form = try request.content.decode(PrivateForm.SendNotifications.self)
    var notifications = [bosslib.Notification]()
    for notif in form.notifications {
        let n = try await api.notification.saveNotification(
            bundleId: notif.controller?.bundleId ?? "io.bithead.boss",
            controllerName: notif.controller?.name ?? "Notification",
            deepLink: notif.deepLink,
            title: notif.title,
            body: notif.body,
            metadata: notif.metadata,
            userId: notif.userId,
            persist: notif.persist
        )
        notifications.append(n)
    }
    await ConnectionManager.shared.sendNotifications(notifications)
    return Fragment.OK()
}

func sendEvents(request: Request) async throws -> some Content {
    let form = try request.content.decode(PrivateForm.SendEvents.self)
    await ConnectionManager.shared.sendEvents(form.events)
    return Fragment.OK()
}
