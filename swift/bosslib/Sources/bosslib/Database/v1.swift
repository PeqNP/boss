/// Copyright ⓒ 2023 Bithead LLC. All rights reserved.

import Foundation
internal import SQLKit

/// Create initial database
func createDatabase(db: Database) async throws {
    let sql = try await db.session().conn().sql()
    try await sql.create(table: "versions")
        .column("id", type: .int, .primaryKey)
        .column("version", type: .text)
        .column("create_date", type: .timestamp)
        .run()
    try await sql.insert(into: "versions")
        .columns("id", "version", "create_date")
        .values(SQLLiteral.null, SQLBind("1.0.0"), SQLBind(Date.now))
        .run()

    try await sql.create(table: "nodes")
        .column("id", type: .bigint, .primaryKey)
        .column("create_date", type: .timestamp)
        .column("path", type: .text)
        .column("node_type_id", type: .int) // Schema.NodeTypeEnum
        .column("node_type", type: .text) // JSON `NodeType`
        .column("logo", type: .text)
        .column("description", type: .text)
        .column("contacts", type: .text) // JSON `[Contact]`
        .column("acl", type: .text) // JSON `[ACL]`
        // NOTE: These may need to be table rows. Not sure yet. They need an ID.
        .column("properties", type: .text) // JSON `[NodeProperty]`
        .column("alerting_config", type: .text) // JSON `[AlertingConfig]`
        .run()
    try await sql.create(index: "node_node_type_id_idx")
        .on("nodes")
        .column("node_type_id")
        .run()

    // Parent child relationship
    try await sql.create(table: "child_nodes")
        .column("node_id", type: .bigint)
        .column("child_node_id", type: .bigint)
        .run()
    try await sql.create(index: "child_nodes_node_id_idx")
        .on("child_nodes")
        .column("node_id")
        .run()
    try await sql.create(index: "child_nodes_child_node_id_idx")
        .on("child_nodes")
        .column("child_node_id")
        .run()

    // Dependency relationship between two nodes
    try await sql.create(table: "dependency_nodes")
        // The node who is dependent on the dependency
        .column("dependent_node_id", type: .bigint)
        // The node who is the dependency of the dependent node
        .column("dependency_node_id", type: .bigint)
        .run()
    try await sql.create(index: "dependency_nodes_dependent_node_id_idx")
        .on("dependency_nodes")
        .column("dependent_node_id")
        .run()
    try await sql.create(index: "dependency_nodes_dependency_node_id_idx")
        .on("dependency_nodes")
        .column("dependency_node_id")
        .run()

    try await sql.create(table: "users")
        // The node who is dependent on the dependency
        .column("id", type: .bigint, .primaryKey)
        // The node who is the dependency of the dependent node
        .column("system_id", type: .smallint)
        .column("create_date", type: .timestamp)
        // .column("update_date", type: .timestamp)
        .column("email", type: .text)
        .column("password", type: .text)
        .column("full_name", type: .text)
        .column("verified", type: .smallint)
        .column("enabled", type: .smallint)
        .column("home_node_id", type: .bigint)
        .run()
    try await sql.create(index: "users_email_idx")
        .on("users")
        .column("email")
        .unique()
        .run()

    try await sql.create(table: "user_sessions")
        .column("token_id", type: .text)
        .column("access_token", type: .text)
        .column("create_date", type: .timestamp)
        .run()
    try await sql.create(index: "user_sessions_token_id_idx")
        .on("user_sessions")
        .column("token_id")
        .unique()
        .run()

    try await sql.create(table: "user_verifications")
        .column("user_id", type: .bigint)
        .column("org_node_path", type: .text)
        .column("create_date", type: .timestamp)
        .column("code", type: .text)
        .run()
    try await sql.create(index: "user_verifications_code_idx")
        .on("user_verifications")
        .column("code")
        .unique()
        .run()

    let conn = try await db.session().conn()
    // Super User
    _ = try await service.user.createUser(
        conn: conn,
        system: .ays,
        email: "bitheadrl@protonmail.com",
        password: Bcrypt.hash("Password1!"),
        fullName: "Admin",
        verified: true,
        enabled: true
    )
    // Guest User
    _ = try await service.user.createUser(
        conn: conn,
        system: .ays,
        email: "eric.j.chamberlain@protonmail.com",
        password: Bcrypt.hash("Password1!"),
        fullName: "Guest",
        verified: true,
        enabled: true
    )
    // Common TLDs
    let tlds: [String] = [
        "al", "app", "at", "au",
        "be", "biz", "br",
        "ca", "cc", "ch", "cl", "cn", "co", "com", "cz",
        "de",
        "edu", "es", "eu",
        "fi", "fr",
        "gov",
        "id", "in", "info", "int", "io", "ir", "it",
        "jp",
        "kr",
        "li", "ly",
        "me", "mil", "mx",
        "net", "news", "nl", "no",
        "org",
        "pl",
        "ru",
        "se", "sk",
        "tech", "to", "tr", "tv", "tw",
        "ua", "uk", "us",
        "vn",
        "xyz"
    ]
    for tld in tlds {
        _ = try await service.node.createNode(
            conn: conn,
            path: tld,
            type: .group,
            acl: [.makeOwnerACL(using: superUser().user)]
        )
    }

    // TODO: The node_health databases may already be SQLite3. They should be managed by a different system.
    
    try await sql.create(table: "projects")
        .column("id", type: .bigint, .primaryKey)
        .column("name", type: .text)
        .column("test_suite_ids", type: .text)
        .run()
    try await sql.create(table: "test_suites")
        .column("id", type: .bigint, .primaryKey)
        .column("project_id", type: .bigint)
        .column("name", type: .text)
        .column("text", type: .text)
        .column("test_case_ids", type: .text)
        .foreignKey(["project_id"], references: "projects", ["id"], onDelete: .cascade)
        .run()
    try await sql.create(table: "test_cases")
        .column("id", type: .bigint, .primaryKey)
        .column("project_id", type: .bigint)
        .column("test_suite_id", type: .bigint)
        .column("name", type: .text)
        .column("notes", type: .text)
        .column("is_automated", type: .smallint)
        .foreignKey(["project_id"], references: "projects", ["id"], onDelete: .cascade)
        .foreignKey(["test_suite_id"], references: "test_suites", ["id"], onDelete: .cascade)
        .run()
    try await sql.create(table: "test_suite_resources")
        .column("id", type: .bigint, .primaryKey)
        .column("test_suite_id", type: .bigint)
        .column("mime_type", type: .text)
        .column("name", type: .text)
        .column("path", type: .text)
        .foreignKey(["test_suite_id"], references: "test_suites", ["id"], onDelete: .cascade)
        .run()
    try await sql.create(table: "test_runs")
        .column("id", type: .bigint, .primaryKey)
        .column("date_created", type: .bigint)
        .column("name", type: .text)
        .column("text", type: .text)
        // The original model IDs responsible for finding test cases
        .column("model_ids", type: .text)
        .column("include_automated", type: .smallint)
        .column("selected_test_case_id", type: .bigint)
        .column("is_finished", type: .smallint)
        .foreignKey(["selected_test_case_id"], references: "test_cases", ["id"], onDelete: .cascade)
        .run()
    try await sql.create(table: "test_case_results")
        .column("id", type: .bigint, .primaryKey)
        .column("test_run_id", type: .bigint)
        .column("test_case_id", type: .bigint)
        .column("user_id", type: .bigint)
        // The last time the result was statused
        .column("date_statused", type: .bigint)
        .column("notes", type: .text)
        .column("status", type: .smallint)
        .foreignKey(["test_run_id"], references: "test_runs", ["id"], onDelete: .cascade)
        .foreignKey(["test_case_id"], references: "test_cases", ["id"], onDelete: .setNull)
        .foreignKey(["user_id"], references: "users", ["id"], onDelete: .setNull)
        .run()
    try await sql.create(table: "test_run_results")
        .column("test_run_id", type: .bigint, .primaryKey)
        .column("user_id", type: .bigint)
        .column("date_created", type: .bigint)
        .column("determination", type: .smallint)
        .column("notes", type: .text)
        .foreignKey(["test_run_id"], references: "test_runs", ["id"], onDelete: .cascade)
        .foreignKey(["user_id"], references: "users", ["id"], onDelete: .setNull)
        .run()
}
