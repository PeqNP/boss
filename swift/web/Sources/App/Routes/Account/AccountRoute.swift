/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import ayslib
import Foundation
import Vapor

/// Register the `/account/` routes.
public func registerAccount(_ app: Application) {
    app.group("account") { group in
        group.get { req async throws -> View in
            return try await req.view.render("account/index", AccountForm.Account.empty)
        }.openAPI(
            summary: "Begin the process of creating an @ys account."
        )
        
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
                let (_ /* node */, user, _ /* code */) = try await api.account.createAccount(
                    admin: admin,
                    fullName: form.fullname,
                    orgPath: form.orgpath,
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
                let (node, user) = try await api.account.verifyAccountCode(code: code)

                return try await req.view.render(
                    "account/verified",
                    AccountForm.AccountVerified(orgpath: node.path, email: user.email)
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
                let (_, session) = try await api.account.signIn(email: form.email, password: form.password)
                let cookie = HTTPCookies.Value(
                    string: session.accessToken,
                    expires: session.jwt.expiration.value,
                    isSecure: false,
                    isHTTPOnly: true,
                    sameSite: HTTPCookies.SameSitePolicy.none
                )
                // FIXME: Have to redirect in order to set cookies. Ideally this should not be necessary.
                let response = req.redirect(to: "/")
                response.cookies["accessToken"] = cookie
                return response
            } catch {
                let fragment = Fragment.SignIn(
                    error: "Failed to sign in. Please check your email and password."
                )
                let response = Response()
                response.status = .ok
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

        group.post("setcookie", ":org_path") { (req: Request) async throws -> Response in
            guard let orgPath = req.parameters.get("node_path") else {
                throw api.error.InvalidAccountInfo(field: .orgPath)
            }
            return req.redirect(to: "/node/graph/\(orgPath)")
        }
        
        group.get("signout") { req in
            // Eventually I should use the session?
            // req.session.destroy()
            let auth = try await verifyAccess(app: app, cookie: req)
            try await api.account.signOut(user: auth)
            
            // NOTE: Just like sign in, a redirect must occur in order for the headers to be written with lateest cookie info. There may be a world where a `DELETE` request is made and the client clears their cookie.
            let response = req.redirect(to: "/")
            response.cookies["accessToken"] = .init(string: "", expires: Date.distantPast, maxAge: 0)
            return response
        }.openAPI(
            summary: "Sign out from your Bithead OS account",
            description: "This will sign you out of your Bithead OS account and redirect to the home page."
        )
        
        // MARK: User
        
        group.get("user") { req in
            do {
                let auth = try await verifyAccess(app: app, cookie: req)
                let fragment = Fragment.User(user: auth.user)
                return fragment
            }
            catch {
                let fragment = Fragment.User(user: nil)
                return fragment
            }
        }.openAPI(
            summary: "Retreive currently signed in BOSS user",
            description: "This is used primarily by private services to validate that a user is signed in.",
            response: .type(Fragment.User.self),
            responseContentType: .application(.json)
        )

        group.get("users") { req async throws in
            let auth = try await verifyAccess(app: app, cookie: req)
            let users = try await api.account.users(user: auth)
            let fragment = Fragment.Users(
                users: users.map { Fragment.Option(id: $0.id, name: $0.email) }
            )
            return fragment
        }.openAPI(
            summary: "Return all BOSS users",
            contentType: .application(.json),
            response: .type(Fragment.Users.self),
            responseContentType: .application(.json)
        )
        
        group.get("user", ":userID") { req in
            let auth = try await verifyAccess(app: app, cookie: req)
            let userID = req.parameters.get("userID")
            let user = try await api.account.user(auth: auth, id: .require(userID))
            let fragment = Fragment.User(
                user: user
            )
            return fragment
        }.openAPI(
            summary: "Load user",
            response: .type(Fragment.User.self),
            responseContentType: .application(.json)
        )
        
        group.post("user") { req in
            let auth = try await verifyAccess(app: app, cookie: req)
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
            return Fragment.SaveUser(user: user)
        }.openAPI(
            summary: "Save user",
            response: .type(Fragment.SaveUser.self),
            responseContentType: .application(.json)
        )
        
        group.delete("user", ":userID") { req in
            let auth = try await verifyAccess(app: app, cookie: req)
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
