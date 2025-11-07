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
    func userAcl(session: Database.Session, for user: User) async throws -> [ACLID]
    func acl(session: Database.Session) async throws -> [ACL]
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
        try await p.assignAccessToAcl(session: session, id: id, to: user)
    }
    
    /// Assign access to multiple ACL records at once.
    @discardableResult
    public func assignAccessToAcl(
        session: Database.Session = Database.session(),
        ids: [ACLID],
        to user: User
    ) async throws -> [ACLItem] {
        try await p.assignAccessToAcl(session: session, ids: ids, to: user)
    }
    
    /// Remove access to ACL record.
    public func removeAccessToAcl(
        session: Database.Session = Database.session(),
        id: ACLID,
        from user: User
    ) async throws {
        try await p.removeAccessToAcl(session: session, id: id, from: user)
    }
    
    /// Remove access to multiple ACL records at once.
    public func removeAccessToAcl(
        session: Database.Session = Database.session(),
        ids: [ACLID],
        from user: User
    ) async throws {
        try await p.removeAccessToAcl(session: session, ids: ids, from: user)
    }
    
    /// Verify that user has access to permission.
    public func verifyAccess(for authUser: AuthenticatedUser, to acl: ACLKey) async throws {
        try await p.verifyAccess(for: authUser, to: acl)
    }
    
    /// Get all ACL IDs assigned to user.
    func userAcl(
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
    
    /// Get hierchical representation of ACL tree.
    ///
    /// Useful for UI. Should only be accessed by admins.
    public func aclTree(
        session: Database.Session = Database.session()
    ) async throws -> ACLTree {
        try await p.aclTree(session: session)
    }
}
