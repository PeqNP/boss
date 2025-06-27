/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation
import SwiftOTP
import XCTest

@testable import bosslib

final class accountTests: XCTestCase {
    func testSuperUser() throws {
        let admin = superUser()
        XCTAssertTrue(admin.isSuperUser)
        XCTAssertFalse(admin.isGuestUser)
        let guest = guestUser()
        XCTAssertFalse(guest.isSuperUser)
        XCTAssertTrue(guest.isGuestUser)
        let actual = AuthenticatedUser(user: .fake(id: 3), session: .fake(), peer: "192.168.0.1")
        XCTAssertFalse(actual.isSuperUser)
        XCTAssertFalse(actual.isGuestUser)
    }

    func testCreateUser() async throws {
        try await boss.start(storage: .memory)
        
        // describe: create user
        // when: admin account is not provided
        await XCTAssertError(
            try await api.account.saveUser(user: guestUser(), id: nil, email: nil, password: nil, fullName: nil, verified: true, enabled: true),
            api.error.AdminRequired()
        )

        // when: no email is provided
        await XCTAssertError(
            try await api.account.saveUser(user: superUser(), id: nil, email: nil, password: nil, fullName: nil, verified: false, enabled: true),
            api.error.InvalidAccountInfo(field: .email)
        )

        // when: email does not have two parts
        await XCTAssertError(
            try await api.account.saveUser(user: superUser(), id: nil, email: "eric", password: nil, fullName: nil, verified: false, enabled: true),
            api.error.InvalidAccountInfo(field: .email)
        )

        // when: password is not provided
        await XCTAssertError(
            try await api.account.saveUser(user: superUser(), id: nil, email: "test@example.com", password: nil, fullName: nil, verified: false, enabled: true),
            api.error.InvalidAccountInfo(field: .password)
        )
        await XCTAssertError(
            try await api.account.saveUser(user: superUser(), id: nil, email: "test@example.com", password: "   ", fullName: nil, verified: false, enabled: true),
            api.error.InvalidAccountInfo(field: .password)
        )

        // when: full name is not provided
        await XCTAssertError(
            try await api.account.saveUser(user: superUser(), id: nil, email: "test@example.com", password: "pass", fullName: nil, verified: true, enabled: true),
            api.error.InvalidAccountInfo(field: .fullName)
        )
        await XCTAssertError(
            try await api.account.saveUser(user: superUser(), id: nil, email: "test@example.com", password: "pass", fullName: "", verified: true, enabled: true),
            api.error.InvalidAccountInfo(field: .fullName)
        )

        // when: the user already has an account; user is NOT verified
        service.user._userWithEmail = { (conn, email) -> User in
            .fake(verified: false)
        }
        await XCTAssertError(
            try await api.account.saveUser(user: superUser(), id: nil, email: "eric@example", password: "Password1!", fullName: "Eric", verified: false, enabled: true),
            GenericError("This user is not verified. To verify your account, please call \(Global.phoneNumber).")
        )

        // when: the user already has an account; user is verified
        service.user._userWithEmail = { (conn, email) -> User in
            .fake(verified: true)
        }
        await XCTAssertError(
            try await api.account.saveUser(user: superUser(), id: nil, email: "eric@example", password: "Password1!", fullName: "Eric", verified: false, enabled: true),
            GenericError("This user is already verified. If you need your username, org, password, or wish to use to use this same email address with a different organization, please call \(Global.phoneNumber).")
        )

        // when: user does not exist
        service.user._userWithEmail = { (conn, email) -> User in
            throw GenericError()
        }

        // when: failed to create user
        service.user._createUser = { _, _, _, _, _, _, _ -> User in
            throw GenericError("User error")
        }
        await XCTAssertError(
            try await api.account.saveUser(user: superUser(), id: nil, email: "eric@example", password: "Password1!", fullName: "Eric", verified: false, enabled: true),
            GenericError("User error")
        )

        // when: user is created successfully
        let expectedUser = User.fake(id: 3, fullName: "Eric", email: "test@example.com", password: "Password1!", verified: false, enabled: true)
        service.user._createUser = { _, _, _, _, _, _, _ -> User in
            expectedUser
        }
        let user = try await api.account.saveUser(user: superUser(), id: nil, email: "eric@example", password: "Password1!", fullName: "Eric", verified: false, enabled: true)

        XCTAssertEqual(user, expectedUser)
    }

    func testCreateUser_integration() async throws {
        try await boss.start(storage: .memory)

        var user = try await api.account.saveUser(user: superUser(), id: nil, email: "test@example.com", password: "Password1!", fullName: "Eric", verified: false, enabled: true)

        var expectedUser = User.fake(id: 3, fullName: "Eric", email: "test@example.com", password: "Password1!", verified: false, enabled: true)
        XCTAssertEqual(user, expectedUser)
        
        // describe: Enable MFA
        user.mfaEnabled = true
        
        // when: TOTP secret is not provided
        await XCTAssertError(
            try await api.account.updateUser(auth: superUser(), user: user),
            api.error.TOTPSecretRequired()
        )
        
        // when: TOTP secret is provided
        user.totpSecret = "TEST"
        user = try await api.account.updateUser(auth: superUser(), user: user)
        
        // it: should save MFA
        expectedUser.mfaEnabled = true
        expectedUser.totpSecret = "TEST"
        XCTAssertEqual(user, expectedUser)
    }
    
    func testCreateAccount() async throws {
        try await boss.start(storage: .memory)
        
        // when: admin account is not provided
        await XCTAssertError(
            try await api.account.createAccount(admin: guestUser(), fullName: nil, email: nil, password: nil, verified: true),
            api.error.AdminRequired()
        )

        // describe: create non-verified user
        var (user, code) = try await api.account.createAccount(admin: superUser(), fullName: "Eric", email: "test@example.com", password: "Password1!", verified: false)

        // it: should create the user
        let eric = User(id: 3, system: .boss, fullName: "Eric", email: "test@example.com", password: "Password1!", verified: false, enabled: true, mfaEnabled: false, totpSecret: nil)
        XCTAssertEqual(user, eric)
        // it: should provide verification code
        XCTAssertEqual(code?.count, 6)

        // describe: verify account code
        let u = try await api.account.verifyAccountCode(code: code)
        let updatedUser = with(user) { o in
            o.verified = true
        }
        // it: should update the user's verification status
        XCTAssertEqual(u, updatedUser)

        // describe: create verified user
        (user, code) = try await api.account.createAccount(admin: superUser(), fullName: "Eric", email: "test2@example.com", password: "Password1!", verified: true)

        // it: should not send email and generate code
        XCTAssertNil(code)
    }

    func testVerifyAccountCode() async throws {
        try await boss.start(storage: .memory)
        
        // when: code input is invalid
        await XCTAssertError(
            try await api.account.verifyAccountCode(code: nil),
            api.error.InvalidVerificationCode()
        )

        // when: code can not be found
        service.user._userVerification = { _, _ in
            throw service.error.RecordNotFound()
        }
        await XCTAssertError(
            try await api.account.verifyAccountCode(code: "code"),
            api.error.FailedToVerifyAccountCode()
        )

        // when: user is not found
        service.user._userVerification = { _, _ in
            UserVerification(userID: 1)
        }
        service.user._userWithID = { _, _ in
            throw service.error.RecordNotFound()
        }
        await XCTAssertError(
            try await api.account.verifyAccountCode(code: "code"),
            api.error.UserNotFound()
        )

        // when: user exists; user is already verified
        var expectedUser = User.fake(id: 1, verified: true)
        service.user._userWithID = { _, _ in
            expectedUser
        }
        await XCTAssertError(
            try await api.account.verifyAccountCode(code: "code"),
            api.error.UserIsVerified()
        )

        expectedUser.verified = false
        service.user._userWithID = { _, _ in
            expectedUser
        }

        // when: user fails to update
        service.user._updateUser = { _, _ in
            throw service.error.FailedToSave(User.self)
        }
        await XCTAssertError(
            try await api.account.verifyAccountCode(code: "code"),
            service.error.FailedToSave(User.self)
        )

        service.user._updateUser = { _, _ in
            expectedUser
        }

        // when: verification is successful
        var verifiedUser = expectedUser
        verifiedUser.verified = true
        service.user._updateUser = { _, _ in
            verifiedUser
        }
        let user = try await api.account.verifyAccountCode(code: "code")
        // it: should verify the user
        XCTAssertEqual(user, verifiedUser)
    }
    
    func test_sendVerificationCode() async throws {
        service.user._createUserVerification = { _, _, _ in
            throw GenericError("Failed")
        }
        let user = User.fake(email: "test@example.com")
        await XCTAssertError(
            try await api.account.sendVerificationCode(to: user),
            api.error.FailedToSendVerificationCode()
        )

        service.user._createUserVerification = { _, _, _ in }
        let code = try await api.account.sendVerificationCode(to: user)
        // it: should return 6 digit alpha-numeric code
        XCTAssertEqual(code.count, 6)
    }
    
    func test_mfa() async throws {
        try await boss.start(storage: .memory)
        
        let superUser = superUser()
        let user = User.fake(
            id: 10,
            email: "test@example.com",
            password: try Bcrypt.hash("Password1!"),
            verified: true,
            enabled: true
        )
        var session = UserSession.fake()
        var authUser = AuthenticatedUser(user: user, session: session, peer: "localhost")
        
        // describe: verify user mfa code; user is not registered for mfa
        
        // context: MFA code is not provided
        await XCTAssertError(
            try await api.account.verifyMfa(authUser: authUser, code: nil),
            api.error.RequiredParameter("MFA code")
        )
        await XCTAssertError(
            try await api.account.verifyMfa(authUser: authUser, code: "000"),
            api.error.MFANotEnabled()
        )
    
        // describe: update user w/o totp secret; mfa is enabled
        // NOTE: This should never happen. If MFA is enabled, a TOTP secret must be set at the same time.
        let tmpUser = User.fake(id: 10, email: "test@example.com", mfaEnabled: true)
        await XCTAssertError(
            try await api.account.updateUser(auth: authUser, user: tmpUser),
            api.error.TOTPSecretRequired()
        )
        
        // context: user has mfa enabled (somehow) but no totp secret exists on user
        let tmpAuthUser = AuthenticatedUser.fake(user: .fake(id: 10, mfaEnabled: true))
        await XCTAssertError(
            try await api.account.verifyMfa(authUser: tmpAuthUser, code: "000"),
            api.error.MFANotConfigured()
        )
        
        // describe: register for mfa
        
        // context: generate totp for different user
        await XCTAssertError(
            try await api.account.generateTotpSecret(authUser: superUser, user: user),
            api.error.TOTPError("You must be the user to generate a new TOTP secret")
        )
        
        // context: database failed to create mfa
        service.user._createMfa = { _, _, _ in
            throw GenericError("Failed to create MFA")
        }
        await XCTAssertError(
            try await api.account.generateTotpSecret(authUser: authUser, user: user),
            GenericError("Failed to create MFA")
        )
        
        // context: valid mfa code is provided
        service.user._createMfa = { _, _, _ in
            // no-op
        }
        let (totpSecret, url) = try await api.account.generateTotpSecret(authUser: authUser, user: user)
        XCTAssertEqual(url, URL(string: "otpauth://totp/BOSS:test@example.com?secret=\(totpSecret)"))
        
        // context: invalid mfa code provided
        await XCTAssertError(
            try await api.account.registerMfa(authUser: authUser, code: nil),
            api.error.RequiredParameter("MFA Code")
        )
        
        // context: totp secret was corrupt in database
        var deletedMfa = false
        service.user._deleteMfa = { _, _ in
            deletedMfa = true
        }
        service.user._mfa = { _, _ in
            TemporaryMFA(id: 1, createDate: .now, userId: user.id, secret: "8XYZ123")
        }
        await XCTAssertError(
            try await api.account.registerMfa(authUser: authUser, code: "123494"),
            api.error.TOTPError("Failed to decode MFA secret. Retry enabling MFA on this account.")
        )
        XCTAssertTrue(deletedMfa, "it: should attempt to delete invalid MFA code")
        
        deletedMfa = false
        
        // describe: MFA code does not match
        service.user._mfa = { _, _ in
            TemporaryMFA(id: 1, createDate: .now, userId: user.id, secret: totpSecret)
        }
        guard let data = base32DecodeToData(totpSecret) else {
            fatalError("Failed to decode TOTP secret")
        }
        await XCTAssertError(
            try await api.account.registerMfa(authUser: authUser, code: "000"),
            api.error.InvalidMFA()
        )
        XCTAssertFalse(deletedMfa)
                
        // describe: successfully register MFA
        service.user._updateUser = { _, u in
            u // return user provided
        }
        let totp = TOTP(secret: data, digits: 6, timeInterval: 30, algorithm: .sha1)
        let validCode = totp?.generate(time: .now)
        var validatedUser = try await api.account.registerMfa(authUser: authUser, code: validCode)
        XCTAssertEqual(validatedUser.totpSecret, totpSecret)
        XCTAssertTrue(validatedUser.mfaEnabled)
        XCTAssertTrue(deletedMfa, "it: should delete tmp MFA code record")
        
        authUser = AuthenticatedUser.fake(user: validatedUser)

        // describe: verify user
        
        // context: valid mfa code is provided; user has not been verified
        await XCTAssertError(
            try await api.account.verifyMfa(authUser: authUser, code: validCode),
            api.error.UserNotFoundInSessionStore()
        )
        
        service.user._userWithEmail = { _, _ in
            validatedUser
        }
        service.user._sessionExists = { _, _ in
            false
        }
        service.user._createSession = { _, s in
            // no-op
        }
        
        // context: invalid mfa code provided; user is verified
        validatedUser = try await api.account.verifyCredentials(email: user.email, password: "Password1!")
        session = try await api.account.makeUserSession(user: validatedUser)
        await XCTAssertError(
            try await api.account.verifyMfa(authUser: authUser, code: "000"),
            api.error.InvalidMFA()
        )

        // context: valid mfa code is provied
        try await api.account.verifyMfa(authUser: authUser, code: validCode)
    }

    func testCreateAccount_integration() async throws {
        try await boss.start(storage: .memory)

        let (user, code) = try await api.account.createAccount(
            admin: superUser(),
            fullName: "Eric",
            email: "test@example.com",
            password: "Password1!",
            verified: false
        )

        // it: should create the user
        var expectedUser = User.fake(
            fullName: "Eric",
            email: "test@example.com",
            password: "Password1!",
            verified: false,
            enabled: true
        )
        XCTAssertEqual(user, expectedUser)
        // it: should send an email w/ a 6 digit alpha-numeric code
        XCTAssertEqual(code?.count, 6)

        // when: account is verified
        let verifiedUser = try await api.account.verifyAccountCode(code: code)
        // it: should return the user's account and node
        expectedUser.verified = true
        XCTAssertEqual(verifiedUser, expectedUser)

        // when: user is queried from database
        let conn = try await Database.current.session().conn()
        let updatedUser = try await service.user.user(conn: conn, id: verifiedUser.id)
        // it: should have updated correctly
        XCTAssertEqual(updatedUser, verifiedUser)
    }

    func testSignIn() async throws {
        // when: email is invalid
        try await XCTAssertError(
            await api.account.signIn(email: nil, password: "Password1!"),
            api.error.InvalidAccountInfo(field: .email)
        )
        try await XCTAssertError(
            await api.account.signIn(email: " ", password: "Password1!"),
            api.error.InvalidAccountInfo(field: .email)
        )

        // when: password is invalid
        try await XCTAssertError(
            await api.account.signIn(email: "test@example.com", password: nil),
            api.error.InvalidAccountInfo(field: .password)
        )
        try await XCTAssertError(
            await api.account.signIn(email: "test@example.com", password: ""),
            api.error.InvalidAccountInfo(field: .password)
        )

        // when: user is not found
        service.user._userWithEmail = { _, _ in
            throw GenericError("User not found")
        }
        try await XCTAssertError(
            await api.account.signIn(email: "test@example.com", password: "Password1!"),
            api.error.UserNotFound()
        )

        // when: user exists in system; password is incorrect
        var expectedUser = User.fake(
            password: try Bcrypt.hash("Password1!")
        )
        service.user._userWithEmail = { _, _ in
            expectedUser
        }
        try await XCTAssertError(
            await api.account.signIn(email: "test@example.com", password: "Oops"),
            api.error.UserNotFound()
        )

        // when: user is NOT verified
        expectedUser = User.fake(
            password: try Bcrypt.hash("Password1!"),
            verified: false
        )
        try await XCTAssertError(
            await api.account.signIn(email: "test@example.com", password: "Password1!"),
            api.error.UserIsNotVerified()
        )

        // when: user is NOT enabled
        expectedUser = User.fake(
            password: try Bcrypt.hash("Password1!"),
            verified: true,
            enabled: false
        )
        try await XCTAssertError(
            await api.account.signIn(email: "test@example.com", password: "Password1!"),
            api.error.UserNotFound()
        )

        expectedUser = User.fake(
            password: try Bcrypt.hash("Password1!"),
            verified: true,
            enabled: true
        )

        // when: generated token already exists in database
        // it: should retry N times before stopping
        service.user._sessionExists = { _, _ in
            true
        }
        try await XCTAssertError(
            await api.account.signIn(email: "test@example.com", password: "Password1!"),
            api.error.FailedToCreateJWT()
        )

        // when: session does not exist
        service.user._sessionExists = { _, _ in false }

        // when: token fails to be written to database
        service.user._createSession = { _, _ in
            throw GenericError()
        }
        try await XCTAssertError(
            await api.account.signIn(email: "test@example.com", password: "Password1!"),
            api.error.FailedToCreateJWT()
        )

        // when: session is created successfully
        service.user._createSession = { _, _ in }

        // when: credentials are valid
        let (user, session) = try await api.account.signIn(email: "test@example.com", password: "Password1!")
        XCTAssertEqual(user, expectedUser)
        XCTAssertNotEqual(session.accessToken, "")
        XCTAssertNotEqual(session.tokenId, "")
    }

    func testVerifyAccessToken_mfaEnabled() async throws {
        try await boss.start(storage: .memory)

        let u = try await api.account.saveUser(
            user: superUser(),
            id: nil,
            email: "eric@example",
            password: "Password1!",
            fullName: "Eric",
            verified: true,
            enabled: true
        )

        let fake = FakeSignerProvider()
        api.signer = SignerAPI(p: fake)
        
        // context: invalid jwt provided
        fake._verify = { _ in
            throw GenericError("Invalid JWT")
        }
        await XCTAssertError(
            try await api.account.verifyAccessToken("invalid-token"),
            api.error.InvalidJWT()
        )
        
        // context: invalid user ID; valid token
        fake._verify = { _ in
            BOSSJWT(id: .init(value: "id"), issuedAt: .init(value: .now), subject: .init(value: "e"), expiration: .init(value: .now))
        }
        await XCTAssertError(
            try await api.account.verifyAccessToken("valid-token"),
            api.error.InvalidJWT()
        )
        
        // context: user does not have session
        fake._verify = { _ in
            BOSSJWT(id: .init(value: "id"), issuedAt: .init(value: .now), subject: .init(value: String(u.id)), expiration: .init(value: .now))
        }
        await XCTAssertError(
            try await api.account.verifyAccessToken("valid-token"),
            api.error.UserNotFoundInSessionStore()
        )
        
        // describe: start mfa registration
        
        // context: user registering for mfa is not the same user
        await XCTAssertError(
            try await api.account.generateTotpSecret(authUser: superUser(), user: u),
            api.error.TOTPError("You must be the user to generate a new TOTP secret")
        )
        
        // context: user is same user
        service.user._createMfa = { _, _, _ in  }
        var authUser = AuthenticatedUser(user: u, session: .fake(), peer: nil)
        let (totpSecret, totpUrl) = try await api.account.generateTotpSecret(authUser: authUser, user: u)
        XCTAssertEqual(totpUrl, URL(string: "otpauth://totp/BOSS:eric@example?secret=\(totpSecret)"))
        
        service.user._mfa = { _, _ in TemporaryMFA(id: 1, createDate: .now, userId: u.id, secret: totpSecret) }
        
        // describe: register for mfa
        
        // context: no mfa code provided
        await XCTAssertError(
            try await api.account.registerMfa(authUser: superUser(), code: nil),
            api.error.RequiredParameter("MFA Code")
        )
        
        // context: invalid mfa code
        await XCTAssertError(
            try await api.account.registerMfa(authUser: superUser(), code: "1234"),
            api.error.InvalidMFA()
        )
        
        // context: valid mfa code
        guard let data = base32DecodeToData(totpSecret) else {
            fatalError("Failed to decode TOTP secret")
        }
        let totp = TOTP(secret: data, digits: 6, timeInterval: 30, algorithm: .sha1)
        let code = totp?.generate(time: .now)
        
        service.user._deleteMfa = { _, _ in }
        _ = service.user._updateUser = { _, user in
            user
        }
        
        // describe: sign out
        // This is done to test the MFA challenge after signing in
        service.user._deleteSession = { _, _ in }
        var registeredUser = try await api.account.registerMfa(authUser: authUser, code: code)
        authUser = AuthenticatedUser(
            user: registeredUser,
            session: .fake(
                tokenId: "token",
                accessToken: "access-token",
                jwt: .init(
                    id: .init(value: "1111"),
                    issuedAt: .init(value: .now),
                    subject: .init(value: String(u.id)),
                    expiration: .init(value: .now)
                )),
            peer: nil
        )
        try await api.account.signOut(user: authUser)
        
        // describe: sign in and verify mfa token
        service.user._userWithEmail = { _, _ in
            registeredUser.password = u.password
            return registeredUser
        }
        service.user._sessionExists = { _, _ in false }
        fake._sign = { _ in "access-token" }
        service.user._createSession = { _, _ in }
        
        // NOTE: This is the "proper" way to sign in a user. Verify credentials, then create a user session.
        _ /* user */ = try await api.account.verifyCredentials(email: registeredUser.email, password: "Password1!")
        let session = try await api.account.makeUserSession(user: registeredUser)
        
        // context: user has not passed mfa challenge
        await XCTAssertError(
            try await api.account.verifyAccessToken("access-token", verifyMfaChallenge: true),
            api.error.MFANotVerified()
        )
        
        // context: user has not passed mfa challenge; do not verify mfa challenge
        // This is necessary when we need to verify the token but NOT verify MFA. The contexts are 1) when we're validating the MFA challenge 2) heartbeats
        service.user._session = { _, _ in session.makeShallowUserSession() }
        _ = try await api.account.verifyAccessToken("access-token", refreshToken: true, verifyMfaChallenge: false)
        
        // sanity: make sure the user is still requires verification
        await XCTAssertError(
            try await api.account.verifyAccessToken("access-token", verifyMfaChallenge: true),
            api.error.MFANotVerified()
        )
        
        // context: verify mfa challenge
        try await api.account.verifyMfa(authUser: authUser, code: code)
        // it: should verify token, even if challenged, as mfa has been verified
        _ = try await api.account.verifyAccessToken("access-token", verifyMfaChallenge: true)
    }
    
    /// testVerifyAccessToken_mfaEnabled performs most of verification tests. This is a simple set of tests that ensure non-MFA accounts still work.
    func testVerifyAccessToken() async throws {
        try await boss.start(storage: .memory)
        
        // FIXME: boss.start() should do this
        service.user = UserService(UserSQLiteService())
        
        // describe: create and sign in user
        let u = try await api.account.createUser(
            admin: superUser(),
            email: "eric@example",
            password: "Password1!",
            fullName: "Eric",
            verified: true,
            enabled: true
        )
        let (_ /* user */, session) = try await api.account.signIn(email: u.email, password: "Password1!")
        
        // NOTE: All internal verification logic has been already tested in MFA tests
        
        // describe: invalid token is provided
        await XCTAssertError(
            try await api.account.verifyAccessToken("invalid"),
            api.error.InvalidJWT()
        )
        
        // describe: token is valid; not found in database
        service.user._session = { _, _ in
            throw service.error.RecordNotFound()
        }
        await XCTAssertError(
            try await api.account.verifyAccessToken(session.accessToken),
            api.error.InvalidJWT()
        )

        // describe: access token is valid; found in database
        service.user._session = { _, _ in
            ShallowUserSession(tokenId: session.tokenId, accessToken: session.accessToken)
        }

        let _session = try await api.account.verifyAccessToken(session.accessToken)
        XCTAssertEqual(_session.makeShallowUserSession(), session.makeShallowUserSession())
    }

    func testSignIn_integration() async throws {
        try await boss.start(storage: .memory)

        // describe: create user
        let u = try await api.account.saveUser(
            user: superUser(),
            id: nil,
            email: "eric@example",
            password: "Password1!",
            fullName: "Eric",
            verified: true,
            enabled: true
        )
        
        // describe: sign in
         _ = try await api.account.verifyCredentials(email: u.email, password: "Password1!")
        var session = try await api.account.makeUserSession(user: u)
        _ = try await api.account.verifyAccessToken(session.accessToken)
        
        var authUser = AuthenticatedUser(user: u, session: session, peer: "localhost")

        // describe: register for mfa
        let (totpSecret, _) = try await api.account.generateTotpSecret(authUser: authUser, user: u)
        
        // describe: authenticate with mfa
        guard let data = base32DecodeToData(totpSecret) else {
            fatalError("Failed to decode TOTP secret")
        }
        let totp = TOTP(secret: data, digits: 6, timeInterval: 30, algorithm: .sha1)
        
        // describe: verify mfa
        let code = totp?.generate(time: .now)
        let registeredUser = try await api.account.registerMfa(authUser: authUser, code: code)
        XCTAssertEqual(code?.count, 6)
        XCTAssertEqual(registeredUser.totpSecret, totpSecret)
        XCTAssertTrue(registeredUser.mfaEnabled)
        
        // describe: Sign user out
        try await api.account.signOut(user: authUser)
        
        // it: should invalidate the session
        await XCTAssertError(
            _ = try await api.account.verifyAccessToken(session.accessToken),
            api.error.UserNotFoundInSessionStore()
        )
        
        let conn = try await Database.session().conn()
        let exists = try await service.user.sessionExists(conn: conn, tokenID: session.tokenId)
        XCTAssertFalse(exists)
        
        // describe: Sign in w/ MFA enabled
        _ = try await api.account.verifyCredentials(email: u.email, password: "Password1!")
        session = try await api.account.makeUserSession(user: u)
        authUser = AuthenticatedUser(user: registeredUser, session: session, peer: "localhost")
                
        try await api.account.verifyMfa(authUser: authUser, code: totp?.generate(time: .now))
    }
}

private extension bosslib.UserSession {
    func makeShallowUserSession() -> bosslib.ShallowUserSession {
        .init(tokenId: tokenId, accessToken: accessToken)
    }
}
