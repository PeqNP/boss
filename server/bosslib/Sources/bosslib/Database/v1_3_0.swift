/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

internal import SQLKit

class Version1_3_0: DatabaseVersion {
    var version: String { "1.3.0" }
    
    func update(_ session: Database.Session) async throws {
        let conn = try await session.conn()
        let sql = conn.sql()
        
        // When an ACL stops being registered, it is retired rather than deleted.
        //
        // A registration used to be read as the whole truth, so anything it did not
        // carry was deleted along with every grant and license referencing it. Absence
        // has three causes and only one of them is somebody deciding to remove
        // something: an app that fails to load registers nothing, a route that stops
        // naming a feature takes it out of the set, and a genuine removal looks exactly
        // like both.
        //
        // Retiring keeps the row, its ID, and everything pointing at it. A name that
        // comes back is revived rather than recreated, so tokens already issued still
        // name it. `api.acl.pruneAcl()` is how a retired record is destroyed on purpose.
        //
        // NULL means active, which is what every existing row becomes.
        try await sql.alter(table: "acl")
            .column("retired_date", type: .timestamp)
            .run()
        
        // A role is a named set of permissions within one app, and is what a
        // user is granted. Granting a role rather than each permission lets an
        // app move a feature between roles without re-granting anyone: the role
        // keeps its ID, and the grant names the role.
        //
        // Roles are declared by an app's routes and accumulate at registration,
        // so a role exists because something names it. One that stops being
        // named is retired, for the same reason an ACL is.
        try await sql.create(table: "acl_roles")
            .column("id", type: .int, .primaryKey)
            .column("create_date", type: .timestamp)
            // The `ACLType.app` record this role belongs to
            .column("app_acl_id", type: .int)
            .column("name", type: .text)
            .column("retired_date", type: .timestamp)
            .run()
        try await sql.create(index: "acl_roles_app_acl_id_idx")
            .on("acl_roles")
            .column("app_acl_id")
            .run()
        
        // What a role holds. Rebuilt from the payload on every registration,
        // because a route retagged from one role to another is the ordinary way
        // this changes — and the grant, which names the role, is untouched by it.
        try await sql.create(table: "acl_role_permissions")
            .column("id", type: .bigint, .primaryKey)
            .column("create_date", type: .timestamp)
            .column("role_id", type: .int)
            .column("acl_id", type: .int)
            .run()
        try await sql.create(index: "acl_role_permissions_role_id_idx")
            .on("acl_role_permissions")
            .column("role_id")
            .run()
        try await sql.create(index: "acl_role_permissions_acl_id_idx")
            .on("acl_role_permissions")
            .column("acl_id")
            .run()
    }
}
