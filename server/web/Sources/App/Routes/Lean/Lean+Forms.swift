/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import bosslib
import Vapor

enum LeanForm {
    struct CreateLine: Content {
        var factoryId: bosslib.Factory.ID
    }

    struct CreateInventory: Content {
        var factoryId: bosslib.Factory.ID
    }

    struct SaveLinePosition: Content {
        var id: Int
        var gridX: Int
        var gridY: Int
    }

    struct SaveInventoryPosition: Content {
        var id: Int
        var gridX: Int
        var gridY: Int
    }

    struct SaveLineLocked: Content {
        var id: Int
        var locked: Bool
    }

    struct SaveLineFocus: Content {
        var id: Int
        var focused: Bool
    }

    struct StartWorkUnit: Content {
        var id: Int
    }

    struct UpdateLineName: Content {
        var id: Int
        var name: String
    }

    struct UpdateStationName: Content {
        var id: Int
        var name: String
    }

    struct UpdateIntakeQueueName: Content {
        var id: Int
        var name: String
    }

    struct UpdateInventoryName: Content {
        var id: Int
        var name: String
    }
}
