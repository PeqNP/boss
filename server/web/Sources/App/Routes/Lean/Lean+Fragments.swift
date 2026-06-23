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

    struct FileResource: Content {
        let id: Int
        let url: String
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

    struct StationFlowMetrics: Content {
        let id: Int
        let createDate: String
        let cycleTime: Int
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
        /// Operators assigned when `assigneeAction` is `"replace"`.
        let assignees: [Fragment.Option]
        /// The linked intake queue when `type` is `"intakeQueue"`. `nil` otherwise.
        let intakeQueue: Fragment.Option?
        let theme: LeanFragment.Theme?
        let metrics: LeanFragment.StationFlowMetrics?
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
            let `operator`: LeanFragment.Operator?
        }

        struct Comment: Content {
            let id: Int
            let `operator`: LeanFragment.Operator
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

    /// Read-only data needed to pre-populate the Create Work Unit form.
    struct CreateWorkUnit: Content {
        let intakeQueueName: String
        let companyId: Int
        let `operator`: LeanFragment.Operator
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
            let connectsToInventory: Int?
            /// When set, this station sends work units to the named intake queue.
            /// The owning line is resolved on the client via the intake-queue → line map,
            /// so no separate connectsToLine field is needed.
            let connectsToIntakeQueue: Int?
            let color: LeanFragment.FactoryFloor.Color?
            let workUnits: [LeanFragment.FactoryFloor.StationWorkUnit]
            /// Persisted overlay state: "none" | "workUnits" | "operations"
            let overlay: String
            /// Grid position relative to the first station (which is always 0, 0).
            /// posX increases to the right; posY increases downward. Both are non-negative.
            let posX: Int
            let posY: Int
        }

        struct IntakeQueue: Content {
            let id: Int
            let name: String
            let mixRatio: Int?
            let cycleTime: Int
            let numWorkUnits: Int
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

        struct ReorderAlgorithm: Content {
            /// Discriminator: `"reorderPoint"` | `"minMax"` | `"oneTime"`
            let type: String
            /// ReorderPoint + MinMax
            let minStock: Int?
            let maxStock: Int?
            /// ReorderPoint only
            let estimatedDate: String?
            let lastComputed: String?
            /// OneTime only
            let buffer: Int?
        }

        struct OrderRequest: Content {
            let amount: Int
            let estimatedDeliveryDate: String
            /// Present once shipped.
            let tracking: String?
            /// Present once arrived and added to inventory.
            let arriveDate: String?
        }

        struct Inventory: Content {
            let id: Int
            let gridX: Int
            let gridY: Int
            let name: String
            let cycleStock: Int?
            let bufferStockLevel: Int?
            let safetyStockLevel: Int?
            let reorderAlgorithm: LeanFragment.FactoryFloor.ReorderAlgorithm?
            let orderRequest: LeanFragment.FactoryFloor.OrderRequest?
            let health: String?
        }

        let id: Int
        let companyId: Int
        let name: String
        let throughputInterval: String
        let lines: [LeanFragment.FactoryFloor.Line]
        let inventories: [LeanFragment.FactoryFloor.Inventory]
    }

    struct Operation: Content {
        let id: Int
        let name: String
        let instructions: String?
        let agent: Fragment.Option?
        let supplyRequest: LeanFragment.SupplyRequest?
    }

    struct SupplyRequest: Content {
        let type: String
        let inventory: Fragment.Option?
        let amount: Int?
        let supply: Fragment.Option?
        let intakeQueue: Fragment.Option?
    }

    struct Supply: Content {
        let id: Int
        let name: String
        let theme: LeanFragment.Theme?
        let amount: Int?
        let fields: [Fragment.Option]
    }

    struct SupplyField: Content {
        let id: Int
        let name: String
        /// One of `SupplyFieldType`
        let type: String
        /// Text type fields `SupplyFieldType.TextType`
        let textType: String?
        let placeholder: String?
        /// Options (radio/multiSelect) fields
        let append: Bool?
        let options: [Fragment.Option]?
        let intakeQueue: Fragment.Option?
    }

    struct SupplyFieldOption: Content {
        let id: Int
        let name: String
        let hidden: Bool
    }

    struct StationNotificationTrigger: Content {
        let id: Int
        /// Event names: `"onEnter"` and/or `"onExit"`
        let events: [String]
        let operators: [LeanFragment.Operator]
        let message: String
    }

    struct LineFlowMetrics: Content {
        let id: Int
        let lineId: Int
        let createDate: String
        let operatingTime: Int
        let leadTime: Int
        let value: Double
        let performanceEfficiency: Double
        let totalWorkUnitsCompleted: Int
        let numOperators: Double
        let taktTime: Int
        let completedWorkUnits: Int
    }

    struct Line: Content {
        let id: Int
        let name: String
        let locked: Bool
        let hasOutput: Bool
        let subAssemblyLine: Bool
        let metrics: LeanFragment.LineFlowMetrics?
    }

    struct WorkspaceField: Content {
        let id: Int
        let name: String
        /// "text" | "file" | "radio" | "multiSelect" | "button" | "intakeQueue"
        let type: String
        /// For text fields: "plain" | "textarea" | "numeric" | "url" | "phoneNumber" | "price" | "wholeNumber"
        let textType: String?
        /// Current value for text fields
        let value: String?
        /// Available options for radio/multiSelect fields
        let options: [Fragment.Option]?
        /// Selected option IDs for radio/multiSelect fields
        let selectedOptionIds: [Int]?
        /// Uploaded file resource for file fields
        let fileResource: LeanFragment.FileResource?
        /// Associated work unit for intakeQueue fields
        let workUnit: Fragment.Option?
        /// Intake queue ID for intakeQueue fields
        let intakeQueueId: Int?
    }

    struct WorkspaceOperation: Content {
        let workUnitSupplyId: Int
        let name: String
        let instructions: String?
        /// "pending" | "fulfilled" | "waived"
        let status: String
        let active: Bool
        let fields: [LeanFragment.WorkspaceField]
    }

    struct Workspace: Content {
        let id: Int
        let key: String
        let name: String
        let companyId: Int
        let stationId: Int
        let stationName: String
        let operations: [LeanFragment.WorkspaceOperation]
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
