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
    func intakeQueue(session: Database.Session, user: User, id: IntakeQueue.ID) async throws -> IntakeQueue
    func createIntakeQueue(session: Database.Session, user: User, lineId: Line.ID, name: String?, key: String?) async throws -> IntakeQueue
    func updateIntakeQueueName(session: Database.Session, user: User, id: IntakeQueue.ID, name: String?) async throws
    func updateIntakeQueueMixRatio(session: Database.Session, user: User, id: IntakeQueue.ID, mixRatio: Int) async throws
    func deleteFactory(session: Database.Session, user: User, id: Factory.ID) async throws
    func deleteCompany(session: Database.Session, user: User, id: Company.ID) async throws
    func company(session: Database.Session, user: User, id: Company.ID) async throws -> Company
    func updateCompany(session: Database.Session, user: User, id: Company.ID, name: String?) async throws
    func factory(session: Database.Session, user: User, id: Factory.ID) async throws -> Factory
    func updateFactory(session: Database.Session, user: User, id: Factory.ID, name: String?) async throws
    func updateInventoryName(session: Database.Session, user: User, id: Inventory.ID, name: String?) async throws
    func inventory(session: Database.Session, user: User, id: Inventory.ID) async throws -> Inventory
    func updateLineName(session: Database.Session, user: User, id: Line.ID, name: String?) async throws
    func line(session: Database.Session, user: User, id: Line.ID) async throws -> Line
    func saveLinePosition(session: Database.Session, user: User, id: Line.ID, x: Int, y: Int) async throws
    func saveLineLocked(session: Database.Session, user: User, id: Line.ID, locked: Bool) async throws
    func saveLineFocus(session: Database.Session, user: User, id: Line.ID, focused: Bool) async throws
    func saveInventoryPosition(session: Database.Session, user: User, id: Inventory.ID, x: Int, y: Int) async throws
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

    public func createFactory(
        session: Database.Session = Database.session(),
        user: User,
        companyId: Company.ID,
        name: String?
    ) async throws -> Factory {
        try await p.createFactory(session: session, user: user, companyId: companyId, name: name)
    }

    public func createLine(
        session: Database.Session = Database.session(),
        user: User,
        factoryId: Factory.ID,
        name: String?
    ) async throws -> Line {
        try await p.createLine(session: session, user: user, factoryId: factoryId, name: name)
    }

    public func createInventory(
        session: Database.Session = Database.session(),
        user: User,
        factoryId: Factory.ID,
        name: String?
    ) async throws -> Inventory {
        try await p.createInventory(session: session, user: user, factoryId: factoryId, name: name)
    }
    
    public func intakeQueue(
        session: Database.Session = Database.session(),
        user: User,
        id: IntakeQueue.ID
    ) async throws -> IntakeQueue {
        try await p.intakeQueue(session: session, user: user, id: id)
    }
    
    public func createIntakeQueue(
        session: Database.Session = Database.session(),
        user: User,
        lineId: Line.ID,
        name: String?,
        key: String?
    ) async throws -> IntakeQueue {
        try await p.createIntakeQueue(session: session, user: user, lineId: lineId, name: name, key: key)
    }

    public func updateIntakeQueueName(
        session: Database.Session = Database.session(),
        user: User,
        id: IntakeQueue.ID,
        name: String?
    ) async throws {
        try await p.updateIntakeQueueName(session: session, user: user, id: id, name: name)
    }

    public func updateIntakeQueueMixRatio(
        session: Database.Session = Database.session(),
        user: User,
        id: IntakeQueue.ID,
        mixRatio: Int
    ) async throws {
        try await p.updateIntakeQueueMixRatio(session: session, user: user, id: id, mixRatio: mixRatio)
    }

    public func deleteFactory(
        session: Database.Session = Database.session(),
        user: User,
        id: Factory.ID
    ) async throws {
        try await p.deleteFactory(session: session, user: user, id: id)
    }

    public func deleteCompany(
        session: Database.Session = Database.session(),
        user: User,
        id: Company.ID
    ) async throws {
        try await p.deleteCompany(session: session, user: user, id: id)
    }

    public func company(
        session: Database.Session = Database.session(),
        user: User,
        id: Company.ID
    ) async throws -> Company {
        try await p.company(session: session, user: user, id: id)
    }

    public func updateCompany(
        session: Database.Session = Database.session(),
        user: User,
        id: Company.ID,
        name: String?
    ) async throws {
        try await p.updateCompany(session: session, user: user, id: id, name: name)
    }

    public func factory(
        session: Database.Session = Database.session(),
        user: User,
        id: Factory.ID
    ) async throws -> Factory {
        try await p.factory(session: session, user: user, id: id)
    }

    public func updateFactory(
        session: Database.Session = Database.session(),
        user: User,
        id: Factory.ID,
        name: String?
    ) async throws {
        try await p.updateFactory(session: session, user: user, id: id, name: name)
    }

    public func updateInventoryName(
        session: Database.Session = Database.session(),
        user: User,
        id: Inventory.ID,
        name: String?
    ) async throws {
        try await p.updateInventoryName(session: session, user: user, id: id, name: name)
    }

    public func inventory(
        session: Database.Session = Database.session(),
        user: User,
        id: Inventory.ID
    ) async throws -> Inventory {
        try await p.inventory(session: session, user: user, id: id)
    }

    public func updateLineName(
        session: Database.Session = Database.session(),
        user: User,
        id: Line.ID,
        name: String?
    ) async throws {
        try await p.updateLineName(session: session, user: user, id: id, name: name)
    }

    public func line(
        session: Database.Session = Database.session(),
        user: User,
        id: Line.ID
    ) async throws -> Line {
        try await p.line(session: session, user: user, id: id)
    }

    public func saveLinePosition(
        session: Database.Session = Database.session(),
        user: User,
        id: Line.ID,
        x: Int,
        y: Int
    ) async throws {
        try await p.saveLinePosition(session: session, user: user, id: id, x: x, y: y)
    }

    public func saveLineLocked(
        session: Database.Session = Database.session(),
        user: User,
        id: Line.ID,
        locked: Bool
    ) async throws {
        try await p.saveLineLocked(session: session, user: user, id: id, locked: locked)
    }

    public func saveLineFocus(
        session: Database.Session = Database.session(),
        user: User,
        id: Line.ID,
        focused: Bool
    ) async throws {
        try await p.saveLineFocus(session: session, user: user, id: id, focused: focused)
    }

    public func saveInventoryPosition(
        session: Database.Session = Database.session(),
        user: User,
        id: Inventory.ID,
        x: Int,
        y: Int
    ) async throws {
        try await p.saveInventoryPosition(session: session, user: user, id: id, x: x, y: y)
    }
}
