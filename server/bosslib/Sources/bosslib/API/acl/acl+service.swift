/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

class ACLService: ACLProvider {
    private var catalog: ACLCatalog = .init(paths: [:])
    
//    private func createAcl(for bundleId: String, feature: String) async throws -> ACLItem {
//        let bundleId = bundleId.trimmingCharacters(in: .whitespacesAndNewlines)
//        guard bundleId.count > 0 else {
//            throw api.error.InvalidParameter(name: "bundleId")
//        }
//        let feature = feature.trimmingCharacters(in: .whitespacesAndNewlines)
//        guard feature.count > 0 else {
//            throw api.error.InvalidParameter(name: "feature")
//        }
//        
//        let parts = feature.split(separator: ".")
//        guard parts.count == 2 else {
//            throw api.error.InvalidParameter(name: "feature", expected: "String with a dot separator")
//        }
//        let name = String(parts[0])
//        guard name.count > 0 else {
//            throw api.error.InvalidParameter(name: "feature", expected: "First part must be a feature name with at least one character")
//        }
//        let permission = String(parts[1])
//        guard permission.count > 0 else {
//            throw api.error.InvalidParameter(name: "feature", expected: "Second part must be a permission name with at least one character")
//        }
//        
//        return .init(id: 0, bundleId: bundleId, name: name, permission: permission)
//    }
    
    func createAclCatalog(for name: String, apps: [ACLApp]) async throws -> ACLCatalog {
        let name = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard name.count > 0 else {
            throw api.error.InvalidParameter(name: "name")
        }
        
        var acls = [ACL]()
        let _catalog = try await saveAclCatalog(name: name)
        acls.append(_catalog)
        for app in apps {
            let _app = try await saveAclApp(catalog: name, bundleId: app.bundleId)
            acls.append(_app)
            // TODO: ACLApp must have valid name
            for feature in app.features {
                // TODO: ACL feature must have valid name, must have valid first part, second (if given)
                let parts = feature.components(separatedBy: ".")
                let acl = try await saveAcl(catalog: name, bundleId: app.bundleId, feature: feature, permission: parts[safe: 1])
                acls.append(acl)
            }
        }
        
        // TODO: Given all ACL that was just registered, for any missing, for the given catalog, they should be removed.
        // TODO: Refresh all catalogs
        
        catalog = .init(paths: [:])
        
        return .init(paths: [:])
    }
    
    func assignAccessToAcl(id: Int, to user: User) async throws {
        
    }
    
    func assignAccessToAcl(ids: [Int], to user: User) async throws {
        
    }

    func verifyAccess(for authUser: AuthenticatedUser, to acl: ACLKey) async throws {
        // TODO: Verify
    }
}

private extension ACLService {
    func saveAclCatalog(name: String) async throws -> ACL {
        // TODO: Check if catalog exists first
        .init(id: 0, createDate: .now, path: name)
    }
    
    func saveAclApp(catalog: String, bundleId: String) async throws -> ACL {
        // TODO: Check if app exists first
        .init(id: 0, createDate: .now, path: "\(catalog),\(bundleId)")
    }
    
    func saveAcl(catalog: String, bundleId: String, feature: String, permission: String?) async throws -> ACL {
        // TODO: Check if resource exists first
        if let permission {
            .init(id: 0, createDate: .now, path: "\(catalog),\(bundleId),\(feature),\(permission)")
        }
        else {
            .init(id: 0, createDate: .now, path: "\(catalog),\(bundleId),\(feature)")
        }
    }
}
