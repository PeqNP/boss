/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import Foundation

extension api {
    public static let lean = LeanAPI(provider: LeanService())
}

private enum LeanProviderContext {
    @TaskLocal static var current: (any LeanProvider)?
}

protocol LeanProvider: Sendable {
    // Existing API surface
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
    func saveIntakeQueuePosition(session: Database.Session, user: User, id: IntakeQueue.ID, position: Int) async throws
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
    func saveInventoryLocked(session: Database.Session, user: User, id: Inventory.ID, locked: Bool) async throws
    func saveInventoryFocus(session: Database.Session, user: User, id: Inventory.ID, focused: Bool) async throws

    // One-method-per-route interface
    func factoryFloor(session: Database.Session, user: User, factoryId: Int) async throws -> FactoryFloor

    func findAgents(session: Database.Session, user: User, companyId: Int, query: String) async throws -> [FoundItem]
    func findIntakeQueue(session: Database.Session, user: User, lineId: Int, query: String) async throws -> [FoundItem]
    func findIntakeQueues(session: Database.Session, user: User, companyId: Int, query: String) async throws -> [FoundItem]
    func findInventories(session: Database.Session, user: User, companyId: Int, query: String) async throws -> [FoundItem]
    func findMimeTypes(session: Database.Session, user: User, query: String) async throws -> [FoundItem]
    func findOperators(session: Database.Session, user: User, companyId: Int, query: String) async throws -> [FoundItem]
    func findSupplies(session: Database.Session, user: User, companyId: Int, query: String) async throws -> [FoundItem]
    func findWorkUnit(session: Database.Session, user: User, companyId: Int, query: String) async throws -> [FoundItem]

    func saveImage(session: Database.Session, user: User) async throws -> FileResource
    func image(session: Database.Session, user: User, imageId: Int) async throws -> FileResource
    func deleteImage(session: Database.Session, user: User, imageId: Int) async throws

    func createIntakeQueue(session: Database.Session, user: User, lineId: Int, name: String?) async throws -> ListItem
    func intakeQueue(session: Database.Session, user: User, intakeQueueId: Int) async throws -> IntakeQueue
    func saveIntakeQueue(session: Database.Session, user: User, intakeQueueId: Int, name: String?, key: String?, mixRatioType: String?, mixRatio: Int?, workUnitNameType: String?, workUnitMaterialName: String?, theme: Theme?) async throws

    func saveInventory(session: Database.Session, user: User, inventoryId: Int, name: String?) async throws

    func line(session: Database.Session, user: User, lineId: Int) async throws -> Line
    func saveLine(session: Database.Session, user: User, lineId: Int, name: String, hasOutput: Bool, subAssemblyLine: Bool) async throws -> Line
    func deleteLine(session: Database.Session, user: User, lineId: Int) async throws

    func createOperation(session: Database.Session, user: User, stationId: Int, name: String, agentId: Int?, supplyRequestType: String?, inventoryId: Int?, amount: Int?, supplyId: Int?, intakeQueueId: Int?) async throws -> Operation
    func operation(session: Database.Session, user: User, operationId: Int) async throws -> Operation
    func saveOperation(session: Database.Session, user: User, operationId: Int, name: String, instructions: String?, agentId: Int?, supplyRequestType: String?, inventoryId: Int?, amount: Int?, supplyId: Int?, intakeQueueId: Int?) async throws -> Operation
    func deleteOperation(session: Database.Session, user: User, operationId: Int) async throws

    func createOperator(session: Database.Session, user: User, userId: Int?, agentId: Int?) async throws
    func `operator`(session: Database.Session, user: User, operatorId: Int) async throws -> Operator
    func saveOperator(session: Database.Session, user: User, operatorId: Int, userId: Int?, agentId: Int?) async throws
    func deleteOperator(session: Database.Session, user: User, operatorId: Int) async throws

    func startWorkUnit(session: Database.Session, user: User, workUnitId: Int) async throws -> WorkUnit

    func createStation(session: Database.Session, user: User, lineId: Int, name: String?, index: Int?) async throws -> Station
    func station(session: Database.Session, user: User, stationId: Int) async throws -> Station
    func stationNotificationTriggers(session: Database.Session, user: User, stationId: Int) async throws -> [ListItem]
    func stationOperations(session: Database.Session, user: User, stationId: Int) async throws -> [ListItem]
    func stationWorkUnits(session: Database.Session, user: User, stationId: Int) async throws -> [WorkUnit]
    func saveStation(session: Database.Session, user: User, stationId: Int, name: String?, assigneeAction: String?, assigneeIds: [Int]?, theme: Theme?) async throws -> Station
    func saveStationPosition(session: Database.Session, user: User, id: Station.ID, position: Int) async throws
    func saveStationTypeIntakeQueue(session: Database.Session, user: User, stationId: Int, intakeQueueId: Int) async throws
    func saveStationTypeStation(session: Database.Session, user: User, stationId: Int) async throws
    func saveStationName(session: Database.Session, user: User, stationId: Int, name: String) async throws
    func saveStationOperationPositions(session: Database.Session, user: User, stationId: Int, position: Int, operationIds: [Int]) async throws
    func saveStationViewState(session: Database.Session, user: User, stationId: Int, overlay: String) async throws
    func deleteStation(session: Database.Session, user: User, stationId: Int) async throws

    func createStationNotificationTrigger(session: Database.Session, user: User, stationId: Int, events: [String], operatorIds: [Int], message: String?) async throws -> StationNotificationTrigger
    func stationNotificationTrigger(session: Database.Session, user: User, triggerId: Int) async throws -> StationNotificationTrigger
    func saveStationNotificationTrigger(session: Database.Session, user: User, triggerId: Int, events: [String]?, operatorIds: [Int]?, message: String?) async throws -> StationNotificationTrigger
    func deleteStationNotificationTrigger(session: Database.Session, user: User, triggerId: Int) async throws

    func suggestedAgents(session: Database.Session, user: User, companyId: Int) async throws -> [SuggestedItem]
    func suggestedIntakeQueue(session: Database.Session, user: User, lineId: Int) async throws -> [SuggestedItem]
    func suggestedIntakeQueues(session: Database.Session, user: User, companyId: Int) async throws -> [SuggestedItem]
    func suggestedInventories(session: Database.Session, user: User, companyId: Int) async throws -> [SuggestedItem]
    func suggestedMimeTypes(session: Database.Session, user: User) async throws -> [SuggestedItem]
    func suggestedOperators(session: Database.Session, user: User, companyId: Int) async throws -> [SuggestedItem]
    func suggestedSupplies(session: Database.Session, user: User, companyId: Int) async throws -> [SuggestedItem]
    func suggestedWorkUnit(session: Database.Session, user: User, companyId: Int) async throws -> [SuggestedItem]
    func suggestedSupplyFieldOptions(session: Database.Session, user: User, supplyFieldId: Int) async throws -> [SuggestedItem]
    func findSupplyFieldOptions(session: Database.Session, user: User, supplyFieldId: Int, query: String) async throws -> [FoundItem]

    func createSupply(session: Database.Session, user: User, companyId: Int, name: String, theme: Theme?, amount: Int?) async throws -> ListItem
    func supply(session: Database.Session, user: User, supplyId: Int) async throws -> Supply
    func saveSupply(session: Database.Session, user: User, supplyId: Int, name: String, theme: Theme?, amount: Int?) async throws -> Supply
    func deleteSupply(session: Database.Session, user: User, supplyId: Int) async throws
    func supplyFields(session: Database.Session, user: User, supplyId: Int) async throws -> [ListItem]
    func saveSupplyFieldPositions(session: Database.Session, user: User, supplyId: Int, position: Int, fieldIds: [Int]) async throws

    func createSupplyField(session: Database.Session, user: User, supplyId: Int, name: String) async throws -> SupplyField
    func supplyField(session: Database.Session, user: User, supplyFieldId: Int) async throws -> SupplyField
    func supplyFieldOptions(session: Database.Session, user: User, supplyFieldId: Int) async throws -> [ListItem]
    func saveSupplyField(session: Database.Session, user: User, supplyFieldId: Int, name: String?, type: String?, textType: String?, placeholder: String?, intakeQueueId: Int?, append: Bool?, optionNames: [String]?) async throws -> SupplyField
    func deleteSupplyField(session: Database.Session, user: User, supplyFieldId: Int) async throws

    func createSupplyFieldOption(session: Database.Session, user: User, supplyFieldId: Int, name: String, hidden: Bool?) async throws -> SupplyFieldOption
    func supplyFieldOption(session: Database.Session, user: User, supplyFieldOptionId: Int) async throws -> SupplyFieldOption
    func saveSupplyFieldOption(session: Database.Session, user: User, supplyFieldOptionId: Int, name: String?, hidden: Bool?) async throws -> SupplyFieldOption
    func deleteSupplyFieldOption(session: Database.Session, user: User, supplyFieldOptionId: Int) async throws

    func createWorkUnit(session: Database.Session, user: User, intakeQueueId: Int, name: String?, reporterId: Int?, assigneeIds: [Int], parentWorkUnitId: Int?) async throws -> WorkUnit
    func saveWorkUnitChild(session: Database.Session, user: User, workUnitId: Int, childWorkUnitId: Int) async throws
    func saveWorkUnitHold(session: Database.Session, user: User, workUnitId: Int) async throws
    func workUnit(session: Database.Session, user: User, workUnitId: Int) async throws -> WorkUnit
    func workUnitChildren(session: Database.Session, user: User, workUnitId: Int) async throws -> [WorkUnit]
    func saveWorkUnit(session: Database.Session, user: User, workUnitId: Int, name: String?, eta: String?) async throws -> WorkUnit
    func saveWorkUnitAssignees(session: Database.Session, user: User, workUnitId: Int, operatorIds: [Int]) async throws
    func saveWorkUnitParent(session: Database.Session, user: User, workUnitId: Int, parentWorkUnitId: Int?) async throws
    func saveWorkUnitReporter(session: Database.Session, user: User, workUnitId: Int, operatorId: Int?) async throws
    func deleteWorkUnit(session: Database.Session, user: User, workUnitId: Int) async throws
    func deleteWorkUnitChild(session: Database.Session, user: User, workUnitId: Int, childWorkUnitId: Int) async throws
    func deleteWorkUnitHold(session: Database.Session, user: User, workUnitId: Int, comments: String?) async throws

    func saveWorkUnitComment(session: Database.Session, user: User, workUnitId: Int, text: String) async throws
    func saveWorkUnitComment(session: Database.Session, user: User, commentId: Int, text: String) async throws
    func deleteWorkUnitComment(session: Database.Session, user: User, commentId: Int) async throws

    func saveWorkUnitPosition(session: Database.Session, user: User, position: Int, workUnitIds: [Int]) async throws

    func workUnits(session: Database.Session, user: User, intakeQueueId: Int) async throws -> [WorkUnit]
    func workUnitLogs(session: Database.Session, user: User, workUnitId: Int) async throws -> [WorkUnitLog]
    func saveWorkUnits(session: Database.Session, user: User, intakeQueueId: Int, name: String?, key: String?, mixRatioType: String?, mixRatio: Int?, workUnitNameType: String?, workUnitMaterialName: String?, theme: Theme?) async throws

    func workspace(session: Database.Session, user: User, workUnitId: Int) async throws -> Workspace

    func saveWorkUnitMoveToNextStation(session: Database.Session, user: User, workUnitId: Int) async throws

    func saveWorkUnitSupply(session: Database.Session, user: User, id: Int, fields: [WorkUnitSupplyFieldInput]) async throws -> Workspace
    func saveWorkUnitSupplyFulfill(session: Database.Session, user: User, id: Int) async throws -> Workspace
    func saveWorkUnitSupplyWaive(session: Database.Session, user: User, id: Int, comments: String) async throws -> Workspace

    func suggestedWorkUnitsForIntakeQueue(session: Database.Session, user: User, intakeQueueId: Int) async throws -> [SuggestedItem]
    func findWorkUnitsForIntakeQueue(session: Database.Session, user: User, intakeQueueId: Int, query: String) async throws -> [FoundItem]
}

final public class LeanAPI: Sendable {
    private let defaultProvider: any LeanProvider

    private var p: any LeanProvider {
        LeanProviderContext.current ?? defaultProvider
    }

    init(provider: any LeanProvider) {
        self.defaultProvider = provider
    }

    func withProvider<T: Sendable>(
        _ provider: any LeanProvider,
        operation: @Sendable () async throws -> T
    ) async rethrows -> T {
        try await LeanProviderContext.$current.withValue(provider, operation: operation)
    }

    // Existing API surface
    public func companies(session: Database.Session = Database.session(), user: User) async throws -> [Company] {
        try await p.companies(session: session, user: user)
    }

    public func createCompany(session: Database.Session = Database.session(), user: User, name: String?) async throws -> Company {
        try await p.createCompany(session: session, user: user, name: name)
    }

    public func factories(session: Database.Session = Database.session(), companyId: Company.ID) async throws -> [Factory] {
        try await p.factories(session: session, companyId: companyId)
    }

    public func createFactory(session: Database.Session = Database.session(), user: User, companyId: Company.ID, name: String?) async throws -> Factory {
        try await p.createFactory(session: session, user: user, companyId: companyId, name: name)
    }

    public func createLine(session: Database.Session = Database.session(), user: User, factoryId: Factory.ID, name: String?) async throws -> Line {
        try await p.createLine(session: session, user: user, factoryId: factoryId, name: name)
    }

    public func createInventory(session: Database.Session = Database.session(), user: User, factoryId: Factory.ID, name: String?) async throws -> Inventory {
        try await p.createInventory(session: session, user: user, factoryId: factoryId, name: name)
    }

    public func intakeQueue(session: Database.Session = Database.session(), user: User, id: IntakeQueue.ID) async throws -> IntakeQueue {
        try await p.intakeQueue(session: session, user: user, id: id)
    }

    public func createIntakeQueue(session: Database.Session = Database.session(), user: User, lineId: Line.ID, name: String?, key: String?) async throws -> IntakeQueue {
        try await p.createIntakeQueue(session: session, user: user, lineId: lineId, name: name, key: key)
    }

    public func updateIntakeQueueName(session: Database.Session = Database.session(), user: User, id: IntakeQueue.ID, name: String?) async throws {
        try await p.updateIntakeQueueName(session: session, user: user, id: id, name: name)
    }

    public func updateIntakeQueueMixRatio(session: Database.Session = Database.session(), user: User, id: IntakeQueue.ID, mixRatio: Int) async throws {
        try await p.updateIntakeQueueMixRatio(session: session, user: user, id: id, mixRatio: mixRatio)
    }

    public func saveIntakeQueuePosition(session: Database.Session = Database.session(), user: User, id: IntakeQueue.ID, position: Int) async throws {
        try await p.saveIntakeQueuePosition(session: session, user: user, id: id, position: position)
    }

    public func deleteFactory(session: Database.Session = Database.session(), user: User, id: Factory.ID) async throws {
        try await p.deleteFactory(session: session, user: user, id: id)
    }

    public func deleteCompany(session: Database.Session = Database.session(), user: User, id: Company.ID) async throws {
        try await p.deleteCompany(session: session, user: user, id: id)
    }

    public func company(session: Database.Session = Database.session(), user: User, id: Company.ID) async throws -> Company {
        try await p.company(session: session, user: user, id: id)
    }

    public func updateCompany(session: Database.Session = Database.session(), user: User, id: Company.ID, name: String?) async throws {
        try await p.updateCompany(session: session, user: user, id: id, name: name)
    }

    public func factory(session: Database.Session = Database.session(), user: User, id: Factory.ID) async throws -> Factory {
        try await p.factory(session: session, user: user, id: id)
    }

    public func updateFactory(session: Database.Session = Database.session(), user: User, id: Factory.ID, name: String?) async throws {
        try await p.updateFactory(session: session, user: user, id: id, name: name)
    }

    public func updateInventoryName(session: Database.Session = Database.session(), user: User, id: Inventory.ID, name: String?) async throws {
        try await p.updateInventoryName(session: session, user: user, id: id, name: name)
    }

    public func inventory(session: Database.Session = Database.session(), user: User, id: Inventory.ID) async throws -> Inventory {
        try await p.inventory(session: session, user: user, id: id)
    }

    public func updateLineName(session: Database.Session = Database.session(), user: User, id: Line.ID, name: String?) async throws {
        try await p.updateLineName(session: session, user: user, id: id, name: name)
    }

    public func line(session: Database.Session = Database.session(), user: User, id: Line.ID) async throws -> Line {
        try await p.line(session: session, user: user, id: id)
    }

    public func saveLinePosition(session: Database.Session = Database.session(), user: User, id: Line.ID, x: Int, y: Int) async throws {
        try await p.saveLinePosition(session: session, user: user, id: id, x: x, y: y)
    }

    public func saveLineLocked(session: Database.Session = Database.session(), user: User, id: Line.ID, locked: Bool) async throws {
        try await p.saveLineLocked(session: session, user: user, id: id, locked: locked)
    }

    public func saveLineFocus(session: Database.Session = Database.session(), user: User, id: Line.ID, focused: Bool) async throws {
        try await p.saveLineFocus(session: session, user: user, id: id, focused: focused)
    }

    public func saveInventoryPosition(session: Database.Session = Database.session(), user: User, id: Inventory.ID, x: Int, y: Int) async throws {
        try await p.saveInventoryPosition(session: session, user: user, id: id, x: x, y: y)
    }

    public func saveInventoryLocked(session: Database.Session = Database.session(), user: User, id: Inventory.ID, locked: Bool) async throws {
        try await p.saveInventoryLocked(session: session, user: user, id: id, locked: locked)
    }

    public func saveInventoryFocus(session: Database.Session = Database.session(), user: User, id: Inventory.ID, focused: Bool) async throws {
        try await p.saveInventoryFocus(session: session, user: user, id: id, focused: focused)
    }

    // Route-first pass-through surface
    public func factoryFloor(session: Database.Session = Database.session(), user: User, factoryId: Int) async throws -> FactoryFloor { try await p.factoryFloor(session: session, user: user, factoryId: factoryId) }
    public func findAgents(session: Database.Session = Database.session(), user: User, companyId: Int, query: String) async throws -> [FoundItem] { try await p.findAgents(session: session, user: user, companyId: companyId, query: query) }
    public func findIntakeQueue(session: Database.Session = Database.session(), user: User, lineId: Int, query: String) async throws -> [FoundItem] { try await p.findIntakeQueue(session: session, user: user, lineId: lineId, query: query) }
    public func findIntakeQueues(session: Database.Session = Database.session(), user: User, companyId: Int, query: String) async throws -> [FoundItem] { try await p.findIntakeQueues(session: session, user: user, companyId: companyId, query: query) }
    public func findInventories(session: Database.Session = Database.session(), user: User, companyId: Int, query: String) async throws -> [FoundItem] { try await p.findInventories(session: session, user: user, companyId: companyId, query: query) }
    public func findMimeTypes(session: Database.Session = Database.session(), user: User, query: String) async throws -> [FoundItem] { try await p.findMimeTypes(session: session, user: user, query: query) }
    public func findOperators(session: Database.Session = Database.session(), user: User, companyId: Int, query: String) async throws -> [FoundItem] { try await p.findOperators(session: session, user: user, companyId: companyId, query: query) }
    public func findSupplies(session: Database.Session = Database.session(), user: User, companyId: Int, query: String) async throws -> [FoundItem] { try await p.findSupplies(session: session, user: user, companyId: companyId, query: query) }
    public func findWorkUnit(session: Database.Session = Database.session(), user: User, companyId: Int, query: String) async throws -> [FoundItem] { try await p.findWorkUnit(session: session, user: user, companyId: companyId, query: query) }

    public func saveImage(session: Database.Session = Database.session(), user: User) async throws -> FileResource { try await p.saveImage(session: session, user: user) }
    public func image(session: Database.Session = Database.session(), user: User, imageId: Int) async throws -> FileResource { try await p.image(session: session, user: user, imageId: imageId) }
    public func deleteImage(session: Database.Session = Database.session(), user: User, imageId: Int) async throws { try await p.deleteImage(session: session, user: user, imageId: imageId) }

    public func createIntakeQueue(session: Database.Session = Database.session(), user: User, lineId: Int, name: String?) async throws -> ListItem { try await p.createIntakeQueue(session: session, user: user, lineId: lineId, name: name) }
    public func intakeQueue(session: Database.Session = Database.session(), user: User, intakeQueueId: Int) async throws -> IntakeQueue { try await p.intakeQueue(session: session, user: user, intakeQueueId: intakeQueueId) }
    public func saveIntakeQueue(session: Database.Session = Database.session(), user: User, intakeQueueId: Int, name: String?, key: String?, mixRatioType: String?, mixRatio: Int?, workUnitNameType: String?, workUnitMaterialName: String?, theme: Theme?) async throws { try await p.saveIntakeQueue(session: session, user: user, intakeQueueId: intakeQueueId, name: name, key: key, mixRatioType: mixRatioType, mixRatio: mixRatio, workUnitNameType: workUnitNameType, workUnitMaterialName: workUnitMaterialName, theme: theme) }

    public func saveInventory(session: Database.Session = Database.session(), user: User, inventoryId: Int, name: String?) async throws { try await p.saveInventory(session: session, user: user, inventoryId: inventoryId, name: name) }

    public func line(session: Database.Session = Database.session(), user: User, lineId: Int) async throws -> Line { try await p.line(session: session, user: user, lineId: lineId) }
    public func saveLine(session: Database.Session = Database.session(), user: User, lineId: Int, name: String, hasOutput: Bool, subAssemblyLine: Bool) async throws -> Line { try await p.saveLine(session: session, user: user, lineId: lineId, name: name, hasOutput: hasOutput, subAssemblyLine: subAssemblyLine) }
    public func deleteLine(session: Database.Session = Database.session(), user: User, lineId: Int) async throws { try await p.deleteLine(session: session, user: user, lineId: lineId) }

    public func createOperation(session: Database.Session = Database.session(), user: User, stationId: Int, name: String, agentId: Int?, supplyRequestType: String?, inventoryId: Int?, amount: Int?, supplyId: Int?, intakeQueueId: Int?) async throws -> Operation { try await p.createOperation(session: session, user: user, stationId: stationId, name: name, agentId: agentId, supplyRequestType: supplyRequestType, inventoryId: inventoryId, amount: amount, supplyId: supplyId, intakeQueueId: intakeQueueId) }
    public func operation(session: Database.Session = Database.session(), user: User, operationId: Int) async throws -> Operation { try await p.operation(session: session, user: user, operationId: operationId) }
    public func saveOperation(session: Database.Session = Database.session(), user: User, operationId: Int, name: String, instructions: String?, agentId: Int?, supplyRequestType: String?, inventoryId: Int?, amount: Int?, supplyId: Int?, intakeQueueId: Int?) async throws -> Operation { try await p.saveOperation(session: session, user: user, operationId: operationId, name: name, instructions: instructions, agentId: agentId, supplyRequestType: supplyRequestType, inventoryId: inventoryId, amount: amount, supplyId: supplyId, intakeQueueId: intakeQueueId) }
    public func deleteOperation(session: Database.Session = Database.session(), user: User, operationId: Int) async throws { try await p.deleteOperation(session: session, user: user, operationId: operationId) }

    public func createOperator(session: Database.Session = Database.session(), user: User, userId: Int?, agentId: Int?) async throws { try await p.createOperator(session: session, user: user, userId: userId, agentId: agentId) }
    public func `operator`(session: Database.Session = Database.session(), user: User, operatorId: Int) async throws -> Operator { try await p.operator(session: session, user: user, operatorId: operatorId) }
    public func saveOperator(session: Database.Session = Database.session(), user: User, operatorId: Int, userId: Int?, agentId: Int?) async throws { try await p.saveOperator(session: session, user: user, operatorId: operatorId, userId: userId, agentId: agentId) }
    public func deleteOperator(session: Database.Session = Database.session(), user: User, operatorId: Int) async throws { try await p.deleteOperator(session: session, user: user, operatorId: operatorId) }

    public func startWorkUnit(session: Database.Session = Database.session(), user: User, workUnitId: Int) async throws -> WorkUnit { try await p.startWorkUnit(session: session, user: user, workUnitId: workUnitId) }

    public func createStation(session: Database.Session = Database.session(), user: User, lineId: Int, name: String?, index: Int?) async throws -> Station { try await p.createStation(session: session, user: user, lineId: lineId, name: name, index: index) }
    public func station(session: Database.Session = Database.session(), user: User, stationId: Int) async throws -> Station { try await p.station(session: session, user: user, stationId: stationId) }
    public func stationNotificationTriggers(session: Database.Session = Database.session(), user: User, stationId: Int) async throws -> [ListItem] { try await p.stationNotificationTriggers(session: session, user: user, stationId: stationId) }
    public func stationOperations(session: Database.Session = Database.session(), user: User, stationId: Int) async throws -> [ListItem] { try await p.stationOperations(session: session, user: user, stationId: stationId) }
    public func stationWorkUnits(session: Database.Session = Database.session(), user: User, stationId: Int) async throws -> [WorkUnit] { try await p.stationWorkUnits(session: session, user: user, stationId: stationId) }
    public func saveStation(session: Database.Session = Database.session(), user: User, stationId: Int, name: String?, assigneeAction: String?, assigneeIds: [Int]?, theme: Theme?) async throws -> Station { try await p.saveStation(session: session, user: user, stationId: stationId, name: name, assigneeAction: assigneeAction, assigneeIds: assigneeIds, theme: theme) }
    public func saveStationPosition(session: Database.Session = Database.session(), user: User, id: Station.ID, position: Int) async throws { try await p.saveStationPosition(session: session, user: user, id: id, position: position) }
    public func saveStationTypeIntakeQueue(session: Database.Session = Database.session(), user: User, stationId: Int, intakeQueueId: Int) async throws { try await p.saveStationTypeIntakeQueue(session: session, user: user, stationId: stationId, intakeQueueId: intakeQueueId) }
    public func saveStationTypeStation(session: Database.Session = Database.session(), user: User, stationId: Int) async throws { try await p.saveStationTypeStation(session: session, user: user, stationId: stationId) }
    public func saveStationName(session: Database.Session = Database.session(), user: User, stationId: Int, name: String) async throws { try await p.saveStationName(session: session, user: user, stationId: stationId, name: name) }
    public func saveStationOperationPositions(session: Database.Session = Database.session(), user: User, stationId: Int, position: Int, operationIds: [Int]) async throws { try await p.saveStationOperationPositions(session: session, user: user, stationId: stationId, position: position, operationIds: operationIds) }
    public func saveStationViewState(session: Database.Session = Database.session(), user: User, stationId: Int, overlay: String) async throws { try await p.saveStationViewState(session: session, user: user, stationId: stationId, overlay: overlay) }
    public func deleteStation(session: Database.Session = Database.session(), user: User, stationId: Int) async throws { try await p.deleteStation(session: session, user: user, stationId: stationId) }

    public func createStationNotificationTrigger(session: Database.Session = Database.session(), user: User, stationId: Int, events: [String], operatorIds: [Int], message: String?) async throws -> StationNotificationTrigger { try await p.createStationNotificationTrigger(session: session, user: user, stationId: stationId, events: events, operatorIds: operatorIds, message: message) }
    public func stationNotificationTrigger(session: Database.Session = Database.session(), user: User, triggerId: Int) async throws -> StationNotificationTrigger { try await p.stationNotificationTrigger(session: session, user: user, triggerId: triggerId) }
    public func saveStationNotificationTrigger(session: Database.Session = Database.session(), user: User, triggerId: Int, events: [String]?, operatorIds: [Int]?, message: String?) async throws -> StationNotificationTrigger { try await p.saveStationNotificationTrigger(session: session, user: user, triggerId: triggerId, events: events, operatorIds: operatorIds, message: message) }
    public func deleteStationNotificationTrigger(session: Database.Session = Database.session(), user: User, triggerId: Int) async throws { try await p.deleteStationNotificationTrigger(session: session, user: user, triggerId: triggerId) }

    public func suggestedAgents(session: Database.Session = Database.session(), user: User, companyId: Int) async throws -> [SuggestedItem] { try await p.suggestedAgents(session: session, user: user, companyId: companyId) }
    public func suggestedIntakeQueue(session: Database.Session = Database.session(), user: User, lineId: Int) async throws -> [SuggestedItem] { try await p.suggestedIntakeQueue(session: session, user: user, lineId: lineId) }
    public func suggestedIntakeQueues(session: Database.Session = Database.session(), user: User, companyId: Int) async throws -> [SuggestedItem] { try await p.suggestedIntakeQueues(session: session, user: user, companyId: companyId) }
    public func suggestedInventories(session: Database.Session = Database.session(), user: User, companyId: Int) async throws -> [SuggestedItem] { try await p.suggestedInventories(session: session, user: user, companyId: companyId) }
    public func suggestedMimeTypes(session: Database.Session = Database.session(), user: User) async throws -> [SuggestedItem] { try await p.suggestedMimeTypes(session: session, user: user) }
    public func suggestedOperators(session: Database.Session = Database.session(), user: User, companyId: Int) async throws -> [SuggestedItem] { try await p.suggestedOperators(session: session, user: user, companyId: companyId) }
    public func suggestedSupplies(session: Database.Session = Database.session(), user: User, companyId: Int) async throws -> [SuggestedItem] { try await p.suggestedSupplies(session: session, user: user, companyId: companyId) }
    public func suggestedWorkUnit(session: Database.Session = Database.session(), user: User, companyId: Int) async throws -> [SuggestedItem] { try await p.suggestedWorkUnit(session: session, user: user, companyId: companyId) }
    public func suggestedSupplyFieldOptions(session: Database.Session = Database.session(), user: User, supplyFieldId: Int) async throws -> [SuggestedItem] { try await p.suggestedSupplyFieldOptions(session: session, user: user, supplyFieldId: supplyFieldId) }
    public func findSupplyFieldOptions(session: Database.Session = Database.session(), user: User, supplyFieldId: Int, query: String) async throws -> [FoundItem] { try await p.findSupplyFieldOptions(session: session, user: user, supplyFieldId: supplyFieldId, query: query) }

    public func createSupply(session: Database.Session = Database.session(), user: User, companyId: Int, name: String, theme: Theme?, amount: Int?) async throws -> ListItem { try await p.createSupply(session: session, user: user, companyId: companyId, name: name, theme: theme, amount: amount) }
    public func supply(session: Database.Session = Database.session(), user: User, supplyId: Int) async throws -> Supply { try await p.supply(session: session, user: user, supplyId: supplyId) }
    public func saveSupply(session: Database.Session = Database.session(), user: User, supplyId: Int, name: String, theme: Theme?, amount: Int?) async throws -> Supply { try await p.saveSupply(session: session, user: user, supplyId: supplyId, name: name, theme: theme, amount: amount) }
    public func deleteSupply(session: Database.Session = Database.session(), user: User, supplyId: Int) async throws { try await p.deleteSupply(session: session, user: user, supplyId: supplyId) }
    public func supplyFields(session: Database.Session = Database.session(), user: User, supplyId: Int) async throws -> [ListItem] { try await p.supplyFields(session: session, user: user, supplyId: supplyId) }
    public func saveSupplyFieldPositions(session: Database.Session = Database.session(), user: User, supplyId: Int, position: Int, fieldIds: [Int]) async throws { try await p.saveSupplyFieldPositions(session: session, user: user, supplyId: supplyId, position: position, fieldIds: fieldIds) }

    public func createSupplyField(session: Database.Session = Database.session(), user: User, supplyId: Int, name: String) async throws -> SupplyField { try await p.createSupplyField(session: session, user: user, supplyId: supplyId, name: name) }
    public func supplyField(session: Database.Session = Database.session(), user: User, supplyFieldId: Int) async throws -> SupplyField { try await p.supplyField(session: session, user: user, supplyFieldId: supplyFieldId) }
    public func supplyFieldOptions(session: Database.Session = Database.session(), user: User, supplyFieldId: Int) async throws -> [ListItem] { try await p.supplyFieldOptions(session: session, user: user, supplyFieldId: supplyFieldId) }
    public func saveSupplyField(session: Database.Session = Database.session(), user: User, supplyFieldId: Int, name: String?, type: String?, textType: String?, placeholder: String?, intakeQueueId: Int?, append: Bool?, optionNames: [String]?) async throws -> SupplyField { try await p.saveSupplyField(session: session, user: user, supplyFieldId: supplyFieldId, name: name, type: type, textType: textType, placeholder: placeholder, intakeQueueId: intakeQueueId, append: append, optionNames: optionNames) }
    public func deleteSupplyField(session: Database.Session = Database.session(), user: User, supplyFieldId: Int) async throws { try await p.deleteSupplyField(session: session, user: user, supplyFieldId: supplyFieldId) }

    public func createSupplyFieldOption(session: Database.Session = Database.session(), user: User, supplyFieldId: Int, name: String, hidden: Bool?) async throws -> SupplyFieldOption { try await p.createSupplyFieldOption(session: session, user: user, supplyFieldId: supplyFieldId, name: name, hidden: hidden) }
    public func supplyFieldOption(session: Database.Session = Database.session(), user: User, supplyFieldOptionId: Int) async throws -> SupplyFieldOption { try await p.supplyFieldOption(session: session, user: user, supplyFieldOptionId: supplyFieldOptionId) }
    public func saveSupplyFieldOption(session: Database.Session = Database.session(), user: User, supplyFieldOptionId: Int, name: String?, hidden: Bool?) async throws -> SupplyFieldOption { try await p.saveSupplyFieldOption(session: session, user: user, supplyFieldOptionId: supplyFieldOptionId, name: name, hidden: hidden) }
    public func deleteSupplyFieldOption(session: Database.Session = Database.session(), user: User, supplyFieldOptionId: Int) async throws { try await p.deleteSupplyFieldOption(session: session, user: user, supplyFieldOptionId: supplyFieldOptionId) }

    public func createWorkUnit(session: Database.Session = Database.session(), user: User, intakeQueueId: Int, name: String?, reporterId: Int?, assigneeIds: [Int], parentWorkUnitId: Int?) async throws -> WorkUnit { try await p.createWorkUnit(session: session, user: user, intakeQueueId: intakeQueueId, name: name, reporterId: reporterId, assigneeIds: assigneeIds, parentWorkUnitId: parentWorkUnitId) }
    public func saveWorkUnitChild(session: Database.Session = Database.session(), user: User, workUnitId: Int, childWorkUnitId: Int) async throws { try await p.saveWorkUnitChild(session: session, user: user, workUnitId: workUnitId, childWorkUnitId: childWorkUnitId) }
    public func saveWorkUnitHold(session: Database.Session = Database.session(), user: User, workUnitId: Int) async throws { try await p.saveWorkUnitHold(session: session, user: user, workUnitId: workUnitId) }
    public func workUnit(session: Database.Session = Database.session(), user: User, workUnitId: Int) async throws -> WorkUnit { try await p.workUnit(session: session, user: user, workUnitId: workUnitId) }
    public func workUnitChildren(session: Database.Session = Database.session(), user: User, workUnitId: Int) async throws -> [WorkUnit] { try await p.workUnitChildren(session: session, user: user, workUnitId: workUnitId) }
    public func saveWorkUnit(session: Database.Session = Database.session(), user: User, workUnitId: Int, name: String?, eta: String?) async throws -> WorkUnit { try await p.saveWorkUnit(session: session, user: user, workUnitId: workUnitId, name: name, eta: eta) }
    public func saveWorkUnitAssignees(session: Database.Session = Database.session(), user: User, workUnitId: Int, operatorIds: [Int]) async throws { try await p.saveWorkUnitAssignees(session: session, user: user, workUnitId: workUnitId, operatorIds: operatorIds) }
    public func saveWorkUnitParent(session: Database.Session = Database.session(), user: User, workUnitId: Int, parentWorkUnitId: Int?) async throws { try await p.saveWorkUnitParent(session: session, user: user, workUnitId: workUnitId, parentWorkUnitId: parentWorkUnitId) }
    public func saveWorkUnitReporter(session: Database.Session = Database.session(), user: User, workUnitId: Int, operatorId: Int?) async throws { try await p.saveWorkUnitReporter(session: session, user: user, workUnitId: workUnitId, operatorId: operatorId) }
    public func deleteWorkUnit(session: Database.Session = Database.session(), user: User, workUnitId: Int) async throws { try await p.deleteWorkUnit(session: session, user: user, workUnitId: workUnitId) }
    public func deleteWorkUnitChild(session: Database.Session = Database.session(), user: User, workUnitId: Int, childWorkUnitId: Int) async throws { try await p.deleteWorkUnitChild(session: session, user: user, workUnitId: workUnitId, childWorkUnitId: childWorkUnitId) }
    public func deleteWorkUnitHold(session: Database.Session = Database.session(), user: User, workUnitId: Int, comments: String?) async throws { try await p.deleteWorkUnitHold(session: session, user: user, workUnitId: workUnitId, comments: comments) }

    public func saveWorkUnitComment(session: Database.Session = Database.session(), user: User, workUnitId: Int, text: String) async throws { try await p.saveWorkUnitComment(session: session, user: user, workUnitId: workUnitId, text: text) }
    public func saveWorkUnitComment(session: Database.Session = Database.session(), user: User, commentId: Int, text: String) async throws { try await p.saveWorkUnitComment(session: session, user: user, commentId: commentId, text: text) }
    public func deleteWorkUnitComment(session: Database.Session = Database.session(), user: User, commentId: Int) async throws { try await p.deleteWorkUnitComment(session: session, user: user, commentId: commentId) }

    public func saveWorkUnitPosition(session: Database.Session = Database.session(), user: User, position: Int, workUnitIds: [Int]) async throws { try await p.saveWorkUnitPosition(session: session, user: user, position: position, workUnitIds: workUnitIds) }

    public func workUnits(session: Database.Session = Database.session(), user: User, intakeQueueId: Int) async throws -> [WorkUnit] { try await p.workUnits(session: session, user: user, intakeQueueId: intakeQueueId) }
    public func workUnitLogs(session: Database.Session = Database.session(), user: User, workUnitId: Int) async throws -> [WorkUnitLog] { try await p.workUnitLogs(session: session, user: user, workUnitId: workUnitId) }
    public func saveWorkUnits(session: Database.Session = Database.session(), user: User, intakeQueueId: Int, name: String?, key: String?, mixRatioType: String?, mixRatio: Int?, workUnitNameType: String?, workUnitMaterialName: String?, theme: Theme?) async throws { try await p.saveWorkUnits(session: session, user: user, intakeQueueId: intakeQueueId, name: name, key: key, mixRatioType: mixRatioType, mixRatio: mixRatio, workUnitNameType: workUnitNameType, workUnitMaterialName: workUnitMaterialName, theme: theme) }

    public func workspace(session: Database.Session = Database.session(), user: User, workUnitId: Int) async throws -> Workspace { try await p.workspace(session: session, user: user, workUnitId: workUnitId) }

    public func saveWorkUnitMoveToNextStation(session: Database.Session = Database.session(), user: User, workUnitId: Int) async throws { try await p.saveWorkUnitMoveToNextStation(session: session, user: user, workUnitId: workUnitId) }

    public func saveWorkUnitSupply(session: Database.Session = Database.session(), user: User, id: Int, fields: [WorkUnitSupplyFieldInput]) async throws -> Workspace { try await p.saveWorkUnitSupply(session: session, user: user, id: id, fields: fields) }
    public func saveWorkUnitSupplyFulfill(session: Database.Session = Database.session(), user: User, id: Int) async throws -> Workspace { try await p.saveWorkUnitSupplyFulfill(session: session, user: user, id: id) }
    public func saveWorkUnitSupplyWaive(session: Database.Session = Database.session(), user: User, id: Int, comments: String) async throws -> Workspace { try await p.saveWorkUnitSupplyWaive(session: session, user: user, id: id, comments: comments) }

    public func suggestedWorkUnitsForIntakeQueue(session: Database.Session = Database.session(), user: User, intakeQueueId: Int) async throws -> [SuggestedItem] { try await p.suggestedWorkUnitsForIntakeQueue(session: session, user: user, intakeQueueId: intakeQueueId) }
    public func findWorkUnitsForIntakeQueue(session: Database.Session = Database.session(), user: User, intakeQueueId: Int, query: String) async throws -> [FoundItem] { try await p.findWorkUnitsForIntakeQueue(session: session, user: user, intakeQueueId: intakeQueueId, query: query) }
}
