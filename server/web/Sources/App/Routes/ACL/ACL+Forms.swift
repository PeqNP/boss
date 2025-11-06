/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import bosslib
import Vapor

enum ACLForm {
    struct RegisterCatalog: Content {
        struct ACLApp: Content {
            let bundleId: String
            let features: [String]
        }
        
        let name: String
        let apps: [ACLForm.RegisterCatalog.ACLApp]
    }
    
    struct VerifyACL: Content {
        let catalog: String
        let bundleId: String
        let feature: String?
        let permission: String?
    }
}
