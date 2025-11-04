/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

extension api {
    public nonisolated(unsafe) internal(set) static var acl = ACLAPI(provider: ACLService())
}

public protocol ACLProvider {
    func createAclCatalog(session: Database.Session, for name: String, apps: [ACLApp]) async throws -> ACLCatalog
    func assignAccessToAcl(session: Database.Session, id: Int, to user: User) async throws
    func assignAccessToAcl(session: Database.Session, ids: [Int], to user: User) async throws
    func verifyAccess(for authUser: AuthenticatedUser, to acl: ACLKey) async throws
    func userAcl(session: Database.Session, for user: User) async throws -> [ACLID]
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
    ) async throws -> ACLCatalog {
        try await p.createAclCatalog(session: session, for: name, apps: apps)
    }
    
    /// Assign access to an ACL record.
    public func assignAccessToAcl(
        session: Database.Session = Database.session(),
        id: Int,
        to user: User
    ) async throws {
        try await p.assignAccessToAcl(session: session, id: id, to: user)
    }
    
    /// Assign access to multiple ACL records at once.
    public func assignAccessToAcl(
        session: Database.Session = Database.session(),
        ids: [Int],
        to user: User
    ) async throws {
        try await p.assignAccessToAcl(session: session, ids: ids, to: user)
    }
    
    /// Verify that user has access to permission.
    public func verifyAccess(for authUser: AuthenticatedUser, to acl: ACLKey) async throws {
        try await p.verifyAccess(for: authUser, to: acl)
    }
    
    func userAcl(
        session: Database.Session = Database.session(),
        for user: User
    ) async throws -> [ACLID] {
        try await p.userAcl(session: session, for: user)
    }
}
