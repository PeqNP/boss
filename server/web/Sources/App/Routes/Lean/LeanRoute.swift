/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import bosslib
import Foundation
import Vapor

/// Register the `/lean/` routes.
public func registerLean(_ app: Application) {
    app.group("lean") { group in
        group.post("company") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateCompany.self)
            let company = try await api.lean.createCompany(user: authUser.user, name: form.name)
            return LeanFragment.List.Company(id: company.id, name: company.name)
        }.openAPI(
            summary: "Create a company",
            body: .type(LeanForm.CreateCompany.self),
            contentType: .application(.json),
            response: .type(LeanFragment.List.Company.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.post("factory") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateFactory.self)
            let factory = try await api.lean.createFactory(user: authUser.user, companyId: form.companyId, name: form.name)
            return LeanFragment.List.Factory(id: factory.id, name: factory.name)
        }.openAPI(
            summary: "Create a factory",
            body: .type(LeanForm.CreateFactory.self),
            contentType: .application(.json),
            response: .type(LeanFragment.List.Factory.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("companies") { req in
            let authUser = try req.authUser
            let companies = try await api.lean.companies(user: authUser.user)
            return LeanFragment.List.Companies(companies: companies.map { .init(id: $0.id, name: $0.name) })
        }.openAPI(
            summary: "Get all companies",
            response: .type(LeanFragment.List.Companies.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("factory-floor", ":factoryId") { req in
            let _ = try req.authUser
            return try loadFixture("Fixtures/Lean/factory-floor.json") as LeanFragment.FactoryFloor
            let factoryId = try req.parameters.require("factoryId", as: Int.self)
            // TODO: Fetch factory floor data
        }.openAPI(
            summary: "Get factory floor",
            description: "Returns the full factory floor layout including all lines, stations, intake queues, and inventories.",
            response: .type(LeanFragment.FactoryFloor.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("factories", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let factories = try await api.lean.factories(companyId: companyId)
            return LeanFragment.List.Factories(factories: factories.map { .init(id: $0.id, name: $0.name) })
        }.openAPI(
            summary: "Get factories for a company",
            response: .type(LeanFragment.List.Factories.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.post("line") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateLine.self)
            let line = try await api.lean.createLine(user: authUser.user, factoryId: form.factoryId, name: form.name)
            return Fragment.Option(id: line.id, name: line.name)
        }.openAPI(
            summary: "Create a line",
            body: .type(LeanForm.CreateLine.self),
            contentType: .application(.json),
            response: .type(Fragment.Option.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.post("inventory") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateInventory.self)
            let inventory = try await api.lean.createInventory(user: authUser.user, factoryId: form.factoryId, name: form.name)
            return Fragment.Option(id: inventory.id, name: inventory.supply.name)
        }.openAPI(
            summary: "Create an inventory",
            body: .type(LeanForm.CreateInventory.self),
            contentType: .application(.json),
            response: .type(Fragment.Option.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("save-line-position") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.SaveLinePosition.self)
            try await api.lean.saveLinePosition(user: authUser.user, id: form.id, x: form.gridX, y: form.gridY)
            return Fragment.OK()
        }.openAPI(
            summary: "Save line position on factory floor",
            body: .type(LeanForm.SaveLinePosition.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("save-inventory-position") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.SaveInventoryPosition.self)
            try await api.lean.saveInventoryPosition(user: authUser.user, id: form.id, x: form.gridX, y: form.gridY)
            return Fragment.OK()
        }.openAPI(
            summary: "Save inventory position on factory floor",
            body: .type(LeanForm.SaveInventoryPosition.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("save-line-locked") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.SaveLineLocked.self)
            try await api.lean.saveLineLocked(user: authUser.user, id: form.id, locked: form.locked)
            return Fragment.OK()
        }.openAPI(
            summary: "Save line locked state",
            body: .type(LeanForm.SaveLineLocked.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("save-line-focus") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.SaveLineFocus.self)
            try await api.lean.saveLineFocus(user: authUser.user, id: form.id, focused: form.focused)
            return Fragment.OK()
        }.openAPI(
            summary: "Save line focus state",
            body: .type(LeanForm.SaveLineFocus.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("save-inventory-locked") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.SaveInventoryLocked.self)
            try await api.lean.saveInventoryLocked(user: authUser.user, id: form.id, locked: form.locked)
            return Fragment.OK()
        }.openAPI(
            summary: "Save inventory locked state",
            body: .type(LeanForm.SaveInventoryLocked.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("save-inventory-focus") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.SaveInventoryFocus.self)
            try await api.lean.saveInventoryFocus(user: authUser.user, id: form.id, focused: form.focused)
            return Fragment.OK()
        }.openAPI(
            summary: "Save inventory focus state",
            body: .type(LeanForm.SaveInventoryFocus.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.post("start-work-unit") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.StartWorkUnit.self)
            // TODO: Start the work unit and move it to the first station
            _ = form
            return LeanFragment.StartWorkUnitResponse(
                nextWorkUnit: .init(id: 9999, key: "FR-9999", name: "Next work unit", companyId: 1, intakeQueueId: nil, eta: nil, creator: .init(id: "5", name: "Eric Chamberlain"), reporter: nil, assignees: [], parentWorkUnit: nil, intakeQueueState: nil, stationState: nil, outputState: nil, onHold: false, onHoldElapsed: nil, logs: [], comments: [], children: [])
            )
        }.openAPI(
            summary: "Start a work unit",
            description: "Moves the work unit to the first station in the line. Returns the next work unit waiting in the intake queue, if any.",
            body: .type(LeanForm.StartWorkUnit.self),
            contentType: .application(.json),
            response: .type(LeanFragment.StartWorkUnitResponse.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("update-line-name") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateLineName.self)
            try await api.lean.updateLineName(user: authUser.user, id: form.id, name: form.name)
            return Fragment.OK()
        }.openAPI(
            summary: "Update line name",
            body: .type(LeanForm.UpdateLineName.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("update-station-name") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateStationName.self)
            // TODO: Update station name
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update station name",
            body: .type(LeanForm.UpdateStationName.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("update-intake-queue-name") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateIntakeQueueName.self)
            try await api.lean.updateIntakeQueueName(user: authUser.user, id: form.id, name: form.name)
            return Fragment.OK()
        }.openAPI(
            summary: "Update intake queue name",
            body: .type(LeanForm.UpdateIntakeQueueName.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("update-intake-queue-mix-ratio") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateIntakeQueueMixRatio.self)
            try await api.lean.updateIntakeQueueMixRatio(user: authUser.user, id: form.id, mixRatio: form.mixRatio)
            return Fragment.OK()
        }.openAPI(
            summary: "Update intake queue mix ratio",
            body: .type(LeanForm.UpdateIntakeQueueMixRatio.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("update-inventory-name") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateInventoryName.self)
            try await api.lean.updateInventoryName(user: authUser.user, id: form.id, name: form.name)
            return Fragment.OK()
        }.openAPI(
            summary: "Update inventory name",
            body: .type(LeanForm.UpdateInventoryName.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("company", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let company = try await api.lean.company(user: authUser.user, id: companyId)
            return LeanFragment.Company(id: company.id, name: company.name, userName: "")
        }.openAPI(
            summary: "Get a company",
            response: .type(LeanFragment.Company.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("company", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateCompany.self)
            try await api.lean.updateCompany(user: authUser.user, id: companyId, name: form.name)
            return Fragment.OK()
        }.openAPI(
            summary: "Update a company",
            body: .type(LeanForm.UpdateCompany.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("company", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            try await api.lean.deleteCompany(user: authUser.user, id: companyId)
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a company",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("factory", ":factoryId") { req in
            let authUser = try req.authUser
            let factoryId = try req.parameters.require("factoryId", as: Int.self)
            let factory = try await api.lean.factory(user: authUser.user, id: factoryId)
            return LeanFragment.Factory(id: factory.id, name: factory.name)
        }.openAPI(
            summary: "Get a factory",
            response: .type(LeanFragment.Factory.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("factory", ":factoryId") { req in
            let authUser = try req.authUser
            let factoryId = try req.parameters.require("factoryId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateFactory.self)
            try await api.lean.updateFactory(user: authUser.user, id: factoryId, name: form.name)
            return Fragment.OK()
        }.openAPI(
            summary: "Update a factory",
            body: .type(LeanForm.UpdateFactory.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("factory", ":factoryId") { req in
            let authUser = try req.authUser
            let factoryId = try req.parameters.require("factoryId", as: Int.self)
            try await api.lean.deleteFactory(user: authUser.user, id: factoryId)
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a factory",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("intake-queue", ":intakeQueueId") { req in
            let authUser = try req.authUser
            return try loadFixture("Fixtures/Lean/intake-queue.json") as LeanFragment.IntakeQueue
            let intakeQueueId = try req.parameters.require("intakeQueueId", as: Int.self)
            let iq = try await api.lean.intakeQueue(user: authUser.user, id: intakeQueueId)
            let mixRatioType = iq.mixRatioType == .fixed ? "fixed" : "distributed"
            let workUnitNameType: String
            let workUnitMaterialName: String?
            switch iq.workUnitName {
            case .material(let name):
                workUnitNameType = "material"
                workUnitMaterialName = name
            case .operatorProvided:
                workUnitNameType = "operatorProvided"
                workUnitMaterialName = nil
            }
            return LeanFragment.IntakeQueue(
                id: iq.id,
                name: iq.name,
                key: iq.key,
                mixRatioType: mixRatioType,
                mixRatio: iq.mixRatio,
                workUnitNameType: workUnitNameType,
                workUnitMaterialName: workUnitMaterialName,
                theme: nil
            )
        }.openAPI(
            summary: "Get an intake queue",
            response: .type(LeanFragment.IntakeQueue.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("intake-queue", ":intakeQueueId") { req in
            let _ = try req.authUser
            let intakeQueueId = try req.parameters.require("intakeQueueId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateIntakeQueue.self)
            // TODO: Save intake queue
            _ = intakeQueueId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update an intake queue",
            body: .type(LeanForm.UpdateIntakeQueue.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("inventory", ":inventoryId") { req in
            let authUser = try req.authUser
            let inventoryId = try req.parameters.require("inventoryId", as: Int.self)
            let inv = try await api.lean.inventory(user: authUser.user, id: inventoryId)
            return Fragment.Option(id: inv.id, name: inv.supply.name)
        }.openAPI(
            summary: "Get an inventory",
            response: .type(Fragment.Option.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("inventory", ":inventoryId") { req in
            let _ = try req.authUser
            let inventoryId = try req.parameters.require("inventoryId", as: Int.self)
            // TODO: Save inventory
            _ = inventoryId
            return Fragment.OK()
        }.openAPI(
            summary: "Update an inventory",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("line", ":lineId") { req in
            let authUser = try req.authUser
            let lineId = try req.parameters.require("lineId", as: Int.self)
            let ln = try await api.lean.line(user: authUser.user, id: lineId)
            return Fragment.Option(id: ln.id, name: ln.name)
        }.openAPI(
            summary: "Get a line",
            response: .type(Fragment.Option.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("line", ":lineId") { req in
            let _ = try req.authUser
            let lineId = try req.parameters.require("lineId", as: Int.self)
            // TODO: Save line
            _ = lineId
            return Fragment.OK()
        }.openAPI(
            summary: "Update a line",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("suggested-intake-queue", ":lineId") { req in
            let _ = try req.authUser
            let lineId = try req.parameters.require("lineId", as: Int.self)
            // TODO: Fetch suggested intake queues for line
            _ = lineId
            return try loadFixture("Fixtures/Lean/suggested-intake-queues.json") as [Fragment.Option]
        }.openAPI(
            summary: "Get suggested intake queues for a line",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("find-intake-queue", ":lineId") { req in
            let _ = try req.authUser
            let lineId = try req.parameters.require("lineId", as: Int.self)
            let q = req.query[String.self, at: "q"] ?? ""
            // TODO: Search intake queues for line by term
            _ = lineId
            _ = q
            return try loadFixture("Fixtures/Lean/suggested-intake-queues.json") as [Fragment.Option]
        }.openAPI(
            summary: "Search intake queues for a line",
            description: "Returns intake queues in the line matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("station", ":stationId", "type", "intake-queue") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateStationTypeIntakeQueue.self)
            // TODO: Update station type to intakeQueue
            _ = stationId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Set station type to intake queue",
            description: "Links the station to a specific intake queue and changes its type to `intakeQueue`.",
            body: .type(LeanForm.UpdateStationTypeIntakeQueue.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("station", ":stationId", "type", "station") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            // TODO: Update station type to station
            _ = stationId
            return Fragment.OK()
        }.openAPI(
            summary: "Set station type to station",
            description: "Removes any linked intake queue and changes the station type back to `station`.",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("station", ":stationId") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            // TODO: Fetch station
            _ = stationId
            return try loadFixture("Fixtures/Lean/station-1.json") as LeanFragment.Station
        }.openAPI(
            summary: "Get a station",
            response: .type(LeanFragment.Station.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("station", ":stationId") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateStation.self)
            // TODO: Save station
            _ = stationId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update a station",
            body: .type(LeanForm.UpdateStation.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("station", ":stationId") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            // TODO: Delete station
            _ = stationId
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a station",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("station", ":stationId", "work-units") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            // TODO: Fetch work units for station
            _ = stationId
            return try loadFixture("Fixtures/Lean/station-work-units.json") as LeanFragment.WorkUnits
        }.openAPI(
            summary: "Get work units for a station",
            response: .type(LeanFragment.WorkUnits.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("station", ":stationId", "notification-triggers") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            // TODO: Fetch notification triggers for station
            _ = stationId
            return try loadFixture("Fixtures/Lean/station-notification-triggers.json") as [Fragment.Option]
        }.openAPI(
            summary: "Get notification triggers for a station",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("station", ":stationId", "operations") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            // TODO: Fetch operations for station
            _ = stationId
            return try loadFixture("Fixtures/Lean/station-operations.json") as [Fragment.Option]
        }.openAPI(
            summary: "Get operations for a station",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("operation", ":operationId") { req in
            let _ = try req.authUser
            let operationId = try req.parameters.require("operationId", as: Int.self)
            // TODO: Fetch operation from DB
            _ = operationId
            return try loadFixture("Fixtures/Lean/operation.json") as LeanFragment.Operation
        }.openAPI(
            summary: "Get an operation",
            response: .type(LeanFragment.Operation.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.post("operation") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.CreateOperation.self)
            // TODO: Create operation in DB
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Create an operation",
            body: .type(LeanForm.CreateOperation.self),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("operation", ":operationId") { req in
            let _ = try req.authUser
            let operationId = try req.parameters.require("operationId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateOperation.self)
            // TODO: Update operation in DB
            _ = operationId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update an operation",
            body: .type(LeanForm.UpdateOperation.self),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("operation", ":operationId") { req in
            let _ = try req.authUser
            let operationId = try req.parameters.require("operationId", as: Int.self)
            // TODO: Delete operation from DB
            _ = operationId
            return Fragment.OK()
        }.openAPI(
            summary: "Delete an operation",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("station-notification-trigger", ":triggerId") { req in
            let _ = try req.authUser
            let triggerId = try req.parameters.require("triggerId", as: Int.self)
            // TODO: Fetch notification trigger from DB
            _ = triggerId
            return try loadFixture("Fixtures/Lean/station-notification-trigger.json") as LeanFragment.StationNotificationTrigger
        }.openAPI(
            summary: "Get a station notification trigger",
            response: .type(LeanFragment.StationNotificationTrigger.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.post("station-notification-trigger") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.CreateStationNotificationTrigger.self)
            // TODO: Create notification trigger in DB
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Create a station notification trigger",
            body: .type(LeanForm.CreateStationNotificationTrigger.self),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("station-notification-trigger", ":triggerId") { req in
            let _ = try req.authUser
            let triggerId = try req.parameters.require("triggerId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateStationNotificationTrigger.self)
            // TODO: Update notification trigger in DB
            _ = triggerId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update a station notification trigger",
            body: .type(LeanForm.UpdateStationNotificationTrigger.self),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("station-notification-trigger", ":triggerId") { req in
            let _ = try req.authUser
            let triggerId = try req.parameters.require("triggerId", as: Int.self)
            // TODO: Delete notification trigger from DB
            _ = triggerId
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a station notification trigger",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("work-unit", ":workUnitId") { req in
            let _ = try req.authUser
            var workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let availableIds: [Int] = [1, 2]
            if !availableIds.contains(workUnitId) {
                boss.log.i("Invalid WorkUnit.id (\(workUnitId)")
                workUnitId = 1
            }
            return try loadFixture("Fixtures/Lean/work-unit-\(workUnitId).json") as LeanFragment.WorkUnit
        }.openAPI(
            summary: "Get a work unit",
            response: .type(LeanFragment.WorkUnit.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("work-unit", "children", ":workUnitId") { req in
            let _ = try req.authUser
            var workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            // TODO: Load children from DB
            if workUnitId < 1 || workUnitId > 2 {
                workUnitId = 1
            }
            return try loadFixture("Fixtures/Lean/work-unit-children-\(workUnitId).json") as [LeanFragment.WorkUnit.Child]
        }.openAPI(
            summary: "Get children of a work unit",
            response: .type([LeanFragment.WorkUnit.Child].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.post("work-unit", "child") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.AddWorkUnitChild.self)
            // TODO: Add child work unit relationship
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Add a child work unit",
            body: .type(LeanForm.AddWorkUnitChild.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("work-unit", "child", ":workUnitId", ":childWorkUnitId") { req in
            let _ = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let childWorkUnitId = try req.parameters.require("childWorkUnitId", as: Int.self)
            // TODO: Remove child work unit relationship
            _ = workUnitId
            _ = childWorkUnitId
            return Fragment.OK()
        }.openAPI(
            summary: "Remove a child work unit",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.post("work-unit", "hold", ":workUnitId") { req in
            let _ = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            // TODO: Place work unit on hold (create WorkUnitLog with LineState.onHold)
            _ = workUnitId
            return Fragment.OK()
        }.openAPI(
            summary: "Place a work unit on hold",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("work-unit", "hold", ":workUnitId") { req in
            let _ = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let form = try req.content.decode(LeanForm.ClearWorkUnitHold.self)
            // TODO: Clear work unit hold
            _ = workUnitId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Clear a work unit hold",
            body: .type(LeanForm.ClearWorkUnitHold.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("suggested-work-unit", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            _ = companyId
            return try loadFixture("Fixtures/Lean/find-work-units.json") as [Fragment.Option]
        }.openAPI(
            summary: "Get suggested work units for a company",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("find-work-unit", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let q = req.query[String.self, at: "q"] ?? ""
            _ = companyId
            _ = q
            return try loadFixture("Fixtures/Lean/find-work-units.json") as [Fragment.Option]
        }.openAPI(
            summary: "Search work units for a company",
            description: "Returns work units matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("suggested-operators", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            // TODO: Return suggested operators for company
            _ = companyId
            return try loadFixture("Fixtures/Lean/suggested-operators.json") as [Fragment.Option]
        }.openAPI(
            summary: "Get suggested operators for a company",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("find-operators", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let q = req.query[String.self, at: "q"] ?? ""
            // TODO: Return operators matching q for company
            _ = companyId
            _ = q
            return try loadFixture("Fixtures/Lean/suggested-operators.json") as [Fragment.Option]
        }.openAPI(
            summary: "Search operators for a company",
            description: "Returns operators matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("work-unit-position") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateWorkUnitPosition.self)
            // TODO: Save work unit position
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Save work unit position in intake queue",
            body: .type(LeanForm.UpdateWorkUnitPosition.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("work-unit", "reporter", ":workUnitId") { req in
            let _ = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateWorkUnitReporter.self)
            // TODO: Save work unit reporter
            _ = workUnitId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update work unit reporter",
            description: "Sets or clears the reporter on a work unit. Send `null` for `operatorId` to clear.",
            body: .type(LeanForm.UpdateWorkUnitReporter.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("work-unit", "parent", ":workUnitId") { req in
            let _ = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateWorkUnitParent.self)
            // TODO: Save work unit parent
            _ = workUnitId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update work unit parent",
            description: "Sets or clears the parent work unit. Send `null` for `parentWorkUnitId` to clear.",
            body: .type(LeanForm.UpdateWorkUnitParent.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("work-unit", "assignees", ":workUnitId") { req in
            let _ = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateWorkUnitAssignees.self)
            // TODO: Save work unit assignees
            _ = workUnitId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update work unit assignees",
            description: "Replaces the full list of assignees. Send an empty array to remove all assignees.",
            body: .type(LeanForm.UpdateWorkUnitAssignees.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("work-unit", ":workUnitId") { req in
            let _ = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateWorkUnit.self)
            // TODO: Save work unit
            _ = workUnitId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update a work unit",
            body: .type(LeanForm.UpdateWorkUnit.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("work-unit", ":workUnitId") { req in
            let _ = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            // TODO: Delete work unit
            _ = workUnitId
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a work unit",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("operator", ":operatorId") { req in
            let _ = try req.authUser
            var operatorId = try req.parameters.require("operatorId", as: Int.self)
            // TODO: Load operator from DB
            if operatorId < 1 || operatorId > 1 {
                operatorId = 1
            }
            return try loadFixture("Fixtures/Lean/operator-\(operatorId).json") as LeanFragment.Operator
        }.openAPI(
            summary: "Get an operator",
            response: .type(LeanFragment.Operator.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.post("operator") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.CreateOperator.self)
            // TODO: Create operator
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Create an operator",
            body: .type(LeanForm.CreateOperator.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("operator", ":operatorId") { req in
            let _ = try req.authUser
            let operatorId = try req.parameters.require("operatorId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateOperator.self)
            // TODO: Update operator
            _ = operatorId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update an operator",
            body: .type(LeanForm.UpdateOperator.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("operator", ":operatorId") { req in
            let _ = try req.authUser
            let operatorId = try req.parameters.require("operatorId", as: Int.self)
            // TODO: Delete operator
            _ = operatorId
            return Fragment.OK()
        }.openAPI(
            summary: "Delete an operator",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("work-units", ":intakeQueueId") { req in
            let _ = try req.authUser
            return try loadFixture("Fixtures/Lean/work-units.json") as LeanFragment.WorkUnits
        }.openAPI(
            summary: "Get work units for an intake queue",
            response: .type(LeanFragment.WorkUnits.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("work-units", ":intakeQueueId") { req in
            let _ = try req.authUser
            let intakeQueueId = try req.parameters.require("intakeQueueId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateWorkUnits.self)
            // TODO: Save intake queue from work units view
            _ = intakeQueueId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update intake queue settings from the work units view",
            body: .type(LeanForm.UpdateWorkUnits.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.post("work-unit-comment") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.CreateWorkUnitComment.self)
            // TODO: Create work unit comment
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Add a comment to a work unit",
            body: .type(LeanForm.CreateWorkUnitComment.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("work-unit-comment", ":commentId") { req in
            let _ = try req.authUser
            let commentId = try req.parameters.require("commentId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateWorkUnitComment.self)
            // TODO: Update work unit comment
            _ = commentId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update a work unit comment",
            body: .type(LeanForm.UpdateWorkUnitComment.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("work-unit-comment", ":commentId") { req in
            let _ = try req.authUser
            let commentId = try req.parameters.require("commentId", as: Int.self)
            // TODO: Delete work unit comment
            _ = commentId
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a work unit comment",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)
    }
}
