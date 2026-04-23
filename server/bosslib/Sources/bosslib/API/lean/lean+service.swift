/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import Foundation
internal import SQLiteKit

struct LeanService: LeanProvider {
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
            hopper: Hopper(id: hopperId, lineId: lineId, workUnit: nil),
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
            .columns("id", "factory_id", "supply_id", "in_stock", "reorder_point", "estimated_reorder_point")
            .values(
                SQLLiteral.null,
                SQLBind(factoryId),
                SQLBind(supplyId),
                SQLBind(0),         // in_stock
                SQLBind(0),         // reorder_point
                SQLBind(Date.now)   // estimated_reorder_point
            )
            .returning("id")
            .all()

        let inventoryId = try inventoryRows[0].decode(column: "id", as: Inventory.ID.self)
        let supply = Supply(id: supplyId, name: name, theme: nil, fields: nil, amount: nil)

        return Inventory(
            id: inventoryId,
            provider: [],
            supply: supply,
            inStock: 0,
            reorderPoint: 0,
            estimatedReorderPoint: Date.now
        )
    }
}
