/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import CryptoKit
import Foundation
import JWTKit
import SwiftOTP

extension api {
    public nonisolated(unsafe) internal(set) static var account = AccountAPI()
}

private actor SessionStore {
    struct State {
        let date: Date
        let passedMfaChallenge: Bool?
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
    
    nonisolated(unsafe) var _generateTotpSecret: (Database.Session, User) async throws -> String
    nonisolated(unsafe) var _generateOtpPassword: (Database.Session, String) async throws -> String
    
    nonisolated(unsafe) var _sendVerificationCode: (Database.Session, User) async throws -> String
    nonisolated(unsafe) var _userWithID: (Database.Session, AuthenticatedUser, UserID) async throws -> User

    nonisolated(unsafe) var _verifyCredentials: (Database.Session, String?, String?) async throws -> User
    nonisolated(unsafe) var _verifyMfa: (Database.Session, User, String? /* MFA code */) async throws -> Void
    nonisolated(unsafe) var _makeUserSession: (Database.Session, User, Bool) async throws -> UserSession
    
    nonisolated(unsafe) var _verifyAccountCode: (Database.Session, VerificationCode?) async throws -> User
    nonisolated(unsafe) var _verifyAccessToken: (Database.Session, AccessToken?, Bool, Bool) async throws -> UserSession
    nonisolated(unsafe) var _internalVerifyAccessToken: (AccessToken, Bool, Bool) async throws -> BOSSJWT
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
        self._generateTotpSecret = bosslib.generateTotpSecret
        self._generateOtpPassword = bosslib.generateOtpPassword
        self._userWithID = bosslib.user
        self._verifyCredentials = bosslib.verifyCredentials
        self._verifyMfa = bosslib.verifyMfa
        self._verifyAccountCode = bosslib.verifyAccountCode
        self._makeUserSession = bosslib.makeUserSession
        self._verifyAccessToken = bosslib.verifyAccessToken
        self._internalVerifyAccessToken = bosslib.verifyAccessToken(_:refreshToken:verifyMfaChallenge:)
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
    
    /// Generate a TOTP secret used to generate OTP passwords.
    ///
    /// When enabling MFA, it is assumed that the secret will be created, tested, and then saved to the user's account.
    ///
    /// - Returns: TOTP secret as URL `otpauth://totp/BOSS:<email>?secret=<secret>`
    public func generateTotpSecret(
        session: Database.Session = Database.session(),
        user: User
    ) async throws -> String {
        try await _generateTotpSecret(session, user)
    }

    /// Generate a 6 digit OTP password, that expires in 30 seconds, from a TOTP secret.
    ///
    /// NOTE: The number of OTP digits and time interval is defined in `Global.otp`.
    ///
    /// - Parameter secret: The TOTP secret to generate a password from
    /// - Returns: OTP password
    public func generateOtpPassword(
        session: Database.Session = Database.session(),
        secret: String
    ) async throws -> String {
        try await _generateOtpPassword(session, secret)
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
        try await _verifyCredentials(session, email, password)
    }

    /// Sign in to a user's account.
    ///
    /// - Parameters:
    ///   - session: Database session
    ///   - mfaCode: If user has MFA code enabled, this value will be checked
    /// - Throws: If user credentials, or MFA code, are invalid.
    public func verifyMfa(
        session: Database.Session = Database.session(),
        user: User,
        mfaCode: String?
    ) async throws {
        try await _verifyMfa(session, user, mfaCode)
    }
    
    /// Create a user session for a given user.
    ///
    /// - Parameters:
    ///   - session: Database session
    ///   - user: User to create a new session for
    /// - Throws: If session could not be created
    public func makeUserSession(
        session: Database.Session = Database.session(),
        user: User,
        requireMfaChallenge: Bool
    ) async throws -> UserSession {
        try await _makeUserSession(session, user, requireMfaChallenge)
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
        refreshToken: Bool = false,
        verifyMfaChallenge: Bool = false
    ) async throws -> UserSession {
        try await _verifyAccessToken(session, accessToken, refreshToken, verifyMfaChallenge)
    }

    public func registerSlackCode(
        session: Database.Session = Database.session(),
        _ code: String?
    ) async throws -> String {
        try await _registerSlackCode(session, code)
    }
    
    /// Sign user out of the system.
    ///
    /// This destroys the session.
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

func guestUser() -> AuthenticatedUser {
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

private func updateUser(
    session: Database.Session,
    auth: AuthenticatedUser,
    user: User
) async throws -> User {
    guard user.id == auth.user.id || auth.isSuperUser else {
        throw api.error.AccessDenied()
    }
    guard user.mfaEnabled, user.totpSecret != nil else {
        throw api.error.TOTPSecretRequired()
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

private func generateTotpSecret(session: Database.Session, user: User) async throws -> String {
    // Generate 20 byte random secret
    var bytes = [UInt8](repeating: 0, count: 20)
    let result = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
    guard result == errSecSuccess else {
        throw api.error.TOTPError("Failed to generate random secret")
    }
    let secretData = Data(bytes)
    let base32Secret = base32Encode(secretData)
    
    // Save the TOTP secret to user's account.
    // Do NOT enable MFA. This allows the secret to be tested against before enabling. It also allows the TOTP to be regenerated, if needed.
    let conn = try await session.conn()
    var user = user
    user.mfaEnabled = false
    user.totpSecret = base32Secret
    _ = try await service.user.updateUser(conn: conn, user: user)
    
    let otpauthUrl = "otpauth://totp/BOSS:\(user.email)?secret=\(base32Secret)"
    return otpauthUrl
}

private func generateOtpPassword(session: Database.Session, secret: String) async throws -> String {
    guard let data: Data = secret.data(using: .utf8) else {
        throw api.error.TOTPError("Failed to decode secret")
    }
    guard let totp = TOTP(
        secret: data,
        digits: Global.otp.numDigits,
        timeInterval: Global.otp.expiresInSeconds,
        algorithm: .sha1
    ) else {
        throw api.error.TOTPError("Failed to initialize TOTP library")
    }
    guard let otp = totp.generate(time: Date()) else {
        throw api.error.TOTPError("Failed to OTP password")
    }
    return otp
}

private func verifyCredentials(
    session: Database.Session,
    email: String?,
    password: String?
) async throws -> User {
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

private func verifyMfa(
    session: Database.Session,
    user: User,
    mfaCode: String?
) async throws {
    let conn = try await session.conn()

    guard let mfaCode else {
        throw api.error.RequiredParameter("MFA code")
    }
    guard user.mfaEnabled else {
        throw api.error.MFANotEnabled()
    }
    guard let totpSecret = user.totpSecret else {
        throw api.error.MFANotConfigured()
    }
    
    // TODO: Validate MFA

    // Update that user passed MFA challenge
    guard let state = try await sessionStore.getSessionDate(for: user.id) else {
        throw api.error.UserNotFoundInSessionStore()
    }
    try await sessionStore.updateSession(
        for: user.id,
        state: .init(date: state.date, passedMfaChallenge: true)
    )
}

private func makeUserSession(
    session: Database.Session,
    user: User,
    requireMfaChallenge: Bool
) async throws -> UserSession {
    let conn = try await session.conn()
    
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
    
    await sessionStore.updateSession(for: user.id, state: .init(date: Date.now, passedMfaChallenge: !requireMfaChallenge))

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

    return userSession
}

private func verifyAccessToken(
    _ accessToken: AccessToken,
    refreshToken: Bool,
    verifyMfaChallenge: Bool
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
    guard let state = await sessionStore.getSessionDate(for: userId) else {
        throw api.error.UserNotFoundInSessionStore()
    }
    guard verifyMfaChallenge, state.passedMfaChallenge == false else {
        throw api.error.MFANotVerified()
    }
    let currentDate = Date.now
    let difference = Calendar.current.dateComponents([.minute], from: state.date, to: currentDate).minute ?? 0
    if difference > Global.maxAllowableInactivityInMinutes {
        throw api.error.UserSessionExpiredDueToInactivity()
    }
    
    // Some contexts only want to verify the access token and do NOT want to refresh the token, such as heartbeats -- when checking if the server is running and the user is signed in.
    if (refreshToken) {
        await sessionStore.updateSession(for: userId, state: .init(date: Date.now, passedMfaChallenge: nil))
    }
    
    return jwt
}

private func verifyAccessToken(
    session: Database.Session,
    accessToken: AccessToken?,
    refreshToken: Bool,
    verifyMfaChallenge: Bool
) async throws -> UserSession {
    guard let accessToken else {
        throw api.error.InvalidJWT()
    }
    
    // https://jwt.io/ - Verify JWTs
    let jwt = try await api.account._internalVerifyAccessToken(accessToken, refreshToken, verifyMfaChallenge)

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
/// - Throws: `api.error.InvalidVerificationCode`
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

private func signOut(session: Database.Session, user: AuthenticatedUser) async throws -> Void {
    do {
        let conn = try await session.conn()
        try await service.user.deleteSession(conn: conn, tokenID: user.session.tokenId)
    }
    catch {
        boss.log.w("Attempting to sign out of a session that does not exist")
    }
    
    await sessionStore.deleteSession(for: user.user.id)
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
