/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

struct ACLService: ACLProvider {
    func checkAccess(authUser: AuthenticatedUser, object: ACLObject, op: ACLOp) throws {
        guard !authUser.isSuperUser else {
            return
        }
        guard authUser.enabled else {
            throw api.error.UserNotFound()
        }
        guard authUser.verified else {
            throw api.error.UserIsNotVerified(authUser.user)
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
}
