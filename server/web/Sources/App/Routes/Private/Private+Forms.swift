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
        let notifications: [bosslib.Notification]
    }
    struct SendEvents: Content {
        let events: [bosslib.NotificationEvent]
    }
}
