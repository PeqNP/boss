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

        let (user, _ /* email */) = try await api.account.createUser(admin: superUser(), email: "lean@example.com", password: "Password!1", fullName: "Lean", verified: true)
        
        // describe: Create a new `Company` with only the name

        // when: name is nil
        await XCTAssertError(
            try await api.lean.createCompany(user: user, name: nil),
            api.error.RequiredParameter("name")
        )

        // when: name is empty
        await XCTAssertError(
            try await api.lean.createCompany(user: user, name: ""),
            api.error.RequiredParameter("name")
        )

        // when: name is valid
        let company = try await api.lean.createCompany(user: user, name: "Acme Co.")
        // it: should save the record to the database and return the record
        XCTAssertGreaterThan(company.id, 0)
        XCTAssertEqual(company.name, "Acme Co.")
        XCTAssertEqual(company.userId, user.id)

        // describe: Create a new `Factory` with only the name

        // when: name is nil
        await XCTAssertError(
            try await api.lean.createFactory(user: user, companyId: company.id, name: nil),
            api.error.RequiredParameter("name")
        )

        // when: name is empty
        await XCTAssertError(
            try await api.lean.createFactory(user: user, companyId: company.id, name: ""),
            api.error.RequiredParameter("name")
        )

        // when: name is valid
        let factory = try await api.lean.createFactory(user: user, companyId: company.id, name: "Main Factory")
        // it: should save the record to the database and return the record
        XCTAssertGreaterThan(factory.id, 0)
        XCTAssertEqual(factory.companyId, company.id)
        XCTAssertEqual(factory.name, "Main Factory")

        // describe: Create a new `Line` with only the name

        // when: name is nil
        await XCTAssertError(
            try await api.lean.createLine(user: user, factoryId: factory.id, name: nil),
            api.error.RequiredParameter("name")
        )

        // when: name is empty
        await XCTAssertError(
            try await api.lean.createLine(user: user, factoryId: factory.id, name: ""),
            api.error.RequiredParameter("name")
        )

        // when: name is valid
        let line = try await api.lean.createLine(user: user, factoryId: factory.id, name: "Assembly Line")
        // it: should save the record to the database and return the record
        XCTAssertGreaterThan(line.id, 0)
        XCTAssertEqual(line.factoryId, factory.id)
        XCTAssertEqual(line.name, "Assembly Line")

        // describe: Create a new `Inventory` with only the name

        // when: name is nil
        await XCTAssertError(
            try await api.lean.createInventory(user: user, factoryId: factory.id, name: nil),
            api.error.RequiredParameter("name")
        )

        // when: name is empty
        await XCTAssertError(
            try await api.lean.createInventory(user: user, factoryId: factory.id, name: ""),
            api.error.RequiredParameter("name")
        )

        // when: name is valid
        let inventory = try await api.lean.createInventory(user: user, factoryId: factory.id, name: "Screws")
        // it: should save the record to the database and return the record
        XCTAssertGreaterThan(inventory.id, 0)
        XCTAssertEqual(inventory.supply.name, "Screws")
        
        // describe: query companies
        let companies = try await api.lean.companies(user: user)
        // it: there should be the same company created earlier
        XCTAssertEqual(companies.count, 1)
        XCTAssertEqual(companies[0].id, company.id)
        XCTAssertEqual(companies[0].name, company.name)

        // describe: query factories
        let factories = try await api.lean.factories(companyId: company.id)
        // it: it should be the same factory created earlier
        XCTAssertEqual(factories.count, 1)
        XCTAssertEqual(factories[0].id, factory.id)
        XCTAssertEqual(factories[0].name, factory.name)
    }
}
