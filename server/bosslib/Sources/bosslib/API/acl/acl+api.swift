/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

extension api {
    public nonisolated(unsafe) internal(set) static var acl = ACLAPI(provider: ACLService())
}

public protocol ACLProvider {
    func createAclCatalog(session: Database.Session, for name: String, apps: [ACLApp]) async throws -> ACLPathMap
    func assignAccessToAcl(session: Database.Session, id: ACLID, to user: User) async throws -> ACLItem
    func assignAccessToAcl(session: Database.Session, ids: [ACLID], to user: User) async throws -> [ACLItem]
    func removeAccessToAcl(session: Database.Session, id: ACLID, from user: User) async throws
    func removeAccessToAcl(session: Database.Session, ids: [ACLID], from user: User) async throws
    func verifyAccess(for authUser: AuthenticatedUser, to acl: ACLKey) async throws
    func issueAppLicense(session: Database.Session, id: ACLID, to user: User) async throws -> AppLicense
    func revokeAppLicense(session: Database.Session, id: ACLID, from user: User) async throws
    func appLicense(session: Database.Session, id: ACLID, user: User) async throws -> AppLicense
    func userApps(session: Database.Session, for user: User) async throws -> [ACLID]
    func userAcl(session: Database.Session, for user: User) async throws -> [ACLID]
    func acl(session: Database.Session) async throws -> [ACL]
    func aclApp(session: Database.Session, bundleId: BundleID) async throws -> ACLID?
    func aclTree(session: Database.Session) async throws -> ACLTree
}

public class ACLAPI {
    let p: ACLProvider

    init(provider: ACLProvider) {
        self.p = provider
    }
    
    /// Create a new ACL catalog.
    ///
    /// Creating a new ACL catalog will also refresh the catalog in-memory so that future requests will have immediate access to the most up-to-date catalog info.
    public func createAclCatalog(
        session: Database.Session = Database.session(),
        for name: String,
        apps: [ACLApp]
    ) async throws -> ACLPathMap {
        try await p.createAclCatalog(session: session, for: name, apps: apps)
    }
    
    /// Assign access to an ACL record.
    @discardableResult
    public func assignAccessToAcl(
        session: Database.Session = Database.session(),
        id: ACLID,
        to user: User
    ) async throws -> ACLItem {
        guard !user.isSuperUser else {
            throw api.error.SuperUserRequiresNoPrivilege()
        }
        return try await p.assignAccessToAcl(session: session, id: id, to: user)
    }
    
    /// Set all ACL that should be assigned to the user.
    ///
    /// This will remove ACL, that is already associated to the user, if it does not exist in the list of ACL IDs that belong to the app.
    ///
    /// - Parameter session:
    /// - Parameter ids: All ACLs that should be assigned to the user
    /// - Parameter user: The user to assign ACLs to
    @discardableResult
    public func assignAccessToAcl(
        session: Database.Session = Database.session(),
        ids: [ACLID],
        to user: User
    ) async throws -> [ACLItem] {
        guard !user.isSuperUser else {
            throw api.error.SuperUserRequiresNoPrivilege()
        }
        return try await p.assignAccessToAcl(session: session, ids: ids, to: user)
    }
    
    /// Remove access to ACL record.
    public func removeAccessToAcl(
        session: Database.Session = Database.session(),
        id: ACLID,
        from user: User
    ) async throws {
        guard !user.isSuperUser else {
            throw api.error.SuperUserRequiresNoPrivilege()
        }
        try await p.removeAccessToAcl(session: session, id: id, from: user)
    }
    
    /// Remove access to multiple ACL records at once.
    public func removeAccessToAcl(
        session: Database.Session = Database.session(),
        ids: [ACLID],
        from user: User
    ) async throws {
        guard !user.isSuperUser else {
            throw api.error.SuperUserRequiresNoPrivilege()
        }
        try await p.removeAccessToAcl(session: session, ids: ids, from: user)
    }
    
    /// Verify that user has access to permission.
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
    
    /// Get all ACL IDs assigned to user.
    public func userAcl(
        session: Database.Session = Database.session(),
        for user: User
    ) async throws -> [ACLID] {
        try await p.userAcl(session: session, for: user)
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
}
