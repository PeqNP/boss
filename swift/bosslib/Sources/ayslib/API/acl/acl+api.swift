/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

extension api {
    public nonisolated(unsafe) internal(set) static var acl = ACLAPI()
}

public class ACLAPI {
    nonisolated(unsafe) var _checkAccess: (AuthenticatedUser, ACLObject, ACLOp) throws -> Void

    init() {
        self._checkAccess = ayslib.checkAccess(authUser:object:op:)
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
        try _checkAccess(authUser, object, op)
    }
}

private func checkAccess(authUser: AuthenticatedUser, object: ACLObject, op: ACLOp) throws {
    guard !authUser.isSuperUser else {
        return
    }
    guard authUser.verified else {
        throw api.error.UserIsNotVerified()
    }
    guard authUser.enabled else {
        throw api.error.UserNotFound()
    }
    guard !object.acl.isEmpty else {
        throw api.error.AccessDenied()
    }
    for _acl in object.acl {
        try checkAccess(user: authUser.user, type: _acl.type, ops: _acl.operations, op: op)
    }
}

private func checkAccess(user: User, type: ACL.EntityType, ops: [ACLOp], op: ACLOp) throws {
    switch type {
    case .all:
        if ops.contains(op) {
            return
        }
    case let .individual(userID):
        if user.id == userID && ops.contains(op) {
            return
        }
    case let .group(userIDs):
        if userIDs.contains(user.id) && ops.contains(op) {
            return
        }
    case let .entities(entities):
        for entity in entities {
            try checkAccess(user: user, type: entity.type, ops: ops, op: op)
        }
        return
    }
    throw api.error.AccessDenied()
}
