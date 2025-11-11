/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import bosslib
import Foundation
import Smtp
import Vapor

/// Register the `/account/` routes.
public func registerAccount(_ app: Application) {
    app.group("account") { group in
        group.post { req async throws -> View in
            let form = try req.content.decode(AccountForm.Account.self)

            let acceptableTermOptions: [String?] = ["on", "checked"]
            if !acceptableTermOptions.contains(form.terms) {
                let f = with(form) { o in
                    o.error = "You must accept the Terms of Service and Privacy Policy."
                }
                return try await req.view.render("account/index", f)
            }

            let admin = superUser()
            do {
                let (user, _ /* code */) = try await api.account.createUser(
                    admin: admin,
                    email: form.email,
                    password: form.password,
                    fullName: form.fullname,
                    verified: false
                )

                return try await req.view.render(
                    "account/verify",
                    AccountForm.AccountVerificationSent(email: user.email)
                )
            }
            catch let error as api.error.InvalidAccountInfo {
                let f = with(form) { o in
                    o.error = "You must enter your \(error.field)."
                }
                return try await req.view.render("account/index", f)
            }
        }.openAPI(
            summary: "Create an @ys account.",
            body: .type(AccountForm.Account.self),
            contentType: .application(.urlEncoded)
        )
        
        group.get("mfa") { req in
            let authUser = try req.authUser
            let (_, url) = try await api.account.generateTotpSecret(authUser: authUser, user: authUser.user)
            let fragment = Fragment.RegisterMFA(otpAuthUrl: url)
            return fragment
        }.openAPI(
            summary: "Enabled MFA on your account",
            description: "Begin the process of enabling MFA on your account. This returns a `otpauth` URL in response.",
            response: .type(Fragment.RegisterMFA.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)
        
        group.patch("mfa") { req in
            let form = try req.content.decode(AccountForm.MFAChallenge.self)
            _ = try await api.account.registerMfa(authUser: req.authUser, code: form.mfaCode)
            let response = Fragment.OK()
            return response
        }.openAPI(
            summary: "Validate MFA registration",
            description: "Validate the MFA code to finalize MFA account registration. Once this process is complete, your account will be enabled with MFA.",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user, verifyMFAChallenge: false)
        
        group.post("mfa") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(AccountForm.MFAChallenge.self)
            do {
                try await api.account.verifyMfa(authUser: authUser, code: form.mfaCode)
                let fragment = Fragment.SignIn(user: authUser.user.makeUser(), error: nil)
                return fragment
            }
            catch {
                let fragment = Fragment.SignIn(
                    user: authUser.user.makeUser(),
                    error: "MFA code is invalid."
                )
                return fragment
            }
        }.openAPI(
            summary: "Provide MFA challenge.",
            description: "Provide MFA challenge directly after a user has been verified from sign in.",
            body: .type(AccountForm.MFAChallenge.self),
            contentType: .application(.json),
            response: .type(Fragment.SignIn.self),
            responseContentType: .application(.json)
        )
        // Verify the session (to ensure credentials are correct), but do not verify MFA challenge. That's what is being done right now.
        .addScope(.user, verifyMFAChallenge: false)

        group.post("signin") { (req: Request) async throws -> Response in
            let form = try req.content.decode(AccountForm.SignIn.self)
            do {
                let user = try await api.account.verifyCredentials(email: form.email, password: form.password)
                guard !user.isGuestUser else {
                    throw api.error.GuestUserAccessDenied()
                }
                
                let session = try await api.account.makeUserSession(user: user)
                
                let response = try makeSessionCookieResponse(user: user, session: session)
                return response
            } catch {
                let fragment = Fragment.SignIn(
                    user: nil,
                    error: "Failed to sign in. Please check your email and password."
                )
                let response = Response(status: .ok)
                response.headers.contentType = .json
                try response.content.encode(fragment)
                return response
            }
        }.openAPI(
            summary: "Sign in to your Bithead OS account.",
            body: .type(AccountForm.SignIn.self),
            contentType: .application(.json),
            response: .type(Fragment.SignIn.self),
            responseContentType: .application(.json)
        )
        
        group.get("refresh") { req in
            let fragment = Fragment.RefreshUser()
            return fragment
        }.openAPI(
            summary: "Refresh user session",
            description: "Refresh a user session for another \(Global.maxAllowableInactivityInMinutes) minutes",
            response: .type(Fragment.RefreshUser.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.post("setcookie", ":org_path") { (req: Request) async throws -> Response in
            guard let orgPath = req.parameters.get("node_path") else {
                throw api.error.InvalidAccountInfo(field: .orgPath)
            }
            return req.redirect(to: "/node/graph/\(orgPath)")
        }
        
        group.get("signout") { req in
            // Eventually I should use the session?
            // req.session.destroy()
            try await api.account.signOut(user: req.authUser)
            
            let response = Response(status: .ok)
            response.cookies["accessToken"] = .init(string: "", expires: Date.distantPast, maxAge: 0)
            response.headers.contentType = .json
            try response.content.encode(Fragment.SignOut())
            return response
        }.openAPI(
            summary: "Sign out from your Bithead OS account",
            description: "This will sign you out of your Bithead OS account.",
            response: .type(Fragment.SignOut.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)
        
        // MARK: User
        
        group.get("user") { req in
            let fragment = try Fragment.GetUser(user: req.authUser.user.makeUser())
            return fragment
        }.openAPI(
            summary: "Retrieve currently signed in BOSS user",
            description: "This is used primarily to validate if a user is signed in.",
            response: .type(Fragment.GetUser.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("users") { req async throws in
            let users = try await api.account.users(user: req.authUser)
            let fragment = Fragment.GetUsers(
                users: users.map { Fragment.Option(id: $0.id, name: $0.email) }
            )
            return fragment
        }.openAPI(
            summary: "Return all BOSS users",
            response: .type(Fragment.GetUsers.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)
        
        group.get("user", ":userID") { req in
            let userID = req.parameters.get("userID")
            let user = try await api.account.user(auth: req.authUser, id: .require(userID))
            let fragment = Fragment.GetUser(
                user: user.makeUser()
            )
            return fragment
        }.openAPI(
            summary: "Load user",
            response: .type(Fragment.User.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)
        
        // Admin route to create user
        group.post("user") { req in
            let form = try req.content.decode(AccountForm.User.self)
            let user = try await api.account.saveUser(
                user: req.authUser,
                id: .make(form.id),
                email: form.email,
                password: form.password,
                fullName: form.fullName,
                verified: form.verified,
                enabled: form.enabled
            )
            return Fragment.SaveUser(user: user.makeUser())
        }.openAPI(
            summary: "Save user",
            response: .type(Fragment.SaveUser.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)
        
        group.delete("user", ":userID") { req in
            let userID = req.parameters.get("userID")
            try await api.account.deleteUser(auth: req.authUser, id: .require(userID))
            return Fragment.DeleteUser()
        }.openAPI(
            summary: "Delete a user",
            response: .type(Fragment.DeleteUser.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)
        
        group.post("create-user") { req in
            let form = try req.content.decode(AccountForm.CreateUser.self)
            let email = try await api.account.createUser(email: form.email)
            if app.environment.isRelease {
                let from = EmailAddress(address: "bitheadrl@protonmail.com", name: "Bithead LLC")
                let to = EmailAddress(address: email.email, name: email.name)
                let e = try Email(
                    from: from,
                    to: [to],
                    subject: email.subject,
                    body: email.body
                )
                try await req.smtp.send(e)
                boss.log.i("Sent email to (\(email.email))")
            }
            else {
                boss.log.i("Send to (\(email.email)) Subject (\(email.subject))")
                boss.log.i(email.body)
            }
            return Fragment.CreateUser()
        }.openAPI(
            summary: "Create a new user with verification code",
            description: "This is a public facing route to create a new user. No authentication is required.",
            response: .type(Fragment.CreateUser.self),
            responseContentType: .application(.json)
        )
        
        group.post("verify-user") { req in
            let form = try req.content.decode(AccountForm.VerifyUser.self)
            _ = try await api.account.verifyUser(
                code: form.code,
                password: form.password,
                fullName: form.fullName
            )
            return Fragment.VerifyUser()
        }.openAPI(
            summary: "Create a new user with verification code",
            description: "This is a public facing route to create a new user. No authentication is required.",
            response: .type(Fragment.VerifyUser.self),
            responseContentType: .application(.json)
        )
        
        group.post("recover-account") { req in
            let form = try req.content.decode(AccountForm.RecoverAccount.self)
            let email: SystemEmail
            do {
                email = try await api.account.createAccountRecoveryEmail(email: form.email)
            }
            catch {
                return Fragment.RecoverAccount()
            }
            
            if app.environment.isRelease {
                let from = EmailAddress(address: "bitheadrl@protonmail.com", name: "Bithead LLC")
                let to = EmailAddress(address: email.email, name: email.name)
                let e = try Email(
                    from: from,
                    to: [to],
                    subject: email.subject,
                    body: email.body
                )
                try await req.smtp.send(e)
                boss.log.i("Sent email to (\(email.email))")
            }
            else {
                boss.log.i("Send to (\(email.email)) Subject (\(email.subject))")
                boss.log.i(email.body)
            }
            return Fragment.RecoverAccount()
        }.openAPI(
            summary: "Recover account",
            description: "Start the process of recovering your account. An email will be sent, to the provided email address, with a code you can use to reset your password.",
            response: .type(Fragment.RecoverAccount.self),
            responseContentType: .application(.json)
        )
        
        group.post("reset-password") { req in
            let form = try req.content.decode(AccountForm.ResetPassword.self)
            _ = try await api.account.recoverAccount(code: form.code, password: form.password)
            
            return Fragment.ResetPassword()
        }.openAPI(
            summary: "Reset password",
            description: "Reset the password for account using the code provided in the email.",
            response: .type(Fragment.ResetPassword.self),
            responseContentType: .application(.json)
        )
        
        group.get("acl-tree") { req in
            let tree = try await api.acl.aclTree()
            let fragment = Fragment.ACLTree(tree: tree)
            return fragment
        }.openAPI(
            summary: "Get ACL associated to user",
            description: "Returns all ACL if super admin. Returns a read-only list of ACL the user has access to.",
            response: .type(Fragment.ACLTree.self),
            responseContentType: .application(.json)
        )
        .addScope(.admin)

        group.post("user-acl") { req in
            let form = try req.content.decode(AccountForm.UserACL.self)
            let authUser = try req.authUser
            let user = try await api.account.user(auth: authUser, id: form.userId)
            let acl = try await api.acl.userAcl(for: user)
            let fragment = Fragment.UserACL(acl: acl)
            return fragment
        }.openAPI(
            summary: "Get ACL associated to user",
            description: "Returns all ACL if super admin. Returns a read-only list of ACL the user has access to.",
            body: .type(AccountForm.AssignACL.self),
            contentType: .application(.json),
            response: .type(Fragment.UserACL.self),
            responseContentType: .application(.json)
        )
        .addScope(.admin)
        
        group.post("assign-acl") { req in
            let form = try req.content.decode(AccountForm.AssignACL.self)
            let authUser = try req.authUser
            let user = try await api.account.user(auth: authUser, id: form.userId)
            let aclItems = try await api.acl.assignAccessToAcl(ids: form.acl, to: user)
            let fragment = Fragment.AssignedACL(aclItems: aclItems)
            return fragment
        }.openAPI(
            summary: "Assign ACL to user.",
            description: "Only available to admins.",
            body: .type(AccountForm.SignIn.self),
            contentType: .application(.json),
            response: .type(Fragment.AssignedACL.self),
            responseContentType: .application(.json)
        )
        .addScope(.admin)
    }
}

/// Make cookie used to store user session.
private func makeSessionCookieResponse(user: User, session: UserSession) throws -> Response {
    let cookie = HTTPCookies.Value(
        string: session.accessToken,
        expires: session.jwt.expiration,
        isSecure: false,
        isHTTPOnly: true,
        sameSite: HTTPCookies.SameSitePolicy.strict
    )
    
    let response = Response(status: .ok)
    response.cookies["accessToken"] = cookie
    response.headers.contentType = .json
    try response.content.encode(Fragment.SignIn.init(user: user.makeUser(), error: nil))
    return response
}
