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

        group.post("update-line-name") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateLineName.self)
            // TODO: Update line name
            _ = form
            return Response(status: .ok)
        }
        .addScope(.user)

        group.post("update-station-name") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateStationName.self)
            // TODO: Update station name
            _ = form
            return Response(status: .ok)
        }
        .addScope(.user)

        group.post("update-intake-queue-name") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateIntakeQueueName.self)
            // TODO: Update intake queue name
            _ = form
            return Response(status: .ok)
        }
        .addScope(.user)

        group.post("update-inventory-name") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateInventoryName.self)
            // TODO: Update inventory name
            _ = form
            return Response(status: .ok)
        }
        .addScope(.user)
    }
}
