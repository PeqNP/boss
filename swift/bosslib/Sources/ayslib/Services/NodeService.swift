/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation
internal import SQLKit

protocol NodeProvider {
    func nodeExists(conn: Database.Connection, path: NodePath) async throws -> Bool
    func createNode(conn: Database.Connection, path: NodePath, type: NodeType, acl: [ACL]) async throws -> Node
    func updateNode(conn: Database.Connection, node: Node) async throws -> Node
    func node(conn: Database.Connection, path: NodePath) async throws -> Node
    func node(conn: Database.Connection, nodeID: NodeID) async throws -> Node
}

public class NodeService {
    var _nodeExists: (Database.Connection, NodePath) async throws -> Bool = { _, _ in fatalError("NodeService.nodeExists") }
    var _createNode: (Database.Connection, NodePath, NodeType, [ACL]) async throws -> Node = { _, _, _, _ in fatalError("NodeService.createNode") }
    var _updateNode: (Database.Connection, Node) async throws -> Node = { _, _ in fatalError("NodeService.updateNode") }
    var _node: (Database.Connection, NodePath) async throws -> Node = { _, _ in fatalError("NodeService.node(path:)") }
    var _nodeWithID: (Database.Connection, NodeID) async throws -> Node = { _, _ in fatalError("NodeService.node(id:)") }

    init() { }

    init(_ p: NodeProvider) {
        self._nodeExists = p.nodeExists
        self._createNode = p.createNode
        self._updateNode = p.updateNode
        self._node = p.node(conn:path:)
        self._nodeWithID = p.node(conn:nodeID:)
    }

    public func nodeExists(conn: Database.Connection, path: NodePath) async throws -> Bool {
        try await _nodeExists(conn, path)
    }

    public func createNode(
        conn: Database.Connection,
        path: NodePath,
        type: NodeType,
        acl: [ACL]
    ) async throws -> Node {
        try await _createNode(conn, path, type, acl)
    }

    public func updateNode(conn: Database.Connection, node: Node) async throws -> Node {
        try await _updateNode(conn, node)
    }

    public func node(conn: Database.Connection, path: NodePath) async throws -> Node {
        try await _node(conn, path)
    }

    public func node(conn: Database.Connection, nodeID: NodeID) async throws -> Node {
        try await _nodeWithID(conn, nodeID)
    }
}

class NodeSQLiteService: NodeProvider {
    func nodeExists(conn: Database.Connection, path: NodePath) async throws -> Bool {
        let rows = try await conn
            .select()
            .column(SQLFunction("count", args: SQLLiteral.all))
            .from("nodes")
            .where(SQLColumn("path"), .equal, SQLBind(path))
            .all()

        let numRows = try rows[0].decode(column: "count(*)", as: UInt.self)
        return numRows > 0
    }

    func createNode(
        conn: Database.Connection,
        path: NodePath,
        type: NodeType,
        acl: [ACL]
    ) async throws -> Node {
        let rows = try await conn.sql().insert(into: "nodes")
            .columns("id", "create_date", "path", "node_type_id", "node_type", "acl")
            .values(SQLLiteral.null, SQLBind(Date.now), SQLBind(path), SQLBind(type.schemaId), encode(type), encode(acl))
            .returning("id")
            .all()
        guard let row = rows.first else {
            throw service.error.FailedToSave(Node.self)
        }
        return try Node(
            id: row.decode(column: "id", as: NodeID.self),
            path: path,
            type: type,
            acl: acl
        )
    }

    func updateNode(conn: Database.Connection, node: Node) async throws -> Node {
        return node
    }

    func node(conn: Database.Connection, path: NodePath) async throws -> Node {
        let rows = try await conn.select()
            .column("*")
            .from("nodes")
            .where("path", .equal, SQLBind(path))
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        // TODO: Enrich all ACL from parents
        return try makeNode(from: row)
    }

    func node(conn: Database.Connection, nodeID: NodeID) async throws -> Node {
        let rows = try await conn.select()
            .column("*")
            .from("nodes")
            .where("id", .equal, SQLBind(nodeID))
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        // TODO: Enrich all ACL from parents
        return try makeNode(from: row)
    }
}

private extension NodeSQLiteService {
    func makeNode(from row: SQLRow) throws -> Node {
        try Node(
            id: row.decode(column: "id", as: NodeID.self),
            path: row.decode(column: "path", as: NodePath.self),
            type: decode(row.decode(column: "node_type", as: Data.self), as: NodeType.self),
            acl: decode(row.decode(column: "acl", as: Data.self), as: [ACL].self)
        )
    }
}

private extension NodeType {
    var schemaId: Int {
        switch self {
        case .unknown: 0
        case .client: 1
        case .service: 2
        case .resource: 3
        case .group: 4
        case .machine: 5
        case .application: 6
        case .proxy: 7
        case .monitor: 8
        case .vendor: 9
        case .template: 10
        case .virtual: 11
        }
    }
}
