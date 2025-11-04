/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import Foundation
internal import SQLiteKit

class ACLService: ACLProvider {
    private var catalog: ACLCatalog = .init(paths: [:])
    
    func createAclCatalog(
        session: Database.Session,
        for name: String,
        apps: [ACLApp]
    ) async throws -> ACLCatalog {
        let name = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard name.count > 0 else {
            throw api.error.InvalidParameter(name: "name")
        }
        
        let conn = try await session.conn()
        
        var acls = [ACL]()
        let _catalog = try await saveAclCatalog(conn: conn, name: name)
        acls.append(_catalog)
        for app in apps {
            let bundleId = app.bundleId.trimmingCharacters(in: .whitespacesAndNewlines)
            guard bundleId.count > 0 else {
                throw api.error.InvalidParameter(name: "bundleId")
            }

            let _app = try await saveAclApp(
                conn: conn,
                catalog: name,
                bundleId: app.bundleId
            )
            acls.append(_app)
            for feature in app.features {
                let feature = feature.trimmingCharacters(in: .whitespacesAndNewlines)
                guard feature.count > 0 else {
                    throw api.error.InvalidParameter(name: "feature")
                }
                
                let parts = feature.components(separatedBy: ".")
                let featureName = parts[0]
                guard featureName.count > 0 else {
                    throw api.error.InvalidParameter(name: "feature", expected: "A feature name must have at least one character")
                }

                var permission: String? = nil
                if let p = parts[safe: 1] {
                    guard p.count > 0 else {
                        throw api.error.InvalidParameter(name: "feature", expected: "A permission name must have at least one character")
                    }
                    permission = p
                }
                else if parts.count > 2 {
                    throw api.error.InvalidParameter(name: "feature", expected: "Only one dot is allowed.")
                }

                let _acls = try await saveAcl(
                    conn: conn,
                    catalog: name,
                    bundleId: app.bundleId,
                    feature: featureName,
                    permission: permission
                )
                acls += _acls
            }
        }
        
        // TODO: Given all ACL that was just registered (for this specific catalog), for any missing, for the given catalog, they should be removed.
        
        var registeredCatalog = [ACLPath: ACLID]()
        for acl in acls {
            registeredCatalog[acl.path] = acl.id
        }
        
        catalog = ACLCatalog(paths: catalog.paths.merging(registeredCatalog) { $1 })
        
        return catalog
    }
    
    func assignAccessToAcl(
        session: Database.Session,
        id: Int,
        to user: User
    ) async throws {
        // TODO: Only create ACL for path if it does not exist
    }
    
    func assignAccessToAcl(
        session: Database.Session,
        ids: [Int],
        to user: User
    ) async throws {
        
    }

    func verifyAccess(for authUser: AuthenticatedUser, to acl: ACLKey) async throws {
        var resources = [String]()
        
        // TODO: Verify
        let catalogName = acl.catalog.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !catalogName.isEmpty else {
            throw api.error.InvalidParameter(name: "catalog")
        }
        resources.append(catalogName)
        
        let bundleId = acl.bundleId.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !bundleId.isEmpty else {
            throw api.error.InvalidParameter(name: "bundleId")
        }
        resources.append(bundleId)
        
        let feature = acl.feature?.trimmingCharacters(in: .whitespacesAndNewlines)
        if let feature {
            guard !feature.isEmpty else {
                throw api.error.InvalidParameter(name: "feature")
            }
            
            let parts = feature.components(separatedBy: ".")
            let featureName = parts[0]
            guard featureName.count > 0 else {
                throw api.error.InvalidParameter(name: "feature", expected: "A feature name must have at least one character")
            }
            resources.append(featureName)
            
            if let permission = parts[safe: 1] {
                guard !permission.isEmpty else {
                    throw api.error.InvalidParameter(name: "feature", expected: "A permission name must have at least one character")
                }
                resources.append(permission)
            }
            else if parts.count > 2 {
                throw api.error.InvalidParameter(name: "feature", expected: "Only one dot is allowed.")
            }
        }
        
        let path = resources.joined(separator: ",")
        let acl = catalog.paths[path]
        guard let acl else {
            throw api.error.AccessDenied()
        }
        guard authUser.session.jwt.acl.contains(acl) else {
            throw api.error.AccessDenied()
        }
    }
    
    func userAcl(session: Database.Session, for user: User) async throws -> [ACLID] {
        // TODO: Query
        []
    }
}

private extension ACLService {
    func makeAcl(from row: SQLRow) throws -> ACL {
        try .init(
            id: row.decode(column: "id", as: Int.self),
            createDate: row.decode(column: "create_date", as: Date.self),
            path: row.decode(column: "path", as: String.self)
        )
    }
    
    func getAcl(conn: Database.Connection, path: String) async throws -> ACL? {
        let rows = try await conn.select()
            .column("*")
            .from("acl")
            .where("path", .equal, path)
            .all()
        
        if rows.count == 1 {
            throw service.error.DatabaseFailure("Found multiple ACLs for the same path")
        }

        return rows.isEmpty ? nil : try rows.first.map(makeAcl)
    }
    
    func saveAcl(conn: Database.Connection, path: String) async throws -> ACL {
        if let acl = try await getAcl(conn: conn, path: path) {
            return acl
        }
        
        let createDate = Date.now
        let inserted = try await conn.sql().insert(into: "acl")
            .columns("id", "create_date", "path")
            .values(
                SQLLiteral.null,
                SQLBind(createDate),
                SQLBind(path)
            )
            .returning("id")
            .all()

        return ACL(
            id: try inserted[0].decode(column: "id", as: ACLID.self),
            createDate: createDate,
            path: path
        )
    }
    
    func saveAclCatalog(conn: Database.Connection, name: String) async throws -> ACL {
        try await saveAcl(conn: conn, path: name)
    }
    
    func saveAclApp(conn: Database.Connection, catalog: String, bundleId: String) async throws -> ACL {
        try await saveAcl(conn: conn, path: "\(catalog),\(bundleId)")
    }
    
    func saveAcl(
        conn: Database.Connection,
        catalog: String,
        bundleId: String,
        feature: String,
        permission: String?
    ) async throws -> [ACL] {
        let acls: [ACL] = if let permission {
            [
                try await saveAcl(conn: conn, path: "\(catalog),\(bundleId),\(feature)"),
                try await saveAcl(conn: conn, path: "\(catalog),\(bundleId),\(feature),\(permission)")
            ]
        }
        else {
            [try await saveAcl(conn: conn, path: "\(catalog),\(bundleId),\(feature)")]
        }
        return acls
    }
}
