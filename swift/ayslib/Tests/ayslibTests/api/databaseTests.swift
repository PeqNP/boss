/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation
import XCTest

@testable import ayslib

final class databaseTests: XCTestCase {
    override func setUpWithError() throws {
        try super.setUpWithError()
        ays.reset()
    }

    func testTransactions() async throws {
        try await ays.start(storage: .memory)
        let db = Database.current
        let session = db.session()
        let conn = try await session.conn()

        // when: transaction is rolled back
        try await conn.begin()
        _ = try await service.node.createNode(conn: conn, path: "com.okay", type: .machine, acl: [])
        var nodeExists = try await service.node.nodeExists(conn: conn, path: "com.okay")
        XCTAssertTrue(nodeExists)
        try await conn.rollback()
        nodeExists = try await service.node.nodeExists(conn: conn, path: "com.okay")
        XCTAssertFalse(nodeExists)

        // when: transaction is committed
        try await conn.begin()
        _ = try await service.node.createNode(conn: conn, path: "com.okay", type: .machine, acl: [])
        nodeExists = try await service.node.nodeExists(conn: conn, path: "com.okay")
        XCTAssertTrue(nodeExists)
        try await conn.commit()
        nodeExists = try await service.node.nodeExists(conn: conn, path: "com.okay")
        XCTAssertTrue(nodeExists)

        // when: multiple transactions are began
        try await conn.begin()
        try await conn.begin()
        _ = try await service.node.createNode(conn: conn, path: "com.okay", type: .machine, acl: [])
        nodeExists = try await service.node.nodeExists(conn: conn, path: "com.okay")
        XCTAssertTrue(nodeExists)
        try await conn.commit()
        try await conn.commit()
        // it: should see record once it has been committed
        nodeExists = try await service.node.nodeExists(conn: conn, path: "com.okay")
        XCTAssertTrue(nodeExists)

        // when: commit is called when no transaction has been created
        await XCTAssertError(try await conn.commit(), service.error.TransactionNotStarted())
    }
}
