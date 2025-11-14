/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import bosslib
import Vapor

enum NotificationForm {
    struct DeleteNotifications: Content {
        let notificationIds: [bosslib.NotificationID]
    }
    struct SeenNotifications: Content {
        let notificationIds: [bosslib.NotificationID]
    }
}
