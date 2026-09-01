/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

extension api {
    public nonisolated(unsafe) internal(set) static var acl = ACLAPI(provider: ACLService())
}

public protocol ACLProvider {
    func aclPaths() -> ACLPathMap
    func registerApps(session: Database.Session, _ apps: [ACLApp]) async throws -> ACLPathMap
    func verifyAccess(for authUser: AuthenticatedUser, to acl: ACLKey) async throws
    func assignRole(session: Database.Session, id: ACLRoleID, to user: User) async throws
    func removeRole(session: Database.Session, id: ACLRoleID, from user: User) async throws
    func userRoles(session: Database.Session, for user: User) async throws -> [ACLRoleID]
    func roles(session: Database.Session, bundleId: BundleID) async throws -> [ACLRole]
    func roleFeatures(session: Database.Session, id: ACLRoleID) async throws -> [ACLFeature]
    func rolePermissionCount(session: Database.Session, aclId: ACLID) async throws -> Int
    func retiredAcl(session: Database.Session) async throws -> [ACL]
    func pruneAcl(session: Database.Session) async throws -> Int
    func issueAppLicense(session: Database.Session, id: ACLID, to user: User) async throws -> AppLicense
    func revokeAppLicense(session: Database.Session, id: ACLID, from user: User) async throws
    func appLicense(session: Database.Session, id: ACLID, user: User) async throws -> AppLicense
    func userApps(session: Database.Session, for user: User) async throws -> [ACLID]
    func acl(session: Database.Session) async throws -> [ACL]
    func aclApp(session: Database.Session, bundleId: BundleID) async throws -> ACLID?
    func aclTree(session: Database.Session) async throws -> ACLTree
    
    func cleanAcl(conn: Database.Connection, for userId: User.ID) async throws
}

public class ACLAPI {
    let p: ACLProvider

    init(provider: ACLProvider) {
        self.p = provider
    }
    
    /// Every registered path, and the ID it stands for, as held in memory.
    public func aclPaths() -> ACLPathMap {
        p.aclPaths()
    }
    
    /// Bring BOSS up to what these apps have.
    ///
    /// Called by an app's backend once its routes are registered. Only the apps
    /// carried are reconciled — everything else is left alone, an app that
    /// failed to start looking exactly like an app with nothing in it.
    ///
    /// The in-memory paths are refreshed here, so the next request verifies
    /// against what was just registered.
    ///
    /// An app has one backend. Two services registering the same bundle each
    /// overwrite the other's roles, and neither is told.
    public func registerApps(
        session: Database.Session = Database.session(),
        _ apps: [ACLApp]
    ) async throws -> ACLPathMap {
        try await p.registerApps(session: session, apps)
    }
    
    /// Give a user a role.
    ///
    /// A role rather than the permissions it holds: what the role holds is
    /// resolved when a request arrives, so retagging a route reaches everyone
    /// holding the role without re-granting them.
    ///
    /// Takes effect at the holder's next sign-in, the roles being minted into
    /// their token.
    public func assignRole(
        session: Database.Session = Database.session(),
        id: ACLRoleID,
        to user: User
    ) async throws {
        try await p.assignRole(session: session, id: id, to: user)
    }
    
    /// Take a role away from a user.
    public func removeRole(
        session: Database.Session = Database.session(),
        id: ACLRoleID,
        from user: User
    ) async throws {
        try await p.removeRole(session: session, id: id, from: user)
    }
    
    /// The roles a user holds, across every app.
    public func userRoles(
        session: Database.Session = Database.session(),
        for user: User
    ) async throws -> [ACLRoleID] {
        try await p.userRoles(session: session, for: user)
    }
    
    /// The roles an app declared, as its routes named them.
    ///
    /// An app that declared none has one called `default`, holding every
    /// feature it has.
    public func roles(
        session: Database.Session = Database.session(),
        bundleId: BundleID
    ) async throws -> [ACLRole] {
        try await p.roles(session: session, bundleId: bundleId)
    }
    
    /// The features a role holds, as `<feature>.<permission>`.
    public func roleFeatures(
        session: Database.Session = Database.session(),
        id: ACLRoleID
    ) async throws -> [ACLFeature] {
        try await p.roleFeatures(session: session, id: id)
    }
    
    /// How many roles hold this permission. Zero once it has been pruned.
    public func rolePermissionCount(
        session: Database.Session = Database.session(),
        aclId: ACLID
    ) async throws -> Int {
        try await p.rolePermissionCount(session: session, aclId: aclId)
    }
    
    /// Every ACL that stopped being registered, and is waiting to be pruned.
    ///
    /// Read this before pruning: each one still carries the grants and licenses
    /// that pruning destroys.
    public func retiredAcl(
        session: Database.Session = Database.session()
    ) async throws -> [ACL] {
        try await p.retiredAcl(session: session)
    }
    
    /// Permanently remove every retired ACL, and the grants and licenses that
    /// referenced it. Returns how many were removed.
    ///
    /// This is the only path that destroys a grant. Registration retires rather
    /// than deletes, because an app that failed to load looks exactly like an
    /// app with nothing in it — so removing what a registration did not carry
    /// is something somebody asks for, having seen what goes with it.
    @discardableResult
    public func pruneAcl(
        session: Database.Session = Database.session()
    ) async throws -> Int {
        try await p.pruneAcl(session: session)
    }
    
    public func verifyAccess(for authUser: AuthenticatedUser, to acl: ACLKey) async throws {
        guard !authUser.isSuperUser else {
            return
        }
        try await p.verifyAccess(for: authUser, to: acl)
    }
    
    /// Issue an app license to a user.
    ///
    /// This should only ever be called by administrators or system processes responsible for issuing licenses -- such as when a user purchases a license.
    public func issueAppLicense(
        session: Database.Session = Database.session(),
        id: ACLID,
        to user: User
    ) async throws -> AppLicense {
        try await p.issueAppLicense(session: session, id: id, to: user)
    }
    
    /// Revoke an app license from a user.
    ///
    /// This should only ever be called by administrators or system processes responsible for issuing licenses -- such as when a user purchases a license.
    public func revokeAppLicense(
        session: Database.Session = Database.session(),
        id: ACLID,
        from user: User
    ) async throws {
        try await p.revokeAppLicense(session: session, id: id, from: user)
    }
    
    /// Return the app license associated to user.
    ///
    /// Do not use this method for super users as they have a license to all apps.
    ///
    /// - Parameter session:
    /// - Parameter id: The app's ACLID
    /// - Parameter user: The user requesting if they have an app license
    /// - Returns: `AppLicense` for user
    public func appLicense(
        session: Database.Session = Database.session(),
        id: ACLID,
        user: User
    ) async throws -> AppLicense {
        return try await p.appLicense(session: session, id: id, user: user)
    }
    
    /// Get all apps the user has access to
    public func userApps(
        session: Database.Session = Database.session(),
        for user: User
    ) async throws -> [ACLID] {
        try await p.userApps(session: session, for: user)
    }
        
    /// Get ACL.
    ///
    /// - Returns: All ACL if user is an admin. User ACL if not an admin.
    public func acl(
        session: Database.Session = Database.session(),
        for user: User
    ) async throws -> [ACL] {
        try await p.acl(session: session)
    }
    
    /// Return the app ACLID for respective bundle ID.
    ///
    /// This is used to check if an app has ACL. If it has no ACL, it is assumed the app does not require a license to use.
    public func aclApp(
        session: Database.Session = Database.session(),
        bundleId: BundleID
    ) async throws -> ACLID? {
        try await p.aclApp(session: session, bundleId: bundleId)
    }
    
    /// Get hierchical representation of ACL tree.
    ///
    /// Useful for UI. Should only be accessed by admins.
    public func aclTree(
        session: Database.Session = Database.session()
    ) async throws -> ACLTree {
        try await p.aclTree(session: session)
    }
    
    /// Remove all traces of user from ACL.
    public func cleanAcl(
        conn: Database.Connection,
        for userId: User.ID
    ) async throws {
        try await p.cleanAcl(conn: conn, for: userId)
    }
}
