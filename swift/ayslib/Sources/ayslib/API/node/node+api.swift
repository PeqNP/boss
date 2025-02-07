/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

extension Global {
    static let reservedNodeNames: [String] = ["measurements", "c", "xff"]
    static let nodeNameValidChars = "abcdefghijklmnopqrstuvwxyz0123456789_-"
    static let nodeNameValidFirstChars = "abcdefghijklmnopqrstuvwxyz"
    static let maxNodeNameLength = 30
}

extension api {
    public nonisolated(unsafe) internal(set) static var node = NodeAPI()
}

public class NodeAPI {
    var _createOrgNode: (Database.Session, AuthenticatedUser, NodePath?, OrgConfig, User) async throws -> Node
    var _createNode: (Database.Session, AuthenticatedUser, NodePath, NodeType, String?, String?, [Contact]?, [NodeProperty]?, [ACL]?) async throws -> Node
    var _node: (Database.Session, AuthenticatedUser, NodePath?) async throws -> Node
    var _nodeWithID: (Database.Session, AuthenticatedUser, NodeID?) async throws -> Node

    init() {
        self._createOrgNode = ayslib.createOrgNode
        self._createNode = ayslib.createNode
        self._node = ayslib.node(session:user:path:)
        self._nodeWithID = ayslib.node(session:user:nodeID:)
    }

    public func createOrgNode(
        session: Database.Session = Database.session(),
        admin: AuthenticatedUser,
        path: NodePath?,
        config: OrgConfig,
        owner: User
    ) async throws -> Node {
        try await _createOrgNode(session, admin, path, config, owner)
    }

    public func createNode(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        path: NodePath,
        type: NodeType,
        logo: String? = nil,
        description: String? = nil,
        contacts: [Contact]? = nil,
        properties: [NodeProperty]? = nil,
        acl: [ACL]? = nil
    ) async throws -> Node {
        try await _createNode(session, user, path, type, logo, description, contacts, properties, acl)
    }

    public func node(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        path: NodePath?
    ) async throws -> Node {
        try await _node(session, user, path)
    }

    public func node(
        session: Database.Session = Database.session(),
        user: AuthenticatedUser,
        nodeID: NodeID?
    ) async throws -> Node {
        try await _nodeWithID(session, user, nodeID)
    }
}

private func createOrgNode(
    session: Database.Session,
    // FIXME: Is this user really needed anymore?
    admin: AuthenticatedUser,
    path: NodePath?,
    config: OrgConfig,
    owner: User
) async throws -> Node {
    guard admin.isSuperUser else {
        throw api.error.AdminRequired()
    }
    // Must be valid org node path
    let orgPath = try validateNodePath(stringValue(path, field: .orgPath))
    let parts = orgPath.split(separator: ".")
    guard parts.count == 2 else {
        throw api.error.InvalidOrganization(path: orgPath)
    }

    let conn = try await session.conn()

    let tld = String(parts[0])
    guard try await service.node.nodeExists(conn: conn, path: tld) else {
        throw api.error.TLDDoesNotExist(tld: tld)
    }

    do {
        let node = try await api.node.createNode(
            session: session,
            user: AuthenticatedUser(user: owner, peer: admin.peer),
            path: orgPath,
            type: .group,
            logo: nil,
            description: nil,
            contacts: nil,
            properties: nil,
            acl: nil
        )
        return node
    } catch _ as api.error.NodeExists {
        // Rethrow as different error to provide more detailed information
        throw api.error.OrgNodeExists(path: orgPath)
    }
}

private func createNode(
    session: Database.Session,
    user: AuthenticatedUser,
    path: NodePath,
    type: NodeType,
    logo: String?,
    description: String?,
    contacts: [Contact]?,
    properties: [NodeProperty]?,
    acl: [ACL]?
) async throws -> Node {
    guard !user.isGuestUser else {
        throw ays.Error("Guest user can not create nodes.")
    }
    let conn = try await session.conn()

    guard !(try await service.node.nodeExists(conn: conn, path: path)) else {
        throw api.error.NodeExists(path: path)
    }

    // TODO: User must have access to parent node
    // Ignore if TLD (i.e. this is for creating a new account)

    try await conn.begin()
    let node = try await service.node.createNode(
        conn: conn,
        path: path,
        type: type,
        acl: acl ?? [.makeOwnerACL(using: user.user)]
    )

    // TODO: Update additional properties

    try await conn.commit()
    log.i("Created node (\(node.path))")
    if !node.isTld {
        try await api.health.stageNodeHealth(session: session, node)
        api.health.stageNodeSensor(node)
    }

    return node
}

private func node(
    session: Database.Session,
    user: AuthenticatedUser,
    path: NodePath?
) async throws -> Node {
    let path = try stringValue(path, field: .orgPath)
    let conn = try await session.conn()
    let node = try await call(
        await service.node.node(conn: conn, path: path),
        api.error.NodeNotFound()
    )
    try api.acl.checkAccess(authUser: user, object: node, op: .read)
    return node
}

private func node(
    session: Database.Session,
    user: AuthenticatedUser,
    nodeID: NodeID?
) async throws -> Node {
    guard let nodeID else {
        throw api.error.InvalidParameter(name: "nodeID")
    }
    let conn = try await session.conn()
    let node = try await call(
        await service.node.node(conn: conn, nodeID: nodeID),
        api.error.NodeNotFound()
    )
    try api.acl.checkAccess(authUser: user, object: node, op: .read)
    return node
}


/// Ensures node path is valid.
///
/// - Parameter path: Node path to validate
/// - Returns: Formatted NodePath
func validateNodePath(_ path: NodePath) throws -> NodePath {
    let paths: [String] = path
        .trimmingCharacters(in: .whitespacesAndNewlines)
        .lowercased()
        .split(separator: ".")
        .map { String($0) }
    guard let name = paths.last, name.count > 0 else {
        throw api.error.InvalidNode("Node name not provided")
    }

    if Global.reservedNodeNames.contains(name) {
        throw api.error.InvalidNode("Name (\(name)) is one of the system-reserved names (\(Global.reservedNodeNames.joined(separator: ", ")))")
    }
    else if let firstChar = name.first, !Set(Global.nodeNameValidFirstChars).isSuperset(of: String(firstChar)) {
        throw api.error.InvalidNode("Name (\(name)) must begin with one of these letters (\(Global.nodeNameValidFirstChars))")
    }
    else if !Set(Global.nodeNameValidChars).isSuperset(of: name) {
        throw api.error.InvalidNode("One or more characters in name (\(name)) does not exist in the list of valid characters (\(Global.nodeNameValidChars))")
    }
    else if name.count > Global.maxNodeNameLength {
        throw api.error.InvalidNode("Node name can not exceed (\(Global.maxNodeNameLength)) characters. Name has (\(name.count)) characters.")
    }

    return paths.joined(separator: ".")
}
