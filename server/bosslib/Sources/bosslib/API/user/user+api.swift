/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import Foundation

protocol UserProvider {
    func user(conn: Database.Connection, email: String) async throws -> User
    func user(conn: Database.Connection, id: UserID) async throws -> User
    func users(conn: Database.Connection) async throws -> [User]
    func createUser(conn: Database.Connection, system: AccountSystem, email: String, password: String, fullName: String, verified: Bool, enabled: Bool) async throws -> User
    func updateUser(conn: Database.Connection, user: User) async throws -> User
    func deleteUser(conn: Database.Connection, id: UserID) async throws -> Void
    
    func createMfa(conn: Database.Connection, user: User, totpSecret: String) async throws -> Void
    func mfa(conn: Database.Connection, user: User) async throws -> TemporaryMFA
    func deleteMfa(conn: Database.Connection, userId: UserID) async throws -> Void

    func createSession(conn: Database.Connection, userSession: UserSession) async throws
    func session(conn: Database.Connection, tokenID: TokenID) async throws -> ShallowUserSession
    func sessionExists(conn: Database.Connection, tokenID: TokenID) async throws -> Bool
    func deleteSession(conn: Database.Connection, tokenID: TokenID) async throws -> Void
    func createAccountRecoveryCode(conn: Database.Connection, email: String, code: String) async throws -> AccountRecoveryCode
    func accountRecoveryCode(conn: Database.Connection, code: String) async throws -> AccountRecoveryCode
    func accountRecoveryCode(conn: Database.Connection, email: String) async throws -> AccountRecoveryCode
    func recoverAccount(conn: Database.Connection, code: String) async throws -> Void
}

class UserAPI {
    var _userWithEmail: (Database.Connection, String) async throws -> User = { _, _ in fatalError("UserService.user(email:)") }
    var _userWithID: (Database.Connection, UserID) async throws -> User = { _, _ in fatalError("UserService.user(id:)") }
    var _users: (Database.Connection) async throws -> [User] = { _ in fatalError("UserService.users") }
    var _createUser: (Database.Connection, AccountSystem, String, String, String, Bool, Bool) async throws -> User = { _, _, _, _, _, _, _ in fatalError("UserService.createUser") }
    var _updateUser: (Database.Connection, User) async throws -> User = { _, _ in fatalError("UserService.updateUser") }
    var _deleteUser: (Database.Connection, UserID) async throws -> Void = { _, _ in fatalError("UserService.deleteUser") }
    
    var _createMfa: (Database.Connection, User, String) async throws -> Void = { _, _, _ in fatalError("UserService.createMfa") }
    var _mfa: (Database.Connection, User) async throws -> TemporaryMFA = { _, _ in fatalError("UserService.mfa") }
    var _deleteMfa: (Database.Connection, UserID) async throws -> Void = { _, _ in fatalError("UserService.deleteMfa") }

    var _createSession: (Database.Connection, UserSession) async throws -> Void = { _, _ in fatalError("UserService.createSession") }
    var _session: (Database.Connection, TokenID) async throws -> ShallowUserSession = { _, _ in fatalError("UserService.session") }
    var _sessionExists: (Database.Connection, TokenID) async throws -> Bool = { _ , _ in fatalError("UserService.sessionExists") }
    var _deleteSession: (Database.Connection, TokenID) async throws -> Void = { _ , _ in fatalError("UserService.deleteSession") }
    var _createAccountCode: (Database.Connection, String, String, String) async throws -> AccountRecoveryCode = { _, _, _, _ in fatalError("UserService.createAccountCode") }
    var _createAccountRecoveryCode: (Database.Connection, String, String) async throws -> AccountRecoveryCode = { _, _, _ in fatalError("UserService.createAccountRecoveryCode") }
    var _accountRecoveryCode: (Database.Connection, String) async throws -> AccountRecoveryCode = { _, _ in fatalError("UserService.accountRecoveryCode") }
    var _accountRecoveryCodeByEmail: (Database.Connection, String) async throws -> AccountRecoveryCode = { _, _ in fatalError("UserService.accountRecoveryCodeByEmail") }
    var _recoverAccount: (Database.Connection, String) async throws -> Void = { _, _ in fatalError("UserService.recoverAccount") }

    init() { }

    init(_ p: UserProvider) {
        self._userWithEmail = p.user(conn:email:)
        self._userWithID = p.user(conn:id:)
        self._users = p.users
        self._createUser = p.createUser
        self._updateUser = p.updateUser
        self._deleteUser = p.deleteUser
        
        self._createMfa = p.createMfa
        self._mfa = p.mfa
        self._deleteMfa = p.deleteMfa

        self._createSession = p.createSession
        self._session = p.session
        self._sessionExists = p.sessionExists
        self._deleteSession = p.deleteSession
        self._createAccountRecoveryCode = p.createAccountRecoveryCode
        self._accountRecoveryCode = p.accountRecoveryCode(conn:code:)
        self._accountRecoveryCodeByEmail = p.accountRecoveryCode(conn:email:)
        self._recoverAccount = p.recoverAccount
    }

    func user(conn: Database.Connection, email: String) async throws -> User {
        try await _userWithEmail(conn, email)
    }

    func user(conn: Database.Connection, id: UserID) async throws -> User {
        try await _userWithID(conn, id)
    }
    
    func users(conn: Database.Connection) async throws -> [User] {
        try await _users(conn)
    }

    func createUser(conn: Database.Connection, system: AccountSystem, email: String, password: String, fullName: String, verified: Bool, enabled: Bool) async throws -> User {
        try await _createUser(conn, system, email, password, fullName, verified, enabled)
    }

    func updateUser(conn: Database.Connection, user: User) async throws -> User {
        try await _updateUser(conn, user)
    }
    
    /// Delete user.
    ///
    /// WARNING: Depending on the systems this user had access to, this may delete important historical data that is dependent on this user if the `user_id` CASCADE was set to DELETE, rather han set to NULL. It is better to disable a user then delete them.
    ///
    /// - Parameter conn:
    /// - Parameter id: User ID
    func deleteUser(conn: Database.Connection, id: UserID) async throws {
        try await _deleteUser(conn, id)
    }

    func createSession(conn: Database.Connection, userSession: UserSession) async throws {
        try await _createSession(conn, userSession)
    }

    @discardableResult
    func session(conn: Database.Connection, tokenID: TokenID) async throws -> ShallowUserSession {
        try await _session(conn, tokenID)
    }

    func sessionExists(conn: Database.Connection, tokenID: TokenID) async throws -> Bool {
        try await _sessionExists(conn, tokenID)
    }
    
    func deleteSession(conn: Database.Connection, tokenID: TokenID) async throws -> Void {
        try await _deleteSession(conn, tokenID)
    }
    
    func createMfa(conn: Database.Connection, user: User, totpSecret: String) async throws {
        try await _createMfa(conn, user, totpSecret)
    }
    
    /// Returns most recent MFA registration challenge.
    ///
    /// - Parameter user: The user who has requested to be challenged for registration
    /// - Returns: Record that represents the temporary MFA challenge registration
    func mfa(conn: Database.Connection, user: User) async throws -> TemporaryMFA {
        try await _mfa(conn, user)
    }
    
    func deleteMfa(conn: Database.Connection, user: User) async throws {
        try await deleteMfa(conn: conn, userId: user.id)
    }
    
    func deleteMfa(conn: Database.Connection, userId: UserID) async throws {
        try await _deleteMfa(conn, userId)
    }
    
    /// Create a code used to recover an account.
    func createAccountRecoveryCode(conn: Database.Connection, email: String, code: String) async throws -> AccountRecoveryCode {
        try await _createAccountRecoveryCode(conn, email, code)
    }
    
    /// Returns the account recovery code record.
    ///
    /// Note: This will not return a code if the code expired or previously used.
    func accountRecoveryCode(conn: Database.Connection, code: String) async throws -> AccountRecoveryCode {
        try await _accountRecoveryCode(conn, code)
    }
    
    /// Returns the account recovery code record using e-mail.
    ///
    /// Note: This will not return a code if the code expired or previously used.
    func accountRecoveryCode(conn: Database.Connection, email: String) async throws -> AccountRecoveryCode {
        try await _accountRecoveryCodeByEmail(conn, email)
    }
    
    /// Set the account as being successfully recovered.
    ///
    /// - Note: This must be set in order for the code to not be used again in the future.
    /// - Note: This will not recover the account if code expired or previously used.
    func recoverAccount(conn: Database.Connection, code: String) async throws {
        try await _recoverAccount(conn, code)
    }
}
