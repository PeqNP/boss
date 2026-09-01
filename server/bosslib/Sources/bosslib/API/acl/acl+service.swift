/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import Foundation
internal import SQLiteKit

class ACLService: ACLProvider {
    private var apps: [BundleID: ACLID] = [:]
    private var paths: ACLPathMap = [:]
    /// Role to the permissions it holds, refreshed whenever an app registers.
    ///
    /// Held here rather than read per request, and expanded at the request
    /// rather than at the grant: a route retagged from one role to another
    /// reaches its holders as soon as the app registers, without re-minting
    /// a token or re-granting anybody.
    private var rolePermissions: [ACLRoleID: Set<ACLID>] = [:]
    
    func aclPaths() -> ACLPathMap {
        paths
    }
    
    func registerApps(
        session: Database.Session,
        _ apps: [ACLApp]
    ) async throws -> ACLPathMap {
        let conn = try await session.conn()
        try await conn.begin()
        
        do {
            let acls = try await saveApps(conn: conn, apps: apps)
            var pathMap = ACLPathMap()
            for acl in acls {
                pathMap[acl.path] = acl.id
            }
            
            // Retire ACL this registration no longer carries — within the apps
            // it carried. An app that is absent said nothing, which is not the
            // same as saying it has nothing.
            let bundles = Set(apps.map {
                $0.bundleId.trimmingCharacters(in: .whitespacesAndNewlines)
            })
            let spokenFor = try await bundleAcl(conn: conn, bundles: bundles)
            let registered = Set(acls.map { $0.id })
            let aclsToRetire = spokenFor.filter { !registered.contains($0.id) }
            for acl in aclsToRetire {
                paths.removeValue(forKey: acl.path)
            }
            try await retireAcl(conn: conn, acl: aclsToRetire)
            
            // Roles, against the same payload. A role holds features, so this
            // runs after they have ids to point at.
            for app in apps {
                let bundleId = app.bundleId.trimmingCharacters(in: .whitespacesAndNewlines)
                guard let appAclId = pathMap[bundleId] else {
                    continue
                }
                try await saveRoles(conn: conn, appAclId: appAclId,
                                    bundleId: bundleId, app: app, paths: pathMap)
            }
            
            try await conn.commit()
            
            // Everything, not just what this registration carried: another app
            // may have registered since these were last read.
            let allAcls: [ACL] = try await allAcls(conn: conn)
            var registeredPaths = ACLPathMap()
            for acl in allAcls {
                registeredPaths[acl.path] = acl.id
            }
            paths = registeredPaths
            
            var registeredApps = [BundleID: ACLID]()
            for acl in allAcls {
                switch acl.type {
                case .app:
                    registeredApps[acl.path] = acl.id
                case .feature, .permission, .unknown:
                    continue
                }
            }
            self.apps = registeredApps
            self.rolePermissions = try await allRolePermissions(conn: conn)
            
            return pathMap
        }
        catch {
            try await conn.rollback()
            throw error
        }
    }
    
    func assignRole(session: Database.Session, id: ACLRoleID, to user: User) async throws {
        guard !user.isSuperUser else {
            throw api.error.SuperUserRequiresNoPrivilege()
        }
        let conn = try await session.conn()
        let existing = try await conn.select()
            .column("*")
            .from("acl_role_items")
            .where("role_id", .equal, SQLBind(id))
            .where("user_id", .equal, SQLBind(user.id))
            .all()
        guard existing.isEmpty else {
            return
        }
        try await conn.sql().insert(into: "acl_role_items")
            .columns("id", "create_date", "role_id", "user_id")
            .values(SQLLiteral.null, SQLBind(Date.now), SQLBind(id), SQLBind(user.id))
            .run()
    }
    
    func removeRole(session: Database.Session, id: ACLRoleID, from user: User) async throws {
        let conn = try await session.conn()
        try await conn.sql().delete(from: "acl_role_items")
            .where("role_id", .equal, SQLBind(id))
            .where("user_id", .equal, SQLBind(user.id))
            .run()
    }
    
    func userRoles(session: Database.Session, for user: User) async throws -> [ACLRoleID] {
        let conn = try await session.conn()
        let rows = try await conn.select()
            .column(SQLColumn("role_id", table: "acl_role_items"))
            .from("acl_role_items")
            .join("acl_roles", on: SQLColumn("role_id", table: "acl_role_items"),
                  .equal, SQLColumn("id", table: "acl_roles"))
            .where(SQLColumn("retired_date", table: "acl_roles"), .is, SQLLiteral.null)
            .where(SQLColumn("user_id", table: "acl_role_items"), .equal, SQLBind(user.id))
            .all()
        return try rows.map { try $0.decode(column: "role_id", as: ACLRoleID.self) }
    }
    
    func roles(session: Database.Session, bundleId: BundleID) async throws -> [ACLRole] {
        let conn = try await session.conn()
        guard let appAclId = try await aclApp(session: session, bundleId: bundleId) else {
            return []
        }
        return try await appRoles(conn: conn, appAclId: appAclId)
    }
    
    func roleFeatures(session: Database.Session, id: ACLRoleID) async throws -> [ACLFeature] {
        let conn = try await session.conn()
        let rows = try await conn.select()
            .column(SQLColumn("path", table: "acl"))
            .from("acl_role_permissions")
            .join("acl", on: SQLColumn("acl_id", table: "acl_role_permissions"),
                  .equal, SQLColumn("id", table: "acl"))
            .where(SQLColumn("role_id", table: "acl_role_permissions"),
                   .equal, SQLBind(id))
            .all()
        // The path is `<bundle>,<feature>[,<permission>]`; the app named the
        // last two, so that is what goes back.
        return try rows.map { row in
            let parts = try row.decode(column: "path", as: String.self)
                .split(separator: ",").map(String.init)
            return parts.dropFirst().joined(separator: ".")
        }
    }
    
    func verifyAccess(for authUser: AuthenticatedUser, to acl: ACLKey) async throws {
        var resources = [String]()
        
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
        
        // User must have license to use the app
        guard let aclAppId = apps[bundleId] else {
            throw api.error.AppDoesNotExist()
        }
        guard authUser.session.jwt.apps.contains(aclAppId) else {
            throw api.error.AccessDenied()
        }
        
        // What the roles this user holds add up to. Expanded here rather than at
        // the grant, so a route retagged between roles reaches them at once.
        var held = Set<ACLID>()
        for role in authUser.session.jwt.roles {
            if let permissions = rolePermissions[role] {
                held.formUnion(permissions)
            }
        }
        
        // Widen from the permission to the feature to the app: holding any of
        // them is enough. Nothing held at any width is a denial.
        while resources.count > 0 {
            let path = resources.joined(separator: ",")
            let acl = paths[path]
            if let acl, held.contains(acl) {
                return
            }
            resources.removeLast()
        }
        
        throw api.error.AccessDenied()
    }
    
    func issueAppLicense(session: Database.Session, id: ACLID, to user: User) async throws -> AppLicense {
        do {
            let license = try await appLicense(session: session, id: id, user: user)
            return license
        }
        catch { }
        
        let conn = try await session.conn()
        
        let rows = try await conn.select()
            .column("*")
            .from("acl")
            .where("id", .equal, SQLBind(id))
            .where("type", .equal, SQLBind(ACL.ACLType.app.rawValue))
            .all()
        guard rows.count > 0 else {
            throw service.error.DatabaseFailure("There is no app that exists with ACL ID (\(id))")
        }
        
        let createDate = Date.now
        let inserted = try await conn.sql().insert(into: "app_licenses")
            .columns("id", "create_date", "acl_id", "user_id")
            .values(
                SQLLiteral.null,
                SQLBind(createDate),
                SQLBind(id),
                SQLBind(user.id)
            )
            .returning("id")
            .all()

        return try .init(
            id: inserted[0].decode(column: "id", as: AppLicenseID.self),
            createDate: createDate,
            appAclId: id,
            userId: user.id
        )
    }
    
    func revokeAppLicense(session: Database.Session, id: ACLID, from user: User) async throws {
        let conn = try await session.conn()
        try await conn.sql().delete(from: "app_licenses")
            .where("acl_id", .equal, id)
            .where("user_id", .equal, user.id)
            .run()
    }

    func appLicense(session: Database.Session, id: ACLID, user: User) async throws -> AppLicense {
        let conn = try await session.conn()
        let rows = try await conn.select()
            .column("*")
            .from("app_licenses")
            .where("acl_id", .equal, SQLBind(id))
            .where("user_id", .equal, SQLBind(user.id))
            .all()
        
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        
        return try .init(
            id: row.decode(column: "id", as: AppLicenseID.self),
            createDate: row.decode(column: "create_date", as: Date.self),
            appAclId: row.decode(column: "acl_id", as: ACLID.self),
            userId: row.decode(column: "user_id", as: User.ID.self)
        )
    }
    
    func userApps(session: Database.Session, for user: User) async throws -> [ACLID] {
        let conn = try await session.conn()
        let rows = try await conn.select()
            .column("acl_id")
            .from("app_licenses")
            .where("user_id", .equal, user.id)
            .all()
        let ids = try rows.map { try $0.decode(column: "acl_id", as: ACLID.self) }
        return ids
    }
    
    func retiredAcl(session: Database.Session) async throws -> [ACL] {
        let conn = try await session.conn()
        return try await retiredAcl(conn: conn)
    }
    
    func pruneAcl(session: Database.Session) async throws -> Int {
        let conn = try await session.conn()
        let retired = try await retiredAcl(conn: conn)
        guard !retired.isEmpty else {
            return 0
        }
        try await conn.begin()
        do {
            try await deleteAcl(conn: conn, acl: retired)
            try await conn.commit()
        }
        catch {
            try await conn.rollback()
            throw error
        }
        for acl in retired {
            paths.removeValue(forKey: acl.path)
        }
        return retired.count
    }
    
    func rolePermissionCount(session: Database.Session, aclId: ACLID) async throws -> Int {
        let conn = try await session.conn()
        return try await conn.select()
            .column("*")
            .from("acl_role_permissions")
            .where("acl_id", .equal, SQLBind(aclId))
            .all()
            .count
    }
    
    func acl(session: Database.Session) async throws -> [ACL] {
        let conn = try await session.conn()
        return try await allAcls(conn: conn)
    }
    
    func aclApp(session: Database.Session, bundleId: BundleID) async throws -> ACLID? {
        return apps[bundleId]
    }
    
    func aclTree(session: Database.Session) async throws -> ACLTree {
        let conn = try await session.conn()
        let acls = try await allAcls(conn: conn).sorted { left, right in
            left.path < right.path
        }
        
        // Create intermediary structure used to create hierarchy
        var appInfo: [String: (id: Int, features: [String: (id: Int, perms: [ACLTree.Permission])])] = [:]
        
        for acl in acls {
            let parts = acl.path
                .components(separatedBy: ",")
                .map { $0.trimmingCharacters(in: .whitespaces) }
                .filter { !$0.isEmpty }
            
            guard !parts.isEmpty else {
                continue
            }
            let appName = parts[0]
            
            // app
            var app = appInfo[appName] ?? (id: 0, features: [:])
            if parts.count == 1 { // Override ID if this record represents the app
                app.id = acl.id
            }
            
            // feature (needs 2 parts)
            if parts.count >= 2 {
                let featureName = parts[1]
                var feature = app.features[featureName] ?? (id: 0, perms: [])
                if parts.count == 2 { // Override ID as this represents the feature record
                    feature.id = acl.id
                }
                
                // permission (needs 3 parts)
                if parts.count == 3, let permName = parts[safe: 2] {
                    feature.perms.append(.init(id: acl.id, name: permName))
                }
                app.features[featureName] = feature
            }
            appInfo[appName] = app
        }
        
        // Every role, and what each holds, fetched before the tree is built:
        // the transform below is synchronous.
        let roleRows = try await conn.select()
            .column("*")
            .from("acl_roles")
            .where("retired_date", .is, SQLLiteral.null)
            .all()
            .map(makeRole)
        let held = try await allRolePermissions(conn: conn)
        // A permission's path is `<app>,<feature>,<permission>`, and Settings
        // lists a role one line a feature — so it is split here rather than on
        // the screen.
        var featureOf = [ACLID: (feature: String, permission: String)]()
        for acl in acls where acl.type == .permission {
            let parts = acl.path.split(separator: ",").map(String.init)
            guard parts.count >= 3 else {
                continue
            }
            featureOf[acl.id] = (parts[1], parts[2])
        }
        var rolesByApp = [ACLID: [ACLTree.Role]]()
        for role in roleRows.sorted(by: { $0.name < $1.name }) {
            var byFeature = [String: [ACLTree.Permission]]()
            for id in held[role.id] ?? [] {
                guard let named = featureOf[id] else {
                    continue
                }
                byFeature[named.feature, default: []].append(
                    ACLTree.Permission(id: id, name: named.permission))
            }
            let features = byFeature
                .sorted { $0.key < $1.key }
                .map { name, permissions in
                    ACLTree.Feature(id: 0, name: name,
                                    permissions: permissions.sorted { $0.name < $1.name })
                }
            rolesByApp[role.appAclId, default: []].append(
                ACLTree.Role(id: role.id, name: role.name, features: features))
        }

        // Transform dictionary into objects
        let apps = appInfo
            .sorted(by: { $0.key < $1.key })
            .map { (appName, info) -> ACLTree.App in
                let features = info.features
                    .sorted(by: { $0.key < $1.key })
                    .map { (featName, featInfo) -> ACLTree.Feature in
                        return ACLTree.Feature(
                            id: featInfo.id,
                            name: featName,
                            permissions: featInfo.perms
                        )
                    }
                return ACLTree.App(id: info.id, name: appName,
                                   features: features,
                                   roles: rolesByApp[info.id] ?? [])
            }
        
        return ACLTree(apps: apps)
    }
    
    func cleanAcl(conn: Database.Connection, for userId: User.ID) async throws {
        try await conn.sql().delete(from: "app_licenses")
            .where("user_id", .equal, SQLBind(userId))
            .run()
        try await conn.sql().delete(from: "acl_role_items")
            .where("user_id", .equal, SQLBind(userId))
            .run()
    }
}

private extension ACLService {
    func makeAcl(from row: SQLRow) throws -> ACL {
        try .init(
            id: row.decode(column: "id", as: Int.self),
            createDate: row.decode(column: "create_date", as: Date.self),
            path: row.decode(column: "path", as: String.self),
            type: ACL.ACLType(rawValue: row.decode(column: "type", as: Int.self)) ?? .unknown,
            retiredDate: row.decode(column: "retired_date", as: Date?.self)
        )
    }
    
    /// Every registered ACL. A retired one is left out, which is what stops it
    /// reaching `paths` and answering a verification.
    func allAcls(conn: Database.Connection) async throws -> [ACL] {
        let rows = try await conn.select()
            .column("*")
            .from("acl")
            .where("retired_date", .is, SQLLiteral.null)
            .all()
        
        return try rows.map(makeAcl)
    }
    
    /// Everything registered under these bundles — the app record and every
    /// feature and permission beneath it.
    ///
    /// This is what a registration speaks for. A bundle it did not carry is
    /// left out, so one service reconciling its own apps cannot retire
    /// another's.
    func bundleAcl(conn: Database.Connection, bundles: Set<BundleID>) async throws -> [ACL] {
        guard !bundles.isEmpty else {
            return []
        }
        return try await allAcls(conn: conn).filter { acl in
            guard let bundle = acl.path.split(separator: ",").first else {
                return false
            }
            return bundles.contains(String(bundle))
        }
    }
    
    /// Every registered role, with the permissions it holds.
    func allRolePermissions(conn: Database.Connection) async throws -> [ACLRoleID: Set<ACLID>] {
        let rows = try await conn.select()
            .column(SQLColumn("role_id", table: "acl_role_permissions"))
            .column(SQLColumn("acl_id", table: "acl_role_permissions"))
            .from("acl_role_permissions")
            .join("acl_roles", on: SQLColumn("role_id", table: "acl_role_permissions"),
                  .equal, SQLColumn("id", table: "acl_roles"))
            .where(SQLColumn("retired_date", table: "acl_roles"), .is, SQLLiteral.null)
            .all()
        
        var held = [ACLRoleID: Set<ACLID>]()
        for row in rows {
            let roleId = try row.decode(column: "role_id", as: ACLRoleID.self)
            let aclId = try row.decode(column: "acl_id", as: ACLID.self)
            held[roleId, default: []].insert(aclId)
        }
        return held
    }
    
    func makeRole(from row: SQLRow) throws -> ACLRole {
        try .init(
            id: row.decode(column: "id", as: ACLRoleID.self),
            createDate: row.decode(column: "create_date", as: Date.self),
            appAclId: row.decode(column: "app_acl_id", as: ACLID.self),
            name: row.decode(column: "name", as: ACLRoleName.self),
            retiredDate: row.decode(column: "retired_date", as: Date?.self)
        )
    }
    
    func appRoles(conn: Database.Connection, appAclId: ACLID) async throws -> [ACLRole] {
        let rows = try await conn.select()
            .column("*")
            .from("acl_roles")
            .where("app_acl_id", .equal, SQLBind(appAclId))
            .where("retired_date", .is, SQLLiteral.null)
            .all()
        return try rows.map(makeRole)
    }
    
    /// Bring one app's roles up to what its payload names.
    ///
    /// An app naming none receives `default`, holding every feature it has —
    /// so an app works before it declares roles of its own, and gains them
    /// without a migration when it does.
    ///
    /// A role keeps its ID across this. What it holds is rebuilt, because a
    /// route moving from one role to another is the ordinary way this changes,
    /// and a grant names the role rather than the permission.
    func saveRoles(conn: Database.Connection, appAclId: ACLID,
                   bundleId: BundleID, app: ACLApp,
                   paths: ACLPathMap) async throws {
        var declared = app.roles
        if declared.isEmpty {
            declared = ["default": app.features]
        }
        
        // Everything this app has on record, retired or not, so a name that
        // comes back is revived rather than duplicated.
        let existing = try await conn.select()
            .column("*")
            .from("acl_roles")
            .where("app_acl_id", .equal, SQLBind(appAclId))
            .all()
            .map(makeRole)
        let byName = Dictionary(existing.map { ($0.name, $0) }, uniquingKeysWith: { a, _ in a })
        
        var live = Set<ACLRoleID>()
        for (roleName, features) in declared {
            let name = roleName.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !name.isEmpty else {
                throw api.error.InvalidParameter(name: "role")
            }
            
            let roleId: ACLRoleID
            if let role = byName[name] {
                roleId = role.id
                if role.retiredDate != nil {
                    try await conn.sql().update("acl_roles")
                        .set("retired_date", to: SQLLiteral.null)
                        .where("id", .equal, SQLBind(roleId))
                        .run()
                }
            }
            else {
                let inserted = try await conn.sql().insert(into: "acl_roles")
                    .columns("id", "create_date", "app_acl_id", "name", "retired_date")
                    .values(SQLLiteral.null, SQLBind(Date.now), SQLBind(appAclId),
                            SQLBind(name), SQLLiteral.null)
                    .returning("id")
                    .all()
                roleId = try inserted[0].decode(column: "id", as: ACLRoleID.self)
            }
            live.insert(roleId)
            
            // What it holds, rebuilt from the payload.
            try await conn.sql().delete(from: "acl_role_permissions")
                .where("role_id", .equal, SQLBind(roleId))
                .run()
            for feature in features {
                let parts = feature.components(separatedBy: ".")
                let path = parts.count > 1
                    ? "\(bundleId),\(parts[0]),\(parts[1])"
                    : "\(bundleId),\(parts[0])"
                guard let aclId = paths[path] else {
                    continue
                }
                try await conn.sql().insert(into: "acl_role_permissions")
                    .columns("id", "create_date", "role_id", "acl_id")
                    .values(SQLLiteral.null, SQLBind(Date.now), SQLBind(roleId),
                            SQLBind(aclId))
                    .run()
            }
        }
        
        // A role nothing names any more, retired rather than deleted: a user
        // holding it keeps the grant, and the name coming back revives it.
        let toRetire = existing.filter { $0.retiredDate == nil && !live.contains($0.id) }
        if !toRetire.isEmpty {
            try await conn.sql().update("acl_roles")
                .set("retired_date", to: SQLBind(Date.now))
                .where("id", .in, toRetire.map { $0.id })
                .run()
        }
    }
    
    func retiredAcl(conn: Database.Connection) async throws -> [ACL] {
        let rows = try await conn.select()
            .column("*")
            .from("acl")
            .where("retired_date", .isNot, SQLLiteral.null)
            .all()
        
        return try rows.map(makeAcl)
    }
    
    /// Stop answering for these, and keep everything pointing at them.
    ///
    /// The ID stays, so a token already naming it still names the same record
    /// when the name comes back. The grants and licenses stay, so nothing has
    /// to be re-issued.
    func retireAcl(conn: Database.Connection, acl: [ACL]) async throws {
        guard !acl.isEmpty else {
            return
        }
        try await conn.sql().update("acl")
            .set("retired_date", to: SQLBind(Date.now))
            .where("id", .in, acl.map { $0.id })
            .run()
    }
    
    /// Destroy these, and everything that referenced them.
    ///
    /// Reached by `pruneAcl`, which is asked for. Registration retires instead.
    func deleteAcl(conn: Database.Connection, acl: [ACL]) async throws {
        guard !acl.isEmpty else {
            return
        }
        let ids: [ACLID] = acl.map { $0.id }
        try await conn.sql().delete(from: "acl")
            .where("id", .in, ids)
            .run()
        try await conn.sql().delete(from: "app_licenses")
            .where("acl_id", .in, ids)
            .run()
        // The links a role holds. Left behind, they point at a row that is
        // gone — and SQLite hands a freed rowid to the next insert, so the
        // role would come to hold whatever takes its place.
        try await conn.sql().delete(from: "acl_role_permissions")
            .where("acl_id", .in, ids)
            .run()
    }
    
    func saveApps(
        conn: Database.Connection,
        apps: [ACLApp]
    ) async throws -> [ACL] {
        var paths = Set<ACLPath>()
        for app in apps {
            let bundleId = app.bundleId.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !bundleId.isEmpty else {
                throw api.error.InvalidParameter(name: "bundleId")
            }

            paths.insert(bundleId)
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

                if  let permission = parts[safe: 1] {
                    guard !permission.isEmpty else {
                        throw api.error.InvalidParameter(name: "feature", expected: "A permission name must have at least one character")
                    }
                    paths.insert("\(bundleId),\(featureName)")
                    paths.insert("\(bundleId),\(featureName),\(permission)")
                }
                else {
                    paths.insert("\(bundleId),\(featureName)")
                }
            }
        }
        
        var acl = [ACL]()
        for path in paths.sorted() {
            try await acl.append(saveAcl(conn: conn, path: path))
        }
        return acl
    }
    
    func getAcl(conn: Database.Connection, path: String) async throws -> ACL? {
        let rows = try await conn.select()
            .column("*")
            .from("acl")
            .where("path", .equal, SQLBind(path))
            .all()
        
        if rows.count > 1 {
            throw service.error.DatabaseFailure("Found multiple ACLs for the same path")
        }

        return rows.isEmpty ? nil : try rows.first.map(makeAcl)
    }
    
    func saveAcl(conn: Database.Connection, path: String) async throws -> ACL {
        if let acl = try await getAcl(conn: conn, path: path) {
            guard acl.retiredDate != nil else {
                return acl
            }
            // The name came back. Revive the record rather than making a second
            // one: its ID is in every token that named it, and its grants and
            // licenses are still attached.
            try await conn.sql().update("acl")
                .set("retired_date", to: SQLLiteral.null)
                .where("id", .equal, SQLBind(acl.id))
                .run()
            return ACL(id: acl.id, createDate: acl.createDate, path: acl.path,
                       type: acl.type, retiredDate: nil)
        }
        
        let parts = path.trimmingCharacters(in: .whitespacesAndNewlines).split(separator: ",")
        guard let type = ACL.ACLType(rawValue: parts.count) else {
            throw service.error.InvalidInput("Invalid ACL type from path (\(path))")
        }
        let createDate = Date.now
        let inserted = try await conn.sql().insert(into: "acl")
            .columns("id", "create_date", "path", "type")
            .values(
                SQLLiteral.null,
                SQLBind(createDate),
                SQLBind(path),
                // 1 = App, 2 = Feature, 3 = Permission
                SQLBind(parts.count)
            )
            .returning("id")
            .all()

        return ACL(
            id: try inserted[0].decode(column: "id", as: ACLID.self),
            createDate: createDate,
            path: path,
            type: type,
            retiredDate: nil
        )
    }
}
