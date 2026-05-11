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
        
        // TODO: describe: Re-order `IntakeQueue`s
        
        // Re-ordering model logic; this applies to all models that need to be re-ordered
        // - The start position is always zero
        // - A model moved to the top shall never be a value less than zero
        // - A model moved to the bottom shall never be greater than the total number of models -1. e.g. if there are 3 models, the last model will always be in positino 2 (3 models - 1 = 2)
        // - All model positions are updated to reflect their updated state. Such that, if a model moves from index 1 to the bottom, it will now be at index 2, and the model that used to be in last position, will now be at index 1. The model at index 0 will be left untouched. When making changes to the database, it should only update the necessary records.
        
        // when: Bugs is moved above Tasks
        // NOTE: Remember that the first `IntakeQueue` always takes the remainder of the mix ratio
        // it: should set mix ratio to 34 for Bugs
        // it: should set mix ratio to 33 for Tasks
        
        // when: Tasks is moved back above Bugs
        // it: should set mix ratio to 34 for Tasks
        // it: should set mix ratio to 33 for Bugs
        
        // TODO: describe: update a `Company`

        // when: name is empty
        // when: name is nil
        // when: name is valid
        
        // it: should update all of the values
        
        // TODO: describe: query for a `Company`
        
        // it: should return the full `Company` model
        
        // TODO: describe: update a `Factory`
        
        // when: name is empty
        // when: name is nil
        // when: name is valid
        
        // it: should update all of the values
        
        // TODO: describe: query for a `Factory`
        
        // it: should return the full `Factory` model
        
        // TODO: describe: update an `Inventory`
        
        // TODO: describe: query for a `Factory`
        
        // TODO: describe: update a `Line` (name: "Software development")
        // TODO: describe: query for a `Line`
        
        // TODO: describe: save `Line`'s position
        // it: should save the position
        
        // TODO: describe: save `Line`'s locked state
        // it: should save the locked state
        
        // TODO: describe: save `Line`'s focus state
        // it: should save the focus state
        
        // TODO: describe: save `Inventory`'s position
        // it: should save the position
        
        // MARK: `WorkUnit` flow
        
        // TODO: describe: create a `WorkUnit` on a line (name: "First task")
        // when: the name is nil
        // it: should raise an exception
        // when: the name is empty
        // it: should raise an exception
        // when: the name is valid
        // it: should create `WorkUnit`
        // it: should set the `WorkUnit` to the `Line`'s hopper -- as it's the only `WorkUnit`
        // it: should create `WorkUnitLog` to log the creation of the `WorkUnit`
        // it: should create `WorkUnitLog` to log that it was moved to the `Line`'s hopper
        
        // TODO: describe: query `IntakeQueue`'s `WorkUnit`s
        // it: should return the newly created `WorkUnit`
        
        // NOTE: These `WorkUnit`s will be used to test hopper, re-ordering logic, etc.
        // TODO: describe: create two more `WorkUnit`s (names: "Second task", "Third task", "Fourth task") in first `IntakeQueue`
        // it: should order the new `WorkUnit`s below the previous `WorkUnit`s in the correct order
        
        // TODO: describe: create two more `WorkUnit`s (names: "First bug", "Second bug") in the second `IntakeQueue` -- used for hopper logic
        
        // TODO: describe: update a `WorkUnit`
        // when: the name is nil
        // when: the name is empty
        // when: the name is valid
        // it: should update all values correctly
        
        // TODO: describe: start a `WorkUnit`; no `Station`s exist -- moves the current `WorkUnit` from a `Line`'s hopper to the first `Station`
        // it: should do nothing
        
        // TODO: describe: create `Station` with name "In Progress"
        // it: should place station in sort record
        // TODO: describe: create `Station` with name "Pending deployment" after "In Progress"
        // it: should set (Pending deployment) `sortOrder` to `1`
        // TODO: describe: create `Station` with name "QA" after "In Progress"
        // it: should set (QA) `sortOrder` to `1`
        // it: should set (Pending deployment) `sortOrder` to `2`

        // TODO: describe: query `IntakeQueue` `Stations`
        // it: should return the `Station`s in the correct order
        
        // TODO: describe: move station (QA) to first position
        // it: should set (QA) `sortOrder` to `0`
        // it: should set (In Progress) `sortOrder` to `1`
        // TODO: describe: move station (QA) to last position
        // it: should set (QA) `sortOrder` to `2`
        // it: should set (In Progress) `sortOrder` to `0`
        // it: should set (Pending deployment) `sortOrder` to `1`
        // TODO: describe: move station (QA) to middle position
        // it: should set (QA) `sortOrder` to `1`
        // it: should set (Pending deployment) `sortOrder` to `2`

        // TODO: describe: re-order a `WorkUnit` in the (Tasks) `IntakeQueue`
        
        // NOTE: The way the position of `WorkUnit`s are checked in the `IntakeQueue`, is by querying the `IntakeQueueWorkUnits` and comparing the position of the `WorkUnit`s, within the `IntakeQueueWorkUnits.workUnitIds`.
        
        // when: the first `WorkUnit`, in the `IntakeQueue` is attempting to be ordered above the 0th position
        // it: should do nothing
        
        // when: moving `WorkUnit` to the same position it is currently in
        // it: should do nothing
        
        // when: the last `WorkUnit` is attempting to be ordered below itself
        // it: should do nothing
        
        // when: the `WorkUnit` is already at the top
        // it: should do nothing
        
        // when: the `WorkUnit` is already at the bottom
        // it: should do nothing
        
        // when: the (Third task) `WorkUnit` is moving up
        // it: should re-order the `WorkUnit` above the (Second task) `WorkUnit`
        // NOTE: If the `Line.lastIntakeQueue` matches this `WorkUnit`'s `IntakeQueue`, and it is moving to the top of the `IntakeQueue` (0th position), then it replaces the `Line` `Hopper` `WorkUnit` to work on next.
        // it: should set the `Line`'s hopper to the (Third task)
        // it: should create a `WorkUnitLog` with position change
        
        // when: the (Second task) `WorkUnit` is moving down
        // it: should re-order the `WorkUnit` below the (Fourth task) `WorkUnit`
        // it: should create `WorkUnitLog` with position change
        
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
        
        // TODO: Create `Operation` "Test plan" -- should attach test case #
        // TODO: Create `Operation` "Testing" -- checkbox
        // TODO: Create `Operation` "Assign version" -- List of version options
        // TODO: Test re-ordering `Operation`s -- Uses `StationOperations`
        // TODO: Move `WorkUnit` to QA
        // TODO: Move `WorkUnit` through each `Operation`
        // TODO: Move to Pending Deployment
        // TODO: Move to `Output`
        
        // TODO: describe: query `Output`
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
