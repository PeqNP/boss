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
    struct ResetPassword: Content { }
    
    // User that removes password or any other confidential info that should not
    // be sent to client.
    struct User: Content {
        public var id: UserID
        public let system: AccountSystem
        public var fullName: String
        public var email: String
        public var verified: Bool
        public var enabled: Bool
        public var mfaEnabled: Bool
        
        // Preferences
        public var avatarUrl: URL?
        public var preferredTheme: String?
        public var preferredFont: String?
    }
    
    struct GetUsers: Content {
        let users: [Fragment.Option]
    }
    struct GetUser: Content {
        let user: Fragment.User
    }
    struct SaveUser: Content {
        let user: Fragment.User
    }
    struct CreateUser: Content { }
    struct VerifyUser: Content { }
    struct DeleteUser: Content { }
    struct RefreshUser: Content { }
    
    struct RegisterMFA: Content {
        let otpAuthUrl: URL
    }

    struct AppLicense: Content {
        let valid: Bool
        let license: bosslib.AppLicense?
    }
    struct ACLTree: Content {
        let tree: bosslib.ACLTree
    }
    struct UserACL: Content {
        let license: bosslib.AppLicense?
        let acl: [ACLID]
    }
    struct AssignedACL: Content {
        let license: bosslib.AppLicense?
        let aclItems: [ACLItem]
    }
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
            mfaEnabled: mfaEnabled,
            avatarUrl: avatarUrl
        )
    }
}
