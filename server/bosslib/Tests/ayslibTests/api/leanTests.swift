/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import Foundation
import SwiftOTP
import XCTest

@testable import bosslib

final class leanTests: XCTestCase {
    func testCompany() async throws {
        // try await boss.start(storage: .memory)
    }
    
    func testFactory() async throws {
        // try await boss.start(storage: .memory)
    }
    
    /// Test saving the `Line` model.
    func testCreatingModelsWithOnlyName() async throws {
        try await boss.start(storage: .memory)

        // describe: Create a new `Company` with only the name

        // when: name is nil
        await XCTAssertError(
            try await api.lean.createCompany(user: superUser().user, name: nil),
            api.error.RequiredParameter("name")
        )

        // when: name is empty
        await XCTAssertError(
            try await api.lean.createCompany(user: superUser().user, name: ""),
            api.error.RequiredParameter("name")
        )

        // when: name is valid
        let company = try await api.lean.createCompany(user: superUser().user, name: "Acme Co.")
        // it: should save the record to the database and return the record
        XCTAssertGreaterThan(company.id, 0)
        XCTAssertEqual(company.name, "Acme Co.")
        XCTAssertEqual(company.userId, superUser().user.id)

        // describe: Create a new `Factory` with only the name

        // when: name is nil
        await XCTAssertError(
            try await api.lean.createFactory(user: superUser().user, companyId: company.id, name: nil),
            api.error.RequiredParameter("name")
        )

        // when: name is empty
        await XCTAssertError(
            try await api.lean.createFactory(user: superUser().user, companyId: company.id, name: ""),
            api.error.RequiredParameter("name")
        )

        // when: name is valid
        let factory = try await api.lean.createFactory(user: superUser().user, companyId: company.id, name: "Main Factory")
        // it: should save the record to the database and return the record
        XCTAssertGreaterThan(factory.id, 0)
        XCTAssertEqual(factory.companyId, company.id)
        XCTAssertEqual(factory.name, "Main Factory")

        // describe: Create a new `Line` with only the name

        // when: name is nil
        await XCTAssertError(
            try await api.lean.createLine(user: superUser().user, factoryId: factory.id, name: nil),
            api.error.RequiredParameter("name")
        )

        // when: name is empty
        await XCTAssertError(
            try await api.lean.createLine(user: superUser().user, factoryId: factory.id, name: ""),
            api.error.RequiredParameter("name")
        )

        // when: name is valid
        let line = try await api.lean.createLine(user: superUser().user, factoryId: factory.id, name: "Assembly Line")
        // it: should save the record to the database and return the record
        XCTAssertGreaterThan(line.id, 0)
        XCTAssertEqual(line.factoryId, factory.id)
        XCTAssertEqual(line.name, "Assembly Line")

        // describe: Create a new `Inventory` with only the name

        // when: name is nil
        await XCTAssertError(
            try await api.lean.createInventory(user: superUser().user, factoryId: factory.id, name: nil),
            api.error.RequiredParameter("name")
        )

        // when: name is empty
        await XCTAssertError(
            try await api.lean.createInventory(user: superUser().user, factoryId: factory.id, name: ""),
            api.error.RequiredParameter("name")
        )

        // when: name is valid
        let inventory = try await api.lean.createInventory(user: superUser().user, factoryId: factory.id, name: "Screws")
        // it: should save the record to the database and return the record
        XCTAssertGreaterThan(inventory.id, 0)
        XCTAssertEqual(inventory.supply.name, "Screws")
    }
}
