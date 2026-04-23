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
    }
}
