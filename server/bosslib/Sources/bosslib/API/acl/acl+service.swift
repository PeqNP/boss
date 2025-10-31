/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

struct ACLService: ACLProvider {
    // MARK: - BOSS ACL
    
    func createApp(_ bundleId: String) async throws -> ACLApp {
        let bundleId = bundleId.trimmingCharacters(in: .whitespacesAndNewlines)
        guard bundleId.count > 0 else {
            throw api.error.InvalidParameter(name: "bundleId")
        }
        return .init(bundleId: bundleId, features: [])
    }
    
    func createAcl(for bundleId: String, feature: String) async throws -> ACLItem {
        let bundleId = bundleId.trimmingCharacters(in: .whitespacesAndNewlines)
        guard bundleId.count > 0 else {
            throw api.error.InvalidParameter(name: "bundleId")
        }
        let feature = feature.trimmingCharacters(in: .whitespacesAndNewlines)
        guard feature.count > 0 else {
            throw api.error.InvalidParameter(name: "feature")
        }
        
        let parts = feature.split(separator: ".")
        guard parts.count == 2 else {
            throw api.error.InvalidParameter(name: "feature", expected: "String with a dot separator")
        }
        let name = String(parts[0])
        guard name.count > 0 else {
            throw api.error.InvalidParameter(name: "feature", expected: "First part must be a feature name with at least one character")
        }
        let permission = String(parts[1])
        guard permission.count > 0 else {
            throw api.error.InvalidParameter(name: "feature", expected: "Second part must be a permission name with at least one character")
        }
        
        return .init(id: 0, bundleId: bundleId, name: name, permission: permission)
    }
    
    func createAclCatalog(for serviceName: String, apps: [ACLApp]) async throws -> ACLCatalog {
        let serviceName = serviceName.trimmingCharacters(in: .whitespacesAndNewlines)
        guard serviceName.count > 0 else {
            throw api.error.InvalidParameter(name: "serviceName")
        }
        
        // TODO: Make sure ACLApps have valid names, etc.
        
        return .init(id: 0, name: serviceName, apps: apps)
    }
    
    func assignAccessToApp(_ bundleId: String, to user: User) async throws {
        
    }
    
    func verifyAccess(for user: User, to bundleId: String) async throws {
        
    }
    
    func verifyAccess(for user: User, to bundleId: String, feature: String) async throws {
        
    }
    
    // MARK: - Node ACL
    
    func checkAccess(for authUser: AuthenticatedUser, object: ACLObject, op: ACLOp) throws {
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
