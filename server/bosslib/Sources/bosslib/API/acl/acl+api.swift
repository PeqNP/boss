/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

extension api {
    public nonisolated(unsafe) internal(set) static var acl = ACLAPI(provider: ACLService())
}

public protocol ACLProvider {
    func checkAccess(authUser: AuthenticatedUser, object: ACLObject, op: ACLOp) throws
}

public class ACLAPI {
    let p: ACLProvider

    init(provider: ACLProvider) {
        self.p = provider
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
    public func checkAccess(authUser: AuthenticatedUser, object: ACLObject, op: ACLOp) throws {
        try p.checkAccess(authUser: authUser, object: object, op: op)
    }
}
