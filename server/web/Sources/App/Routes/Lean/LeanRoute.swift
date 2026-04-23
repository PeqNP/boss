/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import bosslib
import Foundation
import Vapor

/// Register the `/lean/` routes.
public func registerLean(_ app: Application) {
    app.group("lean") { group in
        group.post("update-line-name") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateLineName.self)
            // TODO: Update line name
            _ = form
            return Response(status: .ok)
        }

        group.post("update-station-name") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateStationName.self)
            // TODO: Update station name
            _ = form
            return Response(status: .ok)
        }

        group.post("update-intake-queue-name") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateIntakeQueueName.self)
            // TODO: Update intake queue name
            _ = form
            return Response(status: .ok)
        }

        group.post("update-inventory-name") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateInventoryName.self)
            // TODO: Update inventory name
            _ = form
            return Response(status: .ok)
        }
    }
}
