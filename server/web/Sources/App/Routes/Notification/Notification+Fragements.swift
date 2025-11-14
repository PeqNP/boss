/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import bosslib
import Vapor

extension Fragment {
    struct Notifications: Content {
        let notifications: [bosslib.Notification]
    }
}
