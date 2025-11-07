/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import Foundation
internal import SQLiteKit

class ACLService: ACLProvider {
    private var catalog: ACLCatalog = .init(paths: [:])
    
    func createAclCatalog(
        session: Database.Session,
        for name: String,
        apps: [ACLApp]
    ) async throws -> ACLPathMap {
        let conn = try await session.conn()
        try await conn.begin()
        
        do {
            let acls = try await createAclCatalog(conn: conn, for: name, apps: apps)
            var pathMap = ACLPathMap()
            for acl in acls {
                pathMap[acl.path] = acl.id
            }
            
            // Remove ACL that no longer exists in catalog
            let catalogAcl = try await catalogAcl(conn: conn, catalog: name)
            let aclsToRemove = Array(Set(catalogAcl).subtracting(Set(acls)))
            for acl in aclsToRemove {
                catalog.paths.removeValue(forKey: acl.path)
            }
            try await deleteAcl(conn: conn, acl: aclsToRemove)
            
            try await conn.commit()
            
            // Refresh entire catalog (ensures catalog contains no missing catalogs, etc.)
            let allAcls: [ACL] = try await allAcls(conn: conn)
            var registeredCatalog = ACLPathMap()
            for acl in allAcls {
                registeredCatalog[acl.path] = acl.id
            }
            catalog = ACLCatalog(paths: registeredCatalog)
            
            return pathMap
        }
        catch {
            try await conn.rollback()
            throw error
        }
    }
    
    func assignAccessToAcl(
        session: Database.Session,
        id: ACLID,
        to user: User
    ) async throws -> ACLItem {
        let conn = try await session.conn()
        return try await saveAclItem(conn: conn, user: user, acl: id)
    }
    
    func assignAccessToAcl(
        session: Database.Session,
        ids: [ACLID],
        to user: User
    ) async throws -> [ACLItem] {
        let conn = try await session.conn()
        var aclItems = [ACLItem]()
        for id in ids {
            let aclItem = try await saveAclItem(conn: conn, user: user, acl: id)
            aclItems.append(aclItem)
        }
        return aclItems
    }
    
    func removeAccessToAcl(session: Database.Session, id: ACLID, from user: User) async throws {
        let conn = try await session.conn()
        try await conn.sql().delete(from: "acl_items")
            .where("acl_id", .equal, SQLBind(id))
            .where("user_id", .equal, SQLBind(user.id))
            .run()
    }
    
    func removeAccessToAcl(session: Database.Session, ids: [ACLID], from user: User) async throws {
        guard !ids.isEmpty else {
            return
        }
        let conn = try await session.conn()
        try await conn.begin()
        try await conn.sql().delete(from: "acl_items")
            .where("acl_id", .in, ids)
            .where("user_id", .equal, SQLBind(user.id))
            .run()
        try await conn.commit()
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
            if parts.count > 2 {
                throw api.error.InvalidParameter(name: "feature", expected: "Only one dot is allowed")
            }
            
            let featureName = parts[0]
            guard !featureName.isEmpty else {
                throw api.error.InvalidParameter(name: "feature", expected: "A feature name must have at least one character")
            }
            resources.append(featureName)
            
            if let permission = parts[safe: 1] {
                guard !permission.isEmpty else {
                    throw api.error.InvalidParameter(name: "feature", expected: "A permission name must have at least one character")
                }
                resources.append(permission)
            }
        }
        
        // Recursively determine if user has access to permission, feature, app, and then catalog.
        // If user has none of the above, then they do not have permission to access resource.
        while resources.count > 0 {
            let path = resources.joined(separator: ",")
            let acl = catalog.paths[path]
            if let acl, authUser.session.jwt.acl.contains(acl) {
                return
            }
            resources.removeLast()
        }
        
        throw api.error.AccessDenied()
    }
    
    func userAcl(session: Database.Session, for user: User) async throws -> [ACLID] {
        let conn = try await session.conn()
        let rows = try await conn.select()
            .column("acl_id")
            .from("acl_items")
            .where("user_id", .equal, user.id)
            .all()
        let ids = try rows.map { try $0.decode(column: "acl_id", as: ACLID.self) }
        return ids
    }
    
    func acl(session: Database.Session) async throws -> [ACL] {
        let conn = try await session.conn()
        return try await allAcls(conn: conn)
    }
    
    func aclTree(session: Database.Session) async throws -> ACLTree {
        let conn = try await session.conn()
        let acls = try await allAcls(conn: conn).sorted { left, right in
            left.path < right.path
        }
        
        // Create intermediary structure used to create hierarchy
        var catalogInfo: [String: (id: Int, apps: [String: (id: Int, features: [String: (id: Int, perms: [ACLTree.Permission])])])] = [:]
        
        for acl in acls {
            let parts = acl.path
                .components(separatedBy: ",")
                .map { $0.trimmingCharacters(in: .whitespaces) }
                .filter { !$0.isEmpty }
            
            guard !parts.isEmpty else {
                continue
            }
            let catalogName = parts[0]
            
            // catalog
            var catalog = catalogInfo[catalogName] ?? (id: 0, apps: [:])
            if parts.count == 1 { // Override ID if this record represents the catalog
                catalog.id = acl.id
            }
            
            // app
            guard parts.count >= 2 else {
                catalogInfo[catalogName] = catalog
                continue
            }
            let appName = parts[1]
            var app = catalog.apps[appName] ?? (id: 0, features: [:])
            if parts.count == 2 { // Same with app. Override ID asthis represents the app record
                app.id = acl.id
            }
            
            // feature (needs 3 parts)
            if parts.count >= 3 {
                let featureName = parts[2]
                var feature = app.features[featureName] ?? (id: 0, perms: [])
                if parts.count == 3 { // Override ID as this represents the feature record
                    feature.id = acl.id
                }
                
                // permission (needs 4 parts)
                if parts.count == 4, let permName = parts[safe: 3] {
                    feature.perms.append(.init(id: acl.id, name: permName))
                }
                app.features[featureName] = feature
            }
            catalog.apps[appName] = app
            catalogInfo[catalogName] = catalog
        }
        
        // Transform dictionary into objects
        let catalogs = catalogInfo
            .sorted(by: { $0.key < $1.key })
            .map { (catName, catInfo) -> ACLTree.Catalog in
                let apps = catInfo.apps
                    .sorted(by: { $0.key < $1.key })
                    .map { (appName, appInfo) -> ACLTree.App in
                        let features = appInfo.features
                            .sorted(by: { $0.key < $1.key })
                            .map { (featName, featInfo) -> ACLTree.Feature in
                                return ACLTree.Feature(
                                    id: featInfo.id,
                                    name: featName,
                                    permissions: featInfo.perms
                                )
                            }
                        return ACLTree.App(id: appInfo.id, name: appName, features: features)
                    }
                return ACLTree.Catalog(id: catInfo.id, name: catName, apps: apps)
            }
        
        return ACLTree(catalogs: catalogs)
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
    
    func allAcls(conn: Database.Connection) async throws -> [ACL] {
        let rows = try await conn.select()
            .column("*")
            .from("acl")
            .all()
        
        return try rows.map(makeAcl)
    }
    
    func catalogAcl(conn: Database.Connection, catalog: String) async throws -> [ACL] {
        let rows = try await conn.select()
            .column("*")
            .from("acl")
            .where("path", .like, SQLBind("\(catalog),%"))
            .all()
        
        return try rows.map(makeAcl)
    }
    
    func deleteAcl(conn: Database.Connection, acl: [ACL]) async throws {
        guard !acl.isEmpty else {
            return
        }
        let ids: [ACLID] = acl.map { $0.id }
        try await conn.sql().delete(from: "acl")
            .where("id", .in, ids)
            .run()
        try await conn.sql().delete(from: "acl_items")
            .where("acl_id", .in, ids)
            .run()
    }
    
    func createAclCatalog(
        conn: Database.Connection,
        for name: String,
        apps: [ACLApp]
    ) async throws -> [ACL] {
        let name = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !name.isEmpty else {
            throw api.error.InvalidParameter(name: "name")
        }
        
        var acls = [ACL]()
        let _catalog = try await saveAclCatalog(conn: conn, name: name)
        acls.append(_catalog)
        for app in apps {
            let bundleId = app.bundleId.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !bundleId.isEmpty else {
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
                guard !feature.isEmpty else {
                    throw api.error.InvalidParameter(name: "feature")
                }
                
                let parts = feature.components(separatedBy: ".")
                if parts.count > 2 {
                    throw api.error.InvalidParameter(name: "feature", expected: "Only one dot is allowed")
                }
                
                let featureName = parts[0]
                guard !featureName.isEmpty else {
                    throw api.error.InvalidParameter(name: "feature", expected: "A feature name must have at least one character")
                }

                var permission: String? = nil
                if  let p = parts[safe: 1] {
                    guard !p.isEmpty else {
                        throw api.error.InvalidParameter(name: "feature", expected: "A permission name must have at least one character")
                    }
                    permission = p
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
        
        return acls
    }
    
    func getAcl(conn: Database.Connection, path: String) async throws -> ACL? {
        let rows = try await conn.select()
            .column("*")
            .from("acl")
            .where("path", .equal, path)
            .all()
        
        if rows.count > 1 {
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
    
    func makeAclItem(from row: SQLRow) throws -> ACLItem {
        try .init(
            id: row.decode(column: "id", as: Int.self),
            createDate: row.decode(column: "create_date", as: Date.self),
            aclId: row.decode(column: "acl_id", as: ACLID.self),
            userId: row.decode(column: "user_id", as: UserID.self)
        )
    }
    
    func saveAclItem(conn: Database.Connection, user: User, acl: ACLID) async throws -> ACLItem {
        let rows = try await conn.select()
            .column("*")
            .from("acl_items")
            .where("acl_id", .equal, acl)
            .where("user_id", .equal, user.id)
            .all()
        
        if let row = rows.first {
            return try makeAclItem(from: row)
        }

        let createDate = Date.now
        let inserted = try await conn.sql().insert(into: "acl_items")
            .columns("id", "create_date", "acl_id", "user_id")
            .values(
                SQLLiteral.null,
                SQLBind(createDate),
                SQLBind(acl),
                SQLBind(user.id)
            )
            .returning("id")
            .all()

        return ACLItem(
            id: try inserted[0].decode(column: "id", as: ACLItemID.self),
            createDate: createDate,
            aclId: acl,
            userId: user.id
        )
    }
}
