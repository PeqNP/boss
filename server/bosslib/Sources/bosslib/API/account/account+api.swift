/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation

extension api {
    public nonisolated(unsafe) internal(set) static var account = AccountAPI(provider: AccountService())
    public nonisolated(unsafe) internal(set) static var sessionStore = SessionStoreAPI()
}

protocol AccountProvider {
    func users(session: Database.Session, user: AuthenticatedUser) async throws -> [User]
    func createAccount(session: Database.Session, admin: AuthenticatedUser, fullName: String?, email: String?, password: String?, verified: Bool) async throws -> (User, VerificationCode?)
    func createUser(session: Database.Session, admin: AuthenticatedUser, email: String?, password: String?, fullName: String?, verified: Bool, enabled: Bool) async throws -> User
    func saveUser(session: Database.Session, user: AuthenticatedUser, id: UserID?, email: String?, password: String?, fullName: String?, verified: Bool, enabled: Bool) async throws -> User
    func updateUser(session: Database.Session, auth: AuthenticatedUser, user: User) async throws -> User
    func deleteUser(session: Database.Session, auth: AuthenticatedUser, id: UserID) async throws
    func generateTotpSecret(session: Database.Session, authUser: AuthenticatedUser, user: User) async throws -> (TOTPSecret, URL)
    func registerMfa(session: Database.Session, authUser: AuthenticatedUser, code: MFACode?) async throws -> User
    func user(session: Database.Session, auth: AuthenticatedUser, id: UserID) async throws -> User
    func signIn(session: Database.Session, email: String?, password: String?) async throws -> (User, UserSession)
    func verifyCredentials(session: Database.Session, email: String?, password: String?) async throws -> User
    func verifyMfa(session: Database.Session, authUser: AuthenticatedUser, code: String?) async throws
    func makeUserSession(session: Database.Session, user: User) async throws -> UserSession
    func sendVerificationCode(session: Database.Session, to user: User) async throws -> VerificationCode
    func verifyAccountCode(session: Database.Session, code: VerificationCode?) async throws -> User
    func verifyAccessToken(session: Database.Session, _ accessToken: AccessToken?, refreshToken: Bool, verifyMfaChallenge: Bool) async throws -> UserSession
    func registerSlackCode(session: Database.Session, _ code: String?) async throws -> String
    func signOut(session: Database.Session, user: AuthenticatedUser) async throws
    func createAccountRecoveryEmail(session: Database.Session, email: String?) async throws -> AccountRecoveryEmail
    func recoverAccount(session: Database.Session, code: String?) async throws
}

public actor SessionStoreAPI {
    struct State {
        let date: Date
        let passedMfaChallenge: Bool
    }
    
    private var sessionInMemoryMap: [UserID: State] = [:]
    
    func updateSession(for userId: UserID, state: State) {
        sessionInMemoryMap[userId] = state
    }
    
    func getSessionDate(for userId: UserID) -> State? {
        sessionInMemoryMap[userId]
    }
    
    func deleteSession(for userId: UserID) {
        sessionInMemoryMap.removeValue(forKey: userId)
    }
}

public func superUser() -> AuthenticatedUser {
    .init(
        user: .init(
            id: Global.superUserId,
            system: .boss,
            fullName: "Admin",
            email: "bitheadrl@protonmail.com",
            password: "",
            verified: true,
            enabled: true,
            mfaEnabled: false,
            totpSecret: nil
        ),
        session: .makeSystemUserSession(for: Global.superUserId),
        peer: nil
    )
}

public func guestUser() -> AuthenticatedUser {
    .init(
        user: .init(
            id: Global.guestUserId,
            system: .boss,
            fullName: "Guest",
            email: "Guest",
            password: "",
            verified: true,
            enabled: true,
            mfaEnabled: false,
            totpSecret: nil
        ),
        session: .makeSystemUserSession(for: Global.guestUserId),
        peer: nil
    )
}

final public class AccountAPI {
    let p: AccountProvider

    init(provider: AccountProvider) {
        self.p = provider
    }
    
    /// Returns all users in BOSS system.
    ///
    /// - Parameter session:
    /// - Parameter user:
    /// - Returns: All users, if user is admin. Otherwise, returns the current user only.
    public func users(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser
    ) async throws -> [User] {
        try await p.users(session: session, user: user)
    }

    /// Create a new user account.
    ///
    /// - Parameters:
    ///   - admin: Admin user
    ///   - orgPath: New org path to associate to user
    ///   - email: User's email
    ///   - password: Password
    ///   - verified: `true` if the user should be auto-verified
    /// - Returns: The new org `Node` and `User`
    /// - Throws: `BOSSError`
    public func createAccount(
        session: Database.Session = Database.session(),
        admin: AuthenticatedUser,
        fullName: String?,
        email: String?,
        password: String?,
        verified: Bool
    ) async throws -> (User, VerificationCode?) {
        try await p.createAccount(session: session, admin: admin, fullName: fullName, email: email, password: password, verified: verified)
    }
    
    /// Create new user account.
    ///
    /// - Note: Currently only admins can create new accounts.
    public func createUser(
        session: Database.Session = Database.session(),
        admin: AuthenticatedUser,
        email: String?,
        password: String?,
        fullName: String?,
        verified: Bool,
        enabled: Bool
    ) async throws -> User {
        try await p.createUser(session: session, admin: admin, email: email, password: password, fullName: fullName, verified: verified, enabled: enabled)
    }

    /// Create or update a user.
    ///
    /// - Note: This is designed for web requests
    public func saveUser(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        id: UserID?,
        email: String?,
        password: String?,
        fullName: String?,
        verified: Bool,
        enabled: Bool
    ) async throws -> User {
        try await p.saveUser(session: session, user: user, id: id, email: email, password: password, fullName: fullName, verified: verified, enabled: enabled)
    }
    
    /// Update a user.
    public func updateUser(
        session: Database.Session = Database.session(),
        auth: AuthenticatedUser,
        user: User
    ) async throws -> User {
        try await p.updateUser(session: session, auth: auth, user: user)
    }
    
    /// Delete a user.
    public func deleteUser(
        session: Database.Session = Database.session(),
        auth: AuthenticatedUser,
        id: UserID
    ) async throws {
        try await p.deleteUser(session: session, auth: auth, id: id)
    }
    
    /// Generate a TOTP secret used to generate OTP passwords.
    ///
    /// When enabling MFA, it is assumed that the secret will be created, tested, and then saved to the user's account.
    ///
    /// Only the User who owns the account may enable MFA. If a User is created with a process that does not require the registration of MFA, then there _will_ be a gap. In that scenario, admins are encouraged to disable the account. In the future, admins will be able to set MFA as enabled -- which will trigger the user to setup MFA before they sign in next.
    ///
    /// - Returns: TOTP secret as URL `otpauth://totp/BOSS:<email>?secret=<secret>`
    public func generateTotpSecret(
        session: Database.Session = Database.session(),
        authUser: AuthenticatedUser,
        user: User
    ) async throws -> (TOTPSecret, URL) {
        try await p.generateTotpSecret(session: session, authUser: authUser, user: user)
    }

    /// Finalize registration of enabling MFA on user's account.
    ///
    /// - Parameter authUser: The user requesting to enable MFA on account
    /// - Parameter code: The MFA code produced by password app/system, given a TOTP secret
    public func registerMfa(
        session: Database.Session = Database.session(),
        authUser: AuthenticatedUser,
        code: MFACode?
    ) async throws -> User {
        try await p.registerMfa(session: session, authUser: authUser, code: code)
    }

    /// Returns a `User` given a `UserID`.
    ///
    /// - Parameter session: Database session
    /// - Parameter userID: The `UserID` to query with
    /// - Throws: If `User` is not `enabled`, `verified`, or not found in database
    public func user(
        session: Database.Session = Database.session(),
        auth: AuthenticatedUser,
        id: UserID
    ) async throws -> User {
        try await p.user(session: session, auth: auth, id: id)
    }
    
    /// Sign in user.
    ///
    /// This will fail if user has MFA enabled.
    ///
    /// - Parameter email: User's e-mail address
    /// - Parameter password: User's password
    /// - Returns: User account new session
    /// - Throws: If user credentials are invalid
    public func signIn(
        session: Database.Session = Database.session(),
        email: String?,
        password: String?
    ) async throws -> (User, UserSession) {
        try await p.signIn(session: session, email: email, password: password)
    }
    
    /// Verify credentials before attempting to sign in.
    ///
    /// This is typically used during MFA to verify that the user is valid, before generating a MFA password.
    ///
    /// - Parameter email: User's e-mail address
    /// - Parameter password: User's password
    /// - Returns: User account
    /// - Throws: If user credentials are invalid
    public func verifyCredentials(
        session: Database.Session = Database.session(),
        email: String?,
        password: String?
    ) async throws -> User {
        try await p.verifyCredentials(session: session, email: email, password: password)
    }

    /// Verify MFA code.
    ///
    /// - Parameters:
    ///   - session: Database session
    ///   - mfaCode: If user has MFA code enabled, this value will be checked
    /// - Throws: If user credentials, or MFA code, are invalid.
    public func verifyMfa(
        session: Database.Session = Database.session(),
        authUser: AuthenticatedUser,
        code: String?
    ) async throws {
        try await p.verifyMfa(session: session, authUser: authUser, code: code)
    }
    
    /// Create a user session for a given user.
    ///
    /// - Parameters:
    ///   - session: Database session
    ///   - user: User to create a new session for
    /// - Throws: If session could not be created
    public func makeUserSession(
        session: Database.Session = Database.session(),
        user: User
    ) async throws -> UserSession {
        try await p.makeUserSession(session: session, user: user)
    }

    /// Send a verification code to user's e-mail.
    public func sendVerificationCode(
        session: Database.Session = Database.session(),
        to user: User
    ) async throws -> VerificationCode {
        try await p.sendVerificationCode(session: session, to: user)
    }

    /// Verify a user's account using the code sent to user's e-mail.
    public func verifyAccountCode(
        session: Database.Session = Database.session(),
        code: VerificationCode?
    ) async throws -> User {
        try await p.verifyAccountCode(session: session, code: code)
    }

    /// Verify an access token.
    ///
    /// - Parameter accessToken: The access token to compare
    /// - Throws: If token has expired or inactivity detected
    public func verifyAccessToken(
        session: Database.Session = Database.session(),
        _ accessToken: AccessToken?,
        refreshToken: Bool = false,
        verifyMfaChallenge: Bool = true
    ) async throws -> UserSession {
        try await p.verifyAccessToken(session: session, accessToken, refreshToken: refreshToken, verifyMfaChallenge: verifyMfaChallenge)
    }

    /// Register Slack code.
    public func registerSlackCode(
        session: Database.Session = Database.session(),
        _ code: String?
    ) async throws -> String {
        try await p.registerSlackCode(session: session, code)
    }
    
    /// Sign user out of the system.
    ///
    /// This destroys the session.
    public func signOut(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser
    ) async throws {
        try await p.signOut(session: session, user: user)
    }
    
    public func createAccountRecoveryEmail(
        session: Database.Session = Database.session(),
        email: String?
    ) async throws -> AccountRecoveryEmail {
        try await p.createAccountRecoveryEmail(session: session, email: email)
    }
    
    public func recoverAccount(
        session: Database.Session = Database.session(),
        code: String?
    ) async throws {
        try await p.recoverAccount(session: session, code: code)
    }
}

private extension UserSession {
    static func makeSystemUserSession(for userId: UserID) -> UserSession {
        .init(
            tokenId: "SYSTEM",
            accessToken: "SYTEM",
            jwt: .init(
                id: .init(value: "SYSTEM"),
                issuedAt: .init(value: .now),
                subject: .init(value: String(userId)),
                // Immediately expires
                expiration: .init(value: .now.addingTimeInterval(0))
            )
        )
    }
}
