/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import bosslib
import Foundation
import Smtp
import Vapor

/// Register the `/notification/` routes.
///
/// Provides notification service which sends
/// - System notification events (Process finished)
/// - User notification events (Friend requests)
/// - Session expiry event
public func registerNotification(_ app: Application) {
    app.group("notification") { group in
        group.webSocket("connect") { req, ws in
            do {
                try await ConnectionManager.shared.register(ws, to: req.authUser)
            }
            catch {
                try? await ws.close()
            }
        }
        .addScope(.user)
        
        group.get("notifications") { req in
            let fragment = Fragment.Notifications(notifications: [])
            return fragment
        }.openAPI(
            summary: "Get all user notifications",
            description: "Returns all notifications that user has not yet dismissed.",
            response: .type(Fragment.Notifications.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)
        
        /// Update the "seen" bit on notifications
        group.patch("notifications") { req in
            let _ = try req.content.decode(NotificationForm.SeenNotifications.self)
            return Fragment.OK()
        }.openAPI(
            summary: "Indicate that notifications have been seen by the user",
            body: .type(NotificationForm.SeenNotifications.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)
        
        group.delete("notifications") { req in
            return Fragment.OK()
        }.openAPI(
            summary: "Delete one or more notifications",
            body: .type(NotificationForm.DeleteNotifications.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)
    }
}
