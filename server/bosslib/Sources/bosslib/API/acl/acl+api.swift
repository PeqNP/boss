/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

extension api {
    public nonisolated(unsafe) internal(set) static var acl = ACLAPI(provider: ACLService())
}

public protocol ACLProvider {
    // BOSS ACL
    func createAclCatalog(for name: String, apps: [ACLApp]) async throws -> ACLCatalog
    func assignAccessToApp(_ bundleId: String, to user: User) async throws
    func assignAccessToAppFeature(_ bundleId: String, _ feature: String, to user: User) async throws
    func verifyAccess(for user: User, to bundleId: String) async throws
    func verifyAccess(for user: User, to bundleId: String, feature: String) async throws
    
    // Node ACL
    func checkAccess(for user: AuthenticatedUser, object: ACLObject, op: ACLOp) throws
}

public class ACLAPI {
    let p: ACLProvider

    init(provider: ACLProvider) {
        self.p = provider
    }
        
    public func createAclCatalog(for name: String, apps: [ACLApp]) async throws -> ACLCatalog {
        try await p.createAclCatalog(for: name, apps: apps)
    }
    
    public func assignAccessToApp(_ bundleId: String, to user: User) async throws {
        try await p.assignAccessToApp(bundleId, to: user)
    }
    
    public func assignAccessToAppFeature(_ bundleId: String, _ feature: String, to user: User) async throws {
        try await p.assignAccessToAppFeature(bundleId, feature, to: user)
    }
    
    public func verifyAccess(for user: User, to bundleId: String) async throws {
        try await p.verifyAccess(for: user, to: bundleId)
    }
    
    public func verifyAccess(for user: User, to bundleId: String, feature: String) async throws {
        try await p.verifyAccess(for: user, to: bundleId, feature: feature)
    }

    /// Check user's access to ACL object.
    ///
    /// Exampe to check if the guest user has `read` access to `node`.
    /// ```
    /// checkAccess(authUser: guestUser(), object: node, op: .read)
    /// ```
    ///
    /// - Parameters:
    ///   - authUser: Authenticated user
    ///   - object: Object to test ACL against user's permissions
    ///   - op: The ACL object to test for
    public func checkAccess(for user: AuthenticatedUser, object: ACLObject, op: ACLOp) throws {
        try p.checkAccess(for: user, object: object, op: op)
    }
}
