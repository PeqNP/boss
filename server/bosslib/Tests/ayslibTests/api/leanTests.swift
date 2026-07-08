/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import Foundation
import SwiftOTP
import XCTest

@testable import bosslib

final class leanTests: XCTestCase {
    /// Test the saving, updating, and querying of all business models, with exceptions.
    /// Includes testing of flows, ordering of work units, etc.
    func testLeanModelCreationAndFlow() async throws {
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

        // it: should create a `Hopper`
        XCTAssertEqual(line.hopper.lineId, line.id)
        XCTAssertNil(line.hopper.lastIntakeQueueId)
        XCTAssertEqual(line.hopper.number, 0)
        XCTAssertNil(line.hopper.workUnit)

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
        
        // describe: create `IntakeQueues with only a name

        // when: the name is nil
        await XCTAssertError(
            try await api.lean.createIntakeQueue(user: user, lineId: line.id, name: nil, key: nil),
            api.error.RequiredParameter("name")
        )
        // it: should raise exception

        // when: the name is an empty string
        await XCTAssertError(
            try await api.lean.createIntakeQueue(user: user, lineId: line.id, name: "", key: nil),
            api.error.RequiredParameter("name")
        )
        // it: should raise exception

        // when: the name is valid; create `IntakeQueue` with name "Tasks"
        var tasks = try await api.lean.createIntakeQueue(user: user, lineId: line.id, name: "Tasks", key: nil)
        // it: should save the `IntakeQueue` correctly
        // it: should set the mix ratio to 100%
        XCTAssertEqual(tasks.mixRatio, 100)

        // NOTE: The mix ratio must always be equal to 100% between all `IntakeQueues`
        // NOTE: The top-most `IntakeQueue` will always get the left-over ratio
        
        // describe: validate key name

        // when: key name is less than 2 characters
        // it: should raise error
        await XCTAssertError(
            try await api.lean.createIntakeQueue(user: user, lineId: line.id, name: "Backlog", key: "X"),
            service.error.InvalidInput("Key must be 2-4 characters")
        )

        // when: key name is greater than 4 characters
        // it: should raise error
        await XCTAssertError(
            try await api.lean.createIntakeQueue(user: user, lineId: line.id, name: "Backlog", key: "TOOLNG"),
            service.error.InvalidInput("Key must be 2-4 characters")
        )
        
        // describe: create an `IntakeQueue` with name "Bugs"; key name is valid
        var bugs = try await api.lean.createIntakeQueue(user: user, lineId: line.id, name: "Bugs", key: "BUG")
        tasks = try await api.lean.intakeQueue(user: user, id: tasks.id)
        // it: should distribute the mix ratio to be even with the first `IntakeQueue` by 50%
        XCTAssertEqual(tasks.mixRatio, 50)
        XCTAssertEqual(bugs.mixRatio, 50)
        // it: should save the key
        XCTAssertEqual(bugs.key, "BUG")
        
        // describe: update an `IntakeQueue`'s name to "Support"
        var support = try await api.lean.createIntakeQueue(user: user, lineId: line.id, name: "Support", key: nil)
        bugs = try await api.lean.intakeQueue(user: user, id: bugs.id)
        tasks = try await api.lean.intakeQueue(user: user, id: tasks.id)
        // it: should distribute the mix ratio between all `IntakeQueues` to 33%, except the first. Which should be 34%
        XCTAssertEqual(tasks.mixRatio, 34)
        XCTAssertEqual(bugs.mixRatio, 33)
        XCTAssertEqual(support.mixRatio, 33)

        // describe: update an `IntakeQueue` record

        // when: name is nil
        await XCTAssertError(
            try await api.lean.updateIntakeQueueName(user: user, id: tasks.id, name: nil),
            api.error.RequiredParameter("name")
        )

        // when: name is empty
        await XCTAssertError(
            try await api.lean.updateIntakeQueueName(user: user, id: tasks.id, name: ""),
            api.error.RequiredParameter("name")
        )

        // when: name is valid
        try await api.lean.updateIntakeQueueName(user: user, id: tasks.id, name: "Feature Requests")
        tasks = try await api.lean.intakeQueue(user: user, id: tasks.id)
        // it: should update the name
        XCTAssertEqual(tasks.name, "Feature Requests")

        // describe: update `IntakeQueue` mix ratio

        // when: updating `IntakeQueue` (Tasks) mix ratio to 60%
        try await api.lean.updateIntakeQueueMixRatio(user: user, id: tasks.id, mixRatio: 60)
        tasks = try await api.lean.intakeQueue(user: user, id: tasks.id)
        bugs = try await api.lean.intakeQueue(user: user, id: bugs.id)
        support = try await api.lean.intakeQueue(user: user, id: support.id)
        // it: should update (Tasks) mix ratio to 60%
        XCTAssertEqual(tasks.mixRatio, 60)
        // it: should update (Bugs) mix ratio to 20%
        XCTAssertEqual(bugs.mixRatio, 20)
        // it: should update (Support) mix ratio to 20%
        XCTAssertEqual(support.mixRatio, 20)

        // describe: mix ratio edge cases

        // when: mix ratio is less than zero
        // it: should raise error
        await XCTAssertError(
            try await api.lean.updateIntakeQueueMixRatio(user: user, id: tasks.id, mixRatio: -1),
            service.error.InvalidInput("Invalid mix ratio")
        )

        // when: mix ratio is greater than 100
        // it: should raise error
        await XCTAssertError(
            try await api.lean.updateIntakeQueueMixRatio(user: user, id: tasks.id, mixRatio: 101),
            service.error.InvalidInput("Invalid mix ratio")
        )

        // when: mix ratio forces sibling `IntakeQueue`s to receive less than 1% each
        // NOTE: Setting (Tasks) to 99% leaves only 1% for 2 distributed siblings. The maximum
        // valid value for (Tasks) with 2 distributed siblings is 98%.
        // it: should raise error
        await XCTAssertError(
            try await api.lean.updateIntakeQueueMixRatio(user: user, id: tasks.id, mixRatio: 99),
            service.error.InvalidInput("Invalid mix ratio. The remaining ratio cannot be evenly distributed among sibling intake queues.")
        )

        // when: the remainder can be distributed as whole values
        // NOTE: 97% leaves 3% for 2 siblings: the first absorbs the remainder, giving Bugs 2% and Support 1%.
        try await api.lean.updateIntakeQueueMixRatio(user: user, id: tasks.id, mixRatio: 97)
        tasks = try await api.lean.intakeQueue(user: user, id: tasks.id)
        bugs = try await api.lean.intakeQueue(user: user, id: bugs.id)
        support = try await api.lean.intakeQueue(user: user, id: support.id)
        // it: should set (Tasks) to 97%
        XCTAssertEqual(tasks.mixRatio, 97)
        // it: should set (Bugs) to 2% -- absorbs the remainder as the first distributed queue
        XCTAssertEqual(bugs.mixRatio, 2)
        // it: should set (Support) to 1%
        XCTAssertEqual(support.mixRatio, 1)
        
        // describe: Re-order `IntakeQueue`s
        
        // Re-ordering model logic; this applies to all models that need to be re-ordered
        // - The start position is always zero
        // - A model moved to the top shall never be a value less than zero
        // - A model moved to the bottom shall never be greater than the total number of models -1. e.g. if there are 3 models, the last model will always be in positino 2 (3 models - 1 = 2)
        // - All model positions are updated to reflect their updated state. Such that, if a model moves from index 1 to the bottom, it will now be at index 2, and the model that used to be in last position, will now be at index 1. The model at index 0 will be left untouched. When making changes to the database, it should only update the necessary records.
        
        // when: position is less than zero
        // it: should raise error
        await XCTAssertError(
            try await api.lean.saveIntakeQueuePosition(user: user, id: bugs.id, position: -1),
            service.error.InvalidInput("Invalid position")
        )

        // when: position is greater than the last index
        // it: should raise error
        await XCTAssertError(
            try await api.lean.saveIntakeQueuePosition(user: user, id: bugs.id, position: 3),
            service.error.InvalidInput("Invalid position")
        )

        // when: Bugs is moved above Tasks
        // note: mix-ratio types remain unchanged; this reorders intake queues only
        try await api.lean.saveIntakeQueuePosition(user: user, id: bugs.id, position: 0)
        let floorAfterBugsTop = try await api.lean.factoryFloor(user: user, factoryId: factory.id)
        let lineAfterBugsTop = try XCTUnwrap(floorAfterBugsTop.lines.first(where: { $0.id == line.id }))
        // it: should move Bugs to index 0 and shift others accordingly
        XCTAssertEqual(lineAfterBugsTop.intakeQueues.map(\.id), [bugs.id, tasks.id, support.id])

        // when: Tasks is moved back above Bugs
        try await api.lean.saveIntakeQueuePosition(user: user, id: tasks.id, position: 0)
        let floorAfterTasksTop = try await api.lean.factoryFloor(user: user, factoryId: factory.id)
        let lineAfterTasksTop = try XCTUnwrap(floorAfterTasksTop.lines.first(where: { $0.id == line.id }))
        // it: should restore original order
        XCTAssertEqual(lineAfterTasksTop.intakeQueues.map(\.id), [tasks.id, bugs.id, support.id])

        // when: Bugs is moved to the last position
        try await api.lean.saveIntakeQueuePosition(user: user, id: bugs.id, position: 2)
        let floorAfterBugsLast = try await api.lean.factoryFloor(user: user, factoryId: factory.id)
        let lineAfterBugsLast = try XCTUnwrap(floorAfterBugsLast.lines.first(where: { $0.id == line.id }))
        // it: should move Bugs to the last position
        XCTAssertEqual(lineAfterBugsLast.intakeQueues.map(\.id), [tasks.id, support.id, bugs.id])
        
        // describe: update a `Company`

        // when: name is nil
        await XCTAssertError(try await api.lean.updateCompany(user: user, id: company.id, name: nil), api.error.RequiredParameter("name"))
        // when: name is empty
        await XCTAssertError(try await api.lean.updateCompany(user: user, id: company.id, name: ""), api.error.RequiredParameter("name"))
        // when: name is valid
        try await api.lean.updateCompany(user: user, id: company.id, name: "Updated Company")

        // describe: query for a `Company`

        let fetchedCompany = try await api.lean.company(user: user, id: company.id)
        // it: should return the updated company
        XCTAssertEqual(fetchedCompany.id, company.id)
        XCTAssertEqual(fetchedCompany.name, "Updated Company")

        // describe: update a `Factory`

        // when: name is nil
        await XCTAssertError(try await api.lean.updateFactory(user: user, id: factory.id, name: nil), api.error.RequiredParameter("name"))
        // when: name is empty
        await XCTAssertError(try await api.lean.updateFactory(user: user, id: factory.id, name: ""), api.error.RequiredParameter("name"))
        // when: name is valid
        try await api.lean.updateFactory(user: user, id: factory.id, name: "Updated Factory")

        // describe: query for a `Factory`

        let fetchedFactory = try await api.lean.factory(user: user, id: factory.id)
        // it: should return the updated factory
        XCTAssertEqual(fetchedFactory.id, factory.id)
        XCTAssertEqual(fetchedFactory.name, "Updated Factory")

        // describe: update an `Inventory`'s name

        // when: name is nil
        await XCTAssertError(try await api.lean.updateInventoryName(user: user, id: inventory.id, name: nil), api.error.RequiredParameter("name"))
        // when: name is empty
        await XCTAssertError(try await api.lean.updateInventoryName(user: user, id: inventory.id, name: ""), api.error.RequiredParameter("name"))
        // when: name is valid
        try await api.lean.updateInventoryName(user: user, id: inventory.id, name: "Updated Inventory")

        // describe: query for an `Inventory`

        let fetchedInventory = try await api.lean.inventory(user: user, id: inventory.id)
        // it: should return the updated inventory
        XCTAssertEqual(fetchedInventory.id, inventory.id)
        XCTAssertEqual(fetchedInventory.supply.name, "Updated Inventory")

        // describe: update a `Line`'s name

        // when: name is nil
        await XCTAssertError(try await api.lean.updateLineName(user: user, id: line.id, name: nil), api.error.RequiredParameter("name"))
        // when: name is empty
        await XCTAssertError(try await api.lean.updateLineName(user: user, id: line.id, name: ""), api.error.RequiredParameter("name"))
        // when: name is valid
        try await api.lean.updateLineName(user: user, id: line.id, name: "Software development")

        // describe: query for a `Line`

        let fetchedLine = try await api.lean.line(user: user, id: line.id)
        // it: should return the updated line
        XCTAssertEqual(fetchedLine.id, line.id)
        XCTAssertEqual(fetchedLine.name, "Software development")

        // describe: save the `Line`'s position

        // when: x is negative
        await XCTAssertError(
            try await api.lean.saveLinePosition(user: user, id: line.id, x: -1, y: 0),
            service.error.InvalidInput("Position cannot be negative")
        )

        // when: y is negative
        await XCTAssertError(
            try await api.lean.saveLinePosition(user: user, id: line.id, x: 0, y: -1),
            service.error.InvalidInput("Position cannot be negative")
        )

        // when: x and y are valid
        try await api.lean.saveLinePosition(user: user, id: line.id, x: 10, y: 20)
        let lineAfterPosition = try await api.lean.line(user: user, id: line.id)
        // it: should persist x and y
        XCTAssertEqual(lineAfterPosition.viewState.x, 10)
        XCTAssertEqual(lineAfterPosition.viewState.y, 20)

        // describe: save the `Line`'s locked state

        // when: locking the line
        try await api.lean.saveLineLocked(user: user, id: line.id, locked: true)
        let lineAfterLocked = try await api.lean.line(user: user, id: line.id)
        // it: should persist locked = true
        XCTAssertTrue(lineAfterLocked.viewState.locked)

        // when: unlocking the line
        try await api.lean.saveLineLocked(user: user, id: line.id, locked: false)
        let lineAfterUnlocked = try await api.lean.line(user: user, id: line.id)
        // it: should persist locked = false
        XCTAssertFalse(lineAfterUnlocked.viewState.locked)

        // describe: save the `Line`'s focus state

        // when: focusing the line
        try await api.lean.saveLineFocus(user: user, id: line.id, focused: true)
        let lineAfterFocus = try await api.lean.line(user: user, id: line.id)
        // it: should persist focused = true
        XCTAssertTrue(lineAfterFocus.viewState.focused)

        // when: unfocusing the line
        try await api.lean.saveLineFocus(user: user, id: line.id, focused: false)
        let lineAfterUnfocused = try await api.lean.line(user: user, id: line.id)
        // it: should persist focused = false
        XCTAssertFalse(lineAfterUnfocused.viewState.focused)

        // describe: save the `Inventory`'s position

        // when: x is negative
        await XCTAssertError(
            try await api.lean.saveInventoryPosition(user: user, id: inventory.id, x: -1, y: 0),
            service.error.InvalidInput("Position cannot be negative")
        )

        // when: y is negative
        await XCTAssertError(
            try await api.lean.saveInventoryPosition(user: user, id: inventory.id, x: 0, y: -1),
            service.error.InvalidInput("Position cannot be negative")
        )

        // when: x and y are valid
        try await api.lean.saveInventoryPosition(user: user, id: inventory.id, x: 5, y: 15)
        let inventoryAfterPosition = try await api.lean.inventory(user: user, id: inventory.id)
        // it: should persist x and y
        XCTAssertEqual(inventoryAfterPosition.viewState.x, 5)
        XCTAssertEqual(inventoryAfterPosition.viewState.y, 15)

        // describe: save the `Inventory`'s locked state

        // when: locking the inventory
        try await api.lean.saveInventoryLocked(user: user, id: inventory.id, locked: true)
        let inventoryAfterLocked = try await api.lean.inventory(user: user, id: inventory.id)
        // it: should persist locked = true
        XCTAssertTrue(inventoryAfterLocked.viewState.locked)

        // when: unlocking the inventory
        try await api.lean.saveInventoryLocked(user: user, id: inventory.id, locked: false)
        let inventoryAfterUnlocked = try await api.lean.inventory(user: user, id: inventory.id)
        // it: should persist locked = false
        XCTAssertFalse(inventoryAfterUnlocked.viewState.locked)

        // describe: save the `Inventory`'s focus state

        // when: focusing the inventory
        try await api.lean.saveInventoryFocus(user: user, id: inventory.id, focused: true)
        let inventoryAfterFocus = try await api.lean.inventory(user: user, id: inventory.id)
        // it: should persist focused = true
        XCTAssertTrue(inventoryAfterFocus.viewState.focused)

        // when: unfocusing the inventory
        try await api.lean.saveInventoryFocus(user: user, id: inventory.id, focused: false)
        let inventoryAfterUnfocused = try await api.lean.inventory(user: user, id: inventory.id)
        // it: should persist focused = false
        XCTAssertFalse(inventoryAfterUnfocused.viewState.focused)

        // MARK: `WorkUnit` flow
        
        // describe: create a `WorkUnit` on a line (name: "First task")

        // when: the name is nil
        // it: should raise an exception
        await XCTAssertError(
            try await api.lean.createWorkUnit(user: user, intakeQueueId: tasks.id, name: nil, reporterId: nil, assigneeIds: [], parentWorkUnitId: nil),
            api.error.RequiredParameter("name")
        )

        // when: the name is empty
        // it: should raise an exception
        await XCTAssertError(
            try await api.lean.createWorkUnit(user: user, intakeQueueId: tasks.id, name: "", reporterId: nil, assigneeIds: [], parentWorkUnitId: nil),
            api.error.RequiredParameter("name")
        )

        // when: the name is valid
        var firstTask = try await api.lean.createWorkUnit(user: user, intakeQueueId: tasks.id, name: "First task", reporterId: nil, assigneeIds: [], parentWorkUnitId: nil)
        // it: should create WorkUnit
        XCTAssertEqual(firstTask.name, "First task")
        XCTAssertEqual(firstTask.intakeQueueID, tasks.id)

        // it: should set the `WorkUnit` to the `Line`'s hopper -- as it's the only `WorkUnit`
        let floorAfterFirstTask = try await api.lean.factoryFloor(user: user, factoryId: factory.id)
        let lineAfterFirstTask = try XCTUnwrap(floorAfterFirstTask.lines.first(where: { $0.id == line.id }))
        XCTAssertEqual(lineAfterFirstTask.hopper.workUnit?.id, firstTask.id)

        // it: should create `WorkUnitLog` to log the creation of the `WorkUnit`
        let logsAfterFirstTask = try await api.lean.workUnitLogs(user: user, workUnitId: firstTask.id)
        XCTAssertEqual(logsAfterFirstTask.count, 1)
        let firstTaskLog = try XCTUnwrap(logsAfterFirstTask.first)
        if case .intakeQueue(let iqId, _) = firstTaskLog.lineState {
            XCTAssertEqual(iqId, tasks.id)
        } else {
            XCTFail("Expected intakeQueue line state")
        }
        
        // describe: query `IntakeQueue`'s `WorkUnit`s
        let tasksWorkUnits = try await api.lean.workUnits(user: user, intakeQueueId: tasks.id)
        // it: should return the newly created `WorkUnit`
        XCTAssertEqual(tasksWorkUnits.count, 1)
        XCTAssertEqual(tasksWorkUnits[0].id, firstTask.id)

        // NOTE: These `WorkUnit`s will be used to test hopper, re-ordering logic, etc.
        // describe: create three more `WorkUnit`s (names: "Second task", "Third task", "Fourth task") in first `IntakeQueue`
        let secondTask = try await api.lean.createWorkUnit(user: user, intakeQueueId: tasks.id, name: "Second task", reporterId: nil, assigneeIds: [], parentWorkUnitId: nil)
        let thirdTask = try await api.lean.createWorkUnit(user: user, intakeQueueId: tasks.id, name: "Third task", reporterId: nil, assigneeIds: [], parentWorkUnitId: nil)
        let fourthTask = try await api.lean.createWorkUnit(user: user, intakeQueueId: tasks.id, name: "Fourth task", reporterId: nil, assigneeIds: [], parentWorkUnitId: nil)
        let tasksWorkUnitsAfterCreation = try await api.lean.workUnits(user: user, intakeQueueId: tasks.id)
        // it: should order the new `WorkUnit`s below the previous `WorkUnit`s in the correct order
        XCTAssertEqual(tasksWorkUnitsAfterCreation.map(\.id), [firstTask.id, secondTask.id, thirdTask.id, fourthTask.id])
        
        // describe: create two more `WorkUnit`s (names: "First bug", "Second bug") in the second `IntakeQueue` -- used for hopper logic
        let firstBug = try await api.lean.createWorkUnit(user: user, intakeQueueId: bugs.id, name: "First bug", reporterId: nil, assigneeIds: [], parentWorkUnitId: nil)
        let secondBug = try await api.lean.createWorkUnit(user: user, intakeQueueId: bugs.id, name: "Second bug", reporterId: nil, assigneeIds: [], parentWorkUnitId: nil)
        let bugsWorkUnits = try await api.lean.workUnits(user: user, intakeQueueId: bugs.id)
        XCTAssertEqual(bugsWorkUnits.map(\.id), [firstBug.id, secondBug.id])

        // describe: update a `WorkUnit`

        // when: the name is nil
        await XCTAssertError(
            try await api.lean.saveWorkUnit(user: user, workUnitId: firstTask.id, name: nil, eta: nil),
            api.error.RequiredParameter("name")
        )
        // when: the name is empty
        await XCTAssertError(
            try await api.lean.saveWorkUnit(user: user, workUnitId: firstTask.id, name: "", eta: nil),
            api.error.RequiredParameter("name")
        )
        // when: the name is valid
        firstTask = try await api.lean.saveWorkUnit(user: user, workUnitId: firstTask.id, name: "First task (updated)", eta: nil)
        // it: should update all values correctly
        XCTAssertEqual(firstTask.name, "First task (updated)")
        
        // describe: start a `WorkUnit`; no `Station`s exist -- moves the current `WorkUnit` from a `Line`'s hopper to the first `Station`
        // it: should do nothing
        _ = try await api.lean.startWorkUnit(user: user, workUnitId: firstTask.id)
        let floorNoStations = try await api.lean.factoryFloor(user: user, factoryId: factory.id)
        let lineNoStations = try XCTUnwrap(floorNoStations.lines.first(where: { $0.id == line.id }))
        XCTAssertEqual(lineNoStations.hopper.workUnit?.id, firstTask.id)

        // describe: create `Station` with name "In Progress"
        let inProgress = try await api.lean.createStation(user: user, lineId: line.id, name: "In Progress", index: nil)
        let floorAfterInProgress = try await api.lean.factoryFloor(user: user, factoryId: factory.id)
        let lineAfterInProgress = try XCTUnwrap(floorAfterInProgress.lines.first(where: { $0.id == line.id }))
        // it: should place station in sort record
        XCTAssertEqual(lineAfterInProgress.stations.map(\.id), [inProgress.id])

        // describe: create `Station` with name "Pending deployment" after "In Progress"
        let pendingDeployment = try await api.lean.createStation(user: user, lineId: line.id, name: "Pending deployment", index: 1)
        let floorAfterPending = try await api.lean.factoryFloor(user: user, factoryId: factory.id)
        let lineAfterPending = try XCTUnwrap(floorAfterPending.lines.first(where: { $0.id == line.id }))
        // it: should set (Pending deployment) `sortOrder` to `1`
        XCTAssertEqual(lineAfterPending.stations.map(\.id), [inProgress.id, pendingDeployment.id])

        // describe: create `Station` with name "QA" after "In Progress"
        let qa = try await api.lean.createStation(user: user, lineId: line.id, name: "QA", index: 1)
        let floorAfterQA = try await api.lean.factoryFloor(user: user, factoryId: factory.id)
        let lineAfterQA = try XCTUnwrap(floorAfterQA.lines.first(where: { $0.id == line.id }))
        // it: should set (QA) `sortOrder` to `1`
        // it: should set (Pending deployment) `sortOrder` to `2`
        XCTAssertEqual(lineAfterQA.stations.map(\.id), [inProgress.id, qa.id, pendingDeployment.id])

        // describe: query `IntakeQueue` `Stations`
        // it: should return the `Station`s in the correct order
        let floorForStationQuery = try await api.lean.factoryFloor(user: user, factoryId: factory.id)
        let lineForStationQuery = try XCTUnwrap(floorForStationQuery.lines.first(where: { $0.id == line.id }))
        XCTAssertEqual(lineForStationQuery.stations.map(\.id), [inProgress.id, qa.id, pendingDeployment.id])

        // describe: move station (QA) to first position
        try await api.lean.saveStationPosition(user: user, id: qa.id, position: 0)
        let floorQAFirst = try await api.lean.factoryFloor(user: user, factoryId: factory.id)
        let lineQAFirst = try XCTUnwrap(floorQAFirst.lines.first(where: { $0.id == line.id }))
        // it: should set (QA) `sortOrder` to `0`
        // it: should set (In Progress) `sortOrder` to `1`
        XCTAssertEqual(lineQAFirst.stations.map(\.id), [qa.id, inProgress.id, pendingDeployment.id])

        // describe: move station (QA) to last position
        try await api.lean.saveStationPosition(user: user, id: qa.id, position: 2)
        let floorQALast = try await api.lean.factoryFloor(user: user, factoryId: factory.id)
        let lineQALast = try XCTUnwrap(floorQALast.lines.first(where: { $0.id == line.id }))
        // it: should set (QA) `sortOrder` to `2`
        // it: should set (In Progress) `sortOrder` to `0`
        // it: should set (Pending deployment) `sortOrder` to `1`
        XCTAssertEqual(lineQALast.stations.map(\.id), [inProgress.id, pendingDeployment.id, qa.id])

        // describe: move station (QA) to middle position
        try await api.lean.saveStationPosition(user: user, id: qa.id, position: 1)
        let floorQAMiddle = try await api.lean.factoryFloor(user: user, factoryId: factory.id)
        let lineQAMiddle = try XCTUnwrap(floorQAMiddle.lines.first(where: { $0.id == line.id }))
        // it: should set (QA) `sortOrder` to `1`
        // it: should set (Pending deployment) `sortOrder` to `2`
        XCTAssertEqual(lineQAMiddle.stations.map(\.id), [inProgress.id, qa.id, pendingDeployment.id])

        // describe: re-order a `WorkUnit` in the (Tasks) `IntakeQueue`
        // note: positions out of bounds are silently clamped; no error is thrown

        // when: the first `WorkUnit`, in the `IntakeQueue` is attempting to be ordered above the 0th position
        // it: should do nothing
        try await api.lean.saveWorkUnitPosition(user: user, position: -1, workUnitIds: [firstTask.id])
        var tasksOrder = try await api.lean.workUnits(user: user, intakeQueueId: tasks.id)
        XCTAssertEqual(tasksOrder.map(\.id), [firstTask.id, secondTask.id, thirdTask.id, fourthTask.id])

        // when: moving `WorkUnit` to the same position it is currently in
        // it: should do nothing
        try await api.lean.saveWorkUnitPosition(user: user, position: 1, workUnitIds: [secondTask.id])
        tasksOrder = try await api.lean.workUnits(user: user, intakeQueueId: tasks.id)
        XCTAssertEqual(tasksOrder.map(\.id), [firstTask.id, secondTask.id, thirdTask.id, fourthTask.id])

        // when: the last `WorkUnit` is attempting to be ordered below itself
        // it: should do nothing
        try await api.lean.saveWorkUnitPosition(user: user, position: 4, workUnitIds: [fourthTask.id])
        tasksOrder = try await api.lean.workUnits(user: user, intakeQueueId: tasks.id)
        XCTAssertEqual(tasksOrder.map(\.id), [firstTask.id, secondTask.id, thirdTask.id, fourthTask.id])

        // when: the `WorkUnit` is already at the top
        // it: should do nothing
        try await api.lean.saveWorkUnitPosition(user: user, position: 0, workUnitIds: [firstTask.id])
        tasksOrder = try await api.lean.workUnits(user: user, intakeQueueId: tasks.id)
        XCTAssertEqual(tasksOrder.map(\.id), [firstTask.id, secondTask.id, thirdTask.id, fourthTask.id])

        // when: the `WorkUnit` is already at the bottom
        // it: should do nothing
        try await api.lean.saveWorkUnitPosition(user: user, position: 3, workUnitIds: [fourthTask.id])
        tasksOrder = try await api.lean.workUnits(user: user, intakeQueueId: tasks.id)
        XCTAssertEqual(tasksOrder.map(\.id), [firstTask.id, secondTask.id, thirdTask.id, fourthTask.id])

        // when: the (Third task) `WorkUnit` is moving up
        // it: should re-order the `WorkUnit` above the (Second task) `WorkUnit`
        try await api.lean.saveWorkUnitPosition(user: user, position: 0, workUnitIds: [thirdTask.id])
        tasksOrder = try await api.lean.workUnits(user: user, intakeQueueId: tasks.id)
        XCTAssertEqual(tasksOrder.map(\.id), [thirdTask.id, firstTask.id, secondTask.id, fourthTask.id])
        // it: should set the `Line`'s hopper to the (Third task)
        let floorAfterThirdTop = try await api.lean.factoryFloor(user: user, factoryId: factory.id)
        let lineAfterThirdTop = try XCTUnwrap(floorAfterThirdTop.lines.first(where: { $0.id == line.id }))
        XCTAssertEqual(lineAfterThirdTop.hopper.workUnit?.id, thirdTask.id)
        // it: should create a `WorkUnitLog` with position change
        let thirdTaskLogsAfterMove = try await api.lean.workUnitLogs(user: user, workUnitId: thirdTask.id)
        XCTAssertEqual(thirdTaskLogsAfterMove.count, 2)

        // when: the (Second task) `WorkUnit` is moving down
        // it: should re-order the `WorkUnit` below the (Fourth task) `WorkUnit`
        try await api.lean.saveWorkUnitPosition(user: user, position: 3, workUnitIds: [secondTask.id])
        tasksOrder = try await api.lean.workUnits(user: user, intakeQueueId: tasks.id)
        XCTAssertEqual(tasksOrder.map(\.id), [thirdTask.id, firstTask.id, fourthTask.id, secondTask.id])
        // it: should create `WorkUnitLog` with position change
        let secondTaskLogsAfterMove = try await api.lean.workUnitLogs(user: user, workUnitId: secondTask.id)
        XCTAssertEqual(secondTaskLogsAfterMove.count, 2)
        
        // NOTE: The Second task is moved back to the top for clarity of the following tests
        // TODO: describe: move (Second task) to the top of the `IntakeQueue` (Tasks)
        // it: should set the `Line`'s hopper to the correct `WorkUnit` (Second task)
        // it: should create a `WorkUnitLog` with position change
        
        // TODO: describe: start a `WorkUnit`
        // it: should move `WorkUnit` (First task) to first station (In Progress)
        // it: should create `WorkUnitLog` with change to `LineState.station`
        // it: should set `WorkUnit` (Second task) from (Tasks) to `Line`'s hopper
        // NOTE: Setting a `WorkUnit` to the `Line`'s hopper does _not_ move it out of the `IntakeQueue`
        
        // Demonstrate that the hopper logic is pulling from the correct `IntakeQueue`
        
        // TODO: describe: start a `WorkUnit`
        // it: should move `WorkUnit` (Second task) to first station (In Progress) below last `WorkUnit` in `Station`
        // it: should set `WorkUnit` (First bug) from (Bugs) to `Line`'s hopper
        
        // TODO: describe: query `Station`s (In progress) `WorkUnit`s
        // it: should return `WorkUnit`s in correct order (First task, Second task)
        
        // TODO: describe: Reorder `WorkUnit`s in `Station`
        // when: Second task is moved above First task
        // NOTE: This should query `Station`'s (In Progress) `WorkUnit`s
        // it: should return `WorkUnit`s in the correct order (Second task, First task)
        
        // when: Second task is moved below zero
        // it: should throw an error
        // when: Second task is moved to a position that does not exist
        // it: should throw an error
        
        // TODO: describe: create and order station operations for release workflow
        // context: creating required operations on QA station
        // it: should create `Operation` "Test plan" and attach test-case metadata
        // it: should create `Operation` "Testing" as a checkbox-style operation
        // it: should create `Operation` "Assign version" with version option list
        // context: reordering operations within QA station
        // it: should reorder `Operation`s using `StationOperations` and persist order

        // TODO: describe: move a work unit through release stages
        // context: moving the work unit from in-progress to QA
        // it: should move `WorkUnit` to QA and update line state logs
        // context: completing operations in QA
        // it: should move `WorkUnit` through each `Operation` in order
        // context: moving from QA to release completion
        // it: should move `WorkUnit` to Pending Deployment
        // it: should move `WorkUnit` to `Output`

        // MARK: Route-surface API plan (new APIs)

        // TODO: describe: open a factory floor snapshot
        // context: opening the floor for a valid factory
        // it: should include all lines for factory with view state
        // it: should include all inventories for factory with view state
        // it: should include stations/intake queues/work units per line
        // context: opening the floor for a non-existent factory
        // it: should raise record-not-found
        // note: schema blocker - verify v1_3_0 includes all columns needed to materialize floor projection (line view state, station view state, inventory view state)

        // TODO: describe: search for people and resources by typed term
        // context: searching agents/operators in a company with a matching term
        // it: should return only operators in the target company
        // it: should return filtered list by query term
        // context: searching intake queues within one line vs across one company
        // it: should respect line/company scope boundaries
        // context: searching inventories/supplies/work units in a company
        // it: should return list items with stable id/name projection
        // context: searching MIME types
        // it: should return filtered MIME options without requiring company scope
        // context: searching options for a single supply field
        // it: should return options scoped to supplyFieldId only
        // context: searching work units within a single intake queue
        // it: should return queue-scoped matches only

        // TODO: describe: load default suggestions before the user types
        // context: loading company and line scoped suggestions with valid ids
        // it: should return default suggestion lists per scope
        // context: loading suggestions when no matching records exist
        // it: should return empty arrays, not errors
        // context: loading default work-unit suggestions for an intake queue
        // it: should return options for only the provided intakeQueue
        // context: loading default options for a supply field
        // it: should return options for only the provided supply field

        // TODO: describe: upload, read, and delete an image asset
        // context: completing image lifecycle for a valid image upload
        // it: should persist file resource and fetch by id
        // it: should remove file resource and fail on subsequent fetch
        // context: non-image uploads
        // it: should reject non-image MIME types
        // note: schema blocker - confirm v1_3_0 file_resource metadata supports MIME/type validation path

        // TODO: describe: create and configure intake-queue settings
        // context: creating a new intake queue from a line
        // it: should create queue and return list item
        let routeSurfaceQueue = try await api.lean.createIntakeQueue(user: user, lineId: line.id, name: "Route Queue")
        XCTAssertGreaterThan(routeSurfaceQueue.id, 0)
        XCTAssertEqual(routeSurfaceQueue.name, "Route Queue")

        // context: reading the created queue
        // it: should return the created queue details
        let routeSurfaceQueueDetail = try await api.lean.intakeQueue(user: user, intakeQueueId: routeSurfaceQueue.id)
        XCTAssertEqual(routeSurfaceQueueDetail.id, routeSurfaceQueue.id)
        XCTAssertEqual(routeSurfaceQueueDetail.name, "Route Queue")

        // context: editing one intake queue from its details view
        // it: should update key/mix-ratio/work-unit-name/theme fields atomically
        // context: editing the same queue from the work-units screen
        // it: should mirror update semantics of saveIntakeQueue update path
        // note: schema blocker - confirm theme FK and work-unit-name discriminator columns exist and are nullable where required

        // TODO: describe: create and rename an inventory
        // context: creating inventory from a factory
        // it: should create inventory and return list item
        // context: renaming an existing inventory
        // it: should persist updated name and read back via inventory(id)

        // TODO: describe: create, configure, and remove a line
        // context: creating a line from factory actions and from name-only action
        // it: should create line and return list item
        // context: opening line details
        // it: should return full line model including view state defaults
        // context: updating line attributes (name/output/sub-assembly)
        // it: should update editable fields and preserve dependent records
        // context: deleting a line
        // it: should cascade delete line-dependent records only
        // note: schema blocker - verify line type/output/view-state columns in v1_3_0 match latest API parameters

        // TODO: describe: manage station operations
        // context: creating operations with each request type variant
        // it: should create operation with inventory/supply/intakeQueue request variants
        // context: opening operation details
        // it: should return operation with agent and supplyRequest projection
        // context: editing operation attributes and request settings
        // it: should update name/instructions/agent/request fields
        // context: reordering operations within one station
        // it: should reorder operations consistently in station
        // context: deleting an operation
        // it: should remove operation and preserve station integrity

        // TODO: describe: create, edit, and remove an operator profile
        // context: creating an operator from a user or agent identity
        // it: should create human or agent operator association
        // context: opening an operator profile
        // it: should return operator with correct type discriminator
        // context: editing an operator identity mapping
        // it: should update association and reject invalid mixed state
        // context: deleting an operator profile
        // it: should delete operator while preserving referential constraints
        // note: schema blocker - confirm operator type discriminator columns align with user/agent optionality

        // TODO: describe: start the next work unit from hopper
        // context: starting work when at least one station exists
        // it: should move current hopper work unit into first station
        // it: should return next hopper candidate according to mix-ratio logic
        // context: starting work when no station exists
        // it: should return nil nextWorkUnit and no state mutation

        // TODO: describe: create, configure, and remove stations
        // context: creating stations by append and by indexed insert
        // it: should insert at expected position and maintain station ordering
        // context: opening station details
        // it: should include type, assignee action, and metrics
        // context: listing station work units, operations, and notification triggers
        // it: should return list projections scoped to station
        // context: editing station details, assignee behavior, and theme
        // it: should validate assigneeAction semantics and apply theme updates
        // context: switching station type between intake-queue and station
        // it: should switch station type and enforce operation constraints
        // context: editing station name and overlay view state
        // it: should persist name and overlay/view state updates
        // context: deleting a station
        // it: should delete station and repair ordering references
        // note: schema blocker - verify station overlay/type/sort tables in v1_3_0 support current behavior

        // TODO: describe: manage station notification rules
        // context: creating a notification rule for a station
        // it: should validate at least one event and operator
        // context: opening one notification rule
        // it: should return trigger with normalized events
        // context: editing a notification rule
        // it: should support partial updates without clearing unspecified fields
        // context: deleting a notification rule
        // it: should delete trigger and no longer return in station list

        // TODO: describe: create, edit, and remove a supply definition
        // context: creating a supply in a company
        // it: should create supply and return list item
        // context: opening supply details
        // it: should return supply with fields and theme projection
        // context: editing supply name/theme/amount
        // it: should update editable fields and preserve field definitions
        // context: deleting a supply
        // it: should delete supply and enforce/cascade dependent records
        // context: listing supply fields and reordering their positions
        // it: should return/reorder field list correctly

        // TODO: describe: create, edit, read, and delete supply fields
        // context: creating a supply field on a supply
        // it: should create default field shape
        // context: opening one supply field
        // it: should return normalized type-specific projection
        // context: editing one supply field for each supported field type
        // it: should support text/file/radio/multiSelect/intakeQueue variants
        // context: deleting a supply field
        // it: should delete field and associated values/options safely
        // note: schema blocker - confirm polymorphic storage tables in v1_3_0 for field type variants

        // TODO: describe: create, list, edit, read, and delete supply field options
        // context: creating an option for a supply field
        // it: should append option and return record
        // context: opening one option by id
        // it: should return option with hidden flag
        // context: editing an option name and visibility
        // it: should support hide/unhide and rename
        // context: listing options for one supply field
        // it: should return only options belonging to that field
        // context: deleting an option
        // it: should remove option and handle existing selected values consistently

        // TODO: describe: create, edit, and restructure work units
        // context: creating a work unit in an intake queue
        // it: should create work unit with reporter/assignees/optional parent
        let firstRouteSurfaceWorkUnit = try await api.lean.createWorkUnit(
            user: user,
            intakeQueueId: routeSurfaceQueue.id,
            name: "First route-surface task",
            reporterId: nil,
            assigneeIds: [],
            parentWorkUnitId: nil
        )
        XCTAssertGreaterThan(firstRouteSurfaceWorkUnit.id, 0)
        XCTAssertEqual(firstRouteSurfaceWorkUnit.name, "First route-surface task")

        // context: starting work for created work unit
        // it: should return the updated WorkUnit directly
        let startedRouteSurfaceWorkUnit = try await api.lean.startWorkUnit(user: user, workUnitId: firstRouteSurfaceWorkUnit.id)
        XCTAssertEqual(startedRouteSurfaceWorkUnit.id, firstRouteSurfaceWorkUnit.id)

        // context: editing a work unit details payload
        // it: should update editable fields and preserve immutable fields
        // context: linking and unlinking parent-child work unit relation
        // it: should add/remove parent-child relation and prevent cycles
        // context: placing and removing hold state on a work unit
        // it: should set/clear hold state and append logs/comments as required
        // context: editing assignees, reporter, and parent as sub-resource updates
        // it: should update sub-resource fields without mutating unrelated fields
        // context: reordering work units within intake queue positions
        // it: should reorder intake queue work units with bounds validation
        // context: reading one work unit, its children, and queue list views
        // it: should return consistent projections for detail, children list, and queue list
        // context: deleting a work unit
        // it: should delete work unit and repair queue/station ordering references

        // TODO: describe: create, edit, and delete work unit comments
        // context: creating a comment on a work unit
        // it: should persist comment with author/date metadata
        // context: editing an existing comment
        // it: should update text and preserve thread metadata
        // context: deleting a comment
        // it: should remove comment and preserve sibling comments

        // TODO: describe: execute workspace supply workflow
        // context: opening workspace for a work unit
        // it: should return full operation + field state for active station
        // context: moving work unit to the next station
        // it: should enforce all required operations fulfilled or waived before move
        // context: saving supply field values for one operation work unit
        // it: should save field values and return updated workspace
        let fieldInputs = [
            WorkUnitSupplyFieldInput(
                fieldId: 1,
                value: "ok",
                selectedOptionIds: nil,
                fileResourceId: nil,
                workUnitId: nil
            )
        ]
        let updatedWorkspace = try await api.lean.saveWorkUnitSupply(user: user, id: 1, fields: fieldInputs)
        XCTAssertEqual(updatedWorkspace.workUnit.id, 1)

        // context: fulfilling a supply operation
        // it: should mark operation fulfilled and update workspace state
        // context: waiving a supply operation with comments
        // it: should mark operation waived with reason and update workspace state
        // note: schema blocker - verify work_unit_supplies and supply_field_values tables include all fields for latest API payload
        
        // TODO: describe: query `Output`
        // context: querying output after multiple completed work units
        // it: should return `WorkUnit`s ordered by `doneDate` in descending order
        
        // describe: delete a `Factory`

        // when: the factory does not exist
        // it: should raise Error
        await XCTAssertError(
            try await api.lean.deleteFactory(user: user, id: -1),
            service.error.RecordNotFound()
        )

        // when: the factory exists
        // it: should remove factory, lines, and all other related records
        try await api.lean.deleteFactory(user: user, id: factory.id)
        let remainingFactories = try await api.lean.factories(companyId: company.id)
        XCTAssertEqual(remainingFactories.count, 0)

        // describe: delete a `Company`

        // when: the company does not exist
        // it: should raise Error
        await XCTAssertError(
            try await api.lean.deleteCompany(user: user, id: -1),
            service.error.RecordNotFound()
        )

        // when: the company exists
        // it: should remove company, factory, lines, and all other related records
        try await api.lean.deleteCompany(user: user, id: company.id)
        let remainingCompanies = try await api.lean.companies(user: user)
        XCTAssertEqual(remainingCompanies.count, 0)
    }

}
