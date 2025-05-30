/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation
import XCTest

@testable import bosslib

final class accountTests: XCTestCase {
    override func setUpWithError() throws {
        try super.setUpWithError()
        boss.reset()
    }

    func testSuperUser() throws {
        let admin = superUser()
        XCTAssertTrue(admin.isSuperUser)
        XCTAssertFalse(admin.isGuestUser)
        let guest = guestUser()
        XCTAssertFalse(guest.isSuperUser)
        XCTAssertTrue(guest.isGuestUser)
        let actual = AuthenticatedUser(user: .fake(id: 3), peer: "192.168.0.1")
        XCTAssertFalse(actual.isSuperUser)
        XCTAssertFalse(actual.isGuestUser)
    }

    func testCreateUser() async throws {
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

        let user = try await api.account.saveUser(user: superUser(), id: nil, email: "test@example.com", password: "Password1!", fullName: "Eric", verified: false, enabled: true)

        let expectedUser = User.fake(id: 3, fullName: "Eric", email: "test@example.com", password: "Password1!", verified: false, enabled: true)
        XCTAssertEqual(user, expectedUser)
    }

    func testCreateAccount() async throws {
        // when: admin account is not provided
        await XCTAssertError(
            try await api.account.createAccount(admin: guestUser(), fullName: nil, email: nil, password: nil, verified: true),
            api.error.AdminRequired()
        )

        // when: user failed to be created
        api.account._createUser = { _, _, _, _, _, _, _ in
            throw GenericError("Failed to create user")
        }
        await XCTAssertError(
            try await api.account.createAccount(admin: superUser(), fullName: "Eric", email: "eric@example", password: "Password1!", verified: false),
            GenericError("Failed to create user")
        )

        // when: user is created successfully
        var eric = User(id: 2, system: .ays, fullName: "Eric", email: "test@example.com", password: "Password1!", verified: false, enabled: true)
        api.account._createUser = { _, _, _, _, _, _, _ in
            eric
        }

        api.account._updateUser = { _, _, user in
            eric
        }

        // when: user is NOT verified
        api.account._sendVerificationCode = { _, _ in
            "verify"
        }
        var (user, code) = try await api.account.createAccount(admin: superUser(), fullName: "Eric", email: "test@example", password: "Password1!", verified: false)

        // it: should create the user
        XCTAssertEqual(user, eric)
        // it: should provide a code
        XCTAssertEqual(code, "verify")

        // when: user is verified
        (user, code) = try await api.account.createAccount(admin: superUser(), fullName: "Eric", email: "test@example", password: "Password1!", verified: true)

        // it: should not send email and generate code
        XCTAssertNil(code)
    }

    func testVerifyAccountCode() async throws {
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
        var expectedUser = User.fake(fullName: "Eric", email: "test@example.com", password: "Password1!", verified: false, enabled: true)
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

    func testVerifyAccessToken() async throws {
        try await boss.start(storage: .memory)

        let u = try await api.account.saveUser(user: superUser(), id: nil, email: "eric@example", password: "Password1!", fullName: "Eric", verified: true, enabled: true)
        let (_ /* user */, _ /* session */) = try await api.account.signIn(email: u.email, password: "Password1!")

        api.reset()
        boss.reset()

        // when: access token is valid when value is `access`
        let expectedJWT = BOSSJWT(
            id: .init(value: "id"),
            issuedAt: .init(value: .now),
            subject: .init(value: "subject"),
            expiration: .init(value: .now)
        )
        api.account._internalVerifyAccessToken = { token, refreshToken in
            guard token == "access" else {
                throw api.error.InvalidJWT()
            }
            return expectedJWT
        }

        // when: access token is invalid
        await XCTAssertError(
            try await api.account.verifyAccessToken("invalid"),
            api.error.InvalidJWT()
        )

        // when: token is not found in database
        service.user._session = { _, _ in
            throw service.error.RecordNotFound()
        }
        await XCTAssertError(
            try await api.account.verifyAccessToken("access"),
            api.error.InvalidJWT()
        )

        // when: access token is valid
        service.user._session = { _, _ in
            ShallowUserSession(tokenId: "token", accessToken: "access")
        }

        let session = try await api.account.verifyAccessToken("access")
        XCTAssertEqual(session.jwt, expectedJWT)
    }

    func testSignIn_integration() async throws {
        try await boss.start(storage: .memory)

        let u = try await api.account.saveUser(user: superUser(), id: nil, email: "eric@example", password: "Password1!", fullName: "Eric", verified: true, enabled: true)
        let (_, session) = try await api.account.signIn(email: u.email, password: "Password1!")
        _ = try await api.account.verifyAccessToken(session.accessToken)
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
}
