/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import bosslib
import Vapor

enum LeanFragment {
    struct Company: Content {
        let id: bosslib.Company.ID
        let name: String
    }

    struct Companies: Content {
        let companies: [LeanFragment.Company]
    }

    struct Line: Content {
        let id: Int
        let name: String
    }

    struct Inventory: Content {
        let id: Int
        let name: String
    }

    struct WorkUnit: Content {
        let id: Int
        let key: String
        let name: String
        let intakeQueueId: Int?
        let eta: String?
    }

    struct StartWorkUnitResponse: Content {
        let nextWorkUnit: LeanFragment.WorkUnit?
    }

    struct Factory: Content {
        let id: Int
        let name: String
    }

    struct Factories: Content {
        let factories: [LeanFragment.Factory]
    }
}

extension bosslib.Company {
    func makeCompanyOption() -> LeanFragment.Company {
        .init(id: id, name: name)
    }
}
