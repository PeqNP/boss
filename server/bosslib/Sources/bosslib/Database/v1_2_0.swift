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
            // Indicates that the code has been used for recovery. This ensures the record can not be used again.
            .column("recovered", type: .smallint)
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
    }
}
