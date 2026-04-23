/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import bosslib
import Vapor

enum LeanForm {
    struct CreateLine: Content {
        var companyId: bosslib.Company.ID
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
