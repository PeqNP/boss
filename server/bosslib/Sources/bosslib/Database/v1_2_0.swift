/// Copyright ⓒ 2023 Bithead LLC. All rights reserved.

internal import SQLKit

class Version1_2_0: DatabaseVersion {
    var version: String { "1.2.0" }
    
    func update(_ conn: Database.Connection) async throws {
        let sql = conn.sql()
        
        // Stores account recover email codes
        try await sql.create(table: "account_recovery_codes")
            .column("id", type: .bigint, .primaryKey)
            .column("create_date", type: .timestamp)
            .column("update_date", type: .timestamp)
            // The time the expiration code expires
            .column("expiration_date", type: .timestamp)
            // Account e-mail attempting to recover. This doesn't have a functional value except for logging purposes and ensuring only one recovery takes place at a time.
            .column("email", type: .text)
            // Randomly generated code sent to user's e-mail
            .column("code", type: .text)
            // The time the account was recovered
            .column("recovered_date", type: .timestamp)
            .run()
        // Email is used to prevent more than one active recover from taking place
        try await sql.create(index: "account_recovery_codes_email_idx")
            .on("account_recovery_codes")
            .column("email")
            .run()
        // Recovery is done by matching recovery code
        try await sql.create(index: "account_recovery_codes_code_idx")
            .on("account_recovery_codes")
            .column("code")
            .run()
        // This is now managed by account_recovery_codes for both password recovery and account creation
        try await sql.drop(table: "user_verifications").run()
        
        
        try await sql.create(table: "friend_requests")
            .column("id", type: .bigint, .primaryKey)
            .column("create_date", type: .timestamp)
            .column("user_id", type: .bigint)
            // The recipient e-mail (it does not need to be an existing user)
            .column("email", type: .text)
            .foreignKey(["user_id"], references: "users", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "friend_user_id_idx")
            .on("friend_requests")
            .column("user_id")
            .run()
        try await sql.create(index: "friend_requests_email_idx")
            .on("friend_requests")
            .column("email")
            .run()

        try await sql.create(table: "friends")
            .column("id", type: .bigint, .primaryKey)
            // The create date is the same as the same thing as the "accepted" date
            .column("create_date", type: .timestamp)
            .column("user_id", type: .bigint)
            .column("friend_user_id", type: .bigint)
            .foreignKey(["user_id"], references: "users", ["id"], onDelete: .cascade)
            .foreignKey(["friend_user_id"], references: "users", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "friends_user_id_idx")
            .on("friends")
            .column("user_id")
            .run()
        try await sql.create(index: "friends_friend_user_id_idx")
            .on("friends")
            .column("friend_user_id")
            .run()
    }
}
