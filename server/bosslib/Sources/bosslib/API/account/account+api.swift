/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation
import JWTKit

extension api {
    public nonisolated(unsafe) internal(set) static var account = AccountAPI()
}

private actor SessionStore {
    private var sessionInMemoryMap: [UserID: Date] = [:]
    
    func updateSession(for userID: UserID, date: Date) {
        sessionInMemoryMap[userID] = date
    }
    
    func getSessionDate(for userID: UserID) -> Date? {
        sessionInMemoryMap[userID]
    }
}

private let sessionStore = SessionStore()

public struct BOSSJWT: JWTPayload, Equatable {
    enum CodingKeys: String, CodingKey {
        /// TokenID
        case id = "id"
        case issuedAt = "iat"
        /// User.id
        case subject = "sub"
        case expiration = "exp"
    }

    public var id: IDClaim
    public var issuedAt: IssuedAtClaim
    public var subject: SubjectClaim
    public var expiration: ExpirationClaim

    public func verify(using signer: JWTKit.JWTSigner) throws {
        try self.expiration.verifyNotExpired()
    }
}

final public class AccountAPI: Sendable {
    nonisolated(unsafe) var _superUser: () -> AuthenticatedUser
    nonisolated(unsafe) var _guestUser: () -> AuthenticatedUser
    nonisolated(unsafe) var _users: (Database.Session, AuthenticatedUser) async throws -> [User]
    nonisolated(unsafe) var _createAccount: (Database.Session, AuthenticatedUser, String?, String?, String?, Bool) async throws -> (User, VerificationCode?)
    nonisolated(unsafe) var _createUser: (Database.Session, AuthenticatedUser, String?, String?, String?, Bool, Bool) async throws -> User
    nonisolated(unsafe) var _saveUser: (Database.Session, AuthenticatedUser, UserID?, String?, String?, String?, Bool, Bool) async throws -> User
    nonisolated(unsafe) var _updateUser: (Database.Session, AuthenticatedUser, User) async throws -> User
    nonisolated(unsafe) var _deleteUser: (Database.Session, AuthenticatedUser, UserID) async throws -> Void
    
    nonisolated(unsafe) var _sendVerificationCode: (Database.Session, User) async throws -> String
    nonisolated(unsafe) var _userWithID: (Database.Session, AuthenticatedUser, UserID) async throws -> User

    nonisolated(unsafe) var _signIn: (Database.Session, String?, String?) async throws -> (User, UserSession)
    nonisolated(unsafe) var _verifyAccountCode: (Database.Session, VerificationCode?) async throws -> User
    nonisolated(unsafe) var _verifyAccessToken: (Database.Session, AccessToken?, Bool) async throws -> UserSession
    nonisolated(unsafe) var _internalVerifyAccessToken: (AccessToken, Bool) async throws -> BOSSJWT
    nonisolated(unsafe) var _registerSlackCode: (Database.Session, String?) async throws -> String
    nonisolated(unsafe) var _signOut: (Database.Session, AuthenticatedUser) async throws -> Void

    init() {
        self._superUser = bosslib.superUser
        self._guestUser = bosslib.guestUser
        self._users = bosslib.users
        self._createAccount = bosslib.createAccount
        self._createUser = bosslib.createUser
        self._updateUser = bosslib.updateUser
        self._deleteUser = bosslib.deleteUser
        self._saveUser = bosslib.saveUser
        self._userWithID = bosslib.user
        self._signIn = bosslib.signIn
        self._verifyAccountCode = bosslib.verifyAccountCode
        self._verifyAccessToken = bosslib.verifyAccessToken
        self._internalVerifyAccessToken = bosslib.verifyAccessToken(_:refreshToken:)
        self._registerSlackCode = bosslib.registerSlackCode
        self._sendVerificationCode = bosslib.sendVerificationCode
        self._signOut = bosslib.signOut
    }

    public func superUser() -> AuthenticatedUser {
        _superUser()
    }

    public func guestUser() -> AuthenticatedUser {
        _guestUser()
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
        try await _users(session, user)
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
        try await _createAccount(session, admin, fullName, email, password, verified)
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
        try await _createUser(session, admin, email, password, fullName, verified, enabled)
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
        try await _saveUser(session, user, id, email, password, fullName, verified, enabled)
    }
    
    public func updateUser(
        session: Database.Session = Database.session(),
        auth: AuthenticatedUser,
        user: User
    ) async throws -> User {
        try await _updateUser(session, auth, user)
    }
    
    public func deleteUser(
        session: Database.Session = Database.session(),
        auth: AuthenticatedUser,
        id: UserID
    ) async throws {
        try await _deleteUser(session, auth, id)
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
        try await _userWithID(session, auth, id)
    }

    public func signIn(
        session: Database.Session = Database.session(),
        email: String?,
        password: String?
    ) async throws -> (User, UserSession) {
        try await _signIn(session, email, password)
    }

    public func sendVerificationCode(
        session: Database.Session = Database.session(),
        to user: User
    ) async throws -> VerificationCode {
        try await _sendVerificationCode(session, user)
    }

    public func verifyAccountCode(
        session: Database.Session = Database.session(),
        code: VerificationCode?
    ) async throws -> User {
        try await _verifyAccountCode(session, code)
    }

    /// Verify an access token.
    ///
    /// - Parameter accessToken: The access token to compare
    /// - Throws: If token has expired or inactivity detected
    public func verifyAccessToken(
        session: Database.Session = Database.session(),
        _ accessToken: AccessToken?,
        refreshToken: Bool = false
    ) async throws -> UserSession {
        try await _verifyAccessToken(session, accessToken, refreshToken)
    }

    public func registerSlackCode(
        session: Database.Session = Database.session(),
        _ code: String?
    ) async throws -> String {
        try await _registerSlackCode(session, code)
    }
    
    public func signOut(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser
    ) async throws -> Void {
        try await _signOut(session, user)
    }
}

/// Return super user who can perform system-level actions.
///
/// - Returns: Admin user
func superUser() -> AuthenticatedUser {
    .init(
        user: .init(
            id: Global.superUserId,
            system: .ays,
            fullName: "Admin",
            email: "bitheadrl@protonmail.com",
            password: "",
            verified: true,
            enabled: true,
            mfaEnabled: false,
            totpSecret: nil
        ),
        peer: nil
    )
}

func guestUser() -> AuthenticatedUser {
    .init(
        user: .init(
            id: Global.guestUserId,
            system: .ays,
            fullName: "Guest",
            email: "Guest",
            password: "",
            verified: true,
            enabled: true,
            mfaEnabled: false,
            totpSecret: nil
        ),
        peer: nil
    )
}

private func users(session: Database.Session, user: AuthenticatedUser) async throws -> [User] {
    let conn = try await session.conn()
    if user.isSuperUser {
        return try await service.user.users(conn: conn)
    }
    let user = try await service.user.user(conn: conn, id: user.user.id)
    return [user]
}

func createAccount(
    session: Database.Session,
    admin: AuthenticatedUser,
    fullName: String?,
    email: String?,
    password: String?,
    verified: Bool
) async throws -> (User, VerificationCode?) {
    guard admin.isSuperUser else {
        throw api.error.AdminRequired()
    }

    let conn = try await session.conn()

    try await conn.begin()
    var user = try await api.account.createUser(
        session: session,
        admin: admin,
        email: email,
        password:  password,
        fullName: fullName,
        verified: verified,
        enabled: true
    )
    user = try await api.account.updateUser(session: session, auth: admin, user: user)
    try await conn.commit()

    var code: VerificationCode?
    if !verified {
        code = try await api.account.sendVerificationCode(session: session, to: user)
    }

    return (user, code)
}

private func saveUser(
    session: Database.Session,
    user: AuthenticatedUser,
    id: UserID?,
    email: String?,
    password: String?,
    fullName: String?,
    verified: Bool,
    enabled: Bool
) async throws -> User {
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
        return try await api.account.updateUser(session: session, auth: user, user: u)
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

private func createUser(
    session: Database.Session,
    admin: AuthenticatedUser,
    email: String?,
    password: String?,
    fullName: String?,
    verified: Bool,
    enabled: Bool
) async throws -> User {
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
        system: .ays,
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

private func updateUser(
    session: Database.Session,
    auth: AuthenticatedUser,
    user: User
) async throws -> User {
    guard user.id == auth.user.id || auth.isSuperUser else {
        throw api.error.AccessDenied()
    }
    
    // TODO: Not tested
    let conn = try await session.conn()
    try await conn.begin()
    let user = try await service.user.updateUser(conn: conn, user: user)
    try await conn.commit()
    return user
}

private func deleteUser(
    session: Database.Session,
    auth: AuthenticatedUser,
    id: UserID
) async throws {
    guard auth.isSuperUser else {
        throw api.error.AccessDenied()
    }
    
    // TODO: Not tested
    let conn = try await session.conn()
    try await conn.begin()
    try await service.user.deleteUser(conn: conn, id: id)
    try await conn.commit()
}

private func user(
    session: Database.Session,
    auth: AuthenticatedUser,
    id: UserID
) async throws -> User {
    guard auth.user.id == id || auth.isSuperUser else {
        throw api.error.AccessDenied()
    }
    
    let conn = try await session.conn()
    let user = try await service.user.user(conn: conn, id: id)
    return user
}

private func signIn(
    session: Database.Session,
    email: String?,
    password: String?
) async throws -> (User, UserSession) {
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

    let signer = JWTSigner.hs256(key: boss.config.hmacKey)

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
    
    await sessionStore.updateSession(for: user.id, date: Date.now)

    let jwt = BOSSJWT(
        id: .init(value: tokenID),
        issuedAt: .init(value: .now),
        subject: .init(value: String(user.id)),
        expiration: .init(value: .now.addingTimeInterval(Global.sessionTimeoutInSeconds))
    )
    let accessToken = try signer.sign(jwt)

    let userSession = UserSession(tokenId: tokenID, accessToken: accessToken, jwt: jwt)
    try await call(
        await service.user.createSession(conn: conn, userSession: userSession),
        api.error.FailedToCreateJWT()
    )

    return (user, userSession)
}

private func verifyAccessToken(
    _ accessToken: AccessToken,
    refreshToken: Bool
) async throws -> BOSSJWT {
    // https://jwt.io/ - Verify JWTs
    let signer = JWTSigner.hs256(key: boss.config.hmacKey)
    let jwt = try await call(
        signer.verify(accessToken, as: BOSSJWT.self),
        api.error.InvalidJWT()
    )
    guard let userId = UserID(jwt.subject.value) else {
        throw api.error.InvalidJWT()
    }
    guard let lastTrackedInput = await sessionStore.getSessionDate(for: userId) else {
        throw api.error.UserNotFoundInSessionStore()
    }
    let currentDate = Date.now
    let difference = Calendar.current.dateComponents([.minute], from: lastTrackedInput, to: currentDate).minute ?? 0
    if difference > Global.maxAllowableInactivityInMinutes {
        throw api.error.UserSessionExpiredDueToInactivity()
    }
    
    // Some contexts only want to verify the access token and do NOT want to refresh the token, such as heartbeats -- when checking if the server is running and the user is signed in.
    if (refreshToken) {
        await sessionStore.updateSession(for: userId, date: Date.now)
    }
    
    return jwt
}

private func verifyAccessToken(
    session: Database.Session,
    accessToken: AccessToken?,
    refreshToken: Bool
) async throws -> UserSession {
    guard let accessToken else {
        throw api.error.InvalidJWT()
    }
    
    // https://jwt.io/ - Verify JWTs
    let jwt = try await api.account._internalVerifyAccessToken(accessToken, refreshToken)

    let conn = try await session.conn()
    try await call(
        await service.user.session(conn: conn, tokenID: jwt.id.value),
        api.error.InvalidJWT()
    )

    return .init(tokenId: jwt.id.value, accessToken: accessToken, jwt: jwt)
}

private func sendVerificationCode(
    session: Database.Session,
    to user: User
) async throws -> VerificationCode {
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

/// Verify an account code used to verify a new user's email address.
///
/// - Parameter code: System provided code to verify user.
/// - Throws: `ays.error.InvalidVerificationCode`
private func verifyAccountCode(
    session: Database.Session = Database.session(),
    code: VerificationCode?
) async throws -> User {
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

/// Register a Slack account with token provided by Slack.
///
/// The code returned from this must be entered into @ys.
///
/// TODO: Automatically associate the account with code. This would make Slack registration a one-step process.
///
/// - Parameter code: Code provided by Slack
/// - Returns: A code a user will register in their @ys account
private func registerSlackCode(
    session: Database.Session = Database.session(),
    code: String?
) async throws -> String {
    guard let code else {
        throw api.error.InvalidSlackCode()
    }

    // TODO: Stage Slack registration code so that it can be associated to the respective @ys account.
    return "fake-code"
}

private func signOut(session: Database.Session, User: AuthenticatedUser) async throws -> Void {
    // TODO: Delete session from database
}

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
