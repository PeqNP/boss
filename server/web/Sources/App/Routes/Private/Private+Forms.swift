/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import bosslib
import Vapor

enum PrivateForm {
    struct RegisterCatalog: Content {
        struct ACLApp: Content {
            let bundleId: String
            let features: [String]
        }
        
        let name: String
        let apps: [PrivateForm.RegisterCatalog.ACLApp]
    }
    
    struct VerifyACL: Content {
        let catalog: String
        let bundleId: String
        let feature: String?
    }
    
    struct SendNotifications: Content {
        struct Notification: Content {
            // The bundle where the `NotificationController` is located
            public let bundleId: BundleID
            // Name of BOSS `NotificationController`
            public let controllerName: String
            // Location where user is redirected to when the notification is tapped
            public let deepLink: String
            // The title of the notification.
            public let title: String
            // The message body of the notification
            public let body: String?
            // Metadata the notification may use to display dynamic data (images, names, etc.) that may not be part of the body. The source of the message will most likely either use the `body` or `metadata`. The body will most likely be created for custom events, which will prefer metadata over the body.
            public let metadata: [String: String]?
            // The user the notification is sent to
            public let userId: UserID
            // Indicates that the notification must persist until closed. Non-persistent notifications are not saved. The user is expected to dismiss them.
            public let persist: Bool
        }
        
        let notifications: [PrivateForm.SendNotifications.Notification]
    }
    struct SendEvents: Content {
        let events: [bosslib.NotificationEvent]
    }
}
