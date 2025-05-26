/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import bosslib
import Vapor

extension Fragment {
    struct SignIn: Content {
        var user: User?
        var error: String?
    }
    
    struct SignOut: Content { }
    struct RecoverAccount: Content { }
    
    // User that removes password or any other confidential info that should not
    // be sent to client.
    struct User: Content {
        public var id: UserID
        public let system: AccountSystem
        public var fullName: String
        public var email: String
        public var verified: Bool
        public var enabled: Bool
        
        // Preferences
        public var homeNodeID: NodeID?
        public var avatarUrl: URL?
        public var preferredLanguage: Script.Language?
        public var preferredTheme: String?
        public var preferredFont: String?
    }
    
    struct GetUsers: Content {
        let users: [Fragment.Option]
    }
    struct GetUser: Content {
        let user: Fragment.User?
    }
    struct SaveUser: Content {
        let user: Fragment.User
    }
    struct DeleteUser: Content { }
    struct RefreshUser: Content { }
}

extension bosslib.User {
    func makeUser() -> Fragment.User {
        .init(
            id: id,
            system: system,
            fullName: fullName,
            email: email,
            verified: verified,
            enabled: enabled,
            avatarUrl: avatarUrl
        )
    }
}
