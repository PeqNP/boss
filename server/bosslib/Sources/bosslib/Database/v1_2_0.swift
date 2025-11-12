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
        
        // Every ACL record has its own (full) `path`. e.g. `python`, `python,io.bithead.test-manager`, `python.io.bithead.test-manager,projects`, and `python.io.bithead.test-manager,projects,r`. This allows for:
        // - A simple flat record for every possible ACL resource
        // - Dictionary `ACLPathMap` that can be used to compare a route's resource to a user's assigned `acl_paths.id`. Route provides `ACLPath`, JWT provides list of `ACLPathID`s
        // - A very small JWT that contain all of the `ACLPathID`s. It could get crazy if there were 100s of apps/permissions assigned to the user. But it's way less than if the paths themselves were stored in the JWT.
        // If hundreds of `ACLPathID`s are stored in the JWT, it would make sense to pull out the mapping of the user to path IDs (`[UserID: [ACLPathIDs]]`) into a Reddis/memcache server. Currently, there is only a single app resource. No need to over-engineer at the moment. Lastly, this pattern is easy to move from JWT to Reddis/memcache, if needed.
        // TBD: Worst case scenario, it may easy enough to make a request to get all ACL for a user from SQLite for every request being verified.
        try await sql.create(table: "acl")
            .column("id", type: .int, .primaryKey)
            .column("create_date", type: .timestamp)
            .column("path", type: .text)
            // 0 = Catalog, 1 = App, 2 = Feature, 3 = Permission
            .column("type", type: .int)
            .run()
        try await sql.create(index: "acl_path_idx")
            .on("acl")
            .column("path")
            .run()
        
        // `app_licenses` serve a different purpose from `acl` and `acl_items`. A license helps determine if a user can open the app.
        // In the future, this may contain a license key, a start, and an end date.
        // There is no `apps` table, because apps already live in the `acl` table. They have the full <catalog>,<bundle_id> path and have their type set to ACLType.App
        // I kept the `bundle_id` here to avoid a JOIN on the `acl` table when checking if a user has a license to the app. However, it still links to the respective ACL. It's important to note that if the app is removed, so will all of the licenses. It is assumed that a bundle ID will _never_ change after it is created. This is a pretty standard pattern. Where the bundle ID is unique across all apps, and that it will never change.
        // If an app doesn't have ACL, then it is assumed the app does not need a license to operate.
        try await sql.create(table: "app_licenses")
            .column("id", type: .int, .primaryKey)
            .column("create_date", type: .timestamp)
            .column("acl_id", type: .int)
            .column("user_id", type: .int)
            .run()
        try await sql.create(index: "app_licenses_acl_id_idx")
            .on("app_licenses")
            .column("acl_id")
            .run()
        try await sql.create(index: "app_licenses_user_id_idx")
            .on("app_licenses")
            .column("user_id")
            .run()

        // The item is how ACL is associated to a user. The idea is that, when a user signs in, all of their `acl_items.acl_id`s are returned and put into an array. These IDs are compared when verification takes place.
        try await sql.create(table: "acl_items")
            .column("id", type: .bigint, .primaryKey)
            .column("create_date", type: .timestamp)
            .column("acl_id", type: .int)
            .column("user_id", type: .bigint)
            .run()
        try await sql.create(index: "acl_items_acl_id_idx")
            .on("acl_items")
            .column("acl_id")
            .run()
        try await sql.create(index: "acl_items_user_id_idx")
            .on("acl_items")
            .column("user_id")
            .run()
    }
}
