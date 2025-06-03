/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import Foundation
import XCTest

@testable import bosslib

final class databaseTests: XCTestCase {
    override func setUpWithError() throws {
        try super.setUpWithError()
        boss.reset()
    }

    func testTransactions() async throws {
        try await boss.start(storage: .memory)
        let db = Database.current
        let session = db.session()
        let conn = try await session.conn()

        // when: transaction is rolled back
        try await conn.begin()
        var user = try await service.user.createUser(conn: conn, system: .boss, email: "me@example.com", password: "Password123", fullName: "Me", verified: true, enabled: true)
        var test = try? await service.user.user(conn: conn, id: user.id)
        XCTAssertNotNil(test)
        try await conn.rollback()
        test = try? await service.user.user(conn: conn, id: user.id)
        XCTAssertNil(test)

        // when: transaction is committed
        try await conn.begin()
        user = try await service.user.createUser(conn: conn, system: .boss, email: "you@example.com", password: "Password123", fullName: "You", verified: true, enabled: true)
        test = try? await service.user.user(conn: conn, id: user.id)
        XCTAssertNotNil(test)
        try await conn.commit()
        test = try? await service.user.user(conn: conn, id: user.id)
        XCTAssertNotNil(test)

        // when: multiple transactions are began
        try await conn.begin()
        try await conn.begin()
        user = try await service.user.createUser(conn: conn, system: .boss, email: "them@example.com", password: "Password123", fullName: "Them", verified: true, enabled: true)
        test = try? await service.user.user(conn: conn, id: user.id)
        try await conn.commit()
        try await conn.commit()
        // it: should see record once it has been committed
        test = try? await service.user.user(conn: conn, id: user.id)
        XCTAssertNotNil(test)

        // when: commit is called when no transaction has been created
        await XCTAssertError(try await conn.commit(), service.error.TransactionNotStarted())
    }
}
