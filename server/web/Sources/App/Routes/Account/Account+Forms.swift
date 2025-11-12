/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import bosslib
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
        var email: String
    }
    
    struct AccountVerify: Content {
        var code: String?
    }
    
    struct SignIn: Content {
        var email: String?
        var password: String?
    }
    
    struct MFAChallenge: Content {
        var mfaCode: String
    }
    
    struct CreateUser: Content {
        var email: String?
    }
    struct VerifyUser: Content {
        let code: String?
        let password: String?
        let fullName: String?
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
    struct ResetPassword: Content {
        let code: String
        let password: String
    }
    
    struct CheckAppAccess: Content {
        let bundleId: BundleID
    }
    struct UserACL: Content {
        let userId: UserID
        let bundleId: BundleID
    }
    struct AssignACL: Content {
        let userId: UserID
        let bundleId: BundleID
        let issueLicense: Bool
        let addAcl: [ACLID]
        let removeAcl: [ACLID]
    }
}
