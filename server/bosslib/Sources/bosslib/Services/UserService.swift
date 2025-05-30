/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation
internal import SQLKit

protocol UserProvider {
    func user(conn: Database.Connection, email: String) async throws -> User
    func user(conn: Database.Connection, id: UserID) async throws -> User
    func users(conn: Database.Connection) async throws -> [User]
    func createUser(conn: Database.Connection, system: AccountSystem, email: String, password: String, fullName: String, verified: Bool, enabled: Bool) async throws -> User
    func createUserVerification(conn: Database.Connection, user: User, code: VerificationCode) async throws -> Void
    func userVerification(conn: Database.Connection, code: VerificationCode) async throws -> UserVerification
    func updateUser(conn: Database.Connection, user: User) async throws -> User
    func deleteUser(conn: Database.Connection, id: UserID) async throws -> Void

    func createSession(conn: Database.Connection, userSession: UserSession) async throws
    func session(conn: Database.Connection, tokenID: TokenID) async throws -> ShallowUserSession
    func sessionExists(conn: Database.Connection, tokenID: TokenID) async throws -> Bool
}

class UserService {
    var _userWithEmail: (Database.Connection, String) async throws -> User = { _, _ in fatalError("UserService.user(email:)") }
    var _userWithID: (Database.Connection, UserID) async throws -> User = { _, _ in fatalError("UserService.user(id:)") }
    var _users: (Database.Connection) async throws -> [User] = { _ in fatalError("UserService.users") }
    var _createUser: (Database.Connection, AccountSystem, String, String, String, Bool, Bool) async throws -> User = { _, _, _, _, _, _, _ in fatalError("UserService.createUser") }
    var _createUserVerification: (Database.Connection, User, VerificationCode) async throws -> Void = { _, _, _ in fatalError("UserService.createUserVerification") }
    var _userVerification: (Database.Connection, VerificationCode) async throws -> UserVerification = { _, _ in fatalError("UserService.userVerification") }
    var _updateUser: (Database.Connection, User) async throws -> User = { _, _ in fatalError("UserService.updateUser") }
    var _deleteUser: (Database.Connection, UserID) async throws -> Void = { _, _ in fatalError("UserService.deleteUser") }

    var _createSession: (Database.Connection, UserSession) async throws -> Void = { _, _ in fatalError("UserService.createSession") }
    var _session: (Database.Connection, TokenID) async throws -> ShallowUserSession = { _, _ in fatalError("UserService.session") }
    var _sessionExists: (Database.Connection, TokenID) async throws -> Bool = { _ , _ in fatalError("UserService.sessionExists") }

    init() { }

    init(_ p: UserProvider) {
        self._userWithEmail = p.user(conn:email:)
        self._userWithID = p.user(conn:id:)
        self._users = p.users
        self._createUser = p.createUser
        self._createUserVerification = p.createUserVerification
        self._userVerification = p.userVerification
        self._updateUser = p.updateUser
        self._deleteUser = p.deleteUser

        self._createSession = p.createSession
        self._session = p.session
        self._sessionExists = p.sessionExists
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

    func createUserVerification(conn: Database.Connection, user: User, code: VerificationCode) async throws {
        try await _createUserVerification(conn, user, code)
    }

    func userVerification(conn: Database.Connection, code: VerificationCode) async throws -> UserVerification {
        try await _userVerification(conn, code)
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
}

class UserSQLiteService: UserProvider {
    func user(conn: Database.Connection, email: String) async throws -> User {
        let rows = try await conn.select()
            .column("*")
            .from("users")
            .where("email", .equal, SQLBind(email))
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        return try makeUser(with: row)
    }

    func user(conn: Database.Connection, id: UserID) async throws -> User {
        let rows = try await conn.select()
            .column("*")
            .from("users")
            .where("id", .equal, SQLBind(id))
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        return try makeUser(with: row)
    }
    
    func users(conn: Database.Connection) async throws -> [User] {
        let rows = try await conn.select()
            .column("*")
            .from("users")
            .all()
        var _users = [User]()
        for row in rows {
            _users.append(try makeUser(with: row))
        }
        return _users
    }

    private func makeUser(with row: SQLRow) throws -> User {
        return try User(
            id: row.decode(column: "id", as: UserID.self),
            system: .makeFrom(row.decode(column: "system_id", as: Int.self)),
            fullName: row.decode(column: "full_name", as: String.self),
            email: row.decode(column: "email", as: String.self),
            password: row.decode(column: "password", as: String.self),
            verified: row.decode(column: "verified", as: Bool.self),
            enabled: row.decode(column: "enabled", as: Bool.self),
            mfaEnabled: row.decode(column: "mfa_enabled", as: Bool.self),
            totpSecret: row.decode(column: "totp_secret", as: String?.self)
        )
    }

    func createUser(
        conn: Database.Connection,
        system: AccountSystem,
        email: String,
        password: String,
        fullName: String,
        verified: Bool,
        enabled: Bool
    ) async throws -> User {
        let rows = try await conn.sql().insert(into: "users")
            .columns("id", "system_id", "create_date", "email", "password", "full_name", "verified", "enabled")
            .values(
                SQLLiteral.null,
                SQLBind(system.schemaId),
                SQLBind(Date.now),
                SQLBind(email),
                SQLBind(password),
                SQLBind(fullName),
                SQLBind(verified),
                SQLBind(enabled)
            )
            .returning("id")
            .all()

        return User(
            id: try rows[0].decode(column: "id", as: UserID.self),
            system: system,
            fullName: fullName,
            email: email,
            password: password,
            verified: verified,
            enabled: true,
            mfaEnabled: false,
            totpSecret: nil
        )
    }

    func updateUser(conn: Database.Connection, user: User) async throws -> User {
        try await conn.sql().update("users")
            .set("system_id", to: SQLBind(user.system.schemaId))
            .set("email", to: SQLBind(user.email))
            .set("password", to: SQLBind(user.password))
            .set("full_name", to: SQLBind(user.fullName))
            .set("verified", to: SQLBind(user.verified))
            .set("enabled", to: SQLBind(user.enabled))
            .set("mfa_enabled", to: SQLBind(user.mfaEnabled))
            .set("totp_secret", to: SQLBind(user.totpSecret))
            .where("id", .equal, SQLBind(user.id))
            .run()
        return user
    }
    
    func deleteUser(conn: Database.Connection, id: UserID) async throws {
        try await conn.sql().delete(from: "users")
            .where("id", .equal, SQLBind(id))
            .run()
    }

    func createUserVerification(conn: Database.Connection, user: User, code: VerificationCode) async throws {
        try await conn.sql().insert(into: "user_verifications")
            .columns("user_id", "create_date", "code")
            .values(
                SQLBind(user.id),
                SQLBind(Date.now),
                SQLBind(code)
            )
            .run()
    }

    func userVerification(conn: Database.Connection, code: VerificationCode) async throws -> UserVerification {
        let rows = try await conn.select()
            .column("*")
            .from("user_verifications")
            .where("code", .equal, SQLBind(code))
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        return UserVerification(
            userID: try row.decode(column: "user_id", as: UserID.self)
        )
    }

    func createSession(conn: Database.Connection, userSession: UserSession) async throws {
        try await conn.sql().insert(into: "user_sessions")
            .columns("token_id", "access_token", "create_date")
            .values(
                SQLBind(userSession.tokenId),
                SQLBind(userSession.accessToken),
                SQLBind(Date.now)
            )
            .run()
    }

    func session(conn: Database.Connection, tokenID: String) async throws -> ShallowUserSession {
        let rows = try await conn.select()
            .column("*")
            .from("user_sessions")
            .where("token_id", .equal, SQLBind(tokenID))
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        return .init(
            tokenId: try row.decode(column: "token_id", as: TokenID.self),
            accessToken: try row.decode(column: "access_token", as: String.self)
        )
    }

    func sessionExists(conn: Database.Connection, tokenID: TokenID) async throws -> Bool {
        let rows = try await conn.select()
            .column("token_id")
            .from("user_sessions")
            .where("token_id", .equal, SQLBind(tokenID))
            .all()
        return rows.count != 0
    }
}

private extension AccountSystem {
    var schemaId: Int {
        switch self {
        case .ays: return 0
        }
    }

    static func makeFrom(_ schemaId: Int) throws -> AccountSystem {
        switch schemaId {
        case 0: .ays
        default: throw service.error.InvalidSchemaID(AccountSystem.self)
        }
    }
}
