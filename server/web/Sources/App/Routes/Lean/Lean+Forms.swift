/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import Vapor

enum LeanForm {
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
