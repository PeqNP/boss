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
    }
}
