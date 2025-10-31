/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

extension api {
    public nonisolated(unsafe) internal(set) static var acl = ACLAPI(provider: ACLService())
}

public protocol ACLProvider {
    // BOSS ACL
    func createApp(_ bundleId: String) async throws -> ACLApp
    func createAcl(for bundleId: String, feature: String) async throws -> ACLItem
    func createAclCatalog(for serviceName: String, apps: [ACLApp]) async throws -> ACLCatalog
    func assignAccessToApp(_ bundleId: String, to user: User) async throws
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
    
    func createApp(_ bundleId: String) async throws -> ACLApp {
        try await p.createApp(bundleId)
    }
    
    func createAcl(for bundleId: String, feature: String) async throws -> ACLItem {
        try await p.createAcl(for: bundleId, feature: feature)
    }
    
    func createAclCatalog(for serviceName: String, apps: [ACLApp]) async throws -> ACLCatalog {
        try await p.createAclCatalog(for: serviceName, apps: apps)
    }
    
    func assignAccessToApp(_ bundleId: String, to user: User) async throws {
        try await p.assignAccessToApp(bundleId, to: user)
    }
    
    func verifyAccess(for user: User, to bundleId: String) async throws {
        try await p.verifyAccess(for: user, to: bundleId)
    }
    
    func verifyAccess(for user: User, to bundleId: String, feature: String) async throws {
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
