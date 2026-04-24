/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import Foundation

extension api {
    public nonisolated(unsafe) internal(set) static var lean = LeanAPI(provider: LeanService())
}

protocol LeanProvider {
    func companies(session: Database.Session, user: User) async throws -> [Company]
    func createCompany(session: Database.Session, user: User, name: String?) async throws -> Company
    func factories(session: Database.Session, companyId: Company.ID) async throws -> [Factory]
    func createFactory(session: Database.Session, user: User, companyId: Company.ID, name: String?) async throws -> Factory
    func createLine(session: Database.Session, user: User, factoryId: Factory.ID, name: String?) async throws -> Line
    func createInventory(session: Database.Session, user: User, factoryId: Factory.ID, name: String?) async throws -> Inventory
}

final public class LeanAPI {
    let p: LeanProvider
    
    init(provider: LeanProvider) {
        self.p = provider
    }

    public func companies(
        session: Database.Session = Database.session(),
        user: User
    ) async throws -> [Company] {
        try await p.companies(session: session, user: user)
    }

    @discardableResult
    public func createCompany(
        session: Database.Session = Database.session(),
        user: User,
        name: String?
    ) async throws -> Company {
        try await p.createCompany(session: session, user: user, name: name)
    }

    public func factories(
        session: Database.Session = Database.session(),
        companyId: Company.ID
    ) async throws -> [Factory] {
        try await p.factories(session: session, companyId: companyId)
    }

    @discardableResult
    public func createFactory(
        session: Database.Session = Database.session(),
        user: User,
        companyId: Company.ID,
        name: String?
    ) async throws -> Factory {
        try await p.createFactory(session: session, user: user, companyId: companyId, name: name)
    }

    @discardableResult
    public func createLine(
        session: Database.Session = Database.session(),
        user: User,
        factoryId: Factory.ID,
        name: String?
    ) async throws -> Line {
        try await p.createLine(session: session, user: user, factoryId: factoryId, name: name)
    }

    @discardableResult
    public func createInventory(
        session: Database.Session = Database.session(),
        user: User,
        factoryId: Factory.ID,
        name: String?
    ) async throws -> Inventory {
        try await p.createInventory(session: session, user: user, factoryId: factoryId, name: name)
    }
}
