/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import bosslib
import Vapor

enum Fragment {
    /// Used in `UIListBox`es, `Folder`s, etc. to display options
    struct Option: Content {
        let id: String
        let name: String
        
        init(id: String, name: String) {
            self.id = id
            self.name = name
        }
        
        init(id: Int, name: String) {
            self.id = String(id)
            self.name = name
        }
    }
    
    struct Debug: Content {
        let html: String
    }
    
    struct Index: Content {
        let username: String
    }
    
    struct Heartbeat: Content {
        let isSignedIn: Bool
        let isSecurityEnabled: Bool
    }
    
    struct OK: Content { }
}
