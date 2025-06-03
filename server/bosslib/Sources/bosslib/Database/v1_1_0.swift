/// Copyright ⓒ 2023 Bithead LLC. All rights reserved.

internal import SQLKit

class Version1_1_0: DatabaseVersion {
    var version: String { "1.1.0" }
    
    func update(_ conn: Database.Connection) async throws {
        let sql = conn.sql()
        
        try await sql.alter(table: "users")
            .dropColumn("home_node_id")
            .run()
        try await sql.alter(table: "users")
            .column("mfa_enabled", type: .smallint, .default(0), .notNull)
            .run()
        try await sql.alter(table: "users")
            .column("totp_secret", type: .text)
            .run()
        
        // Store TOTP secrets temporarily before they are assigned to a user's account
        try await sql.create(table: "tmp_secrets")
            .column("id", type: .bigint, .primaryKey)
            .column("user_id", type: .bigint)
            .column("create_date", type: .timestamp)
            .column("secret", type: .text)
            .foreignKey(["user_id"], references: "users", ["id"], onDelete: .cascade)
            .run()
        
        try await sql.drop(table: "dependency_nodes").ifExists()
            .run()
        try await sql.drop(table: "child_nodes").ifExists()
            .run()
        try await sql.drop(table: "nodes").ifExists()
            .run()
        try await sql.alter(table: "user_verifications")
            .dropColumn("org_node_path")
            .run()
    }
}
