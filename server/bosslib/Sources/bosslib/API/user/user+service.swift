//
//  user+service.swift
//  bosslib
//
//  Created by Eric Chamberlain on 11/13/25.
//

import Foundation
internal import SQLKit

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
    
    func deleteSession(conn: Database.Connection, tokenID: TokenID) async throws -> Void {
        try await conn.sql().delete(from: "user_sessions")
            .where("token_id", .equal, SQLBind(tokenID))
            .run()
    }
        
    func createMfa(conn: Database.Connection, user: User, totpSecret: String) async throws {
        try await conn.sql().insert(into: "tmp_secrets")
            .columns("user_id", "create_date", "secret")
            .values(
                SQLBind(user.id),
                SQLBind(Date.now),
                SQLBind(totpSecret)
            )
            .run()
    }
    
    func mfa(conn: Database.Connection, user: User) async throws -> TemporaryMFA {
        let rows = try await conn.select()
            .column("*")
            .from("tmp_secrets")
            .where("user_id", .equal, SQLBind(user.id))
            .orderBy("id", .descending)
            .limit(1)
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        return .init(
            id: try row.decode(column: "id", as: Int.self),
            createDate: try row.decode(column: "create_date", as: Date.self),
            userId: user.id,
            secret: try row.decode(column: "secret", as: String.self)
        )
    }
    
    func deleteMfa(conn: Database.Connection, userId: UserID) async throws {
        try await conn.sql().delete(from: "tmp_secrets")
            .where("user_id", .equal, SQLBind(userId))
            .run()
    }
        
    func createAccountRecoveryCode(conn: Database.Connection, email: String, code: String) async throws -> AccountRecoveryCode {
        try await conn.sql().insert(into: "account_recovery_codes")
            .columns("create_date", "update_date", "expiration_date", "email", "code", "recovered_date")
            .values(
                SQLBind(Date.now),
                SQLBind(Date.now),
                SQLBind(Date.now.addingTimeInterval(Global.accountRecoveryExpirationTimeInSeconds)),
                SQLBind(email),
                SQLBind(code),
                SQLLiteral.null
            )
            .run()

        return try await accountRecoveryCode(conn: conn, code: code)
    }
    
    func accountRecoveryCode(conn: Database.Connection, code: String) async throws -> AccountRecoveryCode {
        let rows = try await conn.select()
            .column("*")
            .from("account_recovery_codes")
            .where("code", .equal, SQLBind(code))
            .where("expiration_date", .greaterThanOrEqual, SQLBind(Date.now))
            .where("recovered_date", .is, SQLLiteral.null)
            .orderBy("id", .descending)
            .limit(1)
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        return .init(
            id: try row.decode(column: "id", as: Int.self),
            createDate: try row.decode(column: "create_date", as: Date.self),
            updateDate: try row.decode(column: "update_date", as: Date.self),
            expirationDate: try row.decode(column: "expiration_date", as: Date.self),
            email: try row.decode(column: "email", as: String.self),
            code: try row.decode(column: "code", as: String.self),
            recoveredDate: try row.decode(column: "recovered_date", as: Date?.self)
        )
    }
    
    func accountRecoveryCode(conn: Database.Connection, email: String) async throws -> AccountRecoveryCode {
        let rows = try await conn.select()
            .column("*")
            .from("account_recovery_codes")
            .where("email", .equal, SQLBind(email))
            .where("expiration_date", .greaterThanOrEqual, SQLBind(Date.now))
            .where("recovered_date", .is, SQLLiteral.null)
            .orderBy("id", .descending)
            .limit(1)
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        return .init(
            id: try row.decode(column: "id", as: Int.self),
            createDate: try row.decode(column: "create_date", as: Date.self),
            updateDate: try row.decode(column: "update_date", as: Date.self),
            expirationDate: try row.decode(column: "expiration_date", as: Date.self),
            email: try row.decode(column: "email", as: String.self),
            code: try row.decode(column: "code", as: String.self),
            recoveredDate: try row.decode(column: "recovered_date", as: Date?.self)
        )
    }
    
    func recoverAccount(conn: Database.Connection, code: String) async throws {
        try await conn.sql().update("account_recovery_codes")
            .set("update_date", to: SQLBind(Date.now))
            .set("recovered_date", to: SQLBind(Date.now))
            .where("code", .equal, SQLBind(code))
            .where("expiration_date", .greaterThanOrEqual, SQLBind(Date.now))
            .where("recovered_date", .is, SQLLiteral.null)
            .run()
    }
}

private extension AccountSystem {
    var schemaId: Int {
        switch self {
        case .boss: return 0
        }
    }

    static func makeFrom(_ schemaId: Int) throws -> AccountSystem {
        switch schemaId {
        case 0: .boss
        default: throw service.error.InvalidSchemaID(AccountSystem.self)
        }
    }
}
