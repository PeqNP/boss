/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import Foundation
internal import SQLiteKit

struct LeanService: LeanProvider {
    private func lineIntakeQueues(session: Database.Session, lineId: Line.ID) async throws -> LineIntakeQueues {
        let conn = try await session.conn()
        let rows = try await conn.select()
            .column("id")
            .column("intake_queue_id")
            .from("line_intake_queues")
            .where("line_id", .equal, lineId)
            .orderBy("sort_order", .ascending)
            .all()

        if rows.isEmpty {
            let fallbackRows = try await conn.select()
                .column("id")
                .from("intake_queues")
                .where("line_id", .equal, lineId)
                .orderBy("sort_order", .ascending)
                .all()
            let intakeQueueIds = try fallbackRows.map { row in
                try row.decode(column: "id", as: IntakeQueue.ID.self)
            }
            for (index, intakeQueueId) in intakeQueueIds.enumerated() {
                try await conn.sql().insert(into: "line_intake_queues")
                    .columns("id", "line_id", "intake_queue_id", "sort_order")
                    .values(SQLLiteral.null, SQLBind(lineId), SQLBind(intakeQueueId), SQLBind(index))
                    .run()
            }
            return LineIntakeQueues(id: 0, lineId: lineId, intakeQueueIds: intakeQueueIds)
        }

        return LineIntakeQueues(
            id: try rows[0].decode(column: "id", as: LineIntakeQueues.ID.self),
            lineId: lineId,
            intakeQueueIds: try rows.map { row in
                try row.decode(column: "intake_queue_id", as: IntakeQueue.ID.self)
            }
        )
    }

    private func orderedIntakeQueueRows(session: Database.Session, lineId: Line.ID) async throws -> [SQLRow] {
        let conn = try await session.conn()
        let allRows = try await conn.select()
            .column("*")
            .from("intake_queues")
            .where("line_id", .equal, lineId)
            .all()

        let lineQueueOrder = try await lineIntakeQueues(session: session, lineId: lineId)
        let order = lineQueueOrder.intakeQueueIds
        var rowsById: [IntakeQueue.ID: SQLRow] = [:]
        for row in allRows {
            let id = try row.decode(column: "id", as: IntakeQueue.ID.self)
            rowsById[id] = row
        }

        var orderedRows: [SQLRow] = []
        for id in order {
            if let row = rowsById[id] {
                orderedRows.append(row)
            }
        }

        if orderedRows.count == allRows.count {
            return orderedRows
        }

        // Reconcile any missing queue IDs by appending them to the end and persisting their order.
        var missingRows: [SQLRow] = []
        for row in allRows {
            let id = try row.decode(column: "id", as: IntakeQueue.ID.self)
            if !order.contains(id) {
                missingRows.append(row)
            }
        }
        orderedRows.append(contentsOf: missingRows)

        for (index, row) in orderedRows.enumerated() {
            let id = try row.decode(column: "id", as: IntakeQueue.ID.self)
            let existingRows = try await conn.select()
                .column("id")
                .from("line_intake_queues")
                .where("line_id", .equal, lineId)
                .where("intake_queue_id", .equal, id)
                .all()
            if existingRows.isEmpty {
                try await conn.sql().insert(into: "line_intake_queues")
                    .columns("id", "line_id", "intake_queue_id", "sort_order")
                    .values(SQLLiteral.null, SQLBind(lineId), SQLBind(id), SQLBind(index))
                    .run()
            }
        }

        return orderedRows
    }

    private func redistributeDistributedIntakeQueueMixRatios(conn: Database.Connection, orderedRows: [SQLRow]) async throws {
        var fixedTotal = 0
        var distributedIds: [IntakeQueue.ID] = []

        for row in orderedRows {
            let id = try row.decode(column: "id", as: IntakeQueue.ID.self)
            let type = try row.decode(column: "mix_ratio_type", as: Int.self)
            if type == 1 {
                fixedTotal += Int(try row.decode(column: "mix_ratio", as: Double.self))
            } else {
                distributedIds.append(id)
            }
        }

        guard !distributedIds.isEmpty else {
            return
        }

        let remaining = 100 - fixedTotal
        guard remaining >= distributedIds.count else {
            throw service.error.InvalidInput("Invalid mix ratio. The remaining ratio cannot be evenly distributed among sibling intake queues.")
        }

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

    private func `operator`(session: Database.Session, user: User) async throws -> Operator {
        let conn = try await session.conn()

        let existingRows = try await conn.select()
            .column("id")
            .from("operators")
            .where("type", .equal, 0)
            .where("user_id", .equal, user.id)
            .all()

        let operatorId: Operator.ID
        if let row = existingRows.first {
            operatorId = try row.decode(column: "id", as: Operator.ID.self)
        } else {
            let rows = try await conn.sql().insert(into: "operators")
                .columns("id", "type", "user_id", "agent_id")
                .values(SQLLiteral.null, SQLBind(0), SQLBind(user.id), SQLLiteral.null)
                .returning("id")
                .all()
            operatorId = try rows[0].decode(column: "id", as: Operator.ID.self)
        }

        return Operator(id: operatorId, companyId: 0, type: .user(user.id), shifts: [])
    }

    private func makeWorkUnit(session: Database.Session, user: User, row: SQLRow) async throws -> WorkUnit {
        let intakeQueueId = try row.decode(column: "intake_queue_id", as: IntakeQueue.ID.self)
        let workUnitId = try row.decode(column: "id", as: WorkUnit.ID.self)
        let parentWorkUnitId = try row.decode(column: "parent_work_unit_id", as: WorkUnit.ID?.self)
        let stateIntakeQueueId = try row.decode(column: "line_state_intake_queue_id", as: IntakeQueue.ID?.self)

        let conn = try await session.conn()
        let queueRows = try await conn.select()
            .column("key")
            .from("intake_queues")
            .where("id", .equal, intakeQueueId)
            .all()
        let queueKey = try queueRows.first?.decode(column: "key", as: String?.self)
        let keyPrefix = (queueKey?.isEmpty == false) ? queueKey! : "WU"

        let op = try await `operator`(session: session, user: user)

        return WorkUnit(
            id: workUnitId,
            intakeQueueID: intakeQueueId,
            key: "\(keyPrefix)-\(workUnitId)",
            flowMetrics: nil,
            outputDate: nil,
            creator: op,
            reporter: op,
            assignees: [],
            lineState: .intakeQueue(intakeQueue: stateIntakeQueueId ?? intakeQueueId, priority: .up),
            notificationTriggers: [],
            name: try row.decode(column: "name", as: String.self),
            outputReason: nil,
            finishedProduct: nil,
            parent: .parentWorkUnit(parentWorkUnitId ?? workUnitId),
            workUnits: nil,
            onHold: nil,
            returnToStation: [],
            comments: []
        )
    }

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
            hopper: Hopper(id: hopperId, lineId: lineId, lastIntakeQueueId: nil, number: 0, total: 0, workUnit: nil),
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
            viewState: Inventory.ViewState(x: 0, y: 0, locked: false, focused: false),
            reorderAlgorithm: nil,
            orderRequest: nil
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

        // Fetch existing queues in line-defined order to recalculate mix ratios.
        let existingRows = try await orderedIntakeQueueRows(session: session, lineId: lineId)

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

        try await conn.sql().insert(into: "line_intake_queues")
            .columns("id", "line_id", "intake_queue_id", "sort_order")
            .values(SQLLiteral.null, SQLBind(lineId), SQLBind(newId), SQLBind(sortOrder))
            .run()

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

        // Load all sibling queues in line-defined order to pre-validate distribution.
        let allRows = try await orderedIntakeQueueRows(session: session, lineId: lineId)

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
        let updatedRows = try await orderedIntakeQueueRows(session: session, lineId: lineId)
        try await redistributeDistributedIntakeQueueMixRatios(conn: conn, orderedRows: updatedRows)
    }

    func saveIntakeQueuePosition(session: Database.Session, user: User, id: IntakeQueue.ID, position: Int) async throws {
        let conn = try await session.conn()
        let queueRows = try await conn.select()
            .column("line_id")
            .from("intake_queues")
            .where("id", .equal, id)
            .all()
        guard let queueRow = queueRows.first else {
            throw service.error.RecordNotFound()
        }

        let lineId = try queueRow.decode(column: "line_id", as: Line.ID.self)
        let lineQueueOrder = try await lineIntakeQueues(session: session, lineId: lineId)
        let order = lineQueueOrder.intakeQueueIds

        guard position >= 0, position < order.count else {
            throw service.error.InvalidInput("Invalid position")
        }
        guard let currentIndex = order.firstIndex(of: id) else {
            throw service.error.RecordNotFound()
        }
        guard currentIndex != position else {
            return
        }

        var reordered = order
        let moved = reordered.remove(at: currentIndex)
        reordered.insert(moved, at: position)

        let lowerBound = min(currentIndex, position)
        let upperBound = max(currentIndex, position)
        for idx in lowerBound...upperBound {
            try await conn.sql().update("line_intake_queues")
                .set("sort_order", to: SQLBind(idx))
                .where("line_id", .equal, SQLBind(lineId))
                .where("intake_queue_id", .equal, SQLBind(reordered[idx]))
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
            viewState: Inventory.ViewState(
                x: try row.decode(column: "view_x", as: Int.self),
                y: try row.decode(column: "view_y", as: Int.self),
                locked: viewLocked != 0,
                focused: viewFocused != 0
            ),
            
            // TODO: The following properties need to be pulled from database
            reorderAlgorithm: nil,
            orderRequest: nil
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
        let hopperWorkUnitId = try hopperRow.decode(column: "work_unit_id", as: WorkUnit.ID?.self)
        var hopperWorkUnit: WorkUnit? = nil
        if let wuId = hopperWorkUnitId {
            let wuRows = try await conn.select()
                .column("*")
                .from("work_units")
                .where("id", .equal, wuId)
                .all()
            if let wuRow = wuRows.first {
                hopperWorkUnit = try await makeWorkUnit(session: session, user: user, row: wuRow)
            }
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
                total: 0,
                workUnit: hopperWorkUnit
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


// MARK: - Route Surface Stubs

extension LeanService {
    func factoryFloor(session: Database.Session, user: User, factoryId: Int) async throws -> FactoryFloor {
        let conn = try await session.conn()
        let lineRows = try await conn.select()
            .column("*")
            .from("lines")
            .where("factory_id", .equal, factoryId)
            .all()
        var lines: [Line] = []
        for lineRow in lineRows {
            let lineId = try lineRow.decode(column: "id", as: Line.ID.self)
            let hopperRows = try await conn.select()
                .column("*")
                .from("hoppers")
                .where("line_id", .equal, lineId)
                .all()
            guard let hopperRow = hopperRows.first else {
                throw service.error.RecordNotFound()
            }
            let hopperWorkUnitId = try hopperRow.decode(column: "work_unit_id", as: WorkUnit.ID?.self)
            var hopperWorkUnit: WorkUnit? = nil
            if let wuId = hopperWorkUnitId {
                let wuRows = try await conn.select()
                    .column("*")
                    .from("work_units")
                    .where("id", .equal, wuId)
                    .all()
                if let wuRow = wuRows.first {
                    hopperWorkUnit = try await makeWorkUnit(session: session, user: user, row: wuRow)
                }
            }
            let orderedRows = try await orderedIntakeQueueRows(session: session, lineId: lineId)
            let intakeQueues = try orderedRows.map { try makeIntakeQueue(from: $0) }
            let locked = try lineRow.decode(column: "view_locked", as: Int.self)
            let focused = try lineRow.decode(column: "view_focused", as: Int.self)
            lines.append(Line(
                id: lineId,
                type: .model,
                factoryId: factoryId,
                theme: nil,
                name: try lineRow.decode(column: "name", as: String.self),
                intakeQueues: intakeQueues,
                hopper: Hopper(
                    id: try hopperRow.decode(column: "id", as: Hopper.ID.self),
                    lineId: lineId,
                    lastIntakeQueueId: nil,
                    number: 0,
                    total: 0,
                    workUnit: hopperWorkUnit
                ),
                stations: [],
                output: nil,
                shifts: [],
                managers: [],
                viewState: Line.ViewState(
                    x: try lineRow.decode(column: "view_x", as: Int.self),
                    y: try lineRow.decode(column: "view_y", as: Int.self),
                    locked: locked != 0,
                    focused: focused != 0
                ),
                isParallel: false,
                flowMetrics: nil
            ))
        }
        return FactoryFloor(factoryId: factoryId, lines: lines, inventories: [])
    }

    func findAgents(session: Database.Session, user: User, companyId: Int, query: String) async throws -> [FoundItem] {
        throw api.error.NotImplemented()
    }

    func findIntakeQueue(session: Database.Session, user: User, lineId: Int, query: String) async throws -> [FoundItem] {
        throw api.error.NotImplemented()
    }

    func findIntakeQueues(session: Database.Session, user: User, companyId: Int, query: String) async throws -> [FoundItem] {
        throw api.error.NotImplemented()
    }

    func findInventories(session: Database.Session, user: User, companyId: Int, query: String) async throws -> [FoundItem] {
        throw api.error.NotImplemented()
    }

    func findMimeTypes(session: Database.Session, user: User, query: String) async throws -> [FoundItem] {
        throw api.error.NotImplemented()
    }

    func findOperators(session: Database.Session, user: User, companyId: Int, query: String) async throws -> [FoundItem] {
        throw api.error.NotImplemented()
    }

    func findSupplies(session: Database.Session, user: User, companyId: Int, query: String) async throws -> [FoundItem] {
        throw api.error.NotImplemented()
    }

    func findWorkUnit(session: Database.Session, user: User, companyId: Int, query: String) async throws -> [FoundItem] {
        throw api.error.NotImplemented()
    }

    func saveImage(session: Database.Session, user: User) async throws -> FileResource {
        throw api.error.NotImplemented()
    }

    func image(session: Database.Session, user: User, imageId: Int) async throws -> FileResource {
        throw api.error.NotImplemented()
    }

    func deleteImage(session: Database.Session, user: User, imageId: Int) async throws {
        throw api.error.NotImplemented()
    }

    func createIntakeQueue(session: Database.Session, user: User, lineId: Int, name: String?) async throws -> ListItem {
        let queue = try await createIntakeQueue(session: session, user: user, lineId: lineId, name: name, key: nil)
        return ListItem(id: queue.id, name: queue.name)
    }

    func intakeQueue(session: Database.Session, user: User, intakeQueueId: Int) async throws -> IntakeQueue {
        try await intakeQueue(session: session, user: user, id: intakeQueueId)
    }

    func saveIntakeQueue(session: Database.Session, user: User, intakeQueueId: Int, name: String?, key: String?, mixRatioType: String?, mixRatio: Int?, workUnitNameType: String?, workUnitMaterialName: String?, theme: Theme?) async throws {
        throw api.error.NotImplemented()
    }

    func saveInventory(session: Database.Session, user: User, inventoryId: Int, name: String?) async throws {
        throw api.error.NotImplemented()
    }

    func line(session: Database.Session, user: User, lineId: Int) async throws -> Line {
        throw api.error.NotImplemented()
    }

    func saveLine(session: Database.Session, user: User, lineId: Int, name: String, hasOutput: Bool, subAssemblyLine: Bool) async throws -> Line {
        throw api.error.NotImplemented()
    }

    func deleteLine(session: Database.Session, user: User, lineId: Int) async throws {
        throw api.error.NotImplemented()
    }

    func createOperation(session: Database.Session, user: User, stationId: Int, name: String, agentId: Int?, supplyRequestType: String?, inventoryId: Int?, amount: Int?, supplyId: Int?, intakeQueueId: Int?) async throws -> Operation {
        throw api.error.NotImplemented()
    }

    func operation(session: Database.Session, user: User, operationId: Int) async throws -> Operation {
        throw api.error.NotImplemented()
    }

    func saveOperation(session: Database.Session, user: User, operationId: Int, name: String, instructions: String?, agentId: Int?, supplyRequestType: String?, inventoryId: Int?, amount: Int?, supplyId: Int?, intakeQueueId: Int?) async throws -> Operation {
        throw api.error.NotImplemented()
    }

    func deleteOperation(session: Database.Session, user: User, operationId: Int) async throws {
        throw api.error.NotImplemented()
    }

    func createOperator(session: Database.Session, user: User, userId: Int?, agentId: Int?) async throws {
        throw api.error.NotImplemented()
    }

    func `operator`(session: Database.Session, user: User, operatorId: Int) async throws -> Operator {
        throw api.error.NotImplemented()
    }

    func saveOperator(session: Database.Session, user: User, operatorId: Int, userId: Int?, agentId: Int?) async throws {
        throw api.error.NotImplemented()
    }

    func deleteOperator(session: Database.Session, user: User, operatorId: Int) async throws {
        throw api.error.NotImplemented()
    }

    func startWorkUnit(session: Database.Session, user: User, workUnitId: Int) async throws -> WorkUnit {
        let conn = try await session.conn()
        let rows = try await conn.select()
            .column("*")
            .from("work_units")
            .where("id", .equal, workUnitId)
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }
        return try await makeWorkUnit(session: session, user: user, row: row)
    }

    func createStation(session: Database.Session, user: User, lineId: Int, name: String?, index: Int?) async throws -> Station {
        throw api.error.NotImplemented()
    }

    func station(session: Database.Session, user: User, stationId: Int) async throws -> Station {
        throw api.error.NotImplemented()
    }

    func stationNotificationTriggers(session: Database.Session, user: User, stationId: Int) async throws -> [ListItem] {
        throw api.error.NotImplemented()
    }

    func stationOperations(session: Database.Session, user: User, stationId: Int) async throws -> [ListItem] {
        throw api.error.NotImplemented()
    }

    func stationWorkUnits(session: Database.Session, user: User, stationId: Int) async throws -> [WorkUnit] {
        throw api.error.NotImplemented()
    }

    func saveStation(session: Database.Session, user: User, stationId: Int, name: String?, assigneeAction: String?, assigneeIds: [Int]?, theme: Theme?) async throws -> Station {
        throw api.error.NotImplemented()
    }

    func saveStationTypeIntakeQueue(session: Database.Session, user: User, stationId: Int, intakeQueueId: Int) async throws {
        throw api.error.NotImplemented()
    }

    func saveStationTypeStation(session: Database.Session, user: User, stationId: Int) async throws {
        throw api.error.NotImplemented()
    }

    func saveStationName(session: Database.Session, user: User, stationId: Int, name: String) async throws {
        throw api.error.NotImplemented()
    }

    func saveStationOperationPositions(session: Database.Session, user: User, stationId: Int, position: Int, operationIds: [Int]) async throws {
        throw api.error.NotImplemented()
    }

    func saveStationViewState(session: Database.Session, user: User, stationId: Int, overlay: String) async throws {
        throw api.error.NotImplemented()
    }

    func deleteStation(session: Database.Session, user: User, stationId: Int) async throws {
        throw api.error.NotImplemented()
    }

    func createStationNotificationTrigger(session: Database.Session, user: User, stationId: Int, events: [String], operatorIds: [Int], message: String?) async throws -> StationNotificationTrigger {
        throw api.error.NotImplemented()
    }

    func stationNotificationTrigger(session: Database.Session, user: User, triggerId: Int) async throws -> StationNotificationTrigger {
        throw api.error.NotImplemented()
    }

    func saveStationNotificationTrigger(session: Database.Session, user: User, triggerId: Int, events: [String]?, operatorIds: [Int]?, message: String?) async throws -> StationNotificationTrigger {
        throw api.error.NotImplemented()
    }

    func deleteStationNotificationTrigger(session: Database.Session, user: User, triggerId: Int) async throws {
        throw api.error.NotImplemented()
    }

    func suggestedAgents(session: Database.Session, user: User, companyId: Int) async throws -> [SuggestedItem] {
        throw api.error.NotImplemented()
    }

    func suggestedIntakeQueue(session: Database.Session, user: User, lineId: Int) async throws -> [SuggestedItem] {
        throw api.error.NotImplemented()
    }

    func suggestedIntakeQueues(session: Database.Session, user: User, companyId: Int) async throws -> [SuggestedItem] {
        throw api.error.NotImplemented()
    }

    func suggestedInventories(session: Database.Session, user: User, companyId: Int) async throws -> [SuggestedItem] {
        throw api.error.NotImplemented()
    }

    func suggestedMimeTypes(session: Database.Session, user: User) async throws -> [SuggestedItem] {
        throw api.error.NotImplemented()
    }

    func suggestedOperators(session: Database.Session, user: User, companyId: Int) async throws -> [SuggestedItem] {
        throw api.error.NotImplemented()
    }

    func suggestedSupplies(session: Database.Session, user: User, companyId: Int) async throws -> [SuggestedItem] {
        throw api.error.NotImplemented()
    }

    func suggestedWorkUnit(session: Database.Session, user: User, companyId: Int) async throws -> [SuggestedItem] {
        throw api.error.NotImplemented()
    }

    func suggestedSupplyFieldOptions(session: Database.Session, user: User, supplyFieldId: Int) async throws -> [SuggestedItem] {
        throw api.error.NotImplemented()
    }

    func findSupplyFieldOptions(session: Database.Session, user: User, supplyFieldId: Int, query: String) async throws -> [FoundItem] {
        throw api.error.NotImplemented()
    }

    func createSupply(session: Database.Session, user: User, companyId: Int, name: String, theme: Theme?, amount: Int?) async throws -> ListItem {
        throw api.error.NotImplemented()
    }

    func supply(session: Database.Session, user: User, supplyId: Int) async throws -> Supply {
        throw api.error.NotImplemented()
    }

    func saveSupply(session: Database.Session, user: User, supplyId: Int, name: String, theme: Theme?, amount: Int?) async throws -> Supply {
        throw api.error.NotImplemented()
    }

    func deleteSupply(session: Database.Session, user: User, supplyId: Int) async throws {
        throw api.error.NotImplemented()
    }

    func supplyFields(session: Database.Session, user: User, supplyId: Int) async throws -> [ListItem] {
        throw api.error.NotImplemented()
    }

    func saveSupplyFieldPositions(session: Database.Session, user: User, supplyId: Int, position: Int, fieldIds: [Int]) async throws {
        throw api.error.NotImplemented()
    }

    func createSupplyField(session: Database.Session, user: User, supplyId: Int, name: String) async throws -> SupplyField {
        throw api.error.NotImplemented()
    }

    func supplyField(session: Database.Session, user: User, supplyFieldId: Int) async throws -> SupplyField {
        throw api.error.NotImplemented()
    }

    func supplyFieldOptions(session: Database.Session, user: User, supplyFieldId: Int) async throws -> [ListItem] {
        throw api.error.NotImplemented()
    }

    func saveSupplyField(session: Database.Session, user: User, supplyFieldId: Int, name: String?, type: String?, textType: String?, placeholder: String?, intakeQueueId: Int?, append: Bool?, optionNames: [String]?) async throws -> SupplyField {
        throw api.error.NotImplemented()
    }

    func deleteSupplyField(session: Database.Session, user: User, supplyFieldId: Int) async throws {
        throw api.error.NotImplemented()
    }

    func createSupplyFieldOption(session: Database.Session, user: User, supplyFieldId: Int, name: String, hidden: Bool?) async throws -> SupplyFieldOption {
        throw api.error.NotImplemented()
    }

    func supplyFieldOption(session: Database.Session, user: User, supplyFieldOptionId: Int) async throws -> SupplyFieldOption {
        throw api.error.NotImplemented()
    }

    func saveSupplyFieldOption(session: Database.Session, user: User, supplyFieldOptionId: Int, name: String?, hidden: Bool?) async throws -> SupplyFieldOption {
        throw api.error.NotImplemented()
    }

    func deleteSupplyFieldOption(session: Database.Session, user: User, supplyFieldOptionId: Int) async throws {
        throw api.error.NotImplemented()
    }

    func createWorkUnit(session: Database.Session, user: User, intakeQueueId: Int, name: String?, reporterId: Int?, assigneeIds: [Int], parentWorkUnitId: Int?) async throws -> WorkUnit {
        guard let name = name, !name.trimmingCharacters(in: .whitespaces).isEmpty else {
            throw api.error.RequiredParameter("name")
        }

        let conn = try await session.conn()
        let creator = try await `operator`(session: session, user: user)
        let reporterOperatorId = reporterId ?? creator.id

        let rows = try await conn.sql().insert(into: "work_units")
            .columns(
                "id",
                "intake_queue_id",
                "creator_operator_id",
                "reporter_operator_id",
                "name",
                "on_hold",
                "parent_type",
                "parent_operation_id",
                "parent_operation_work_unit_id",
                "parent_work_unit_id",
                "line_state_intake_queue_id",
                "line_state_station_id",
                "line_state_operation_id",
                "line_state_operation_status",
                "line_state_operation_status_message",
                "line_state_output_id"
            )
            .values(
                SQLLiteral.null,
                SQLBind(intakeQueueId),
                SQLBind(creator.id),
                SQLBind(reporterOperatorId),
                SQLBind(name),
                SQLBind(0),
                parentWorkUnitId == nil ? SQLLiteral.null : SQLBind(1),
                SQLLiteral.null,
                SQLLiteral.null,
                parentWorkUnitId.map { SQLBind($0) } ?? SQLLiteral.null,
                SQLBind(intakeQueueId),
                SQLLiteral.null,
                SQLLiteral.null,
                SQLLiteral.null,
                SQLLiteral.null,
                SQLLiteral.null
            )
            .returning("id")
            .all()

        let id = try rows[0].decode(column: "id", as: WorkUnit.ID.self)

        for assigneeId in assigneeIds {
            try await conn.sql().insert(into: "work_unit_assignees")
                .columns("id", "work_unit_id", "operator_id")
                .values(SQLLiteral.null, SQLBind(id), SQLBind(assigneeId))
                .run()
        }

        let workUnitRows = try await conn.select()
            .column("*")
            .from("work_units")
            .where("id", .equal, id)
            .all()
        guard let workUnitRow = workUnitRows.first else {
            throw service.error.RecordNotFound()
        }

        // Get line_id for the log entry
        let iqLineRows = try await conn.select()
            .column("line_id")
            .from("intake_queues")
            .where("id", .equal, intakeQueueId)
            .all()
        guard let iqLineRow = iqLineRows.first else {
            throw service.error.RecordNotFound()
        }
        let lineId = try iqLineRow.decode(column: "line_id", as: Line.ID.self)

        // Log the WorkUnit entering the intake queue
        try await conn.sql().insert(into: "work_unit_logs")
            .columns("id", "work_unit_id", "line_id", "operator_id", "intake_queue_id", "station_id", "operation_id", "operation_status", "operation_status_message", "output_id", "enter_date", "exit_date")
            .values(
                SQLLiteral.null,
                SQLBind(id),
                SQLBind(lineId),
                SQLBind(creator.id),
                SQLBind(intakeQueueId),
                SQLLiteral.null,
                SQLLiteral.null,
                SQLLiteral.null,
                SQLLiteral.null,
                SQLLiteral.null,
                SQLBind(Date.now),
                SQLLiteral.null
            )
            .run()

        // Populate hopper if empty
        let hopperCheckRows = try await conn.select()
            .column("id")
            .column("work_unit_id")
            .from("hoppers")
            .where("line_id", .equal, lineId)
            .all()
        if let hopperCheckRow = hopperCheckRows.first {
            let existingWorkUnitId = try hopperCheckRow.decode(column: "work_unit_id", as: WorkUnit.ID?.self)
            if existingWorkUnitId == nil {
                let hopperId = try hopperCheckRow.decode(column: "id", as: Hopper.ID.self)
                try await conn.sql().update("hoppers")
                    .set("work_unit_id", to: SQLBind(id))
                    .where("id", .equal, SQLBind(hopperId))
                    .run()
            }
        }

        return try await makeWorkUnit(session: session, user: user, row: workUnitRow)
    }

    func saveWorkUnitChild(session: Database.Session, user: User, workUnitId: Int, childWorkUnitId: Int) async throws {
        throw api.error.NotImplemented()
    }

    func saveWorkUnitHold(session: Database.Session, user: User, workUnitId: Int) async throws {
        throw api.error.NotImplemented()
    }

    func workUnit(session: Database.Session, user: User, workUnitId: Int) async throws -> WorkUnit {
        throw api.error.NotImplemented()
    }

    func workUnitChildren(session: Database.Session, user: User, workUnitId: Int) async throws -> [WorkUnit] {
        throw api.error.NotImplemented()
    }

    func saveWorkUnit(session: Database.Session, user: User, workUnitId: Int, name: String?, eta: String?) async throws -> WorkUnit {
        throw api.error.NotImplemented()
    }

    func saveWorkUnitAssignees(session: Database.Session, user: User, workUnitId: Int, operatorIds: [Int]) async throws {
        throw api.error.NotImplemented()
    }

    func saveWorkUnitParent(session: Database.Session, user: User, workUnitId: Int, parentWorkUnitId: Int?) async throws {
        throw api.error.NotImplemented()
    }

    func saveWorkUnitReporter(session: Database.Session, user: User, workUnitId: Int, operatorId: Int?) async throws {
        throw api.error.NotImplemented()
    }

    func deleteWorkUnit(session: Database.Session, user: User, workUnitId: Int) async throws {
        throw api.error.NotImplemented()
    }

    func deleteWorkUnitChild(session: Database.Session, user: User, workUnitId: Int, childWorkUnitId: Int) async throws {
        throw api.error.NotImplemented()
    }

    func deleteWorkUnitHold(session: Database.Session, user: User, workUnitId: Int, comments: String?) async throws {
        throw api.error.NotImplemented()
    }

    func saveWorkUnitComment(session: Database.Session, user: User, workUnitId: Int, text: String) async throws {
        throw api.error.NotImplemented()
    }

    func saveWorkUnitComment(session: Database.Session, user: User, commentId: Int, text: String) async throws {
        throw api.error.NotImplemented()
    }

    func deleteWorkUnitComment(session: Database.Session, user: User, commentId: Int) async throws {
        throw api.error.NotImplemented()
    }

    func saveWorkUnitPosition(session: Database.Session, user: User, position: Int, workUnitIds: [Int]) async throws {
        throw api.error.NotImplemented()
    }

    func workUnits(session: Database.Session, user: User, intakeQueueId: Int) async throws -> [WorkUnit] {
        throw api.error.NotImplemented()
    }

    func workUnitLogs(session: Database.Session, user: User, workUnitId: Int) async throws -> [WorkUnitLog] {
        let conn = try await session.conn()
        let rows = try await conn.select()
            .column("*")
            .from("work_unit_logs")
            .where("work_unit_id", .equal, workUnitId)
            .orderBy("id", .ascending)
            .all()
        return try rows.map { row in
            let intakeQueueId = try row.decode(column: "intake_queue_id", as: IntakeQueue.ID?.self)
            let stationId = try row.decode(column: "station_id", as: Station.ID?.self)
            let outputId = try row.decode(column: "output_id", as: Output.ID?.self)
            let lineState: LineState
            if let iqId = intakeQueueId {
                lineState = .intakeQueue(intakeQueue: iqId, priority: .up)
            } else if let sId = stationId {
                lineState = .station(station: sId, operation: nil, status: nil)
            } else if let oId = outputId {
                lineState = .output(output: oId)
            } else {
                throw service.error.RecordNotFound()
            }
            return WorkUnitLog(
                id: try row.decode(column: "id", as: WorkUnitLog.ID.self),
                workUnitId: try row.decode(column: "work_unit_id", as: WorkUnit.ID.self),
                lineId: try row.decode(column: "line_id", as: Line.ID.self),
                operatorId: try row.decode(column: "operator_id", as: Operator.ID.self),
                lineState: lineState,
                enterDate: try row.decode(column: "enter_date", as: Date.self),
                exitDate: try row.decode(column: "exit_date", as: Date?.self)
            )
        }
    }

    func saveWorkUnits(session: Database.Session, user: User, intakeQueueId: Int, name: String?, key: String?, mixRatioType: String?, mixRatio: Int?, workUnitNameType: String?, workUnitMaterialName: String?, theme: Theme?) async throws {
        throw api.error.NotImplemented()
    }

    func workspace(session: Database.Session, user: User, workUnitId: Int) async throws -> Workspace {
        throw api.error.NotImplemented()
    }

    func saveWorkUnitMoveToNextStation(session: Database.Session, user: User, workUnitId: Int) async throws {
        throw api.error.NotImplemented()
    }

    func saveWorkUnitSupply(session: Database.Session, user: User, id: Int, fields: [WorkUnitSupplyFieldInput]) async throws -> Workspace {
        let conn = try await session.conn()
        let rows = try await conn.select()
            .column("*")
            .from("work_units")
            .where("id", .equal, id)
            .all()
        guard let row = rows.first else {
            throw service.error.RecordNotFound()
        }

        let workUnit = try await makeWorkUnit(session: session, user: user, row: row)
        return Workspace(workUnit: workUnit, operations: [])
    }

    func saveWorkUnitSupplyFulfill(session: Database.Session, user: User, id: Int) async throws -> Workspace {
        throw api.error.NotImplemented()
    }

    func saveWorkUnitSupplyWaive(session: Database.Session, user: User, id: Int, comments: String) async throws -> Workspace {
        throw api.error.NotImplemented()
    }

    func suggestedWorkUnitsForIntakeQueue(session: Database.Session, user: User, intakeQueueId: Int) async throws -> [SuggestedItem] {
        throw api.error.NotImplemented()
    }

    func findWorkUnitsForIntakeQueue(session: Database.Session, user: User, intakeQueueId: Int, query: String) async throws -> [FoundItem] {
        throw api.error.NotImplemented()
    }

}
