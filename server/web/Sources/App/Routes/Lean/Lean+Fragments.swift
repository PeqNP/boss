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

    struct IntakeQueue: Content {
        let id: Int
        let name: String
    }

    struct Station: Content {
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

    struct FactoryFloor: Content {
        struct Color: Content {
            let fill: String
            let border: String
        }

        struct Assignee: Content {
            let id: String
            let name: String
            let avatar: String?
        }

        struct StationWorkUnit: Content {
            let id: Int
            let key: String
            let name: String
            let intakeQueueId: Int?
            let assignees: [LeanFragment.FactoryFloor.Assignee]
            let onHold: Bool
            let startTime: String?
            let eta: String?
            let totalOperations: Int
            let completedOperations: Int
        }

        struct Station: Content {
            let id: Int
            let name: String
            let cycleTime: Int?
            let connectsToLine: Int?
            let connectsToInventory: Int?
            let color: LeanFragment.FactoryFloor.Color?
            let workUnits: [LeanFragment.FactoryFloor.StationWorkUnit]
        }

        struct IntakeQueue: Content {
            let id: Int
            let name: String
            let mixRatio: Int?
            let cycleTime: Int
            let color: LeanFragment.FactoryFloor.Color
        }

        struct HopperWorkUnit: Content {
            let id: Int
            let key: String
            let name: String
            let intakeQueueId: Int?
            let eta: String?
        }

        struct Line: Content {
            let id: Int
            let gridX: Int
            let gridY: Int
            let name: String
            let locked: Bool
            let hasOutput: Bool
            let subAssemblyLine: Bool
            let leadTime: Int?
            let taktTime: Int?
            let throughput: Int?
            let hopperWorkUnit: LeanFragment.FactoryFloor.HopperWorkUnit?
            let intakeQueues: [LeanFragment.FactoryFloor.IntakeQueue]
            let stations: [LeanFragment.FactoryFloor.Station]
        }

        struct Inventory: Content {
            let id: Int
            let gridX: Int
            let gridY: Int
            let name: String
            let cycleStock: Int?
            let bufferStockLevel: Int?
            let safetyStockLevel: Int?
            let reorderPoint: String?
            let estimatedReorderDate: String?
            let health: Int?
        }

        let id: Int
        let name: String
        let throughputInterval: String
        let lines: [LeanFragment.FactoryFloor.Line]
        let inventories: [LeanFragment.FactoryFloor.Inventory]
    }
}

extension bosslib.Company {
    func makeCompanyOption() -> LeanFragment.Company {
        .init(id: id, name: name)
    }
}
