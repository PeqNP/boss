/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import Foundation
internal import SQLiteKit

struct LeanService: LeanProvider {
    func companies(session: Database.Session, user: User) async throws -> [Company] {
        let conn = try await session.conn()
        let rows = try await conn.select()
            .column("*")
            .from("companies")
            .where("user_id", .equal, user.id)
            .all()
        return try rows.map { row in
            Company(
                id: try row.decode(column: "id", as: Company.ID.self),
                name: try row.decode(column: "name", as: String.self),
                userId: try row.decode(column: "user_id", as: User.ID.self)
            )
        }
    }

    func createCompany(session: Database.Session, user: User, name: String?) async throws -> Company {
        guard let name = name, !name.trimmingCharacters(in: .whitespaces).isEmpty else {
            throw api.error.RequiredParameter("name")
        }

        let conn = try await session.conn()
        let rows = try await conn.sql().insert(into: "companies")
            .columns("id", "name", "user_id")
            .values(SQLLiteral.null, SQLBind(name), SQLBind(user.id))
            .returning("id")
            .all()

        let id = try rows[0].decode(column: "id", as: Company.ID.self)
        return Company(id: id, name: name, userId: user.id)
    }

    func factories(session: Database.Session, companyId: Company.ID) async throws -> [Factory] {
        let conn = try await session.conn()
        let rows = try await conn.select()
            .column("*")
            .from("factories")
            .where("company_id", .equal, companyId)
            .all()
        return try rows.map { row in
            let intervalType = try row.decode(column: "flow_metric_interval_type", as: Int.self)
            let intervalDate = try row.decode(column: "flow_metric_interval_date", as: Date.self)
            let interval: Factory.FlowMetricInterval
            switch intervalType {
            case 2:  interval = .weekly(intervalDate)
            default: interval = .daily(intervalDate)
            }
            return Factory(
                id: try row.decode(column: "id", as: Factory.ID.self),
                companyId: try row.decode(column: "company_id", as: Company.ID.self),
                name: try row.decode(column: "name", as: String.self),
                lines: [],
                flowMetricInterval: interval
            )
        }
    }

    func createFactory(session: Database.Session, user: User, companyId: Company.ID, name: String?) async throws -> Factory {
        guard let name = name, !name.trimmingCharacters(in: .whitespaces).isEmpty else {
            throw api.error.RequiredParameter("name")
        }

        let conn = try await session.conn()
        let rows = try await conn.sql().insert(into: "factories")
            .columns("id", "company_id", "name", "flow_metric_interval_type", "flow_metric_interval_date")
            .values(
                SQLLiteral.null,
                SQLBind(companyId),
                SQLBind(name),
                SQLBind(1), // FlowMetricInterval.daily
                SQLBind(Date.now)
            )
            .returning("id")
            .all()

        let id = try rows[0].decode(column: "id", as: Factory.ID.self)
        return Factory(id: id, companyId: companyId, name: name, lines: [], flowMetricInterval: .daily(Date.now))
    }

    func createLine(session: Database.Session, user: User, factoryId: Factory.ID, name: String?) async throws -> Line {
        guard let name = name, !name.trimmingCharacters(in: .whitespaces).isEmpty else {
            throw api.error.RequiredParameter("name")
        }

        let conn = try await session.conn()

        let lineRows = try await conn.sql().insert(into: "lines")
            .columns("id", "factory_id", "name", "line_type", "view_x", "view_y", "view_locked", "is_parallel", "inherit_shifts")
            .values(
                SQLLiteral.null,
                SQLBind(factoryId),
                SQLBind(name),
                SQLBind(0), // LineType.model
                SQLBind(0), // view_x
                SQLBind(0), // view_y
                SQLBind(0), // view_locked
                SQLBind(0), // is_parallel
                SQLBind(0)  // inherit_shifts
            )
            .returning("id")
            .all()

        let lineId = try lineRows[0].decode(column: "id", as: Line.ID.self)

        let hopperRows = try await conn.sql().insert(into: "hoppers")
            .columns("id", "line_id")
            .values(SQLLiteral.null, SQLBind(lineId))
            .returning("id")
            .all()

        let hopperId = try hopperRows[0].decode(column: "id", as: Hopper.ID.self)

        return Line(
            id: lineId,
            type: .model,
            factoryId: factoryId,
            theme: nil,
            name: name,
            intakeQueues: [],
            hopper: Hopper(id: hopperId, lineId: lineId, lastIntakeQueueId: nil, number: 0, workUnit: nil),
            stations: [],
            output: nil,
            shifts: [],
            managers: [],
            viewState: Line.ViewState(x: 0, y: 0, locked: false, focused: false),
            isParallel: false,
            flowMetrics: nil
        )
    }

    func createInventory(session: Database.Session, user: User, factoryId: Factory.ID, name: String?) async throws -> Inventory {
        guard let name = name, !name.trimmingCharacters(in: .whitespaces).isEmpty else {
            throw api.error.RequiredParameter("name")
        }

        let conn = try await session.conn()

        let supplyRows = try await conn.sql().insert(into: "supplies")
            .columns("id", "name")
            .values(SQLLiteral.null, SQLBind(name))
            .returning("id")
            .all()

        let supplyId = try supplyRows[0].decode(column: "id", as: Supply.ID.self)

        let inventoryRows = try await conn.sql().insert(into: "inventories")
            .columns("id", "factory_id", "supply_id", "in_stock", "reorder_point", "estimated_reorder_point", "view_x", "view_y", "view_locked", "view_focused")
            .values(
                SQLLiteral.null,
                SQLBind(factoryId),
                SQLBind(supplyId),
                SQLBind(0),         // in_stock
                SQLBind(0),         // reorder_point
                SQLBind(Date.now),  // estimated_reorder_point
                SQLBind(0),         // view_x
                SQLBind(0),         // view_y
                SQLBind(0),         // view_locked
                SQLBind(0)          // view_focused
            )
            .returning("id")
            .all()

        let inventoryId = try inventoryRows[0].decode(column: "id", as: Inventory.ID.self)
        let supply = Supply(id: supplyId, companyId: 1, /* todo */ name: name, theme: nil, fields: nil, amount: nil)

        return Inventory(
            id: inventoryId,
            provider: [],
            supply: supply,
            inStock: 0,
            reorderPoint: 0,
            estimatedReorderPoint: Date.now,
            viewState: Inventory.ViewState(x: 0, y: 0, locked: false, focused: false)
        )
    }
    
    func intakeQueue(session: Database.Session, user: User, id: IntakeQueue.ID) async throws -> IntakeQueue {
        let conn = try await session.conn()
        let rows = try await conn.select()
            .column("*")
            .from("intake_queues")
            .where("id", .equal, id)
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        return try makeIntakeQueue(from: row)
    }

    func createIntakeQueue(session: Database.Session, user: User, lineId: Line.ID, name: String?, key: String?) async throws -> IntakeQueue {
        guard let name = name, !name.trimmingCharacters(in: .whitespaces).isEmpty else {
            throw api.error.RequiredParameter("name")
        }

        if let key = key {
            guard key.count >= 2 && key.count <= 4 else {
                throw service.error.InvalidInput("Key must be 2-4 characters")
            }
        }

        let conn = try await session.conn()

        // Fetch existing distributed queues ordered by sort_order to recalculate mix ratios
        let existingRows = try await conn.select()
            .column("*")
            .from("intake_queues")
            .where("line_id", .equal, lineId)
            .orderBy("sort_order", .ascending)
            .all()

        let sortOrder = existingRows.count
        let totalCount = existingRows.count + 1
        let baseRatio = 100 / totalCount
        let remainder = 100 % totalCount

        // Insert the new queue
        let newRows = try await conn.sql().insert(into: "intake_queues")
            .columns("id", "line_id", "sort_order", "key", "name", "mix_ratio", "mix_ratio_type")
            .values(
                SQLLiteral.null,
                SQLBind(lineId),
                SQLBind(sortOrder),
                key.map { SQLBind($0) } ?? SQLLiteral.null,
                SQLBind(name),
                SQLBind(Double(baseRatio)),
                SQLBind(0) // distributed
            )
            .returning("id")
            .all()

        let newId = try newRows[0].decode(column: "id", as: IntakeQueue.ID.self)

        // Update mix ratios for all existing distributed queues.
        // The first queue (sort_order = 0) absorbs the remainder.
        for (index, row) in existingRows.enumerated() {
            let existingId = try row.decode(column: "id", as: IntakeQueue.ID.self)
            let ratio = (index == 0) ? baseRatio + remainder : baseRatio
            try await conn.sql().update("intake_queues")
                .set("mix_ratio", to: SQLBind(Double(ratio)))
                .where("id", .equal, SQLBind(existingId))
                .run()
        }

        // The new queue is the last one; it gets baseRatio.
        // When it's the only queue, totalCount=1 so baseRatio+remainder=100.
        let newMixRatio = existingRows.isEmpty ? baseRatio + remainder : baseRatio

        return IntakeQueue(
            id: newId,
            lineId: lineId,
            key: key,
            workUnitNumber: 0,
            name: name,
            theme: nil,
            mixRatioType: .distributed,
            mixRatio: newMixRatio,
            workUnitName: .operatorProvided,
            finishedProduct: nil
        )
    }

    func updateIntakeQueueMixRatio(session: Database.Session, user: User, id: IntakeQueue.ID, mixRatio: Int) async throws {
        guard mixRatio >= 0 && mixRatio <= 100 else {
            throw service.error.InvalidInput("Invalid mix ratio")
        }

        let conn = try await session.conn()

        // Find the target queue to get its lineId
        let targetRows = try await conn.select()
            .column("*")
            .from("intake_queues")
            .where("id", .equal, id)
            .all()
        guard let targetRow = targetRows.first else {
            throw service.error.RecordNotFound()
        }
        let lineId = try targetRow.decode(column: "line_id", as: Line.ID.self)

        // Load all sibling queues to pre-validate the distribution before writing
        let allRows = try await conn.select()
            .column("*")
            .from("intake_queues")
            .where("line_id", .equal, lineId)
            .orderBy("sort_order", .ascending)
            .all()

        // Project what fixedTotal and distributedIds will look like after this change
        var projectedFixedTotal = mixRatio
        var distributedIds: [IntakeQueue.ID] = []
        for row in allRows {
            let rowId = try row.decode(column: "id", as: IntakeQueue.ID.self)
            if rowId == id { continue } // target row becomes fixed with new value
            let rowType = try row.decode(column: "mix_ratio_type", as: Int.self)
            if rowType == 1 {
                projectedFixedTotal += Int(try row.decode(column: "mix_ratio", as: Double.self))
            } else {
                distributedIds.append(rowId)
            }
        }

        if !distributedIds.isEmpty {
            let remaining = 100 - projectedFixedTotal
            guard remaining >= distributedIds.count else {
                throw service.error.InvalidInput("Invalid mix ratio. The remaining ratio cannot be evenly distributed among sibling intake queues.")
            }
        }

        // Validation passed — write the target row
        try await conn.sql().update("intake_queues")
            .set("mix_ratio", to: SQLBind(Double(mixRatio)))
            .set("mix_ratio_type", to: SQLBind(1)) // fixed
            .where("id", .equal, SQLBind(id))
            .run()

        guard !distributedIds.isEmpty else { return }

        let remaining = 100 - projectedFixedTotal
        let baseRatio = remaining / distributedIds.count
        let remainder = remaining % distributedIds.count

        for (index, distId) in distributedIds.enumerated() {
            let ratio = (index == 0) ? baseRatio + remainder : baseRatio
            try await conn.sql().update("intake_queues")
                .set("mix_ratio", to: SQLBind(Double(ratio)))
                .where("id", .equal, SQLBind(distId))
                .run()
        }
    }

    func updateIntakeQueueName(session: Database.Session, user: User, id: IntakeQueue.ID, name: String?) async throws {
        guard let name = name, !name.trimmingCharacters(in: .whitespaces).isEmpty else {
            throw api.error.RequiredParameter("name")
        }
        let conn = try await session.conn()
        try await conn.sql().update("intake_queues")
            .set("name", to: SQLBind(name))
            .where("id", .equal, SQLBind(id))
            .run()
    }

    func deleteFactory(session: Database.Session, user: User, id: Factory.ID) async throws {
        let conn = try await session.conn()
        let rows = try await conn.select()
            .column("id")
            .from("factories")
            .where("id", .equal, id)
            .all()
        guard rows.first != nil else {
            throw service.error.RecordNotFound()
        }
        try await conn.sql().delete(from: "factories")
            .where("id", .equal, SQLBind(id))
            .run()
    }

    func deleteCompany(session: Database.Session, user: User, id: Company.ID) async throws {
        let conn = try await session.conn()
        let rows = try await conn.select()
            .column("id")
            .from("companies")
            .where("id", .equal, id)
            .all()
        guard rows.first != nil else {
            throw service.error.RecordNotFound()
        }
        try await conn.sql().delete(from: "companies")
            .where("id", .equal, SQLBind(id))
            .run()
    }

    func company(session: Database.Session, user: User, id: Company.ID) async throws -> Company {
        let conn = try await session.conn()
        let rows = try await conn.select()
            .column("*")
            .from("companies")
            .where("id", .equal, id)
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        return Company(
            id: try row.decode(column: "id", as: Company.ID.self),
            name: try row.decode(column: "name", as: String.self),
            userId: try row.decode(column: "user_id", as: User.ID.self)
        )
    }

    func updateCompany(session: Database.Session, user: User, id: Company.ID, name: String?) async throws {
        guard let name = name, !name.trimmingCharacters(in: .whitespaces).isEmpty else {
            throw api.error.RequiredParameter("name")
        }
        let conn = try await session.conn()
        try await conn.sql().update("companies")
            .set("name", to: SQLBind(name))
            .where("id", .equal, SQLBind(id))
            .run()
    }

    func factory(session: Database.Session, user: User, id: Factory.ID) async throws -> Factory {
        let conn = try await session.conn()
        let rows = try await conn.select()
            .column("*")
            .from("factories")
            .where("id", .equal, id)
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        let intervalType = try row.decode(column: "flow_metric_interval_type", as: Int.self)
        let intervalDate = try row.decode(column: "flow_metric_interval_date", as: Date.self)
        let interval: Factory.FlowMetricInterval
        switch intervalType {
        case 2:  interval = .weekly(intervalDate)
        default: interval = .daily(intervalDate)
        }
        return Factory(
            id: try row.decode(column: "id", as: Factory.ID.self),
            companyId: try row.decode(column: "company_id", as: Company.ID.self),
            name: try row.decode(column: "name", as: String.self),
            lines: [],
            flowMetricInterval: interval
        )
    }

    func updateFactory(session: Database.Session, user: User, id: Factory.ID, name: String?) async throws {
        guard let name = name, !name.trimmingCharacters(in: .whitespaces).isEmpty else {
            throw api.error.RequiredParameter("name")
        }
        let conn = try await session.conn()
        try await conn.sql().update("factories")
            .set("name", to: SQLBind(name))
            .where("id", .equal, SQLBind(id))
            .run()
    }

    func updateInventoryName(session: Database.Session, user: User, id: Inventory.ID, name: String?) async throws {
        guard let name = name, !name.trimmingCharacters(in: .whitespaces).isEmpty else {
            throw api.error.RequiredParameter("name")
        }
        let conn = try await session.conn()
        let rows = try await conn.select()
            .column("supply_id")
            .from("inventories")
            .where("id", .equal, id)
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        let supplyId = try row.decode(column: "supply_id", as: Supply.ID.self)
        try await conn.sql().update("supplies")
            .set("name", to: SQLBind(name))
            .where("id", .equal, SQLBind(supplyId))
            .run()
    }

    func inventory(session: Database.Session, user: User, id: Inventory.ID) async throws -> Inventory {
        let conn = try await session.conn()
        let rows = try await conn.select()
            .column("*")
            .from("inventories")
            .where("id", .equal, id)
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        let supplyId = try row.decode(column: "supply_id", as: Supply.ID.self)
        let supplyRows = try await conn.select()
            .column("*")
            .from("supplies")
            .where("id", .equal, supplyId)
            .all()
        guard let supplyRow = supplyRows.first else {
            throw service.error.RecordNotFound()
        }
        let viewLocked = try row.decode(column: "view_locked", as: Int.self)
        let viewFocused = try row.decode(column: "view_focused", as: Int.self)
        return Inventory(
            id: try row.decode(column: "id", as: Inventory.ID.self),
            provider: [],
            supply: Supply(
                id: supplyId,
                companyId: 1, /* TODO: Replace with real company ID */
                name: try supplyRow.decode(column: "name", as: String.self),
                theme: nil,
                fields: nil,
                amount: nil
            ),
            inStock: try row.decode(column: "in_stock", as: Int.self),
            reorderPoint: try row.decode(column: "reorder_point", as: Int.self),
            estimatedReorderPoint: try row.decode(column: "estimated_reorder_point", as: Date.self),
            viewState: Inventory.ViewState(
                x: try row.decode(column: "view_x", as: Int.self),
                y: try row.decode(column: "view_y", as: Int.self),
                locked: viewLocked != 0,
                focused: viewFocused != 0
            )
        )
    }

    func updateLineName(session: Database.Session, user: User, id: Line.ID, name: String?) async throws {
        guard let name = name, !name.trimmingCharacters(in: .whitespaces).isEmpty else {
            throw api.error.RequiredParameter("name")
        }
        let conn = try await session.conn()
        try await conn.sql().update("lines")
            .set("name", to: SQLBind(name))
            .where("id", .equal, SQLBind(id))
            .run()
    }

    func line(session: Database.Session, user: User, id: Line.ID) async throws -> Line {
        let conn = try await session.conn()
        let rows = try await conn.select()
            .column("*")
            .from("lines")
            .where("id", .equal, id)
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        let hopperRows = try await conn.select()
            .column("*")
            .from("hoppers")
            .where("line_id", .equal, id)
            .all()
        guard let hopperRow = hopperRows.first else {
            throw service.error.RecordNotFound()
        }
        let locked = try row.decode(column: "view_locked", as: Int.self)
        let focused = try row.decode(column: "view_focused", as: Int.self)
        return Line(
            id: try row.decode(column: "id", as: Line.ID.self),
            type: .model,
            factoryId: try row.decode(column: "factory_id", as: Factory.ID.self),
            theme: nil,
            name: try row.decode(column: "name", as: String.self),
            intakeQueues: [],
            hopper: Hopper(
                id: try hopperRow.decode(column: "id", as: Hopper.ID.self),
                lineId: id,
                lastIntakeQueueId: nil,
                number: 0,
                workUnit: nil
            ),
            stations: [],
            output: nil,
            shifts: [],
            managers: [],
            viewState: Line.ViewState(
                x: try row.decode(column: "view_x", as: Int.self),
                y: try row.decode(column: "view_y", as: Int.self),
                locked: locked != 0,
                focused: focused != 0
            ),
            isParallel: false,
            flowMetrics: nil
        )
    }

    func saveLinePosition(session: Database.Session, user: User, id: Line.ID, x: Int, y: Int) async throws {
        guard x >= 0, y >= 0 else {
            throw service.error.InvalidInput("Position cannot be negative")
        }
        let conn = try await session.conn()
        try await conn.sql().update("lines")
            .set("view_x", to: SQLBind(x))
            .set("view_y", to: SQLBind(y))
            .where("id", .equal, SQLBind(id))
            .run()
    }

    func saveLineLocked(session: Database.Session, user: User, id: Line.ID, locked: Bool) async throws {
        let conn = try await session.conn()
        try await conn.sql().update("lines")
            .set("view_locked", to: SQLBind(locked ? 1 : 0))
            .where("id", .equal, SQLBind(id))
            .run()
    }

    func saveLineFocus(session: Database.Session, user: User, id: Line.ID, focused: Bool) async throws {
        let conn = try await session.conn()
        try await conn.sql().update("lines")
            .set("view_focused", to: SQLBind(focused ? 1 : 0))
            .where("id", .equal, SQLBind(id))
            .run()
    }

    func saveInventoryPosition(session: Database.Session, user: User, id: Inventory.ID, x: Int, y: Int) async throws {
        guard x >= 0, y >= 0 else {
            throw service.error.InvalidInput("Position cannot be negative")
        }
        let conn = try await session.conn()
        try await conn.sql().update("inventories")
            .set("view_x", to: SQLBind(x))
            .set("view_y", to: SQLBind(y))
            .where("id", .equal, SQLBind(id))
            .run()
    }

    func saveInventoryLocked(session: Database.Session, user: User, id: Inventory.ID, locked: Bool) async throws {
        let conn = try await session.conn()
        try await conn.sql().update("inventories")
            .set("view_locked", to: SQLBind(locked ? 1 : 0))
            .where("id", .equal, SQLBind(id))
            .run()
    }

    func saveInventoryFocus(session: Database.Session, user: User, id: Inventory.ID, focused: Bool) async throws {
        let conn = try await session.conn()
        try await conn.sql().update("inventories")
            .set("view_focused", to: SQLBind(focused ? 1 : 0))
            .where("id", .equal, SQLBind(id))
            .run()
    }

    private func makeIntakeQueue(from row: SQLRow) throws -> IntakeQueue {
        let mixRatioReal = try row.decode(column: "mix_ratio", as: Double.self)
        let mixRatioTypeInt = try row.decode(column: "mix_ratio_type", as: Int.self)
        let mixRatioType: IntakeQueue.MixRatioType = mixRatioTypeInt == 1 ? .fixed : .distributed
        return IntakeQueue(
            id: try row.decode(column: "id", as: IntakeQueue.ID.self),
            lineId: try row.decode(column: "line_id", as: Line.ID.self),
            key: try row.decode(column: "key", as: String?.self),
            workUnitNumber: 0,
            name: try row.decode(column: "name", as: String.self),
            theme: nil,
            mixRatioType: mixRatioType,
            mixRatio: Int(mixRatioReal),
            workUnitName: .operatorProvided,
            finishedProduct: nil
        )
    }
}
