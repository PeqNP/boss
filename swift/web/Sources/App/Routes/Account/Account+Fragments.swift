/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import ayslib
import Vapor

extension Fragment {
    struct SignIn: Content {
        var error: String
    }
    
    struct SignOut: Content { }
    struct RecoverAccount: Content { }
        
    struct Users: Content {
        let users: [Fragment.Option]
    }
    
    struct User: Content {
        let user: ayslib.User?
    }
    struct SaveUser: Content {
        let user: ayslib.User
    }
    struct DeleteUser: Content { }
}
