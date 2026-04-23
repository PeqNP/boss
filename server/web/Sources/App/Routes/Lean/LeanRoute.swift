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

        group.get("factory-floor", ":factoryId") { req in
            let _ = try req.authUser
            let factoryId = try req.parameters.require("factoryId", as: Int.self)
            // TODO: Fetch factory floor data
            _ = factoryId
            typealias FF = LeanFragment.FactoryFloor
            return FF(
                id: 1,
                name: "Bithead",
                throughputInterval: "week",
                lines: [
                    .init(
                        id: 1, gridX: 3, gridY: 1, name: "Design",
                        locked: true, hasOutput: true, subAssemblyLine: false,
                        leadTime: 86400, taktTime: 14400, throughput: 12,
                        hopperWorkUnit: nil,
                        intakeQueues: [
                            .init(id: 1, name: "Design Request", mixRatio: nil, cycleTime: 7200, color: .init(fill: "#E8F4F8", border: "#7aa1ad"))
                        ],
                        stations: [
                            .init(id: 1, name: "Planning", cycleTime: 5400, connectsToLine: nil, connectsToInventory: nil, color: nil, workUnits: []),
                            .init(id: 2, name: "Design", cycleTime: 18000, connectsToLine: nil, connectsToInventory: nil, color: nil, workUnits: []),
                            .init(id: 3, name: "Review", cycleTime: 3600, connectsToLine: nil, connectsToInventory: nil, color: nil, workUnits: [])
                        ]
                    ),
                    .init(
                        id: 2, gridX: 9, gridY: 5, name: "Features",
                        locked: false, hasOutput: true, subAssemblyLine: false,
                        leadTime: 604800, taktTime: 28800, throughput: 5,
                        hopperWorkUnit: .init(id: 2000, key: "FR-2000", name: "Upgrade database", intakeQueueId: 2, eta: "2026-05-01T17:00:00"),
                        intakeQueues: [
                            .init(id: 3, name: "Feature Request", mixRatio: 80, cycleTime: 10800, color: .init(fill: "#E8F8E8", border: "#7ea67e"))
                        ],
                        stations: [
                            .init(id: 4, name: "Gather Requirements", cycleTime: 7200, connectsToLine: nil, connectsToInventory: nil, color: .init(fill: "#ffedd5", border: "#c2410c"), workUnits: [
                                .init(id: 2001, key: "FR-2001", name: "IoT Dashboard", intakeQueueId: 3,
                                      assignees: [.init(id: "eric-chamberlain", name: "Eric Chamberlain", avatar: "https://bithead.io/boss/img/logo.png"),
                                                  .init(id: "shayne-smith", name: "Shayne Smith", avatar: nil)],
                                      onHold: true, startTime: "2026-03-05T12:30:00Z", eta: "2026-04-25T17:00:00", totalOperations: 4, completedOperations: 2),
                                .init(id: 2002, key: "FR-2002", name: "Refactor IoT data structure", intakeQueueId: 3,
                                      assignees: [.init(id: "shayne-smith", name: "Shayne Smith", avatar: nil)],
                                      onHold: false, startTime: "2026-03-06T15:45:00Z", eta: "2026-04-28T17:00:00", totalOperations: 3, completedOperations: 3)
                            ]),
                            .init(id: 5, name: "Design", cycleTime: 14400, connectsToLine: 1, connectsToInventory: nil, color: .init(fill: "#dcfce7", border: "#166534"), workUnits: [
                                .init(id: 1004, key: "FR-1004", name: "Redesign Home card", intakeQueueId: 3,
                                      assignees: [.init(id: "eric-chamberlain", name: "Eric Chamberlain", avatar: "https://bithead.io/boss/img/logo.png")],
                                      onHold: false, startTime: "2026-03-05T12:30:00Z", eta: "2026-04-30T17:00:00", totalOperations: 5, completedOperations: 1)
                            ]),
                            .init(id: 6, name: "Development", cycleTime: 28800, connectsToLine: 6, connectsToInventory: nil, color: .init(fill: "#dcfce7", border: "#166534"), workUnits: [
                                .init(id: 1005, key: "FR-1005", name: "Support Discover card in Checkout", intakeQueueId: 3,
                                      assignees: [.init(id: "eric-chamberlain", name: "Eric Chamberlain", avatar: "https://bithead.io/boss/img/logo.png")],
                                      onHold: false, startTime: "2026-03-05T12:30:00Z", eta: "2026-05-05T17:00:00", totalOperations: 5, completedOperations: 1)
                            ])
                        ]
                    ),
                    .init(
                        id: 6, gridX: 12, gridY: 11, name: "Software Development",
                        locked: false, hasOutput: true, subAssemblyLine: false,
                        leadTime: 432000, taktTime: 21600, throughput: 20,
                        hopperWorkUnit: .init(id: 4021, key: "SD-4021", name: "Fix bug", intakeQueueId: 2, eta: "2026-04-28T14:00:00"),
                        intakeQueues: [
                            .init(id: 10, name: "Bugs", mixRatio: 20, cycleTime: 3600, color: .init(fill: "#FFE8E8", border: "#c57c7c")),
                            .init(id: 11, name: "Tasks", mixRatio: 80, cycleTime: 5400, color: .init(fill: "#E8F8E8", border: "#7ea67e"))
                        ],
                        stations: [
                            .init(id: 7, name: "In Progress", cycleTime: 5400, connectsToLine: nil, connectsToInventory: nil, color: .init(fill: "#ffedd5", border: "#c2410c"), workUnits: [
                                .init(id: 1000, key: "SD-1000", name: "Create a button", intakeQueueId: 3,
                                      assignees: [.init(id: "eric-chamberlain", name: "Eric Chamberlain", avatar: "https://bithead.io/boss/img/logo.png"),
                                                  .init(id: "shayne-smith", name: "Shayne Smith", avatar: nil)],
                                      onHold: true, startTime: "2026-03-05T12:30:00Z", eta: "2026-04-24T17:00:00", totalOperations: 4, completedOperations: 2),
                                .init(id: 2000, key: "SD-2000", name: "Create a field", intakeQueueId: 3,
                                      assignees: [.init(id: "shayne-smith", name: "Shayne Smith", avatar: nil)],
                                      onHold: false, startTime: "2026-03-06T15:45:00Z", eta: "2026-04-29T17:00:00", totalOperations: 3, completedOperations: 3)
                            ]),
                            .init(id: 8, name: "PR Review", cycleTime: 3660, connectsToLine: nil, connectsToInventory: nil, color: .init(fill: "#dcfce7", border: "#166534"), workUnits: [
                                .init(id: 3200, key: "SD-3200", name: "Add a button to card", intakeQueueId: 3,
                                      assignees: [.init(id: "eric-chamberlain", name: "Eric Chamberlain", avatar: "https://bithead.io/boss/img/logo.png")],
                                      onHold: false, startTime: "2026-03-05T12:30:00Z", eta: "2026-04-23T17:00:00", totalOperations: 5, completedOperations: 1)
                            ]),
                            .init(id: 9, name: "QA", cycleTime: 10800, connectsToLine: 5, connectsToInventory: nil, color: .init(fill: "#dcfce7", border: "#166534"), workUnits: [
                                .init(id: 3201, key: "SD-3201", name: "Add payment options to card", intakeQueueId: 3,
                                      assignees: [.init(id: "eric-chamberlain", name: "Eric Chamberlain", avatar: "https://bithead.io/boss/img/logo.png")],
                                      onHold: false, startTime: "2026-03-05T12:30:00Z", eta: "2026-04-25T17:00:00", totalOperations: 5, completedOperations: 1)
                            ]),
                            .init(id: 10, name: "Pending Deployment", cycleTime: 1800, connectsToLine: nil, connectsToInventory: nil, color: .init(fill: "#dcfce7", border: "#166534"), workUnits: [
                                .init(id: 3500, key: "SD-3500", name: "Ingest device heartbeat events", intakeQueueId: 3,
                                      assignees: [.init(id: "eric-chamberlain", name: "Eric Chamberlain", avatar: "https://bithead.io/boss/img/logo.png")],
                                      onHold: false, startTime: "2026-03-05T12:30:00Z", eta: "2026-04-27T17:00:00", totalOperations: 5, completedOperations: 1)
                            ])
                        ]
                    ),
                    .init(
                        id: 5, gridX: 21, gridY: 9, name: "QA",
                        locked: false, hasOutput: false, subAssemblyLine: true,
                        leadTime: 57600, taktTime: 14400, throughput: 15,
                        hopperWorkUnit: nil,
                        intakeQueues: [
                            .init(id: 7, name: "QA Request", mixRatio: nil, cycleTime: 5400, color: .init(fill: "#E0F2FE", border: "#6b9fc2"))
                        ],
                        stations: [
                            .init(id: 11, name: "Planning", cycleTime: nil, connectsToLine: nil, connectsToInventory: nil, color: nil, workUnits: []),
                            .init(id: 12, name: "In Test", cycleTime: nil, connectsToLine: nil, connectsToInventory: nil, color: nil, workUnits: [])
                        ]
                    ),
                    .init(
                        id: 3, gridX: 1, gridY: 14, name: "Tech Support",
                        locked: false, hasOutput: true, subAssemblyLine: false,
                        leadTime: 172800, taktTime: 10800, throughput: 30,
                        hopperWorkUnit: nil,
                        intakeQueues: [
                            .init(id: 4, name: "Internal IT", mixRatio: nil, cycleTime: 2700, color: .init(fill: "#FFF8E8", border: "#b5ab80")),
                            .init(id: 5, name: "Support Request", mixRatio: nil, cycleTime: 4500, color: .init(fill: "#F8E8FF", border: "#ae8fbd"))
                        ],
                        stations: [
                            .init(id: 13, name: "Station 1", cycleTime: nil, connectsToLine: nil, connectsToInventory: nil, color: nil, workUnits: []),
                            .init(id: 14, name: "Station 2", cycleTime: nil, connectsToLine: nil, connectsToInventory: nil, color: nil, workUnits: []),
                            .init(id: 15, name: "Station 3", cycleTime: nil, connectsToLine: nil, connectsToInventory: nil, color: nil, workUnits: [])
                        ]
                    ),
                    .init(
                        id: 4, gridX: 1, gridY: 20, name: "Production",
                        locked: false, hasOutput: true, subAssemblyLine: false,
                        leadTime: 259200, taktTime: 18000, throughput: 40,
                        hopperWorkUnit: nil,
                        intakeQueues: [
                            .init(id: 6, name: "Print Request", mixRatio: nil, cycleTime: 1800, color: .init(fill: "#F0E8F8", border: "#9a90a8"))
                        ],
                        stations: [
                            .init(id: 16, name: "Station 1", cycleTime: nil, connectsToLine: nil, connectsToInventory: nil, color: nil, workUnits: []),
                            .init(id: 17, name: "Station 2", cycleTime: nil, connectsToLine: nil, connectsToInventory: 1, color: nil, workUnits: [])
                        ]
                    )
                ],
                inventories: [
                    .init(id: 1, gridX: 6, gridY: 18, name: "RFID Cards",
                          cycleStock: 240, bufferStockLevel: 60, safetyStockLevel: 24,
                          reorderPoint: "20%", estimatedReorderDate: "2026-04-03", health: 1)
                ]
            )
        }
        .addScope(.user)

        group.get("factories", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            // TODO: Fetch factories for the given company
            _ = companyId
            return LeanFragment.Factories(factories: [
                .init(id: 1, name: "Main Factory")
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

        group.post("save-line-focus") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.SaveLineFocus.self)
            // TODO: Save line focus state
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

        group.get("company", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            // TODO: Fetch company
            _ = companyId
            return LeanFragment.Company(id: companyId, name: "")
        }
        .addScope(.user)

        group.post("company", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            // TODO: Save company
            _ = companyId
            return Fragment.OK()
        }
        .addScope(.user)

        group.get("factory", ":factoryId") { req in
            let _ = try req.authUser
            let factoryId = try req.parameters.require("factoryId", as: Int.self)
            // TODO: Fetch factory
            _ = factoryId
            return LeanFragment.Factory(id: factoryId, name: "")
        }
        .addScope(.user)

        group.post("factory", ":factoryId") { req in
            let _ = try req.authUser
            let factoryId = try req.parameters.require("factoryId", as: Int.self)
            // TODO: Save factory
            _ = factoryId
            return Fragment.OK()
        }
        .addScope(.user)

        group.get("intake-queue", ":intakeQueueId") { req in
            let _ = try req.authUser
            let intakeQueueId = try req.parameters.require("intakeQueueId", as: Int.self)
            // TODO: Fetch intake queue
            _ = intakeQueueId
            return LeanFragment.IntakeQueue(id: intakeQueueId, name: "")
        }
        .addScope(.user)

        group.post("intake-queue", ":intakeQueueId") { req in
            let _ = try req.authUser
            let intakeQueueId = try req.parameters.require("intakeQueueId", as: Int.self)
            // TODO: Save intake queue
            _ = intakeQueueId
            return Fragment.OK()
        }
        .addScope(.user)

        group.get("inventory", ":inventoryId") { req in
            let _ = try req.authUser
            let inventoryId = try req.parameters.require("inventoryId", as: Int.self)
            // TODO: Fetch inventory
            _ = inventoryId
            return LeanFragment.Inventory(id: inventoryId, name: "")
        }
        .addScope(.user)

        group.post("inventory", ":inventoryId") { req in
            let _ = try req.authUser
            let inventoryId = try req.parameters.require("inventoryId", as: Int.self)
            // TODO: Save inventory
            _ = inventoryId
            return Fragment.OK()
        }
        .addScope(.user)

        group.get("line", ":lineId") { req in
            let _ = try req.authUser
            let lineId = try req.parameters.require("lineId", as: Int.self)
            // TODO: Fetch line
            _ = lineId
            return LeanFragment.Line(id: lineId, name: "")
        }
        .addScope(.user)

        group.post("line", ":lineId") { req in
            let _ = try req.authUser
            let lineId = try req.parameters.require("lineId", as: Int.self)
            // TODO: Save line
            _ = lineId
            return Fragment.OK()
        }
        .addScope(.user)

        group.get("station", ":stationId") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            // TODO: Fetch station
            _ = stationId
            return LeanFragment.Station(id: stationId, name: "")
        }
        .addScope(.user)

        group.post("station", ":stationId") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            // TODO: Save station
            _ = stationId
            return Fragment.OK()
        }
        .addScope(.user)

        group.get("work-unit", ":workUnitId") { req in
            let _ = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            // TODO: Fetch work unit
            _ = workUnitId
            return LeanFragment.WorkUnit(id: workUnitId, key: "", name: "", intakeQueueId: nil, eta: nil)
        }
        .addScope(.user)

        group.post("work-unit", ":workUnitId") { req in
            let _ = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            // TODO: Save work unit
            _ = workUnitId
            return Fragment.OK()
        }
        .addScope(.user)
    }
}
