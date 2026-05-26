/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import bosslib
import Foundation
import Vapor

/// Register the `/lean/` routes.
public func registerLean(_ app: Application) {
    app.group("lean") { group in

        // MARK: - companies

        group.get("companies") { req in
            let authUser = try req.authUser
            let companies = try await api.lean.companies(user: authUser.user)
            return LeanFragment.List.Companies(companies: companies.map { .init(id: $0.id, name: $0.name) })
        }.openAPI(
            summary: "Get all companies",
            response: .type(LeanFragment.List.Companies.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - company

        group.post("company") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateCompany.self)
            let company = try await api.lean.createCompany(user: authUser.user, name: form.name)
            return LeanFragment.List.Company(id: company.id, name: company.name)
        }.openAPI(
            summary: "Create a company",
            body: .type(LeanForm.CreateCompany.self),
            contentType: .application(.json),
            response: .type(LeanFragment.List.Company.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("company", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let company = try await api.lean.company(user: authUser.user, id: companyId)
            return LeanFragment.Company(id: company.id, name: company.name, userName: "")
        }.openAPI(
            summary: "Get a company",
            response: .type(LeanFragment.Company.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("company", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateCompany.self)
            try await api.lean.updateCompany(user: authUser.user, id: companyId, name: form.name)
            return Fragment.OK()
        }.openAPI(
            summary: "Update a company",
            body: .type(LeanForm.UpdateCompany.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("company", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            try await api.lean.deleteCompany(user: authUser.user, id: companyId)
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a company",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - factories

        group.get("factories", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let factories = try await api.lean.factories(companyId: companyId)
            return LeanFragment.List.Factories(factories: factories.map { .init(id: $0.id, name: $0.name) })
        }.openAPI(
            summary: "Get factories for a company",
            response: .type(LeanFragment.List.Factories.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - factory

        group.post("factory") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateFactory.self)
            let factory = try await api.lean.createFactory(user: authUser.user, companyId: form.companyId, name: form.name)
            return LeanFragment.List.Factory(id: factory.id, name: factory.name)
        }.openAPI(
            summary: "Create a factory",
            body: .type(LeanForm.CreateFactory.self),
            contentType: .application(.json),
            response: .type(LeanFragment.List.Factory.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("factory", ":factoryId") { req in
            let authUser = try req.authUser
            let factoryId = try req.parameters.require("factoryId", as: Int.self)
            let factory = try await api.lean.factory(user: authUser.user, id: factoryId)
            return LeanFragment.Factory(id: factory.id, name: factory.name)
        }.openAPI(
            summary: "Get a factory",
            response: .type(LeanFragment.Factory.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("factory", ":factoryId") { req in
            let authUser = try req.authUser
            let factoryId = try req.parameters.require("factoryId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateFactory.self)
            try await api.lean.updateFactory(user: authUser.user, id: factoryId, name: form.name)
            return Fragment.OK()
        }.openAPI(
            summary: "Update a factory",
            body: .type(LeanForm.UpdateFactory.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("factory", ":factoryId") { req in
            let authUser = try req.authUser
            let factoryId = try req.parameters.require("factoryId", as: Int.self)
            try await api.lean.deleteFactory(user: authUser.user, id: factoryId)
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a factory",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - factory-floor

        group.get("factory-floor", ":factoryId") { req in
            let _ = try req.authUser
            return try loadFixture("Fixtures/Lean/factory-floor.json") as LeanFragment.FactoryFloor
            // let factoryId = try req.parameters.require("factoryId", as: Int.self)
            // TODO: Fetch factory floor data
        }.openAPI(
            summary: "Get factory floor",
            description: "Returns the full factory floor layout including all lines, stations, intake queues, and inventories.",
            response: .type(LeanFragment.FactoryFloor.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - find-agents

        group.get("find-agents", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let q = req.query[String.self, at: "q"] ?? ""
            // TODO: Return agents matching q for company
            _ = companyId
            _ = q
            return try loadFixture("Fixtures/Lean/suggested-agents.json") as [Fragment.Option]
        }.openAPI(
            summary: "Search agents for a company",
            description: "Returns agents (OperatorType.agent) matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - find-intake-queue (line-scoped)

        group.get("find-intake-queue", ":lineId") { req in
            let _ = try req.authUser
            let lineId = try req.parameters.require("lineId", as: Int.self)
            let q = req.query[String.self, at: "q"] ?? ""
            // TODO: Search intake queues for line by term
            _ = lineId
            _ = q
            return try loadFixture("Fixtures/Lean/suggested-intake-queues.json") as [Fragment.Option]
        }.openAPI(
            summary: "Search intake queues for a line",
            description: "Returns intake queues in the line matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - find-intake-queues (company-scoped)

        group.get("find-intake-queues", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let q = req.query[String.self, at: "q"] ?? ""
            // TODO: Return intake queues matching q for company
            _ = companyId
            _ = q
            return try loadFixture("Fixtures/Lean/suggested-intake-queues.json") as [Fragment.Option]
        }.openAPI(
            summary: "Search intake queues for a company",
            description: "Returns intake queues matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - find-inventories

        group.get("find-inventories", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let q = req.query[String.self, at: "q"] ?? ""
            // TODO: Return inventories matching q for company
            _ = companyId
            _ = q
            return try loadFixture("Fixtures/Lean/suggested-inventories.json") as [Fragment.Option]
        }.openAPI(
            summary: "Search inventories for a company",
            description: "Returns inventories matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - find-mime-types

        group.get("find-mime-types") { req in
            let _ = try req.authUser
            let q = req.query[String.self, at: "q"] ?? ""
            // TODO: Return MIME types matching q
            _ = q
            return try loadFixture("Fixtures/Lean/suggested-mime-types.json") as [Fragment.Option]
        }.openAPI(
            summary: "Search MIME types",
            description: "Returns MIME types matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - find-operators

        group.get("find-operators", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let q = req.query[String.self, at: "q"] ?? ""
            // TODO: Return operators matching q for company
            _ = companyId
            _ = q
            return try loadFixture("Fixtures/Lean/suggested-operators.json") as [Fragment.Option]
        }.openAPI(
            summary: "Search operators for a company",
            description: "Returns operators matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - find-supplies

        group.get("find-supplies", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let q = req.query[String.self, at: "q"] ?? ""
            // TODO: Return supplies matching q for company
            _ = companyId
            _ = q
            return try loadFixture("Fixtures/Lean/suggested-supplies.json") as [Fragment.Option]
        }.openAPI(
            summary: "Search supplies for a company",
            description: "Returns supplies matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - find-work-unit

        group.get("find-work-unit", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let q = req.query[String.self, at: "q"] ?? ""
            _ = companyId
            _ = q
            return try loadFixture("Fixtures/Lean/find-work-units.json") as [Fragment.Option]
        }.openAPI(
            summary: "Search work units for a company",
            description: "Returns work units matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - image

        group.post("image") { req in
            let _ = try req.authUser
            // TODO: Save the uploaded image file and return its FileResource id + url.
            // IMPORTANT: Only image MIME types are allowed (e.g. image/png, image/jpeg, image/svg+xml).
            // Reject any non-image file.
            return try loadFixture("Fixtures/Lean/image.json") as LeanFragment.FileResource
        }.openAPI(
            summary: "Upload an image file resource",
            description: "Only image file types are permitted. The uploaded file must have an image MIME type.",
            response: .type(LeanFragment.FileResource.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("image", ":imageId") { req in
            let _ = try req.authUser
            let imageId = try req.parameters.require("imageId", as: Int.self)
            // TODO: Return the image resource by id (image types only)
            _ = imageId
            return try loadFixture("Fixtures/Lean/image.json") as LeanFragment.FileResource
        }.openAPI(
            summary: "Get an image file resource",
            description: "Only image file resources are served.",
            response: .type(LeanFragment.FileResource.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("image", ":imageId") { req in
            let _ = try req.authUser
            let imageId = try req.parameters.require("imageId", as: Int.self)
            // TODO: Delete the image resource (image types only)
            _ = imageId
            return Fragment.OK()
        }.openAPI(
            summary: "Delete an image file resource",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - intake-queue

        group.get("intake-queue", ":intakeQueueId") { req in
            let authUser = try req.authUser
            return try loadFixture("Fixtures/Lean/intake-queue.json") as LeanFragment.IntakeQueue
            /*
            let intakeQueueId = try req.parameters.require("intakeQueueId", as: Int.self)
            let iq = try await api.lean.intakeQueue(user: authUser.user, id: intakeQueueId)
            let mixRatioType = iq.mixRatioType == .fixed ? "fixed" : "distributed"
            let workUnitNameType: String
            let workUnitMaterialName: String?
            switch iq.workUnitName {
            case .material(let name):
                workUnitNameType = "material"
                workUnitMaterialName = name
            case .operatorProvided:
                workUnitNameType = "operatorProvided"
                workUnitMaterialName = nil
            }
            return LeanFragment.IntakeQueue(
                id: iq.id,
                name: iq.name,
                key: iq.key,
                mixRatioType: mixRatioType,
                mixRatio: iq.mixRatio,
                workUnitNameType: workUnitNameType,
                workUnitMaterialName: workUnitMaterialName,
                theme: nil
            )*/
        }.openAPI(
            summary: "Get an intake queue",
            response: .type(LeanFragment.IntakeQueue.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("intake-queue", ":intakeQueueId") { req in
            let _ = try req.authUser
            let intakeQueueId = try req.parameters.require("intakeQueueId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateIntakeQueue.self)
            // TODO: Save intake queue
            _ = intakeQueueId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update an intake queue",
            body: .type(LeanForm.UpdateIntakeQueue.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("intake-queue", "mix-ratio") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateIntakeQueueMixRatio.self)
            try await api.lean.updateIntakeQueueMixRatio(user: authUser.user, id: form.id, mixRatio: form.mixRatio)
            return Fragment.OK()
        }.openAPI(
            summary: "Update intake queue mix ratio",
            body: .type(LeanForm.UpdateIntakeQueueMixRatio.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("intake-queue", "name") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateIntakeQueueName.self)
            try await api.lean.updateIntakeQueueName(user: authUser.user, id: form.id, name: form.name)
            return Fragment.OK()
        }.openAPI(
            summary: "Update intake queue name",
            body: .type(LeanForm.UpdateIntakeQueueName.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - inventory

        group.post("inventory") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateInventory.self)
            let inventory = try await api.lean.createInventory(user: authUser.user, factoryId: form.factoryId, name: form.name)
            return Fragment.Option(id: inventory.id, name: inventory.supply.name)
        }.openAPI(
            summary: "Create an inventory",
            body: .type(LeanForm.CreateInventory.self),
            contentType: .application(.json),
            response: .type(Fragment.Option.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("inventory", ":inventoryId") { req in
            let authUser = try req.authUser
            let inventoryId = try req.parameters.require("inventoryId", as: Int.self)
            let inv = try await api.lean.inventory(user: authUser.user, id: inventoryId)
            return Fragment.Option(id: inv.id, name: inv.supply.name)
        }.openAPI(
            summary: "Get an inventory",
            response: .type(Fragment.Option.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("inventory", ":inventoryId") { req in
            let _ = try req.authUser
            let inventoryId = try req.parameters.require("inventoryId", as: Int.self)
            // TODO: Save inventory
            _ = inventoryId
            return Fragment.OK()
        }.openAPI(
            summary: "Update an inventory",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("inventory", "focused") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateInventoryFocus.self)
            try await api.lean.saveInventoryFocus(user: authUser.user, id: form.id, focused: form.focused)
            return Fragment.OK()
        }.openAPI(
            summary: "Save inventory focus state",
            body: .type(LeanForm.UpdateInventoryFocus.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("inventory", "locked") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateInventoryLocked.self)
            try await api.lean.saveInventoryLocked(user: authUser.user, id: form.id, locked: form.locked)
            return Fragment.OK()
        }.openAPI(
            summary: "Save inventory locked state",
            body: .type(LeanForm.UpdateInventoryLocked.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("inventory", "name") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateInventoryName.self)
            try await api.lean.updateInventoryName(user: authUser.user, id: form.id, name: form.name)
            return Fragment.OK()
        }.openAPI(
            summary: "Update inventory name",
            body: .type(LeanForm.UpdateInventoryName.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("inventory", "position") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateInventoryPosition.self)
            try await api.lean.saveInventoryPosition(user: authUser.user, id: form.id, x: form.gridX, y: form.gridY)
            return Fragment.OK()
        }.openAPI(
            summary: "Save inventory position on factory floor",
            body: .type(LeanForm.UpdateInventoryPosition.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - line

        group.post("line", "name") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateLine.self)
            let line = try await api.lean.createLine(user: authUser.user, factoryId: form.factoryId, name: form.name)
            return Fragment.Option(id: line.id, name: line.name)
        }.openAPI(
            summary: "Create a line (name only)",
            body: .type(LeanForm.CreateLine.self),
            contentType: .application(.json),
            response: .type(Fragment.Option.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("line", ":lineId") { req in
            let _ = try req.authUser
            var lineId = try req.parameters.require("lineId", as: Int.self)
            // TODO: Fetch line from DB
            let availableIds: [Int] = [1, 2]
            if !availableIds.contains(lineId) {
                lineId = 1
            }
            return try loadFixture("Fixtures/Lean/line-\(lineId).json") as LeanFragment.Line
        }.openAPI(
            summary: "Get a line",
            response: .type(LeanFragment.Line.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("line", ":lineId") { req in
            let _ = try req.authUser
            let lineId = try req.parameters.require("lineId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateLine.self)
            // TODO: Update line properties
            _ = lineId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update a line",
            body: .type(LeanForm.UpdateLine.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("line", "focused") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateLineFocus.self)
            try await api.lean.saveLineFocus(user: authUser.user, id: form.id, focused: form.focused)
            return Fragment.OK()
        }.openAPI(
            summary: "Save line focus state",
            body: .type(LeanForm.UpdateLineFocus.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("line", "locked") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateLineLocked.self)
            try await api.lean.saveLineLocked(user: authUser.user, id: form.id, locked: form.locked)
            return Fragment.OK()
        }.openAPI(
            summary: "Save line locked state",
            body: .type(LeanForm.UpdateLineLocked.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("line", "name") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateLineName.self)
            try await api.lean.updateLineName(user: authUser.user, id: form.id, name: form.name)
            return Fragment.OK()
        }.openAPI(
            summary: "Update line name",
            body: .type(LeanForm.UpdateLineName.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("line", "position") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateLinePosition.self)
            try await api.lean.saveLinePosition(user: authUser.user, id: form.id, x: form.gridX, y: form.gridY)
            return Fragment.OK()
        }.openAPI(
            summary: "Save line position on factory floor",
            body: .type(LeanForm.UpdateLinePosition.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("line", ":lineId") { req in
            let _ = try req.authUser
            let lineId = try req.parameters.require("lineId", as: Int.self)
            // TODO: Delete line
            _ = lineId
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a line",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - operation

        group.post("operation") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.CreateOperation.self)
            // TODO: Create operation in DB
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Create an operation",
            body: .type(LeanForm.CreateOperation.self),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("operation", ":operationId") { req in
            let _ = try req.authUser
            let operationId = try req.parameters.require("operationId", as: Int.self)
            // TODO: Fetch operation from DB
            _ = operationId
            return try loadFixture("Fixtures/Lean/operation.json") as LeanFragment.Operation
        }.openAPI(
            summary: "Get an operation",
            response: .type(LeanFragment.Operation.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("operation", ":operationId", "supply-requests") { req in
            let _ = try req.authUser
            let operationId = try req.parameters.require("operationId", as: Int.self)
            // TODO: Fetch supply requests for operation
            _ = operationId
            return try loadFixture("Fixtures/Lean/operation-supply-requests.json") as [Fragment.Option]
        }.openAPI(
            summary: "Get supply requests for an operation",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("operation", ":operationId") { req in
            let _ = try req.authUser
            let operationId = try req.parameters.require("operationId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateOperation.self)
            // TODO: Update operation in DB
            _ = operationId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update an operation",
            body: .type(LeanForm.UpdateOperation.self),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("operation", ":operationId", "supply-request-positions") { req in
            let _ = try req.authUser
            let operationId = try req.parameters.require("operationId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateSupplyRequestPositions.self)
            // TODO: Reorder supply requests for operation
            _ = operationId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Reorder supply requests for an operation",
            body: .type(LeanForm.UpdateSupplyRequestPositions.self),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("operation", ":operationId") { req in
            let _ = try req.authUser
            let operationId = try req.parameters.require("operationId", as: Int.self)
            // TODO: Delete operation from DB
            _ = operationId
            return Fragment.OK()
        }.openAPI(
            summary: "Delete an operation",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - operator

        group.post("operator") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.CreateOperator.self)
            // TODO: Create operator
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Create an operator",
            body: .type(LeanForm.CreateOperator.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("operator", ":operatorId") { req in
            let _ = try req.authUser
            var operatorId = try req.parameters.require("operatorId", as: Int.self)
            // TODO: Load operator from DB
            if operatorId < 1 || operatorId > 1 {
                operatorId = 1
            }
            return try loadFixture("Fixtures/Lean/operator-\(operatorId).json") as LeanFragment.Operator
        }.openAPI(
            summary: "Get an operator",
            response: .type(LeanFragment.Operator.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("operator", ":operatorId") { req in
            let _ = try req.authUser
            let operatorId = try req.parameters.require("operatorId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateOperator.self)
            // TODO: Update operator
            _ = operatorId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update an operator",
            body: .type(LeanForm.UpdateOperator.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("operator", ":operatorId") { req in
            let _ = try req.authUser
            let operatorId = try req.parameters.require("operatorId", as: Int.self)
            // TODO: Delete operator
            _ = operatorId
            return Fragment.OK()
        }.openAPI(
            summary: "Delete an operator",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - start-work-unit

        group.post("start-work-unit") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.StartWorkUnit.self)
            // TODO: Start the work unit and move it to the first station
            _ = form
            return LeanFragment.StartWorkUnitResponse(
                nextWorkUnit: .init(id: 9999, key: "FR-9999", name: "Next work unit", companyId: 1, intakeQueueId: nil, eta: nil, creator: .init(id: "5", name: "Eric Chamberlain"), reporter: nil, assignees: [], parentWorkUnit: nil, intakeQueueState: nil, stationState: nil, outputState: nil, onHold: false, onHoldElapsed: nil, logs: [], comments: [], children: [])
            )
        }.openAPI(
            summary: "Start a work unit",
            description: "Moves the work unit to the first station in the line. Returns the next work unit waiting in the intake queue, if any.",
            body: .type(LeanForm.StartWorkUnit.self),
            contentType: .application(.json),
            response: .type(LeanFragment.StartWorkUnitResponse.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - station

        group.get("station", ":stationId") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            // TODO: Fetch station
            _ = stationId
            return try loadFixture("Fixtures/Lean/station-1.json") as LeanFragment.Station
        }.openAPI(
            summary: "Get a station",
            response: .type(LeanFragment.Station.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("station", ":stationId", "notification-triggers") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            // TODO: Fetch notification triggers for station
            _ = stationId
            return try loadFixture("Fixtures/Lean/station-notification-triggers.json") as [Fragment.Option]
        }.openAPI(
            summary: "Get notification triggers for a station",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("station", ":stationId", "operations") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            // TODO: Fetch operations for station
            _ = stationId
            return try loadFixture("Fixtures/Lean/station-operations.json") as [Fragment.Option]
        }.openAPI(
            summary: "Get operations for a station",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("station", ":stationId", "work-units") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            // TODO: Fetch work units for station
            _ = stationId
            return try loadFixture("Fixtures/Lean/station-work-units.json") as LeanFragment.WorkUnits
        }.openAPI(
            summary: "Get work units for a station",
            response: .type(LeanFragment.WorkUnits.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("station", ":stationId") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateStation.self)
            // TODO: Save station
            _ = stationId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update a station",
            body: .type(LeanForm.UpdateStation.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("station", ":stationId", "type", "intake-queue") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateStationTypeIntakeQueue.self)
            // TODO: Update station type to intakeQueue
            _ = stationId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Set station type to intake queue",
            description: "Links the station to a specific intake queue and changes its type to `intakeQueue`.",
            body: .type(LeanForm.UpdateStationTypeIntakeQueue.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("station", ":stationId", "type", "station") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            // TODO: Update station type to station
            _ = stationId
            return Fragment.OK()
        }.openAPI(
            summary: "Set station type to station",
            description: "Removes any linked intake queue and changes the station type back to `station`.",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("station", "name") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateStationName.self)
            // TODO: Update station name
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update station name",
            body: .type(LeanForm.UpdateStationName.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("station", ":stationId", "operation-positions") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateOperationPositions.self)
            // TODO: Reorder operations for station
            _ = stationId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Reorder operations for a station",
            body: .type(LeanForm.UpdateOperationPositions.self),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("station", ":stationId") { req in
            let _ = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            // TODO: Delete station
            _ = stationId
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a station",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - station-notification-trigger

        group.post("station-notification-trigger") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.CreateStationNotificationTrigger.self)
            // TODO: Create notification trigger in DB
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Create a station notification trigger",
            body: .type(LeanForm.CreateStationNotificationTrigger.self),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("station-notification-trigger", ":triggerId") { req in
            let _ = try req.authUser
            let triggerId = try req.parameters.require("triggerId", as: Int.self)
            // TODO: Fetch notification trigger from DB
            _ = triggerId
            return try loadFixture("Fixtures/Lean/station-notification-trigger.json") as LeanFragment.StationNotificationTrigger
        }.openAPI(
            summary: "Get a station notification trigger",
            response: .type(LeanFragment.StationNotificationTrigger.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("station-notification-trigger", ":triggerId") { req in
            let _ = try req.authUser
            let triggerId = try req.parameters.require("triggerId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateStationNotificationTrigger.self)
            // TODO: Update notification trigger in DB
            _ = triggerId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update a station notification trigger",
            body: .type(LeanForm.UpdateStationNotificationTrigger.self),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("station-notification-trigger", ":triggerId") { req in
            let _ = try req.authUser
            let triggerId = try req.parameters.require("triggerId", as: Int.self)
            // TODO: Delete notification trigger from DB
            _ = triggerId
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a station notification trigger",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - suggested-agents

        group.get("suggested-agents", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            // TODO: Return suggested agents (OperatorType.agent) for company
            _ = companyId
            return try loadFixture("Fixtures/Lean/suggested-agents.json") as [Fragment.Option]
        }.openAPI(
            summary: "Get suggested agents for a company",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - suggested-intake-queue (line-scoped)

        group.get("suggested-intake-queue", ":lineId") { req in
            let _ = try req.authUser
            let lineId = try req.parameters.require("lineId", as: Int.self)
            // TODO: Fetch suggested intake queues for line
            _ = lineId
            return try loadFixture("Fixtures/Lean/suggested-intake-queues.json") as [Fragment.Option]
        }.openAPI(
            summary: "Get suggested intake queues for a line",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - suggested-intake-queues (company-scoped)

        group.get("suggested-intake-queues", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            // TODO: Return suggested intake queues for company
            _ = companyId
            return try loadFixture("Fixtures/Lean/suggested-intake-queues.json") as [Fragment.Option]
        }.openAPI(
            summary: "Get suggested intake queues for a company",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - suggested-inventories

        group.get("suggested-inventories", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            // TODO: Return suggested inventories for company
            _ = companyId
            return try loadFixture("Fixtures/Lean/suggested-inventories.json") as [Fragment.Option]
        }.openAPI(
            summary: "Get suggested inventories for a company",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - suggested-mime-types

        group.get("suggested-mime-types") { req in
            let _ = try req.authUser
            return try loadFixture("Fixtures/Lean/suggested-mime-types.json") as [Fragment.Option]
        }.openAPI(
            summary: "Get suggested MIME types",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - suggested-operators

        group.get("suggested-operators", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            // TODO: Return suggested operators for company
            _ = companyId
            return try loadFixture("Fixtures/Lean/suggested-operators.json") as [Fragment.Option]
        }.openAPI(
            summary: "Get suggested operators for a company",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - suggested-supplies

        group.get("suggested-supplies", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            // TODO: Return suggested supplies for company
            _ = companyId
            return try loadFixture("Fixtures/Lean/suggested-supplies.json") as [Fragment.Option]
        }.openAPI(
            summary: "Get suggested supplies for a company",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - suggested-work-unit

        group.get("suggested-work-unit", ":companyId") { req in
            let _ = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            _ = companyId
            return try loadFixture("Fixtures/Lean/find-work-units.json") as [Fragment.Option]
        }.openAPI(
            summary: "Get suggested work units for a company",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - supply

        group.get("supply", ":supplyId", "fields") { req in
            let _ = try req.authUser
            let supplyId = try req.parameters.require("supplyId", as: Int.self)
            // TODO: Fetch fields for supply
            _ = supplyId
            return try loadFixture("Fixtures/Lean/supply-fields.json") as [Fragment.Option]
        }.openAPI(
            summary: "Get supply fields for a supply",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("supply", ":supplyId", "field-positions") { req in
            let _ = try req.authUser
            let supplyId = try req.parameters.require("supplyId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateSupplyFieldPositions.self)
            // TODO: Reorder supply fields for supply
            _ = supplyId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Reorder supply fields for a supply",
            body: .type(LeanForm.UpdateSupplyFieldPositions.self),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - supply-field

        group.post("supply-field") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.CreateSupplyField.self)
            // TODO: Create supply field in DB
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Create a supply field",
            body: .type(LeanForm.CreateSupplyField.self),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("supply-field", ":supplyFieldId") { req in
            let _ = try req.authUser
            let supplyFieldId = try req.parameters.require("supplyFieldId", as: Int.self)
            // Return different fixture based on ID: 1=text, 2=file, 3=radio, 4=workUnit
            switch supplyFieldId {
            case 1, 2, 3, 4:
                return try loadFixture("Fixtures/Lean/supply-field-\(supplyFieldId).json") as LeanFragment.SupplyField
            default:
                return try loadFixture("Fixtures/Lean/supply-field-1.json") as LeanFragment.SupplyField
            }
        }.openAPI(
            summary: "Get a supply field",
            response: .type(LeanFragment.SupplyField.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("supply-field", ":supplyFieldId", "options") { req in
            let _ = try req.authUser
            let supplyFieldId = try req.parameters.require("supplyFieldId", as: Int.self)
            // TODO: Return options for the given supply field
            _ = supplyFieldId
            return try loadFixture("Fixtures/Lean/supply-field-options.json") as [Fragment.Option]
        }.openAPI(
            summary: "Get supply field options for a supply field",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("supply-field", ":supplyFieldId") { req in
            let _ = try req.authUser
            let supplyFieldId = try req.parameters.require("supplyFieldId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateSupplyField.self)
            // TODO: Update supply field
            _ = supplyFieldId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update a supply field",
            body: .type(LeanForm.UpdateSupplyField.self),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("supply-field", ":supplyFieldId") { req in
            let _ = try req.authUser
            let supplyFieldId = try req.parameters.require("supplyFieldId", as: Int.self)
            // TODO: Delete supply field
            _ = supplyFieldId
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a supply field",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - supply-field-option

        group.post("supply-field-option") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.CreateSupplyFieldOption.self)
            // TODO: Create supply field option
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Create a supply field option",
            body: .type(LeanForm.CreateSupplyFieldOption.self),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("supply-field-option", ":supplyFieldOptionId") { req in
            let _ = try req.authUser
            let supplyFieldOptionId = try req.parameters.require("supplyFieldOptionId", as: Int.self)
            // TODO: Return the specific option (use fixture based on ID if needed)
            _ = supplyFieldOptionId
            return try loadFixture("Fixtures/Lean/supply-field-option-1.json") as LeanFragment.SupplyFieldOption
        }.openAPI(
            summary: "Get a supply field option",
            response: .type(LeanFragment.SupplyFieldOption.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("supply-field-option", ":supplyFieldOptionId") { req in
            let _ = try req.authUser
            let supplyFieldOptionId = try req.parameters.require("supplyFieldOptionId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateSupplyFieldOption.self)
            // TODO: Update supply field option
            _ = supplyFieldOptionId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update a supply field option",
            body: .type(LeanForm.UpdateSupplyFieldOption.self),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("supply-field-option", ":supplyFieldOptionId") { req in
            let _ = try req.authUser
            let supplyFieldOptionId = try req.parameters.require("supplyFieldOptionId", as: Int.self)
            // TODO: Delete supply field option
            _ = supplyFieldOptionId
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a supply field option",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - supply-request

        group.post("supply-request") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.CreateSupplyRequest.self)
            // TODO: Create supply request in DB
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Create a supply request",
            body: .type(LeanForm.CreateSupplyRequest.self),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("supply-request", ":type", "operation", ":operationId") { req in
            let _ = try req.authUser
            let supplyRequestType = try req.parameters.require("type", as: String.self)
            let operationId = try req.parameters.require("operationId", as: Int.self)
            // TODO: Fetch supply request by type+operationId
            _ = supplyRequestType
            _ = operationId
            return try loadFixture("Fixtures/Lean/supply-request.json") as LeanFragment.SupplyRequest
        }.openAPI(
            summary: "Get a supply request",
            response: .type(LeanFragment.SupplyRequest.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("supply-request", ":type", "operation", ":operationId") { req in
            let _ = try req.authUser
            let supplyRequestType = try req.parameters.require("type", as: String.self)
            let operationId = try req.parameters.require("operationId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateSupplyRequest.self)
            // TODO: Update supply request
            _ = supplyRequestType
            _ = operationId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update a supply request",
            body: .type(LeanForm.UpdateSupplyRequest.self),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("supply-request", ":type", "operation", ":operationId") { req in
            let _ = try req.authUser
            let supplyRequestType = try req.parameters.require("type", as: String.self)
            let operationId = try req.parameters.require("operationId", as: Int.self)
            // TODO: Delete supply request
            _ = supplyRequestType
            _ = operationId
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a supply request",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - work-unit

        group.post("work-unit", "child") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.AddWorkUnitChild.self)
            // TODO: Add child work unit relationship
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Add a child work unit",
            body: .type(LeanForm.AddWorkUnitChild.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.post("work-unit", "hold", ":workUnitId") { req in
            let _ = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            // TODO: Place work unit on hold (create WorkUnitLog with LineState.onHold)
            _ = workUnitId
            return Fragment.OK()
        }.openAPI(
            summary: "Place a work unit on hold",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("work-unit", ":workUnitId") { req in
            let _ = try req.authUser
            var workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let availableIds: [Int] = [1, 2]
            if !availableIds.contains(workUnitId) {
                boss.log.i("Invalid WorkUnit.id (\(workUnitId)")
                workUnitId = 1
            }
            return try loadFixture("Fixtures/Lean/work-unit-\(workUnitId).json") as LeanFragment.WorkUnit
        }.openAPI(
            summary: "Get a work unit",
            response: .type(LeanFragment.WorkUnit.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("work-unit", "children", ":workUnitId") { req in
            let _ = try req.authUser
            var workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            // TODO: Load children from DB
            if workUnitId < 1 || workUnitId > 2 {
                workUnitId = 1
            }
            return try loadFixture("Fixtures/Lean/work-unit-children-\(workUnitId).json") as [LeanFragment.WorkUnit.Child]
        }.openAPI(
            summary: "Get children of a work unit",
            response: .type([LeanFragment.WorkUnit.Child].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("work-unit", ":workUnitId") { req in
            let _ = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateWorkUnit.self)
            // TODO: Save work unit
            _ = workUnitId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update a work unit",
            body: .type(LeanForm.UpdateWorkUnit.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("work-unit", "assignees", ":workUnitId") { req in
            let _ = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateWorkUnitAssignees.self)
            // TODO: Save work unit assignees
            _ = workUnitId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update work unit assignees",
            description: "Replaces the full list of assignees. Send an empty array to remove all assignees.",
            body: .type(LeanForm.UpdateWorkUnitAssignees.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("work-unit", "parent", ":workUnitId") { req in
            let _ = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateWorkUnitParent.self)
            // TODO: Save work unit parent
            _ = workUnitId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update work unit parent",
            description: "Sets or clears the parent work unit. Send `null` for `parentWorkUnitId` to clear.",
            body: .type(LeanForm.UpdateWorkUnitParent.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("work-unit", "reporter", ":workUnitId") { req in
            let _ = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateWorkUnitReporter.self)
            // TODO: Save work unit reporter
            _ = workUnitId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update work unit reporter",
            description: "Sets or clears the reporter on a work unit. Send `null` for `operatorId` to clear.",
            body: .type(LeanForm.UpdateWorkUnitReporter.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("work-unit", ":workUnitId") { req in
            let _ = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            // TODO: Delete work unit
            _ = workUnitId
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a work unit",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("work-unit", "child", ":workUnitId", ":childWorkUnitId") { req in
            let _ = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let childWorkUnitId = try req.parameters.require("childWorkUnitId", as: Int.self)
            // TODO: Remove child work unit relationship
            _ = workUnitId
            _ = childWorkUnitId
            return Fragment.OK()
        }.openAPI(
            summary: "Remove a child work unit",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("work-unit", "hold", ":workUnitId") { req in
            let _ = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let form = try req.content.decode(LeanForm.ClearWorkUnitHold.self)
            // TODO: Clear work unit hold
            _ = workUnitId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Clear a work unit hold",
            body: .type(LeanForm.ClearWorkUnitHold.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - work-unit-comment

        group.post("work-unit-comment") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.CreateWorkUnitComment.self)
            // TODO: Create work unit comment
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Add a comment to a work unit",
            body: .type(LeanForm.CreateWorkUnitComment.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("work-unit-comment", ":commentId") { req in
            let _ = try req.authUser
            let commentId = try req.parameters.require("commentId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateWorkUnitComment.self)
            // TODO: Update work unit comment
            _ = commentId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update a work unit comment",
            body: .type(LeanForm.UpdateWorkUnitComment.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("work-unit-comment", ":commentId") { req in
            let _ = try req.authUser
            let commentId = try req.parameters.require("commentId", as: Int.self)
            // TODO: Delete work unit comment
            _ = commentId
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a work unit comment",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - work-unit-position

        group.patch("work-unit-position") { req in
            let _ = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateWorkUnitPosition.self)
            // TODO: Save work unit position
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Save work unit position in intake queue",
            body: .type(LeanForm.UpdateWorkUnitPosition.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - work-units

        group.get("work-units", ":intakeQueueId") { req in
            let _ = try req.authUser
            return try loadFixture("Fixtures/Lean/work-units.json") as LeanFragment.WorkUnits
        }.openAPI(
            summary: "Get work units for an intake queue",
            response: .type(LeanFragment.WorkUnits.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("work-units", ":intakeQueueId") { req in
            let _ = try req.authUser
            let intakeQueueId = try req.parameters.require("intakeQueueId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateWorkUnits.self)
            // TODO: Save intake queue from work units view
            _ = intakeQueueId
            _ = form
            return Fragment.OK()
        }.openAPI(
            summary: "Update intake queue settings from the work units view",
            body: .type(LeanForm.UpdateWorkUnits.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)
    }
}
