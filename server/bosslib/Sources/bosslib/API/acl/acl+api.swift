/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

extension api {
    public nonisolated(unsafe) internal(set) static var acl = ACLAPI(provider: ACLService())
}

public protocol ACLProvider {
    func createAclCatalog(for name: String, apps: [ACLApp]) async throws -> ACLCatalog
    func assignAccessToAcl(id: Int, to user: User) async throws
    func assignAccessToAcl(ids: [Int], to user: User) async throws
    func verifyAccess(for authUser: AuthenticatedUser, to acl: ACLKey) async throws
}

public class ACLAPI {
    let p: ACLProvider

    init(provider: ACLProvider) {
        self.p = provider
    }
    
    /// Create a new ACL catalog.
    ///
    /// Creating a new ACL catalog will also refresh the catalog in-memory so that future requests will have immediate access to the most up-to-date catalog info.
    public func createAclCatalog(for name: String, apps: [ACLApp]) async throws -> ACLCatalog {
        try await p.createAclCatalog(for: name, apps: apps)
    }
    
    /// Assign access to an ACL record.
    public func assignAccessToAcl(id: Int, to user: User) async throws {
        try await p.assignAccessToAcl(id: id, to: user)
    }
    
    /// Assign access to multiple ACL records at once.
    public func assignAccessToAcl(ids: [Int], to user: User) async throws {
        try await p.assignAccessToAcl(ids: ids, to: user)
    }
    
    /// Verify that user has access to permission
    public func verifyAccess(for authUser: AuthenticatedUser, to acl: ACLKey) async throws {
        try await p.verifyAccess(for: authUser, to: acl)
    }
}
