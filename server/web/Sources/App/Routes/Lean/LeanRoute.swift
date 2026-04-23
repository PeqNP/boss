/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import bosslib
import Foundation
import Vapor

/// Register the `/lean/` routes.
public func registerLean(_ app: Application) {
    app.group("lean") { group in
        group.get("companies") { req in
            let _ = try req.authUser
            // TODO: Fetch companies for the authenticated user
            return LeanFragment.Companies(companies: [
                .init(id: 1, name: "Bithead, Inc.")
            ])
        }
        .addScope(.user)

        group.get("factories", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            // TODO: Fetch factories for the given company
            _ = companyId
            return LeanFragment.Factories(factories: [
                .init(id: 1, name: "Main Factory")
            ])
        }
        .addScope(.user)

        group.post("create-line") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.CreateLine.self)
            // TODO: Create a new line for the given company
            _ = form
            return LeanFragment.Line(id: 1, name: "Manufacturing line")
        }
        .addScope(.user)

        group.post("create-inventory") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.CreateInventory.self)
            // TODO: Create a new inventory for the given company
            _ = form
            return LeanFragment.Inventory(id: 1, name: "Inventory")
        }
        .addScope(.user)

        group.post("save-line-position") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.SaveLinePosition.self)
            // TODO: Save line grid position
            _ = form
            return Fragment.OK()
        }
        .addScope(.user)

        group.post("save-inventory-position") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.SaveInventoryPosition.self)
            // TODO: Save inventory grid position
            _ = form
            return Fragment.OK()
        }
        .addScope(.user)

        group.post("save-line-locked") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.SaveLineLocked.self)
            // TODO: Save line locked state
            _ = form
            return Fragment.OK()
        }
        .addScope(.user)

        group.post("save-line-focus") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.SaveLineFocus.self)
            // TODO: Save line focus state
            _ = form
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

        group.post("update-line-name") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateLineName.self)
            // TODO: Update line name
            _ = form
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
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateIntakeQueueName.self)
            // TODO: Update intake queue name
            _ = form
            return Fragment.OK()
        }
        .addScope(.user)

        group.post("update-inventory-name") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateInventoryName.self)
            // TODO: Update inventory name
            _ = form
            return Fragment.OK()
        }
        .addScope(.user)

        group.get("company", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            // TODO: Fetch company
            _ = companyId
            return LeanFragment.Company(id: companyId, name: "")
        }
        .addScope(.user)

        group.post("company", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            // TODO: Save company
            _ = companyId
            return Fragment.OK()
        }
        .addScope(.user)

        group.get("factory", ":factoryId") { req in
            let _ = try req.authUser
            let factoryId = try req.parameters.require("factoryId", as: Int.self)
            // TODO: Fetch factory
            _ = factoryId
            return LeanFragment.Factory(id: factoryId, name: "")
        }
        .addScope(.user)

        group.post("factory", ":factoryId") { req in
            let _ = try req.authUser
            let factoryId = try req.parameters.require("factoryId", as: Int.self)
            // TODO: Save factory
            _ = factoryId
            return Fragment.OK()
        }
        .addScope(.user)

        group.get("intake-queue", ":intakeQueueId") { req in
            let _ = try req.authUser
            let intakeQueueId = try req.parameters.require("intakeQueueId", as: Int.self)
            // TODO: Fetch intake queue
            _ = intakeQueueId
            return LeanFragment.IntakeQueue(id: intakeQueueId, name: "")
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
            let _ = try req.authUser
            let inventoryId = try req.parameters.require("inventoryId", as: Int.self)
            // TODO: Fetch inventory
            _ = inventoryId
            return LeanFragment.Inventory(id: inventoryId, name: "")
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
            let _ = try req.authUser
            let lineId = try req.parameters.require("lineId", as: Int.self)
            // TODO: Fetch line
            _ = lineId
            return LeanFragment.Line(id: lineId, name: "")
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
    }
}
