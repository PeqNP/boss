/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation
import XCTest

@testable import bosslib

final class nodeTests: XCTestCase {
    override func setUpWithError() throws {
        try super.setUpWithError()
        boss.reset()
    }
    
    func testValidateName() async throws {
        // when: name is not provided
        await XCTAssertError(
            try validateNodePath(""),
            api.error.InvalidNode("Node name not provided")
        )
        await XCTAssertError(
            try validateNodePath(" \n"),
            api.error.InvalidNode("Node name not provided")
        )

        // when: name is system-reserved
        // This may not be valid after using SQLite
        await XCTAssertError(
            try validateNodePath("c"),
            api.error.InvalidNode("Name (c) is one of the system-reserved names (\(Global.reservedNodeNames.joined(separator: ", ")))")
        )

        // when: name does not start with a valid character
        await XCTAssertError(
            try validateNodePath("0"),
            api.error.InvalidNode("Name (0) must begin with one of these letters (\(Global.nodeNameValidFirstChars))")
        )

        // when: name is longer than 30 characters
        let longName = "abcdefghijklmnopqrstuvwxyz-0123"
        XCTAssertEqual(longName.count, 31)
        await XCTAssertError(
            try validateNodePath(longName),
            api.error.InvalidNode("Node name can not exceed (\(Global.maxNodeNameLength)) characters. Name has (\(longName.count)) characters.")
        )

        // when: name contains invalid characters
        await XCTAssertError(
            try validateNodePath("abcd&"),
            api.error.InvalidNode("One or more characters in name (abcd&) does not exist in the list of valid characters (\(Global.nodeNameValidChars))")
        )

        XCTAssertEqual(try validateNodePath("example"), "example")

        // when: the name is valid
        // it: should return lowercase name
        XCTAssertEqual(try validateNodePath("Bithead"), "bithead")
    }

    func testCreateOrgNode() async throws {
        let owner = User.fake(id: 3)

        // when: org path is not provided
        await XCTAssertError(
            try await api.node.createOrgNode(admin: superUser(), path: nil, config: .defaultConfig, owner: owner),
            api.error.InvalidAccountInfo(field: .orgPath)
        )
        await XCTAssertError(
            try await api.node.createOrgNode(admin: superUser(), path: "", config: .defaultConfig, owner: owner),
            api.error.InvalidAccountInfo(field: .orgPath)
        )

        // when: org path is not two parts
        await XCTAssertError(
            try await api.node.createOrgNode(admin: superUser(), path: "com", config: .defaultConfig, owner: owner),
            api.error.InvalidOrganization(path: "com")
        )

        // when: TLD does not exist
        service.node._nodeExists = { (conn, nodePath) -> Bool in
            false
        }
        await XCTAssertError(
            try await api.node.createOrgNode(admin: superUser(), path: "com.example", config: .defaultConfig, owner: owner),
            api.error.TLDDoesNotExist(tld: "com")
        )

        // when: node already exists in the system
        service.node._nodeExists = { (conn, nodePath) -> Bool in
            true
        }
        api.node._createNode = { _, _, _, _, _, _, _, _, _ in
            throw api.error.NodeExists(path: "com.example")
        }
        await XCTAssertError(
            try await api.node.createOrgNode(admin: superUser(), path: "com.example", config: .defaultConfig, owner: owner),
            api.error.OrgNodeExists(path: "com.example")
        )

        // when: node does not exist
        let expectedNode = Node.fake(id: 3, path: "com.example", type: .group)
        api.node._createNode = { _, _, _, _, _, _, _, _, _ in
            expectedNode
        }
        let node = try await api.node.createOrgNode(admin: superUser(), path: "com.example", config: .defaultConfig, owner: owner)

        XCTAssertEqual(node, expectedNode)
    }

    func testCreateNode() async throws {
        await XCTAssertError(
            try await api.node.createNode(user: guestUser(), path: "com.path", type: .service),
            GenericError("Guest user can not create nodes.")
        )

        let user = AuthenticatedUser.fake()
        // when: node already exists
        service.node._nodeExists = { _, _ in true }
        await XCTAssertError(
            try await api.node.createNode(user: user, path: "com.path", type: .service),
            api.error.NodeExists(path: "com.path")
        )

        // when: node fails to be created
        service.node._nodeExists = { _, _ in false }
        service.node._createNode = { _, _, _, _ in throw GenericError("Failed") }
        await XCTAssertError(
            try await api.node.createNode(user: user, path: "com.path", type: .service),
            GenericError("Failed")
        )

        // when: node is successfully created
        let expectedNode = Node.fake(path: "com.path", type: .service, acl: [.makeOwnerACL(using: user.user)])
        service.node._createNode = { _, _, _, _ in expectedNode }
        let node = try await api.node.createNode(user: user, path: "com.path", type: .service)
        // it: should create node
        // it: should set user as node owner
        XCTAssertEqual(node, expectedNode)

        // TODO: it: should stage node health
        // TODO: it: should stage node sensor

        // TODO: create TLD
        // TODO: it: should NOT stage node health
        // TODO: it: should NOT stage node sensor
    }

    func testCreateNode_customACL() async throws {
        // when: node is created with custom ACL
        // it: should save node w/ custom ACL
    }

    func testCreateNode_integration() async throws {
        try await boss.start(storage: .memory)

        // when: node is created
        let user = AuthenticatedUser.fake(user: .fake(id: 4, verified: true, enabled: true))
        var expectedNode = Node.fake(path: "com.path", type: .service, acl: [.makeOwnerACL(using: user.user)])
        let node = try await api.node.createNode(user: user, path: "com.path", type: .service)
        // it: should be created
        XCTAssertEqual(node, expectedNode)

        // when: node is created with custom ACL
        let aclNode = try await api.node.createNode(user: user, path: "com.path.test", type: .service, acl: [.fake(name: "Custom", operations: [.read])])
        expectedNode.path = "com.path.test"
        expectedNode.acl = [.fake(name: "Custom", operations: [.read])]
        XCTAssertEqual(aclNode, expectedNode)

        // when: all node properties are provided
        // it: should save all information correctly

        // when: query by node path
        let nodeWithPath = try await api.node.node(user: user, path: "com.path")
        // it: should return node w/ all properties
        XCTAssertEqual(nodeWithPath, node)

        // when: query by node ID
        let nodeWithID = try await api.node.node(user: user, nodeID: node.id)
        // it: should return node w/ all properties
        XCTAssertEqual(nodeWithID, node)

        // when: querying a child node
        // it: should be enriched with parent ACL
    }

    func testUpateNode() async throws {
        // when: user does not have permission to update node
        // when: user has permissions to update node
    }

    func testNodeWithPath() async throws {
        // when: node does not exist
        service.node._node = { _, _ in
            throw service.error.RecordNotFound()
        }
        try await XCTAssertError(
            await api.node.node(user: guestUser(), path: "com.example.node"),
            api.error.NodeNotFound()
        )

        let expectedNode = Node.fake(path: "com.example")
        service.node._node = { _, _ in
            expectedNode
        }

        // when: user does not have permission to read node
        api.acl._checkAccess = { _, _, _ in
            throw api.error.AccessDenied()
        }
        try await XCTAssertError(
            await api.node.node(user: guestUser(), path: "com.example.node"),
            api.error.AccessDenied()
        )

        // when: user has permissions to read node
        // it: should hydrate all information correctly
        api.acl._checkAccess = { _, _, _ in }
        let node = try await api.node.node(user: guestUser(), path: "com.example.node")
        XCTAssertEqual(node, expectedNode)
    }

    func testNodeWithID() async throws {
        // when: node does not exist
        service.node._nodeWithID = { _, _ in
            throw service.error.RecordNotFound()
        }
        try await XCTAssertError(
            await api.node.node(user: guestUser(), nodeID: 1),
            api.error.NodeNotFound()
        )

        let expectedNode = Node.fake(path: "com.example")
        service.node._nodeWithID = { _, _ in
            expectedNode
        }

        // when: user does not have permission to read node
        api.acl._checkAccess = { _, _, _ in
            throw api.error.AccessDenied()
        }
        try await XCTAssertError(
            await api.node.node(user: guestUser(), nodeID: 1),
            api.error.AccessDenied()
        )

        // when: user has permissions to read node
        // it: should hydrate all information correctly
        api.acl._checkAccess = { _, _, _ in }
        let node = try await api.node.node(user: guestUser(), nodeID: 1)
        XCTAssertEqual(node, expectedNode)
    }
}
