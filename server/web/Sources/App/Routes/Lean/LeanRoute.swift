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
        }
        .addScope(.user)

        group.post("factory") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateFactory.self)
            let factory = try await api.lean.createFactory(user: authUser.user, companyId: form.companyId, name: form.name)
            return LeanFragment.List.Factory(id: factory.id, name: factory.name)
        }
        .addScope(.user)

        group.get("companies") { req in
            let authUser = try req.authUser
            let companies = try await api.lean.companies(user: authUser.user)
            return LeanFragment.List.Companies(companies: companies.map { .init(id: $0.id, name: $0.name) })
        }
        .addScope(.user)

        group.get("factory-floor", ":factoryId") { req in
            let _ = try req.authUser
            return try loadFixture("Fixtures/Lean/factory-floor.json") as LeanFragment.FactoryFloor
            let factoryId = try req.parameters.require("factoryId", as: Int.self)
            // TODO: Fetch factory floor data
        }
        .addScope(.user)

        group.get("factories", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let factories = try await api.lean.factories(companyId: companyId)
            return LeanFragment.List.Factories(factories: factories.map { .init(id: $0.id, name: $0.name) })
        }
        .addScope(.user)

        group.post("line") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateLine.self)
            let line = try await api.lean.createLine(user: authUser.user, factoryId: form.factoryId, name: form.name)
            return LeanFragment.Line(id: line.id, name: line.name)
        }
        .addScope(.user)

        group.post("inventory") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateInventory.self)
            let inventory = try await api.lean.createInventory(user: authUser.user, factoryId: form.factoryId, name: form.name)
            return LeanFragment.Inventory(id: inventory.id, name: inventory.supply.name)
        }
        .addScope(.user)

        group.patch("save-line-position") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.SaveLinePosition.self)
            try await api.lean.saveLinePosition(user: authUser.user, id: form.id, x: form.gridX, y: form.gridY)
            return Fragment.OK()
        }
        .addScope(.user)

        group.patch("save-inventory-position") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.SaveInventoryPosition.self)
            try await api.lean.saveInventoryPosition(user: authUser.user, id: form.id, x: form.gridX, y: form.gridY)
            return Fragment.OK()
        }
        .addScope(.user)

        group.patch("save-line-locked") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.SaveLineLocked.self)
            try await api.lean.saveLineLocked(user: authUser.user, id: form.id, locked: form.locked)
            return Fragment.OK()
        }
        .addScope(.user)

        group.patch("save-line-focus") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.SaveLineFocus.self)
            try await api.lean.saveLineFocus(user: authUser.user, id: form.id, focused: form.focused)
            return Fragment.OK()
        }
        .addScope(.user)

        group.patch("save-inventory-locked") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.SaveInventoryLocked.self)
            try await api.lean.saveInventoryLocked(user: authUser.user, id: form.id, locked: form.locked)
            return Fragment.OK()
        }
        .addScope(.user)

        group.patch("save-inventory-focus") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.SaveInventoryFocus.self)
            try await api.lean.saveInventoryFocus(user: authUser.user, id: form.id, focused: form.focused)
            return Fragment.OK()
        }
        .addScope(.user)

        group.post("start-work-unit") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.StartWorkUnit.self)
            // TODO: Start the work unit and move it to the first station
            _ = form
            return LeanFragment.StartWorkUnitResponse(
                nextWorkUnit: .init(id: 9999, key: "FR-9999", name: "Next work unit", intakeQueueId: nil, eta: nil)
            )
        }
        .addScope(.user)

        group.patch("update-line-name") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateLineName.self)
            try await api.lean.updateLineName(user: authUser.user, id: form.id, name: form.name)
            return Fragment.OK()
        }
        .addScope(.user)

        group.post("update-station-name") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateStationName.self)
            // TODO: Update station name
            _ = form
            return Fragment.OK()
        }
        .addScope(.user)

        group.post("update-intake-queue-name") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateIntakeQueueName.self)
            try await api.lean.updateIntakeQueueName(user: authUser.user, id: form.id, name: form.name)
            return Fragment.OK()
        }
        .addScope(.user)

        group.post("update-intake-queue-mix-ratio") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateIntakeQueueMixRatio.self)
            try await api.lean.updateIntakeQueueMixRatio(user: authUser.user, id: form.id, mixRatio: form.mixRatio)
            return Fragment.OK()
        }
        .addScope(.user)

        group.patch("update-inventory-name") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateInventoryName.self)
            try await api.lean.updateInventoryName(user: authUser.user, id: form.id, name: form.name)
            return Fragment.OK()
        }
        .addScope(.user)

        group.get("company", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let company = try await api.lean.company(user: authUser.user, id: companyId)
            return LeanFragment.Company(id: company.id, name: company.name, userName: "")
        }
        .addScope(.user)

        group.put("company", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateCompany.self)
            try await api.lean.updateCompany(user: authUser.user, id: companyId, name: form.name)
            return Fragment.OK()
        }
        .addScope(.user)

        group.delete("company", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            try await api.lean.deleteCompany(user: authUser.user, id: companyId)
            return Fragment.OK()
        }
        .addScope(.user)

        group.get("factory", ":factoryId") { req in
            let authUser = try req.authUser
            let factoryId = try req.parameters.require("factoryId", as: Int.self)
            let factory = try await api.lean.factory(user: authUser.user, id: factoryId)
            return LeanFragment.Factory(id: factory.id, name: factory.name)
        }
        .addScope(.user)

        group.put("factory", ":factoryId") { req in
            let authUser = try req.authUser
            let factoryId = try req.parameters.require("factoryId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateFactory.self)
            try await api.lean.updateFactory(user: authUser.user, id: factoryId, name: form.name)
            return Fragment.OK()
        }
        .addScope(.user)

        group.delete("factory", ":factoryId") { req in
            let authUser = try req.authUser
            let factoryId = try req.parameters.require("factoryId", as: Int.self)
            try await api.lean.deleteFactory(user: authUser.user, id: factoryId)
            return Fragment.OK()
        }
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
                workUnitMaterialName: workUnitMaterialName
            )
        }
        .addScope(.user)

        group.post("intake-queue", ":intakeQueueId") { req in
            let _ = try req.authUser
            let intakeQueueId = try req.parameters.require("intakeQueueId", as: Int.self)
            // TODO: Save intake queue
            _ = intakeQueueId
            return Fragment.OK()
        }
        .addScope(.user)

        group.get("inventory", ":inventoryId") { req in
            let authUser = try req.authUser
            let inventoryId = try req.parameters.require("inventoryId", as: Int.self)
            let inv = try await api.lean.inventory(user: authUser.user, id: inventoryId)
            return LeanFragment.Inventory(id: inv.id, name: inv.supply.name)
        }
        .addScope(.user)

        group.post("inventory", ":inventoryId") { req in
            let _ = try req.authUser
            let inventoryId = try req.parameters.require("inventoryId", as: Int.self)
            // TODO: Save inventory
            _ = inventoryId
            return Fragment.OK()
        }
        .addScope(.user)

        group.get("line", ":lineId") { req in
            let authUser = try req.authUser
            let lineId = try req.parameters.require("lineId", as: Int.self)
            let ln = try await api.lean.line(user: authUser.user, id: lineId)
            return LeanFragment.Line(id: ln.id, name: ln.name)
        }
        .addScope(.user)

        group.post("line", ":lineId") { req in
            let _ = try req.authUser
            let lineId = try req.parameters.require("lineId", as: Int.self)
            // TODO: Save line
            _ = lineId
            return Fragment.OK()
        }
        .addScope(.user)

        group.get("station", ":stationId") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            // TODO: Fetch station
            _ = stationId
            return LeanFragment.Station(id: stationId, name: "")
        }
        .addScope(.user)

        group.post("station", ":stationId") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            // TODO: Save station
            _ = stationId
            return Fragment.OK()
        }
        .addScope(.user)

        group.get("work-unit", ":workUnitId") { req in
            let _ = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            // TODO: Fetch work unit
            _ = workUnitId
            return LeanFragment.WorkUnit(id: workUnitId, key: "", name: "", intakeQueueId: nil, eta: nil)
        }
        .addScope(.user)

        group.post("work-unit", ":workUnitId") { req in
            let _ = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            // TODO: Save work unit
            _ = workUnitId
            return Fragment.OK()
        }
        .addScope(.user)

        group.get("work-units", ":intakeQueueId") { req in
            let _ = try req.authUser
            let intakeQueueId = try req.parameters.require("intakeQueueId", as: Int.self)
            // TODO: Fetch intake queue and its work units
            _ = intakeQueueId
            return LeanFragment.WorkUnits(
                id: intakeQueueId,
                name: "",
                key: nil,
                mixRatioType: "distributed",
                mixRatio: 0,
                workUnitNameType: "operatorProvided",
                workUnitMaterialName: nil
            )
        }
        .addScope(.user)

        group.put("work-units", ":intakeQueueId") { req in
            let _ = try req.authUser
            let intakeQueueId = try req.parameters.require("intakeQueueId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateWorkUnits.self)
            // TODO: Save intake queue from work units view
            _ = intakeQueueId
            _ = form
            return Fragment.OK()
        }
        .addScope(.user)
    }
}
