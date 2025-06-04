/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import bosslib
import Foundation
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

            let admin = api.account.superUser()
            do {
                let (user, _ /* code */) = try await api.account.createAccount(
                    admin: admin,
                    fullName: form.fullname,
                    email: form.email,
                    password: form.password,
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
            let authUser = try await verifyAccess(cookie: req)
            let url = try await api.account.generateTotpSecret(authUser: authUser, user: authUser.user)
            let fragment = Fragment.RegisterMFA(otpAuthUrl: url)
            return fragment
        }.openAPI(
            summary: "Enabled MFA on your account",
            description: "Begin the process of enabling MFA on your account. This returns a `otpauth` URL in response.",
            response: .type(Fragment.RegisterMFA.self),
            responseContentType: .application(.json)
        )
        
        group.patch("mfa") { (req: Request) async throws -> Response in
            let authUser = try await verifyAccess(cookie: req)
            let form = try req.content.decode(AccountForm.MFAChallenge.self)
            try await api.account.registerMfa(authUser: authUser, code: form.mfaCode)
            return Response(status: .ok)
        }.openAPI(
            summary: "Validate MFA registration",
            description: "Validate the MFA code to finalize MFA account registration. Once this process is complete, your account will be enabled with MFA."
        )
        
        group.post("mfa") { req in
            // Verify the session (to ensure credentials are correct), but do not verify MFA challenge. That's what is being done right now.
            let authUser = try await verifyAccess(cookie: req, verifyMfaChallenge: false)
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

        /// Verify a user's account creation code.
        ///
        /// - Returns: `View` which may be an error or success page.
        @Sendable
        func verifyCode(_ req: Request, code: String?) async throws -> View {
            guard let code else {
                return try await req.view.render(
                    "account/verify",
                    AccountForm.AccountCode(error: "A verification code must be provided.")
                )
            }

            do {
                let user = try await api.account.verifyAccountCode(code: code)

                return try await req.view.render(
                    "account/verified",
                    AccountForm.AccountVerified( email: user.email)
                )
            }
            catch is api.error.InvalidVerificationCode {
                return try await req.view.render(
                    "account/verify",
                    AccountForm.AccountCode(error: "The code provided is invalid. Please try again.")
                )
            }
        }

        group.get("verify") { req async throws -> View in
            let form = try req.query.decode(AccountForm.AccountVerify.self)
            return try await verifyCode(req, code: form.code)
        }.openAPI(
            summary: "Verify an @ys account.",
            query: .type(AccountForm.AccountVerify.self)
        )

        group.post("verify") { req async throws -> View in
            let form = try req.content.decode(AccountForm.AccountVerify.self)
            return try await verifyCode(req, code: form.code)
        }.openAPI(
            summary: "Verify an @ys account.",
            body: .type(AccountForm.AccountVerify.self),
            contentType: .application(.urlEncoded)
        )

        group.post("signin") { (req: Request) async throws -> Response in
            let form = try req.content.decode(AccountForm.SignIn.self)
            do {
                let user = try await api.account.verifyCredentials(email: form.email, password: form.password)
                
                let session = try await api.account.makeUserSession(user: user, requireMfaChallenge: user.mfaEnabled)
                
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
            _ = try await verifyAccess(cookie: req)
            let fragment = Fragment.RefreshUser()
            return fragment
        }.openAPI(
            summary: "Refresh user session",
            description: "Refresh a user session for another \(Global.maxAllowableInactivityInMinutes) minutes",
            response: .type(Fragment.RefreshUser.self),
            responseContentType: .application(.json)
        )

        group.post("setcookie", ":org_path") { (req: Request) async throws -> Response in
            guard let orgPath = req.parameters.get("node_path") else {
                throw api.error.InvalidAccountInfo(field: .orgPath)
            }
            return req.redirect(to: "/node/graph/\(orgPath)")
        }
        
        group.get("signout") { req in
            // Eventually I should use the session?
            // req.session.destroy()
            let auth = try await verifyAccess(cookie: req)
            try await api.account.signOut(user: auth)
            
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
        
        // MARK: User
        
        group.get("user") { req in
            do {
                let auth = try await verifyAccess(cookie: req)
                let fragment = Fragment.GetUser(user: auth.user.makeUser())
                return fragment
            }
            catch {
                let fragment = Fragment.GetUser(user: nil)
                return fragment
            }
        }.openAPI(
            summary: "Retreive currently signed in BOSS user",
            description: "This is used primarily by private services to validate that a user is signed in.",
            response: .type(Fragment.User.self),
            responseContentType: .application(.json)
        )

        group.get("users") { req async throws in
            let auth = try await verifyAccess(cookie: req)
            let users = try await api.account.users(user: auth)
            let fragment = Fragment.GetUsers(
                users: users.map { Fragment.Option(id: $0.id, name: $0.email) }
            )
            return fragment
        }.openAPI(
            summary: "Return all BOSS users",
            contentType: .application(.json),
            response: .type(Fragment.GetUsers.self),
            responseContentType: .application(.json)
        )
        
        group.get("user", ":userID") { req in
            let auth = try await verifyAccess(cookie: req)
            let userID = req.parameters.get("userID")
            let user = try await api.account.user(auth: auth, id: .require(userID))
            let fragment = Fragment.GetUser(
                user: user.makeUser()
            )
            return fragment
        }.openAPI(
            summary: "Load user",
            response: .type(Fragment.User.self),
            responseContentType: .application(.json)
        )
        
        group.post("user") { req in
            let auth = try await verifyAccess(cookie: req)
            let form = try req.content.decode(AccountForm.User.self)
            let user = try await api.account.saveUser(
                user: auth,
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
        
        group.delete("user", ":userID") { req in
            let auth = try await verifyAccess(cookie: req)
            let userID = req.parameters.get("userID")
            try await api.account.deleteUser(auth: auth, id: .require(userID))
            return Fragment.DeleteUser()
        }.openAPI(
            summary: "Delete a user",
            response: .type(Fragment.DeleteUser.self),
            responseContentType: .application(.json)
        )
        
        group.post("recover-account") { req in
            let form = try req.content.decode(AccountForm.RecoverAccount.self)
            // TODO: Send e-mail if account exists in system
            return Fragment.RecoverAccount()
        }.openAPI(
            summary: "Save user",
            response: .type(Fragment.RecoverAccount.self),
            responseContentType: .application(.json)
        )
    }
}

/// Make cookie used to store user session.
private func makeSessionCookieResponse(user: User, session: UserSession) throws -> Response {
    let cookie = HTTPCookies.Value(
        string: session.accessToken,
        expires: session.jwt.expiration.value,
        isSecure: false,
        isHTTPOnly: true,
        sameSite: HTTPCookies.SameSitePolicy.none
    )
    
    let response = Response(status: .ok)
    response.cookies["accessToken"] = cookie
    response.headers.contentType = .json
    try response.content.encode(Fragment.SignIn.init(user: user.makeUser(), error: nil))
    return response
}
