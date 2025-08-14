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
    }
}
