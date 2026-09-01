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
        
        // What a user holds. A role rather than a permission, so a route moving
        // between roles reaches its holders without re-granting anyone — the
        // grant names the role, and what the role holds is resolved when the
        // request arrives.
        try await sql.create(table: "acl_role_items")
            .column("id", type: .bigint, .primaryKey)
            .column("create_date", type: .timestamp)
            .column("role_id", type: .int)
            .column("user_id", type: .bigint)
            .run()
        try await sql.create(index: "acl_role_items_role_id_idx")
            .on("acl_role_items")
            .column("role_id")
            .run()
        try await sql.create(index: "acl_role_items_user_id_idx")
            .on("acl_role_items")
            .column("user_id")
            .run()
        
        // `acl_items` granted a permission to a user directly. A role is now
        // the only thing a user is granted, so the table has nothing to say.
        // Nothing is carried over: a permission granted on its own does not
        // name a role, and guessing which role was meant would hand out more
        // than anyone was given.
        try await sql.drop(table: "acl_items").run()
        
        // A path was `<catalog>,<bundle>,<feature>,<permission>`, the first
        // part naming whichever service registered it. It is now `<bundle>`
        // onward: an app has one backend, so the segment only ever held one
        // value per app, while making the same bundle under two services look
        // like two apps whose roles could not see each other.
        //
        // The old rows go. `acl.type` counts the parts of a path, so one left
        // behind reads a level shallower than it is — an app record answering
        // as a feature — and every path is registered again the moment a
        // service starts.
        try await sql.delete(from: "app_licenses").run()
        try await sql.delete(from: "acl").run()
    }
}
