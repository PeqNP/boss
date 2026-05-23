/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import bosslib
import Vapor

enum LeanFragment {
    /// Lightweight fragments used to populate `UIListBox` controls.
    enum List {
        struct Company: Content {
            let id: bosslib.Company.ID
            let name: String
        }

        struct Companies: Content {
            let companies: [LeanFragment.List.Company]
        }

        struct Factory: Content {
            let id: Int
            let name: String
        }

        struct Factories: Content {
            let factories: [LeanFragment.List.Factory]
        }
    }

    struct Company: Content {
        let id: bosslib.Company.ID
        let name: String
        let userName: String
    }

    struct Theme: Content {
        let id: Int
        let fill: String
        let stroke: String
    }

    struct IntakeQueue: Content {
        let id: Int
        let name: String
        let key: String?
        let mixRatioType: String
        let mixRatio: Int
        let workUnitNameType: String
        let workUnitMaterialName: String?
        let theme: LeanFragment.Theme?
    }

    struct Station: Content {
        let id: Int
        let lineId: Int
        let companyId: Int
        let name: String
        /// "station" | "intakeQueue"
        let type: String
        /// "remove" | "retain" | "replace"
        let assigneeAction: String
        /// The linked intake queue when `type` is `"intakeQueue"`. `nil` otherwise.
        let intakeQueue: Fragment.Option?
        let theme: LeanFragment.Theme?
    }

    struct WorkUnit: Content {
        /// The current location of the `WorkUnit` within the `Line`.
        enum LineState {
            struct IntakeQueue: Content {
                let name: String
            }
            struct Station: Content {
                let name: String
                let operationName: String?
                let operationStatus: String?
            }
            struct Output: Content {
                let outputDate: String
                let outputReason: String?
                let finishedProduct: String?
            }
        }

        let id: Int
        let key: String
        let name: String
        let companyId: Int
        let intakeQueueId: Int?
        let eta: String?
        let creator: Fragment.Option?
        let reporter: Fragment.Option?
        let assignees: [Fragment.Option]
        let parentWorkUnit: Fragment.Option?
        let intakeQueueState: LeanFragment.WorkUnit.LineState.IntakeQueue?
        let stationState: LeanFragment.WorkUnit.LineState.Station?
        let outputState: LeanFragment.WorkUnit.LineState.Output?
        let onHold: Bool
        /// Elapsed time since the hold was placed, e.g. `"1d 4h"` or `"4h"`. `nil` when not on hold.
        let onHoldElapsed: String?
        let logs: [LeanFragment.WorkUnit.Log]
        /// Returned in descending order (newest first).
        let comments: [LeanFragment.WorkUnit.Comment]
        let children: [LeanFragment.WorkUnit.Child]

        struct Log: Content {
            let lineName: String
            let state: String
            let enterDate: String
            let exitDate: String?
            let `operator`: Fragment.Option?
        }

        struct Comment: Content {
            let id: Int
            let `operator`: Fragment.Option
            let createDate: String
            let text: String
        }

        struct Child: Content {
            let id: Int
            let key: String
            let name: String
            let eta: String?
        }
    }

    struct WorkUnits: Content {
        let id: Int
        let name: String
        let key: String?
        let workUnits: [Fragment.Option]
    }

    struct StartWorkUnitResponse: Content {
        let nextWorkUnit: LeanFragment.WorkUnit?
    }

    struct Operator: Content {
        let id: Int
        let name: String
        /// "Human" or "AI Agent"
        let type: String
    }

    struct Factory: Content {
        let id: Int
        let name: String
    }

    // Note: LeanFragment.List.Factories is used for UIListBox; this struct is for the Factory form.
    struct Factories: Content {
        let factories: [LeanFragment.List.Factory]
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

extension LeanFragment {
    struct Operation: Content {
        let id: Int
        let name: String
    }
}

extension LeanFragment {
    struct StationNotificationTrigger: Content {
        let id: Int
        /// Event names: `"onEnter"` and/or `"onExit"`
        let events: [String]
        let operators: [Fragment.Option]
        let message: String
    }
}

extension bosslib.Company {
    func makeCompanyOption() -> LeanFragment.List.Company {
        .init(id: id, name: name)
    }
}

extension bosslib.WorkUnit {
    func makeWorkUnitOption() -> Fragment.Option {
        .init(id: id, name: "\(key): \(name)")
    }
}
