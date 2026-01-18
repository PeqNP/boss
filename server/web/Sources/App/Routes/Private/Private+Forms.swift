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
            struct Controller: Content {
                // The bundle where the `NotificationController` is located
                public let bundleId: BundleID
                // Name of BOSS `NotificationController`
                public let name: String
            }
            // If `nil`, this uses the default BOSS `Notification` controller
            public let controller: SendNotifications.Notification.Controller?
            // Location where user is redirected to when the notification is tapped
            public let deepLink: String?
            // The title of the notification.
            public let title: String?
            // The message body of the notification
            public let body: String?
            // Metadata the notification may use to display dynamic data (images, names, etc.) that may not be part of the body. The source of the message will most likely either use the `body` or `metadata`. The body will most likely be created for custom events, which will prefer metadata over the body.
            public let metadata: [String: String]?
            // The user the notification is sent to
            public let userId: UserID
            // Indicates that the notification may persist until dismissed. Persistent notifications disappear, and added to a "Notifications Panel", which a user can look back through. Non-persistent notifications are not saved and do not dismiss automatically. Therefore, the user is expected to dismiss them before they disappear in the UI.
            public let persist: Bool
        }
        
        let notifications: [PrivateForm.SendNotifications.Notification]
    }
    struct SendEvents: Content {
        let events: [bosslib.NotificationEvent]
    }
}
