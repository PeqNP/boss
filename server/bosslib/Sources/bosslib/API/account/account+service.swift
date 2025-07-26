/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation
import JWTKit
import SwiftOTP

private func validateEmail(_ email: String?) throws -> String {
    let email = try stringValue(email, field: .email)
    let parts = email.split(separator: "@")
    guard parts.count == 2 else {
        throw api.error.InvalidAccountInfo(field: .email)
    }
    return email
}

private func validateFullName(_ fullName: String?) throws -> String {
    try stringValue(fullName, field: .fullName)
}

private func validatePassword(_ password: String?) throws -> String {
    try stringValue(password, field: .password)
}

struct AccountService: AccountProvider {
    func users(session: Database.Session, user: AuthenticatedUser) async throws -> [User] {
        let conn = try await session.conn()
        if user.isSuperUser {
            return try await service.user.users(conn: conn)
        }
        let user = try await service.user.user(conn: conn, id: user.user.id)
        return [user]
    }
    
    func createAccount(session: Database.Session, admin: AuthenticatedUser, fullName: String?, email: String?, password: String?, verified: Bool) async throws -> (User, VerificationCode?) {
        guard admin.isSuperUser else {
            throw api.error.AdminRequired()
        }

        let conn = try await session.conn()

        try await conn.begin()
        var user = try await createUser(
            session: session,
            admin: admin,
            email: email,
            password:  password,
            fullName: fullName,
            verified: verified,
            enabled: true
        )
        user = try await updateUser(session: session, auth: admin, user: user)
        try await conn.commit()

        var code: VerificationCode?
        if !verified {
            code = try await sendVerificationCode(session: session, to: user)
        }

        return (user, code)
    }
    
    func createUser(session: Database.Session, admin: AuthenticatedUser, email: String?, password: String?, fullName: String?, verified: Bool, enabled: Bool) async throws -> User {
        guard admin.isSuperUser else {
            throw api.error.AdminRequired()
        }

        let email = try validateEmail(email)
        let password = try validatePassword(password)
        let fullName = try validateFullName(fullName)

        let conn = try await session.conn()

        if let user = try? await service.user.user(conn: conn, email: email) {
            if user.verified {
                throw GenericError("This user is already verified. If you need your username, org, password, or wish to use to use this same email address with a different organization, please call \(Global.phoneNumber).")
            }
            else {
                throw GenericError("This user is not verified. To verify your account, please call \(Global.phoneNumber).")
            }
        }

        try await conn.begin()
        let user = try await service.user.createUser(
            conn: conn,
            system: .boss,
            email: email,
            password: Bcrypt.hash(password),
            fullName: fullName,
            verified: verified,
            enabled: enabled
        )
        try await conn.commit()

        boss.log.i("Created new user ID (\(user.id)) email (\(email))")
        return user
    }
    
    func saveUser(session: Database.Session, user: AuthenticatedUser, id: UserID?, email: String?, password: String?, fullName: String?, verified: Bool, enabled: Bool) async throws -> User {
        let conn = try await session.conn()
        if let id {
            guard let fullName else {
                throw api.error.InvalidParameter(name: "fullName")
            }
            
            var u = try await service.user.user(conn: conn, id: id)
            if let email = stringValue(email) {
                u.email = email
            }
            if let password = stringValue(password) {
                u.password = try Bcrypt.hash(password)
            }
            u.fullName = fullName
            u.verified = verified
            u.enabled = enabled
            return try await updateUser(session: session, auth: user, user: u)
        }
        else {
            return try await createUser(
                session: session,
                admin: user,
                email: email,
                password: password,
                fullName: fullName,
                verified: verified,
                enabled: enabled
            )
        }
    }
    
    func updateUser(session: Database.Session, auth: AuthenticatedUser, user: User) async throws -> User {
        guard user.id == auth.user.id || auth.isSuperUser else {
            throw api.error.AccessDenied()
        }
        if user.mfaEnabled {
            guard user.totpSecret != nil else {
                throw api.error.TOTPSecretRequired()
            }
        }
        
        // TODO: Not tested
        let conn = try await session.conn()
        try await conn.begin()
        let user = try await service.user.updateUser(conn: conn, user: user)
        try await conn.commit()
        return user
    }
    
    func deleteUser(session: Database.Session, auth: AuthenticatedUser, id: UserID) async throws {
        guard auth.isSuperUser else {
            throw api.error.AccessDenied()
        }
        
        // TODO: Not tested
        let conn = try await session.conn()
        try await conn.begin()
        try await service.user.deleteUser(conn: conn, id: id)
        try await conn.commit()
    }
    
    func generateTotpSecret(session: Database.Session, authUser: AuthenticatedUser, user: User) async throws -> (TOTPSecret, URL) {
        guard authUser.user.id == user.id else {
            throw api.error.TOTPError("You must be the user to generate a new TOTP secret")
        }
        
        // Generate 20 byte random secret
        var generator = SystemRandomNumberGenerator()
        let bytes = [UInt8].random(count: 20, using: &generator)
        let secretData = Data(bytes)
        let base32secret = base32Encode(secretData)
        
        // Save the TOTP secret to temporary table
        // Do NOT enable MFA. This allows the secret to be tested against before enabling. It also allows the TOTP to be regenerated, if needed.
        let conn = try await session.conn()
        try await service.user.createMfa(conn: conn, user: user, totpSecret: base32secret)
        
        guard let otpauthUrl = URL(string: "otpauth://totp/BOSS:\(user.email)?secret=\(base32secret)") else {
            throw api.error.TOTPError("Failed to generate OTP auth URL")
        }
        
        return (base32secret, otpauthUrl)
    }
    
    func registerMfa(session: Database.Session, authUser: AuthenticatedUser, code: MFACode?) async throws -> User {
        guard let code else {
            throw api.error.RequiredParameter("MFA Code")
        }
        
        let conn = try await session.conn()
        try await conn.begin()
        let mfa = try await service.user.mfa(conn: conn, user: authUser.user)
        guard let data = base32DecodeToData(mfa.secret) else {
            try await service.user.deleteMfa(conn: conn, user: authUser.user)
            throw api.error.TOTPError("Failed to decode MFA secret. Retry enabling MFA on this account.")
        }
        
        let totp = TOTP(secret: data, digits: 6, timeInterval: 30, algorithm: .sha1)
        let generatedCode = totp?.generate(time: .now)
        guard code == generatedCode else {
            throw api.error.InvalidMFA()
        }
        
        try await service.user.deleteMfa(conn: conn, user: authUser.user)
        var user = authUser.user
        user.mfaEnabled = true
        user.totpSecret = mfa.secret
        user = try await service.user.updateUser(conn: conn, user: user)
        try await conn.commit()
        
        return user
    }
    
    func user(session: Database.Session, auth: AuthenticatedUser, id: UserID) async throws -> User {
        guard auth.user.id == id || auth.isSuperUser else {
            throw api.error.AccessDenied()
        }
        
        let conn = try await session.conn()
        let user = try await service.user.user(conn: conn, id: id)
        return user
    }
    
    func signIn(session: Database.Session, email: String?, password: String?) async throws -> (User, UserSession) {
        let user = try await verifyCredentials(session: session, email: email, password: password)
        guard !user.mfaEnabled else {
            throw api.error.MFARequired()
        }
        
        let session = try await makeUserSession(session: session, user: user)
        return (user, session)
    }
    
    func verifyCredentials(session: Database.Session, email: String?, password: String?) async throws -> User {
        let email = try validateEmail(email)
        let password = try stringValue(password, field: .password)

        let conn = try await session.conn()
        let user = try await call(
            await service.user.user(conn: conn, email: email),
            api.error.UserNotFound()
        )

        let matches = try Bcrypt.verify(password, created: user.password)
        guard matches else {
            throw api.error.UserNotFound()
        }

        guard user.verified else {
            throw api.error.UserIsNotVerified()
        }
        guard user.enabled else {
            throw api.error.UserNotFound()
        }

        return user
    }
    
    func verifyMfa(session: Database.Session, authUser: AuthenticatedUser, code: String?) async throws {
        guard let code else {
            throw api.error.RequiredParameter("MFA code")
        }
        
        let user = authUser.user
        guard user.mfaEnabled else {
            throw api.error.MFANotEnabled()
        }
        guard let totpSecret = user.totpSecret else {
            throw api.error.MFANotConfigured()
        }
        guard let state = await api.sessionStore.getSessionDate(for: user.id) else {
            throw api.error.UserNotFoundInSessionStore()
        }
        
        guard let data = base32DecodeToData(totpSecret) else {
            throw api.error.TOTPError("Failed to decode MFA secret. Retry enabling MFA on this account.")
        }
        
        let totp = TOTP(secret: data, digits: 6, timeInterval: 30, algorithm: .sha1)
        let generatedCode = totp?.generate(time: .now)
        guard code == generatedCode else {
            throw api.error.InvalidMFA()
        }
        
        // Update that user passed MFA challenge
        await api.sessionStore.updateSession(
            for: user.id,
            state: .init(date: state.date, passedMfaChallenge: true)
        )
    }
    
    func makeUserSession(session: Database.Session, user: User) async throws -> UserSession {
        let conn = try await session.conn()
            
        // Try to create new session token ID 3 times
        var tokenID: TokenID = makeTokenID()
        var exists: Bool = true
        for i in 0...2 {
            if try await service.user.sessionExists(conn: conn, tokenID: tokenID) == false {
                exists = false
                break
            }
            boss.log.w("Failed to create JWT attempt (\(i)) using token ID (\(tokenID))")
            tokenID = makeTokenID()
        }
        guard !exists else {
            throw api.error.FailedToCreateJWT()
        }
        
        await api.sessionStore.updateSession(
            for: user.id,
            state: .init(date: Date.now, passedMfaChallenge: !user.mfaEnabled)
        )

        let jwt = BOSSJWT(
            id: .init(value: tokenID),
            issuedAt: .init(value: .now),
            subject: .init(value: String(user.id)),
            expiration: .init(value: .now.addingTimeInterval(Global.sessionTimeoutInSeconds))
        )
        let accessToken = try api.signer.sign(jwt)

        let userSession = UserSession(tokenId: tokenID, accessToken: accessToken, jwt: jwt)
        try await call(
            await service.user.createSession(conn: conn, userSession: userSession),
            api.error.FailedToCreateJWT()
        )

        return userSession
    }
    
    func sendVerificationCode(session: Database.Session, to user: User) async throws -> VerificationCode {
        let code = makeVerificationCode()
        let conn = try await session.conn()
        try await conn.begin()
        try await call(
            await service.user.createUserVerification(conn: conn, user: user, code: code),
            api.error.FailedToSendVerificationCode()
        )
        try await conn.commit()

        boss.log.i("Sent code (\(code)) to email (\(user.email))")

        return code
    }
    
    func verifyAccountCode(session: Database.Session, code: VerificationCode?) async throws -> User {
        let code = try stringValue(code, error: api.error.InvalidVerificationCode())

        let conn = try await session.conn()
        let uv = try await call(
            await service.user.userVerification(conn: conn, code: code),
            api.error.FailedToVerifyAccountCode()
        )

        var user = try await call(
            await service.user.user(conn: conn, id: uv.userID),
            api.error.UserNotFound()
        )

        guard !user.verified else {
            throw api.error.UserIsVerified()
        }

        // TODO: the `peer` needs to be set
        user.verified = true
        let verifiedUser = try await service.user.updateUser(conn: conn, user: user)

        return verifiedUser
    }
    
    private func verifyAccessToken(
        _ accessToken: AccessToken,
        refreshToken: Bool,
        verifyMfaChallenge: Bool
    ) async throws -> BOSSJWT {
        let jwt = try await call(
            api.signer.verify(accessToken),
            api.error.InvalidJWT()
        )
        guard let userId = UserID(jwt.subject.value) else {
            throw api.error.InvalidJWT()
        }
        guard let state = await api.sessionStore.getSessionDate(for: userId) else {
            throw api.error.UserNotFoundInSessionStore()
        }
        if verifyMfaChallenge && !state.passedMfaChallenge {
            throw api.error.MFANotVerified()
        }
        let currentDate = Date.now
        let difference = Calendar.current.dateComponents([.minute], from: state.date, to: currentDate).minute ?? 0
        if difference > Global.maxAllowableInactivityInMinutes {
            throw api.error.UserSessionExpiredDueToInactivity()
        }
        
        // Some contexts only want to verify the access token and do NOT want to refresh the token, such as heartbeats -- when checking if the server is running and the user is signed in.
        if refreshToken {
            await api.sessionStore.updateSession(
                for: userId,
                state: .init(date: Date.now, passedMfaChallenge: state.passedMfaChallenge)
            )
        }
        
        return jwt
    }
    
    func verifyAccessToken(session: Database.Session, _ accessToken: AccessToken?, refreshToken: Bool, verifyMfaChallenge: Bool) async throws -> UserSession {
        guard let accessToken else {
            throw api.error.InvalidJWT()
        }
        
        // https://jwt.io/ - Verify JWTs
        let jwt = try await verifyAccessToken(accessToken, refreshToken: refreshToken, verifyMfaChallenge: verifyMfaChallenge)

        let conn = try await session.conn()
        try await call(
            await service.user.session(conn: conn, tokenID: jwt.id.value),
            api.error.InvalidJWT()
        )

        return .init(tokenId: jwt.id.value, accessToken: accessToken, jwt: jwt)
    }
    
    func registerSlackCode(session: Database.Session, _ code: String?) async throws -> String {
        guard let code else {
            throw api.error.InvalidSlackCode()
        }

        // TODO: Stage Slack registration code so that it can be associated to the respective @ys account.
        return "fake-code"
    }
    
    func signOut(session: Database.Session, user: AuthenticatedUser) async throws {
        do {
            let conn = try await session.conn()
            try await service.user.deleteSession(conn: conn, tokenID: user.session.tokenId)
        }
        catch {
            boss.log.w("Attempting to sign out of a session that does not exist")
        }
        
        await api.sessionStore.deleteSession(for: user.user.id)
    }
    
    func createAccountRecoveryEmail(session: Database.Session, email: String?) async throws -> SystemEmail {
        guard let email else {
            throw api.error.InvalidParameter(name: "email")
        }
        
        let conn = try await session.conn()
        // User must exist with email
        let user = try await service.user.user(conn: conn, email: email)
        let existingRecoveryCode = try? await service.user.accountRecoveryCode(conn: conn, email: email)
        if existingRecoveryCode != nil {
            throw api.error.AccountRecoveryInProgress()
        }
        
        let code = makeVerificationCode()
        _ = try await service.user.createAccountRecoveryCode(conn: conn, email: email, code: code)
        
        let body = """
            Hello, \(user.fullName).
            
            Your account recovery code: \(code)
            
            If you did not request a password reset code, please ignore this request.
            
            Regards,
            Bithead team
            """
        return .init(
            email: email,
            name: user.fullName,
            subject: "Account recovery code",
            body: body,
            code: code
        )
    }
    
    func recoverAccount(session: Database.Session, code: String?, password: String?) async throws -> User {
        guard let code else {
            throw api.error.InvalidParameter(name: "code")
        }
        let password = try Bcrypt.hash(validatePassword(password))

        let conn = try await session.conn()
        try await conn.begin()
        let recoveryCode = try await service.user.accountRecoveryCode(conn: conn, code: code)
        if recoveryCode.recovered {
            throw api.error.AccountAlreadyRecovered()
        }
        guard recoveryCode.expirationDate > Date.now else {
            throw api.error.AccountRecoveryCodeExpired()
        }
        
        try await service.user.recoverAccount(conn: conn, code: code)
        
        let user = try await service.user.user(conn: conn, email: recoveryCode.email)
        let updatedUser = with(user) { o in
            o.password = password
        }
        _ = try await service.user.updateUser(conn: conn, user: updatedUser)
        
        try await conn.commit()
        
        return updatedUser
    }
}
