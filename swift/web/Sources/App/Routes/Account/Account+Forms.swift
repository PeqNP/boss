/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import ayslib
import Vapor

enum AccountForm {
    struct Account: Content {
        var error: String?
        var fullname: String?
        var orgpath: String?
        var email: String?
        var password: String?
        var terms: String?

        static var empty: Account {
            .init(error: "", fullname: "", orgpath: "", email: "", password: "")
        }
    }
    
    struct AccountVerificationSent: Content {
        var email: String
    }
    
    struct AccountCode: Content {
        var error: String?
    }
    
    struct AccountVerified: Content {
        var orgpath: String
        var email: String
    }
    
    struct AccountVerify: Content {
        var code: String?
    }
    
    struct SignIn: Content {
        var email: String?
        var password: String?
    }
    
    struct User: Content {
        let id: UserID?
        let email: String
        let password: String?
        let fullName: String
        let verified: Bool
        let enabled: Bool
    }
    
    struct RecoverAccount: Content {
        let email: String
    }
}
