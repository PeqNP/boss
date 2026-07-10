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
            return LeanFragment.Company(id: companyId, name: form.name ?? "Test", userName: "")
        }.openAPI(
            summary: "Update a company",
            body: .type(LeanForm.UpdateCompany.self),
            contentType: .application(.json),
            response: .type(LeanFragment.Company.self),
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
            return LeanFragment.Factory(id: factoryId, name: form.name ?? "Test")
        }.openAPI(
            summary: "Update a factory",
            body: .type(LeanForm.UpdateFactory.self),
            contentType: .application(.json),
            response: .type(LeanFragment.Factory.self),
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
            let authUser = try req.authUser
            let factoryId = try req.parameters.require("factoryId", as: Int.self)
            let floor = try await api.lean.factoryFloor(user: authUser.user, factoryId: factoryId)
            let factory = try await api.lean.factory(user: authUser.user, id: factoryId)
            // return try loadFixture("Fixtures/Lean/factory-floor.json") as LeanFragment.FactoryFloor
            return makeFactoryFloorFragment(factory: factory, floor: floor)
        }.openAPI(
            summary: "Get factory floor",
            description: "Returns the full factory floor layout including all lines, stations, intake queues, and inventories.",
            response: .type(LeanFragment.FactoryFloor.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - find-agents

        group.get("find-agents", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let q = req.query[String.self, at: "q"] ?? ""
            let items = try await api.lean.findAgents(user: authUser.user, companyId: companyId, query: q)
            // return try loadFixture("Fixtures/Lean/suggested-agents.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Search agents for a company",
            description: "Returns agents (OperatorType.agent) matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - find-intake-queue (line-scoped)

        group.get("find-intake-queue", ":lineId") { req in
            let authUser = try req.authUser
            let lineId = try req.parameters.require("lineId", as: Int.self)
            let q = req.query[String.self, at: "q"] ?? ""
            let items = try await api.lean.findIntakeQueue(user: authUser.user, lineId: lineId, query: q)
            // return try loadFixture("Fixtures/Lean/suggested-intake-queues.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Search intake queues for a line",
            description: "Returns intake queues in the line matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - find-intake-queues (company-scoped)

        group.get("find-intake-queues", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let q = req.query[String.self, at: "q"] ?? ""
            let items = try await api.lean.findIntakeQueues(user: authUser.user, companyId: companyId, query: q)
            // return try loadFixture("Fixtures/Lean/suggested-intake-queues.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Search intake queues for a company",
            description: "Returns intake queues matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - find-inventories

        group.get("find-inventories", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let q = req.query[String.self, at: "q"] ?? ""
            let items = try await api.lean.findInventories(user: authUser.user, companyId: companyId, query: q)
            // return try loadFixture("Fixtures/Lean/suggested-inventories.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Search inventories for a company",
            description: "Returns inventories matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - find-mime-types

        group.get("find-mime-types") { req in
            let authUser = try req.authUser
            let q = req.query[String.self, at: "q"] ?? ""
            let items = try await api.lean.findMimeTypes(user: authUser.user, query: q)
            // return try loadFixture("Fixtures/Lean/suggested-mime-types.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Search MIME types",
            description: "Returns MIME types matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - find-operators

        group.get("find-operators", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let q = req.query[String.self, at: "q"] ?? ""
            let items = try await api.lean.findOperators(user: authUser.user, companyId: companyId, query: q)
            // return try loadFixture("Fixtures/Lean/suggested-operators.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Search operators for a company",
            description: "Returns operators matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - find-supplies

        group.get("find-supplies", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let q = req.query[String.self, at: "q"] ?? ""
            let items = try await api.lean.findSupplies(user: authUser.user, companyId: companyId, query: q)
            // return try loadFixture("Fixtures/Lean/suggested-supplies.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Search supplies for a company",
            description: "Returns supplies matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - find-work-unit

        group.get("find-work-unit", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let q = req.query[String.self, at: "q"] ?? ""
            let items = try await api.lean.findWorkUnit(user: authUser.user, companyId: companyId, query: q)
            // return try loadFixture("Fixtures/Lean/find-work-units.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Search work units for a company",
            description: "Returns work units matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - image

        group.post("image") { req in
            let authUser = try req.authUser
            let image = try await api.lean.saveImage(user: authUser.user)
            // return try loadFixture("Fixtures/Lean/image.json") as LeanFragment.FileResource
            return makeFileResource(image)
        }.openAPI(
            summary: "Upload an image file resource",
            description: "Only image file types are permitted. The uploaded file must have an image MIME type.",
            response: .type(LeanFragment.FileResource.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("image", ":imageId") { req in
            let authUser = try req.authUser
            let imageId = try req.parameters.require("imageId", as: Int.self)
            let image = try await api.lean.image(user: authUser.user, imageId: imageId)
            // return try loadFixture("Fixtures/Lean/image.json") as LeanFragment.FileResource
            return makeFileResource(image)
        }.openAPI(
            summary: "Get an image file resource",
            description: "Only image file resources are served.",
            response: .type(LeanFragment.FileResource.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("image", ":imageId") { req in
            let authUser = try req.authUser
            let imageId = try req.parameters.require("imageId", as: Int.self)
            try await api.lean.deleteImage(user: authUser.user, imageId: imageId)
            return Fragment.OK()
        }.openAPI(
            summary: "Delete an image file resource",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - intake-queue

        group.post("intake-queue") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateIntakeQueue.self)
            let intakeQueue = try await api.lean.createIntakeQueue(user: authUser.user, lineId: form.lineId, name: form.name)
            return makeOption(intakeQueue)
        }.openAPI(
            summary: "Create an intake queue",
            body: .type(LeanForm.CreateIntakeQueue.self),
            contentType: .application(.json),
            response: .type(Fragment.Option.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("intake-queue", ":intakeQueueId") { req in
            let authUser = try req.authUser
            let intakeQueueId = try req.parameters.require("intakeQueueId", as: Int.self)
            let iq = try await api.lean.intakeQueue(user: authUser.user, id: intakeQueueId)
            // return try loadFixture("Fixtures/Lean/intake-queue.json") as LeanFragment.IntakeQueue
            return makeIntakeQueueFragment(iq)
        }.openAPI(
            summary: "Get an intake queue",
            response: .type(LeanFragment.IntakeQueue.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("intake-queue", ":intakeQueueId") { req in
            let authUser = try req.authUser
            let intakeQueueId = try req.parameters.require("intakeQueueId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateIntakeQueue.self)
            try await api.lean.saveIntakeQueue(
                user: authUser.user,
                intakeQueueId: intakeQueueId,
                name: form.name,
                key: form.key,
                mixRatioType: form.mixRatioType,
                mixRatio: form.mixRatio,
                workUnitNameType: form.workUnitNameType,
                workUnitMaterialName: form.workUnitMaterialName,
                theme: form.theme?.makeTheme()
            )
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
            return LeanFragment.Inventory(id: inv.id, name: inv.supply.name)
        }.openAPI(
            summary: "Get an inventory",
            response: .type(LeanFragment.Inventory.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("inventory", ":inventoryId") { req in
            let authUser = try req.authUser
            let inventoryId = try req.parameters.require("inventoryId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateInventory.self)
            try await api.lean.saveInventory(user: authUser.user, inventoryId: inventoryId, name: form.name)
            return Fragment.OK()
        }.openAPI(
            summary: "Update an inventory",
            body: .type(LeanForm.UpdateInventory.self),
            contentType: .application(.json),
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

        group.post("line") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateLine.self)
            let line = try await api.lean.createLine(user: authUser.user, factoryId: form.factoryId, name: form.name)
            return Fragment.Option(id: line.id, name: line.name)
        }.openAPI(
            summary: "Create a line",
            body: .type(LeanForm.CreateLine.self),
            contentType: .application(.json),
            response: .type(Fragment.Option.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

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
            let authUser = try req.authUser
            let lineId = try req.parameters.require("lineId", as: Int.self)
            let line = try await api.lean.line(user: authUser.user, lineId: lineId)
            // return try loadFixture("Fixtures/Lean/line-\(lineId).json") as LeanFragment.Line
            return makeLineFragment(line)
        }.openAPI(
            summary: "Get a line",
            response: .type(LeanFragment.Line.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("line", ":lineId") { req in
            let authUser = try req.authUser
            let lineId = try req.parameters.require("lineId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateLine.self)
            let line = try await api.lean.saveLine(user: authUser.user, lineId: lineId, name: form.name, hasOutput: form.hasOutput, subAssemblyLine: form.subAssemblyLine)
            // return try loadFixture("Fixtures/Lean/line-1.json") as LeanFragment.Line
            return makeLineFragment(line)
        }.openAPI(
            summary: "Update a line",
            body: .type(LeanForm.UpdateLine.self),
            contentType: .application(.json),
            response: .type(LeanFragment.Line.self),
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
            let authUser = try req.authUser
            let lineId = try req.parameters.require("lineId", as: Int.self)
            try await api.lean.deleteLine(user: authUser.user, lineId: lineId)
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a line",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - operation

        group.post("operation") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateOperation.self)
            let operation = try await api.lean.createOperation(
                user: authUser.user,
                stationId: form.stationId,
                name: form.name,
                agentId: form.agentId,
                supplyRequestType: form.supplyRequestType,
                inventoryId: form.inventoryId,
                amount: form.amount,
                supplyId: form.supplyId,
                intakeQueueId: form.intakeQueueId
            )
            // return try loadFixture("Fixtures/Lean/operation.json") as LeanFragment.Operation
            return makeOperationFragment(operation)
        }.openAPI(
            summary: "Create an operation",
            body: .type(LeanForm.CreateOperation.self),
            response: .type(LeanFragment.Operation.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("operation", ":operationId") { req in
            let authUser = try req.authUser
            let operationId = try req.parameters.require("operationId", as: Int.self)
            let operation = try await api.lean.operation(user: authUser.user, operationId: operationId)
            // return try loadFixture("Fixtures/Lean/operation.json") as LeanFragment.Operation
            return makeOperationFragment(operation)
        }.openAPI(
            summary: "Get an operation",
            response: .type(LeanFragment.Operation.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("operation", ":operationId") { req in
            let authUser = try req.authUser
            let operationId = try req.parameters.require("operationId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateOperation.self)
            let operation = try await api.lean.saveOperation(
                user: authUser.user,
                operationId: operationId,
                name: form.name,
                instructions: form.instructions,
                agentId: form.agentId,
                supplyRequestType: form.supplyRequestType,
                inventoryId: form.inventoryId,
                amount: form.amount,
                supplyId: form.supplyId,
                intakeQueueId: form.intakeQueueId
            )
            // return try loadFixture("Fixtures/Lean/operation.json") as LeanFragment.Operation
            return makeOperationFragment(operation)
        }.openAPI(
            summary: "Update an operation",
            body: .type(LeanForm.UpdateOperation.self),
            response: .type(LeanFragment.Operation.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("operation", ":operationId") { req in
            let authUser = try req.authUser
            let operationId = try req.parameters.require("operationId", as: Int.self)
            try await api.lean.deleteOperation(user: authUser.user, operationId: operationId)
            return Fragment.OK()
        }.openAPI(
            summary: "Delete an operation",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - operator

        group.post("operator") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateOperator.self)
            try await api.lean.createOperator(user: authUser.user, userId: form.userId, agentId: form.agentId)
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
            let authUser = try req.authUser
            let operatorId = try req.parameters.require("operatorId", as: Int.self)
            let value = try await api.lean.operator(user: authUser.user, operatorId: operatorId)
            // return try loadFixture("Fixtures/Lean/operator-\(operatorId).json") as LeanFragment.Operator
            return makeOperatorFragment(value)
        }.openAPI(
            summary: "Get an operator",
            response: .type(LeanFragment.Operator.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("operator", ":operatorId") { req in
            let authUser = try req.authUser
            let operatorId = try req.parameters.require("operatorId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateOperator.self)
            try await api.lean.saveOperator(user: authUser.user, operatorId: operatorId, userId: form.userId, agentId: form.agentId)
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
            let authUser = try req.authUser
            let operatorId = try req.parameters.require("operatorId", as: Int.self)
            try await api.lean.deleteOperator(user: authUser.user, operatorId: operatorId)
            return Fragment.OK()
        }.openAPI(
            summary: "Delete an operator",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - start-work-unit

        group.post("start-work-unit") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.StartWorkUnit.self)
            let workUnit = try await api.lean.startWorkUnit(user: authUser.user, workUnitId: form.id)
            return makeWorkUnitFragment(workUnit)
        }.openAPI(
            summary: "Start a work unit",
            description: "Moves the work unit to the first station in the line and returns the updated work unit.",
            body: .type(LeanForm.StartWorkUnit.self),
            contentType: .application(.json),
            response: .type(LeanFragment.WorkUnit.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - station

        group.post("station") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateStation.self)
            // Position shift rules (form.index):
            //   nil → append: new station placed at last.exit_pos; no cascading.
            //   k (1-based) → insert at k:
            //     Free-cell shortcut: if the cell one step in the first-leg direction
            //     from station[k-1] is unoccupied, place the new station there with no
            //     cascading. First-leg direction is y-axis when Δy ≠ 0 (belt turns
            //     vertically first), otherwise x-axis.
            //     Full cascade (when no free cell): new station takes station[k-1].pos;
            //     stations[k-1..last] each inherit successor's pos;
            //     last station moves in exit direction (right default, left if prev.posX > last.posX).
            //   If exit dir moves posX < 0: try posY+1 (down), then posY-1 (up).
            let station = try await api.lean.createStation(user: authUser.user, lineId: form.lineId, name: form.name, index: form.index)
            // return try loadFixture("Fixtures/Lean/station-1.json") as LeanFragment.Station
            return try await makeStationFragment(user: authUser.user, station: station)
        }.openAPI(
            summary: "Create a station",
            body: .type(LeanForm.CreateStation.self),
            contentType: .application(.json),
            response: .type(LeanFragment.Station.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("station", ":stationId") { req in
            let authUser = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            let station = try await api.lean.station(user: authUser.user, stationId: stationId)
            // return try loadFixture("Fixtures/Lean/station-\(stationId).json") as LeanFragment.Station
            return try await makeStationFragment(user: authUser.user, station: station)
        }.openAPI(
            summary: "Get a station",
            response: .type(LeanFragment.Station.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("station", ":stationId", "notification-triggers") { req in
            let authUser = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            let items = try await api.lean.stationNotificationTriggers(user: authUser.user, stationId: stationId)
            // return try loadFixture("Fixtures/Lean/station-notification-triggers.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Get notification triggers for a station",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("station", ":stationId", "operations") { req in
            let authUser = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            let items = try await api.lean.stationOperations(user: authUser.user, stationId: stationId)
            // return try loadFixture("Fixtures/Lean/station-operations.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Get operations for a station",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("station", ":stationId", "work-units") { req in
            let authUser = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            let workUnits = try await api.lean.stationWorkUnits(user: authUser.user, stationId: stationId)
            // return try loadFixture("Fixtures/Lean/station-work-units.json") as LeanFragment.WorkUnits
            return LeanFragment.WorkUnits(id: stationId, name: "Station \(stationId)", key: nil, workUnits: workUnits.map { $0.makeWorkUnitOption() })
        }.openAPI(
            summary: "Get work units for a station",
            response: .type(LeanFragment.WorkUnits.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("station", ":stationId") { req in
            let authUser = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateStation.self)
            let station = try await api.lean.saveStation(
                user: authUser.user,
                stationId: stationId,
                name: form.name,
                assigneeAction: form.assigneeAction,
                assigneeIds: form.assigneeIds,
                theme: form.theme?.makeTheme()
            )
            // return try loadFixture("Fixtures/Lean/station-1.json") as LeanFragment.Station
            return try await makeStationFragment(user: authUser.user, station: station)
        }.openAPI(
            summary: "Update a station",
            body: .type(LeanForm.UpdateStation.self),
            contentType: .application(.json),
            response: .type(LeanFragment.Station.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("station", ":stationId", "type", "intake-queue") { req in
            let authUser = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateStationTypeIntakeQueue.self)
            try await api.lean.saveStationTypeIntakeQueue(user: authUser.user, stationId: stationId, intakeQueueId: form.intakeQueueId)
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
            let authUser = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            try await api.lean.saveStationTypeStation(user: authUser.user, stationId: stationId)
            return Fragment.OK()
        }.openAPI(
            summary: "Set station type to station",
            description: "Removes any linked intake queue and changes the station type back to `station`.",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("station", "name") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateStationName.self)
            try await api.lean.saveStationName(user: authUser.user, stationId: form.id, name: form.name)
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
            let authUser = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateOperationPositions.self)
            try await api.lean.saveStationOperationPositions(user: authUser.user, stationId: stationId, position: form.position, operationIds: form.operationIds)
            return Fragment.OK()
        }.openAPI(
            summary: "Reorder operations for a station",
            body: .type(LeanForm.UpdateOperationPositions.self),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("station", "view-state", ":stationId") { req in
            let authUser = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateStationViewState.self)
            try await api.lean.saveStationViewState(user: authUser.user, stationId: stationId, overlay: form.overlay)
            return Fragment.OK()
        }.openAPI(
            summary: "Save the station overlay view state",
            description: "Persists which overlay (work units, operations, or none) is open for this station on the factory floor.",
            body: .type(LeanForm.UpdateStationViewState.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("station", ":stationId") { req in
            let authUser = try req.authUser
            let stationId = try req.parameters.require("stationId", as: Int.self)
            try await api.lean.deleteStation(user: authUser.user, stationId: stationId)
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a station",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - station-notification-trigger

        group.post("station-notification-trigger") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateStationNotificationTrigger.self)
            let trigger = try await api.lean.createStationNotificationTrigger(user: authUser.user, stationId: form.stationId, events: form.events, operatorIds: form.operatorIds, message: form.message)
            // return try loadFixture("Fixtures/Lean/station-notification-trigger.json") as LeanFragment.StationNotificationTrigger
            return makeStationNotificationTriggerFragment(trigger)
        }.openAPI(
            summary: "Create a station notification trigger",
            body: .type(LeanForm.CreateStationNotificationTrigger.self),
            response: .type(LeanFragment.StationNotificationTrigger.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("station-notification-trigger", ":triggerId") { req in
            let authUser = try req.authUser
            let triggerId = try req.parameters.require("triggerId", as: Int.self)
            let trigger = try await api.lean.stationNotificationTrigger(user: authUser.user, triggerId: triggerId)
            // return try loadFixture("Fixtures/Lean/station-notification-trigger.json") as LeanFragment.StationNotificationTrigger
            return makeStationNotificationTriggerFragment(trigger)
        }.openAPI(
            summary: "Get a station notification trigger",
            response: .type(LeanFragment.StationNotificationTrigger.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("station-notification-trigger", ":triggerId") { req in
            let authUser = try req.authUser
            let triggerId = try req.parameters.require("triggerId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateStationNotificationTrigger.self)
            let trigger = try await api.lean.saveStationNotificationTrigger(user: authUser.user, triggerId: triggerId, events: form.events, operatorIds: form.operatorIds, message: form.message)
            // return try loadFixture("Fixtures/Lean/station-notification-trigger.json") as LeanFragment.StationNotificationTrigger
            return makeStationNotificationTriggerFragment(trigger)
        }.openAPI(
            summary: "Update a station notification trigger",
            body: .type(LeanForm.UpdateStationNotificationTrigger.self),
            response: .type(LeanFragment.StationNotificationTrigger.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("station-notification-trigger", ":triggerId") { req in
            let authUser = try req.authUser
            let triggerId = try req.parameters.require("triggerId", as: Int.self)
            try await api.lean.deleteStationNotificationTrigger(user: authUser.user, triggerId: triggerId)
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a station notification trigger",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - suggested-agents

        group.get("suggested-agents", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let items = try await api.lean.suggestedAgents(user: authUser.user, companyId: companyId)
            // return try loadFixture("Fixtures/Lean/suggested-agents.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Get suggested agents for a company",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - suggested-intake-queue (line-scoped)

        group.get("suggested-intake-queue", ":lineId") { req in
            let authUser = try req.authUser
            let lineId = try req.parameters.require("lineId", as: Int.self)
            let items = try await api.lean.suggestedIntakeQueue(user: authUser.user, lineId: lineId)
            // return try loadFixture("Fixtures/Lean/suggested-intake-queues.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Get suggested intake queues for a line",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - suggested-intake-queues (company-scoped)

        group.get("suggested-intake-queues", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let items = try await api.lean.suggestedIntakeQueues(user: authUser.user, companyId: companyId)
            // return try loadFixture("Fixtures/Lean/suggested-intake-queues.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Get suggested intake queues for a company",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - suggested-inventories

        group.get("suggested-inventories", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let items = try await api.lean.suggestedInventories(user: authUser.user, companyId: companyId)
            // return try loadFixture("Fixtures/Lean/suggested-inventories.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Get suggested inventories for a company",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - suggested-mime-types

        group.get("suggested-mime-types") { req in
            let authUser = try req.authUser
            let items = try await api.lean.suggestedMimeTypes(user: authUser.user)
            // return try loadFixture("Fixtures/Lean/suggested-mime-types.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Get suggested MIME types",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - suggested-operators

        group.get("suggested-operators", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let items = try await api.lean.suggestedOperators(user: authUser.user, companyId: companyId)
            // return try loadFixture("Fixtures/Lean/suggested-operators.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Get suggested operators for a company",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - suggested-supplies

        group.get("suggested-supplies", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let items = try await api.lean.suggestedSupplies(user: authUser.user, companyId: companyId)
            // return try loadFixture("Fixtures/Lean/suggested-supplies.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Get suggested supplies for a company",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - suggested-work-unit

        group.get("suggested-work-unit", ":companyId") { req in
            let authUser = try req.authUser
            let companyId = try req.parameters.require("companyId", as: Int.self)
            let items = try await api.lean.suggestedWorkUnit(user: authUser.user, companyId: companyId)
            // return try loadFixture("Fixtures/Lean/find-work-units.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Get suggested work units for a company",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - suggested-supply-field-options (field-scoped)

        group.get("suggested-supply-field-options", ":supplyFieldId") { req in
            let authUser = try req.authUser
            let supplyFieldId = try req.parameters.require("supplyFieldId", as: Int.self)
            let items = try await api.lean.suggestedSupplyFieldOptions(user: authUser.user, supplyFieldId: supplyFieldId)
            // return try loadFixture("Fixtures/Lean/suggested-supply-field-options.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Get suggested options for a supply field",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("find-supply-field-options", ":supplyFieldId") { req in
            let authUser = try req.authUser
            let supplyFieldId = try req.parameters.require("supplyFieldId", as: Int.self)
            let q = req.query[String.self, at: "q"] ?? ""
            let items = try await api.lean.findSupplyFieldOptions(user: authUser.user, supplyFieldId: supplyFieldId, query: q)
            // return try loadFixture("Fixtures/Lean/suggested-supply-field-options.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Search options for a supply field",
            description: "Returns supply field options matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - supply

        group.post("supply") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateSupply.self)
            let item = try await api.lean.createSupply(user: authUser.user, companyId: form.companyId, name: form.name, theme: form.theme?.makeTheme(), amount: form.amount)
            return makeOption(item)
        }.openAPI(
            summary: "Create a supply",
            body: .type(LeanForm.CreateSupply.self),
            contentType: .application(.json),
            response: .type(Fragment.Option.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("supply", ":supplyId") { req in
            let authUser = try req.authUser
            let supplyId = try req.parameters.require("supplyId", as: Int.self)
            let supply = try await api.lean.supply(user: authUser.user, supplyId: supplyId)
            // return try loadFixture("Fixtures/Lean/supply.json") as LeanFragment.Supply
            return makeSupplyFragment(supply)
        }.openAPI(
            summary: "Get a supply",
            response: .type(LeanFragment.Supply.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("supply", ":supplyId") { req in
            let authUser = try req.authUser
            let supplyId = try req.parameters.require("supplyId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateSupply.self)
            let supply = try await api.lean.saveSupply(user: authUser.user, supplyId: supplyId, name: form.name, theme: form.theme?.makeTheme(), amount: form.amount)
            // return try loadFixture("Fixtures/Lean/supply.json") as LeanFragment.Supply
            return makeSupplyFragment(supply)
        }.openAPI(
            summary: "Update a supply",
            body: .type(LeanForm.UpdateSupply.self),
            response: .type(LeanFragment.Supply.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("supply", ":supplyId") { req in
            let authUser = try req.authUser
            let supplyId = try req.parameters.require("supplyId", as: Int.self)
            try await api.lean.deleteSupply(user: authUser.user, supplyId: supplyId)
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a supply",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("supply", ":supplyId", "fields") { req in
            let authUser = try req.authUser
            let supplyId = try req.parameters.require("supplyId", as: Int.self)
            let fields = try await api.lean.supplyFields(user: authUser.user, supplyId: supplyId)
            // return try loadFixture("Fixtures/Lean/supply-fields.json") as [Fragment.Option]
            return fields.map(makeOption)
        }.openAPI(
            summary: "Get supply fields for a supply",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("supply", ":supplyId", "field-positions") { req in
            let authUser = try req.authUser
            let supplyId = try req.parameters.require("supplyId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateSupplyFieldPositions.self)
            try await api.lean.saveSupplyFieldPositions(user: authUser.user, supplyId: supplyId, position: form.position, fieldIds: form.fieldIds)
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
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateSupplyField.self)
            let field = try await api.lean.createSupplyField(user: authUser.user, supplyId: form.supplyId, name: form.name)
            // return try loadFixture("Fixtures/Lean/supply-field-1.json") as LeanFragment.SupplyField
            return makeSupplyFieldFragment(field)
        }.openAPI(
            summary: "Create a supply field",
            body: .type(LeanForm.CreateSupplyField.self),
            response: .type(LeanFragment.SupplyField.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("supply-field", ":supplyFieldId") { req in
            let authUser = try req.authUser
            let supplyFieldId = try req.parameters.require("supplyFieldId", as: Int.self)
            // Return different fixture based on ID: 1=text, 2=file, 3=radio, 4=workUnit
//            switch supplyFieldId {
//            case 1, 2, 3, 4:
//                return try loadFixture("Fixtures/Lean/supply-field-\(supplyFieldId).json") as LeanFragment.SupplyField
//            default:
//                return try loadFixture("Fixtures/Lean/supply-field-1.json") as LeanFragment.SupplyField
//            }
//            return try loadFixture("Fixtures/Lean/supply-field-\(supplyFieldId).json") as LeanFragment.SupplyField
            let field = try await api.lean.supplyField(user: authUser.user, supplyFieldId: supplyFieldId)
            return makeSupplyFieldFragment(field)
        }.openAPI(
            summary: "Get a supply field",
            response: .type(LeanFragment.SupplyField.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("supply-field", ":supplyFieldId", "options") { req in
            let authUser = try req.authUser
            let supplyFieldId = try req.parameters.require("supplyFieldId", as: Int.self)
            let options = try await api.lean.supplyFieldOptions(user: authUser.user, supplyFieldId: supplyFieldId)
            // return try loadFixture("Fixtures/Lean/supply-field-options.json") as [Fragment.Option]
            return options.map(makeOption)
        }.openAPI(
            summary: "Get supply field options for a supply field",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("supply-field", ":supplyFieldId") { req in
            let authUser = try req.authUser
            let supplyFieldId = try req.parameters.require("supplyFieldId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateSupplyField.self)
//            switch supplyFieldId {
//            case 1, 2, 3, 4:
//                return try loadFixture("Fixtures/Lean/supply-field-\(supplyFieldId).json") as LeanFragment.SupplyField
//            default:
//                return try loadFixture("Fixtures/Lean/supply-field-1.json") as LeanFragment.SupplyField
//            }
//            return try loadFixture("Fixtures/Lean/supply-field-\(supplyFieldId).json") as LeanFragment.SupplyField
            let field = try await api.lean.saveSupplyField(
                user: authUser.user,
                supplyFieldId: supplyFieldId,
                name: form.name,
                type: form.type,
                textType: form.textType,
                placeholder: form.placeholder,
                intakeQueueId: form.intakeQueueId,
                append: form.append,
                optionNames: form.optionNames
            )
            return makeSupplyFieldFragment(field)
        }.openAPI(
            summary: "Update a supply field",
            body: .type(LeanForm.UpdateSupplyField.self),
            response: .type(LeanFragment.SupplyField.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("supply-field", ":supplyFieldId") { req in
            let authUser = try req.authUser
            let supplyFieldId = try req.parameters.require("supplyFieldId", as: Int.self)
            try await api.lean.deleteSupplyField(user: authUser.user, supplyFieldId: supplyFieldId)
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a supply field",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - supply-field-option

        group.post("supply-field-option") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateSupplyFieldOption.self)
            let value = try await api.lean.createSupplyFieldOption(user: authUser.user, supplyFieldId: form.supplyFieldId, name: form.name, hidden: form.hidden)
            // return try loadFixture("Fixtures/Lean/supply-field-option-1.json") as LeanFragment.SupplyFieldOption
            return makeSupplyFieldOptionFragment(value)
        }.openAPI(
            summary: "Create a supply field option",
            body: .type(LeanForm.CreateSupplyFieldOption.self),
            response: .type(LeanFragment.SupplyFieldOption.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("supply-field-option", ":supplyFieldOptionId") { req in
            let authUser = try req.authUser
            let supplyFieldOptionId = try req.parameters.require("supplyFieldOptionId", as: Int.self)
            let value = try await api.lean.supplyFieldOption(user: authUser.user, supplyFieldOptionId: supplyFieldOptionId)
            // return try loadFixture("Fixtures/Lean/supply-field-option-1.json") as LeanFragment.SupplyFieldOption
            return makeSupplyFieldOptionFragment(value)
        }.openAPI(
            summary: "Get a supply field option",
            response: .type(LeanFragment.SupplyFieldOption.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("supply-field-option", ":supplyFieldOptionId") { req in
            let authUser = try req.authUser
            let supplyFieldOptionId = try req.parameters.require("supplyFieldOptionId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateSupplyFieldOption.self)
            let value = try await api.lean.saveSupplyFieldOption(user: authUser.user, supplyFieldOptionId: supplyFieldOptionId, name: form.name, hidden: form.hidden)
            // return try loadFixture("Fixtures/Lean/supply-field-option-1.json") as LeanFragment.SupplyFieldOption
            return makeSupplyFieldOptionFragment(value)
        }.openAPI(
            summary: "Update a supply field option",
            body: .type(LeanForm.UpdateSupplyFieldOption.self),
            response: .type(LeanFragment.SupplyFieldOption.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("supply-field-option", ":supplyFieldOptionId") { req in
            let authUser = try req.authUser
            let supplyFieldOptionId = try req.parameters.require("supplyFieldOptionId", as: Int.self)
            try await api.lean.deleteSupplyFieldOption(user: authUser.user, supplyFieldOptionId: supplyFieldOptionId)
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a supply field option",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - create-work-unit

        group.get("create-work-unit", ":intakeQueueId") { req in
            let authUser = try req.authUser
            let intakeQueueId = try req.parameters.require("intakeQueueId", as: Int.self)
            let parentWorkUnitId = req.query[Int.self, at: "parentWorkUnitId"]
            let intakeQueue = try await api.lean.intakeQueue(user: authUser.user, intakeQueueId: intakeQueueId)
            let line = try await api.lean.line(user: authUser.user, lineId: intakeQueue.lineId)
            let factory = try await api.lean.factory(user: authUser.user, id: line.factoryId)
            let parent: WorkUnit?
            if let parentWorkUnitId {
                parent = try await api.lean.workUnit(user: authUser.user, workUnitId: parentWorkUnitId)
            } else {
                parent = nil
            }
            // let fixture = try loadFixture("Fixtures/Lean/create-work-unit.json") as LeanFragment.CreateWorkUnit
            return LeanFragment.CreateWorkUnit(
                intakeQueueName: intakeQueue.name,
                companyId: factory.companyId,
                operator: .init(id: authUser.user.id, name: authUser.user.fullName, type: "Human"),
                parent: parent.map { .init(id: $0.id, name: $0.name) }
            )
        }.openAPI(
            summary: "Get read-only data for the Create Work Unit form",
            description: "Returns the intake queue name, company id, current operator, and optional parent needed to pre-populate the Create Work Unit form. Pass optional parentWorkUnitId in the query string to preselect a parent.",
            response: .type(LeanFragment.CreateWorkUnit.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - work-unit

        group.post("work-unit") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateWorkUnit.self)
            let workUnit = try await api.lean.createWorkUnit(user: authUser.user, intakeQueueId: form.intakeQueueId, name: form.name, reporterId: form.reporterId, assigneeIds: form.assigneeIds, parentWorkUnitId: form.parentWorkUnitId)
            // return try loadFixture("Fixtures/Lean/work-unit-1.json") as LeanFragment.WorkUnit
            return makeWorkUnitFragment(workUnit)
        }.openAPI(
            summary: "Create a work unit",
            body: .type(LeanForm.CreateWorkUnit.self),
            contentType: .application(.json),
            response: .type(LeanFragment.WorkUnit.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.post("work-unit", "child") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.AddWorkUnitChild.self)
            try await api.lean.saveWorkUnitChild(user: authUser.user, workUnitId: form.childWorkUnitId, childWorkUnitId: form.childWorkUnitId)
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
            let authUser = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            try await api.lean.saveWorkUnitHold(user: authUser.user, workUnitId: workUnitId)
            return Fragment.OK()
        }.openAPI(
            summary: "Place a work unit on hold",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("work-unit", ":workUnitId") { req in
            let authUser = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
//            let availableIds: [Int] = [1, 2]
//            if !availableIds.contains(workUnitId) {
//                boss.log.i("Invalid WorkUnit.id (\(workUnitId)")
//                workUnitId = 1
//            }
//            return try loadFixture("Fixtures/Lean/work-unit-\(workUnitId).json") as LeanFragment.WorkUnit
            let workUnit = try await api.lean.workUnit(user: authUser.user, workUnitId: workUnitId)
            return makeWorkUnitFragment(workUnit)
        }.openAPI(
            summary: "Get a work unit",
            response: .type(LeanFragment.WorkUnit.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("work-unit", "children", ":workUnitId") { req in
            let authUser = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
//            if workUnitId < 1 || workUnitId > 2 {
//                workUnitId = 1
//            }
//            return try loadFixture("Fixtures/Lean/work-unit-children-\(workUnitId).json") as [LeanFragment.WorkUnit.Child]
            let children = try await api.lean.workUnitChildren(user: authUser.user, workUnitId: workUnitId)
            return children.map { LeanFragment.WorkUnit.Child(id: $0.id, key: $0.key, name: $0.name, eta: nil) }
        }.openAPI(
            summary: "Get children of a work unit",
            response: .type([LeanFragment.WorkUnit.Child].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("work-unit", ":workUnitId") { req in
            let authUser = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateWorkUnit.self)
            let workUnit = try await api.lean.saveWorkUnit(user: authUser.user, workUnitId: workUnitId, name: form.name, eta: form.eta)
            // return try loadFixture("Fixtures/Lean/work-unit-1.json") as LeanFragment.WorkUnit
            return makeWorkUnitFragment(workUnit)
        }.openAPI(
            summary: "Update a work unit",
            body: .type(LeanForm.UpdateWorkUnit.self),
            contentType: .application(.json),
            response: .type(LeanFragment.WorkUnit.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("work-unit", "assignees", ":workUnitId") { req in
            let authUser = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateWorkUnitAssignees.self)
            try await api.lean.saveWorkUnitAssignees(user: authUser.user, workUnitId: workUnitId, operatorIds: form.operatorIds)
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
            let authUser = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateWorkUnitParent.self)
            try await api.lean.saveWorkUnitParent(user: authUser.user, workUnitId: workUnitId, parentWorkUnitId: form.parentWorkUnitId)
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
            let authUser = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateWorkUnitReporter.self)
            try await api.lean.saveWorkUnitReporter(user: authUser.user, workUnitId: workUnitId, operatorId: form.operatorId)
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
            let authUser = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            try await api.lean.deleteWorkUnit(user: authUser.user, workUnitId: workUnitId)
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a work unit",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("work-unit", "child", ":workUnitId", ":childWorkUnitId") { req in
            let authUser = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let childWorkUnitId = try req.parameters.require("childWorkUnitId", as: Int.self)
            try await api.lean.deleteWorkUnitChild(user: authUser.user, workUnitId: workUnitId, childWorkUnitId: childWorkUnitId)
            return Fragment.OK()
        }.openAPI(
            summary: "Remove a child work unit",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.delete("work-unit", "hold", ":workUnitId") { req in
            let authUser = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let form = try req.content.decode(LeanForm.ClearWorkUnitHold.self)
            try await api.lean.deleteWorkUnitHold(user: authUser.user, workUnitId: workUnitId, comments: form.comments)
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
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.CreateWorkUnitComment.self)
            try await api.lean.saveWorkUnitComment(user: authUser.user, workUnitId: form.workUnitId, text: form.text)
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
            let authUser = try req.authUser
            let commentId = try req.parameters.require("commentId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateWorkUnitComment.self)
            try await api.lean.saveWorkUnitComment(user: authUser.user, commentId: commentId, text: form.text)
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
            let authUser = try req.authUser
            let commentId = try req.parameters.require("commentId", as: Int.self)
            try await api.lean.deleteWorkUnitComment(user: authUser.user, commentId: commentId)
            return Fragment.OK()
        }.openAPI(
            summary: "Delete a work unit comment",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - work-unit-position

        group.patch("work-unit-position") { req in
            let authUser = try req.authUser
            let form = try req.content.decode(LeanForm.UpdateWorkUnitPosition.self)
            try await api.lean.saveWorkUnitPosition(user: authUser.user, position: form.position, workUnitIds: form.workUnitIds)
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
            let authUser = try req.authUser
            let intakeQueueId = try req.parameters.require("intakeQueueId", as: Int.self)
            let queue = try await api.lean.intakeQueue(user: authUser.user, intakeQueueId: intakeQueueId)
            let workUnits = try await api.lean.workUnits(user: authUser.user, intakeQueueId: intakeQueueId)
            // return try loadFixture("Fixtures/Lean/work-units.json") as LeanFragment.WorkUnits
            return LeanFragment.WorkUnits(id: queue.id, name: queue.name, key: queue.key, workUnits: workUnits.map { $0.makeWorkUnitOption() })
        }.openAPI(
            summary: "Get work units for an intake queue",
            response: .type(LeanFragment.WorkUnits.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.put("work-units", ":intakeQueueId") { req in
            let authUser = try req.authUser
            let intakeQueueId = try req.parameters.require("intakeQueueId", as: Int.self)
            let form = try req.content.decode(LeanForm.UpdateWorkUnits.self)
            try await api.lean.saveWorkUnits(
                user: authUser.user,
                intakeQueueId: intakeQueueId,
                name: form.name,
                key: form.key,
                mixRatioType: form.mixRatioType,
                mixRatio: form.mixRatio,
                workUnitNameType: form.workUnitNameType,
                workUnitMaterialName: form.workUnitMaterialName,
                theme: nil
            )
            return Fragment.OK()
        }.openAPI(
            summary: "Update intake queue settings from the work units view",
            body: .type(LeanForm.UpdateWorkUnits.self),
            contentType: .application(.json),
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - workspace

        group.get("workspace", ":workUnitId") { req in
            let authUser = try req.authUser
            let workUnitId = try req.parameters.require("workUnitId", as: Int.self)
            let workspace = try await api.lean.workspace(user: authUser.user, workUnitId: workUnitId)
            // return try loadFixture("Fixtures/Lean/workspace.json") as LeanFragment.Workspace
            return makeWorkspaceFragment(workspace)
        }.openAPI(
            summary: "Get the station workspace for a work unit",
            description: "Returns the full workspace state including all operations and their current field values.",
            response: .type(LeanFragment.Workspace.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - work-unit move-to-next-station

        group.post("work-unit", ":id", "move-to-next-station") { req in
            let authUser = try req.authUser
            let id = try req.parameters.require("id", as: Int.self)
            try await api.lean.saveWorkUnitMoveToNextStation(user: authUser.user, workUnitId: id)
            return Fragment.OK()
        }.openAPI(
            summary: "Move a work unit to the next station",
            description: "Advances the work unit through the line. All operations must be fulfilled or waived before calling this.",
            response: .type(Fragment.OK.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - work-unit-supply

        group.patch("work-unit-supply", ":id") { req in
            let authUser = try req.authUser
            let id = try req.parameters.require("id", as: Int.self)
            let form = try req.content.decode(LeanForm.SaveWorkUnitSupply.self)
            let fields: [WorkUnitSupplyFieldInput] = form.fields.map { field in
                WorkUnitSupplyFieldInput(
                    fieldId: field.fieldId,
                    value: field.value,
                    selectedOptionIds: field.selectedOptionIds,
                    fileResourceId: field.fileResourceId,
                    workUnitId: field.workUnitId
                )
            }
            let workspace = try await api.lean.saveWorkUnitSupply(user: authUser.user, id: id, fields: fields)
            // return try loadFixture("Fixtures/Lean/workspace.json") as LeanFragment.Workspace
            return makeWorkspaceFragment(workspace)
        }.openAPI(
            summary: "Save field values for a work unit supply",
            description: "Saves the current field values without fulfilling. Returns the full updated workspace state.",
            body: .type(LeanForm.SaveWorkUnitSupply.self),
            contentType: .application(.json),
            response: .type(LeanFragment.Workspace.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("work-unit-supply", ":id", "fulfill") { req in
            let authUser = try req.authUser
            let id = try req.parameters.require("id", as: Int.self)
            let workspace = try await api.lean.saveWorkUnitSupplyFulfill(user: authUser.user, id: id)
            // return try loadFixture("Fixtures/Lean/workspace.json") as LeanFragment.Workspace
            return makeWorkspaceFragment(workspace)
        }.openAPI(
            summary: "Fulfill a work unit supply operation",
            description: "Marks the operation as fulfilled. Returns the full updated workspace state.",
            response: .type(LeanFragment.Workspace.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.patch("work-unit-supply", ":id", "waive") { req in
            let authUser = try req.authUser
            let id = try req.parameters.require("id", as: Int.self)
            let form = try req.content.decode(LeanForm.WaiveWorkUnitSupply.self)
            let workspace = try await api.lean.saveWorkUnitSupplyWaive(user: authUser.user, id: id, comments: form.comments)
            // return try loadFixture("Fixtures/Lean/workspace.json") as LeanFragment.Workspace
            return makeWorkspaceFragment(workspace)
        }.openAPI(
            summary: "Waive a work unit supply operation",
            description: "Marks the operation as waived with a reason. Returns the full updated workspace state.",
            body: .type(LeanForm.WaiveWorkUnitSupply.self),
            contentType: .application(.json),
            response: .type(LeanFragment.Workspace.self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        // MARK: - find/suggested work-units-for-intake-queue

        group.get("suggested-work-units-for-intake-queue", ":intakeQueueId") { req in
            let authUser = try req.authUser
            let intakeQueueId = try req.parameters.require("intakeQueueId", as: Int.self)
            let items = try await api.lean.suggestedWorkUnitsForIntakeQueue(user: authUser.user, intakeQueueId: intakeQueueId)
            // return try loadFixture("Fixtures/Lean/find-work-units.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Get suggested work units for an intake queue",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)

        group.get("find-work-units-for-intake-queue", ":intakeQueueId") { req in
            let authUser = try req.authUser
            let intakeQueueId = try req.parameters.require("intakeQueueId", as: Int.self)
            let q = req.query[String.self, at: "q"] ?? ""
            let items = try await api.lean.findWorkUnitsForIntakeQueue(user: authUser.user, intakeQueueId: intakeQueueId, query: q)
            // return try loadFixture("Fixtures/Lean/find-work-units.json") as [Fragment.Option]
            return items.map(makeOption)
        }.openAPI(
            summary: "Search work units for an intake queue",
            description: "Returns work units in the given intake queue matching the search term `q`.",
            response: .type([Fragment.Option].self),
            responseContentType: .application(.json)
        )
        .addScope(.user)
    }
}

private func makeOption(_ item: ListItem) -> Fragment.Option {
    .init(id: item.id, name: item.name)
}

private func makeFileResource(_ value: FileResource) -> LeanFragment.FileResource {
    .init(id: value.id, url: value.url.absoluteString)
}

extension LeanForm.Theme {
    func makeTheme() -> bosslib.Theme? {
        guard let id else {
            return nil
        }
        return .init(
            id: id,
            strokeColor: Color(hex: stroke),
            fillColor: Color(hex: fill),
            icon: nil
        )
    }
}

private func makeThemeFragment(_ theme: bosslib.Theme?) -> LeanFragment.Theme? {
    guard let theme else {
        return nil
    }
    return .init(
        id: theme.id,
        fill: theme.fillColor?.description ?? "",
        stroke: theme.strokeColor?.description ?? ""
    )
}

private func makeIntakeQueueFragment(_ iq: bosslib.IntakeQueue) -> LeanFragment.IntakeQueue {
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
    return .init(
        id: iq.id,
        name: iq.name,
        key: iq.key,
        mixRatioType: mixRatioType,
        mixRatio: iq.mixRatio,
        workUnitNameType: workUnitNameType,
        workUnitMaterialName: workUnitMaterialName,
        theme: makeThemeFragment(iq.theme)
    )
}

private func makeLineFragment(_ line: bosslib.Line) -> LeanFragment.Line {
    let hasOutput = line.output != nil
    let subAssemblyLine: Bool
    switch line.type {
    case .subAssembly:
        subAssemblyLine = true
    default:
        subAssemblyLine = false
    }
    let metrics = line.flowMetrics.map {
        LeanFragment.LineFlowMetrics(
            id: $0.id,
            lineId: $0.lineId,
            createDate: ISO8601DateFormatter().string(from: $0.createDate),
            operatingTime: $0.operatingTime,
            leadTime: $0.leadTime,
            value: 0.0,
            performanceEfficiency: $0.performanceEfficiency,
            totalWorkUnitsCompleted: $0.completedWorkUnits,
            numOperators: $0.numOperators,
            taktTime: $0.taktTime,
            completedWorkUnits: $0.completedWorkUnits
        )
    }
    return .init(
        id: line.id,
        name: line.name,
        locked: line.viewState.locked,
        hasOutput: hasOutput,
        subAssemblyLine: subAssemblyLine,
        metrics: metrics
    )
}

private func makeOperationFragment(_ operation: bosslib.Operation) -> LeanFragment.Operation {
    .init(
        id: operation.id,
        name: operation.name,
        instructions: operation.instructions,
        agent: operation.agent.map { .init(id: $0.id, name: "Operator \($0.id)") },
        supplyRequest: makeSupplyRequestFragment(operation.supplyRequest)
    )
}

private func makeSupplyRequestFragment(_ request: bosslib.Operation.SupplyRequest?) -> LeanFragment.SupplyRequest? {
    guard let request else {
        return nil
    }
    switch request {
    case .inventory(let inventoryId, let amount):
        return .init(type: "inventory", inventory: .init(id: inventoryId, name: "Inventory \(inventoryId)"), amount: amount, supply: nil, intakeQueue: nil)
    case .supply(let supplyId):
        return .init(type: "supply", inventory: nil, amount: nil, supply: .init(id: supplyId, name: "Supply \(supplyId)"), intakeQueue: nil)
    case .workUnits(let intakeQueueId):
        return .init(type: "intakeQueue", inventory: nil, amount: nil, supply: nil, intakeQueue: .init(id: intakeQueueId, name: "Intake Queue \(intakeQueueId)"))
    }
}

private func makeOperatorFragment(_ value: bosslib.Operator) -> LeanFragment.Operator {
    let type: String
    switch value.type {
    case .user:
        type = "Human"
    case .agent:
        type = "AI Agent"
    }
    return .init(id: value.id, name: "Operator \(value.id)", type: type)
}

private func makeStationNotificationTriggerFragment(_ trigger: bosslib.StationNotificationTrigger) -> LeanFragment.StationNotificationTrigger {
    .init(
        id: trigger.id,
        events: trigger.events.map { $0 == .onEnter ? "onEnter" : "onExit" },
        operators: trigger.operators.map(makeOperatorFragment),
        message: trigger.message
    )
}

private func makeSupplyFragment(_ supply: bosslib.Supply) -> LeanFragment.Supply {
    .init(
        id: supply.id,
        name: supply.name,
        theme: makeThemeFragment(supply.theme),
        amount: supply.amount,
        fields: supply.fields?.map { .init(id: $0.id, name: $0.name) } ?? []
    )
}

private func makeSupplyFieldFragment(_ field: bosslib.SupplyField) -> LeanFragment.SupplyField {
    let type: String
    var textType: String?
    var placeholder: String?
    var append: Bool?
    var options: [Fragment.Option]?
    var intakeQueue: Fragment.Option?

    switch field.supplyFieldType {
    case .button:
        type = "button"
    case .text(let textField):
        type = "text"
        placeholder = textField.placeholder
        switch textField.text {
        case .plain: textType = "plain"
        case .textarea: textType = "textarea"
        case .numeric: textType = "numeric"
        case .url: textType = "url"
        case .phoneNumber: textType = "phoneNumber"
        case .price: textType = "price"
        case .wholeNumber: textType = "wholeNumber"
        }
    case .measurement:
        type = "measurement"
    case .file:
        type = "file"
    case .radio(let optionField):
        type = "radio"
        append = optionField.append
        options = optionField.options.map { .init(id: $0.id, name: $0.name) }
    case .multiSelect(let optionField):
        type = "multiSelect"
        append = optionField.append
        options = optionField.options.map { .init(id: $0.id, name: $0.name) }
    case .intakeQueue(let intakeQueueId):
        type = "intakeQueue"
        intakeQueue = .init(id: intakeQueueId, name: "Intake Queue \(intakeQueueId)")
    }

    return .init(
        id: field.id,
        name: field.name,
        type: type,
        textType: textType,
        placeholder: placeholder,
        append: append,
        options: options,
        intakeQueue: intakeQueue
    )
}

private func makeSupplyFieldOptionFragment(_ value: bosslib.SupplyFieldOption) -> LeanFragment.SupplyFieldOption {
    .init(id: value.id, name: value.name, hidden: value.hidden)
}

private func makeWorkUnitFragment(_ value: bosslib.WorkUnit) -> LeanFragment.WorkUnit {
    let intakeQueueState: LeanFragment.WorkUnit.LineState.IntakeQueue?
    let stationState: LeanFragment.WorkUnit.LineState.Station?
    let outputState: LeanFragment.WorkUnit.LineState.Output?
    switch value.lineState {
    case .intakeQueue(let intakeQueue, _):
        intakeQueueState = .init(name: "Intake Queue \(intakeQueue)")
        stationState = nil
        outputState = nil
    case .station(let station, let operation, let status):
        intakeQueueState = nil
        stationState = .init(name: "Station \(station)", operationName: operation.map { "Operation \($0)" }, operationStatus: status.map(makeOperationStatusString))
        outputState = nil
    case .output(let output):
        intakeQueueState = nil
        stationState = nil
        outputState = .init(outputDate: value.outputDate.map { ISO8601DateFormatter().string(from: $0) } ?? "", outputReason: value.outputReason?.name, finishedProduct: value.finishedProduct?.supply.name)
    }

    let parentWorkUnit: Fragment.Option?
    switch value.parent {
    case .operationWorkUnit(let rel):
        parentWorkUnit = .init(id: rel.workUnitId, name: "Work Unit \(rel.workUnitId)")
    case .parentWorkUnit(let parentId):
        parentWorkUnit = .init(id: parentId, name: "Work Unit \(parentId)")
    }

    return .init(
        id: value.id,
        key: value.key,
        name: value.name,
        companyId: value.creator.companyId,
        intakeQueueId: value.intakeQueueID,
        eta: value.flowMetrics.map { ISO8601DateFormatter().string(from: $0.eta) },
        creator: .init(id: value.creator.id, name: "Operator \(value.creator.id)"),
        reporter: .init(id: value.reporter.id, name: "Operator \(value.reporter.id)"),
        assignees: value.assignees.map { .init(id: $0.id, name: "Operator \($0.id)") },
        parentWorkUnit: parentWorkUnit,
        intakeQueueState: intakeQueueState,
        stationState: stationState,
        outputState: outputState,
        onHold: value.onHold != nil,
        onHoldElapsed: nil,
        logs: [],
        comments: value.comments.map {
            .init(
                id: $0.id,
                operator: .init(id: $0.operatorId, name: "Operator \($0.operatorId)", type: "Human"),
                createDate: ISO8601DateFormatter().string(from: $0.createDate),
                text: $0.text
            )
        },
        children: value.workUnits?.map { .init(id: $0.id, key: $0.key, name: $0.name, eta: nil) } ?? []
    )
}

private func makeOperationStatusString(_ status: bosslib.OperationStatus) -> String {
    switch status {
    case .waiting:
        return "waiting"
    case .inProgress:
        return "inProgress"
    case .error:
        return "error"
    case .finished:
        return "finished"
    }
}

private func makeWorkspaceFragment(_ workspace: bosslib.Workspace) -> LeanFragment.Workspace {
    let stationId: Int
    let stationName: String
    switch workspace.workUnit.lineState {
    case .station(let station, _, _):
        stationId = station
        stationName = "Station \(station)"
    default:
        stationId = 0
        stationName = ""
    }

    return .init(
        id: workspace.workUnit.id,
        key: workspace.workUnit.key,
        name: workspace.workUnit.name,
        companyId: workspace.workUnit.creator.companyId,
        stationId: stationId,
        stationName: stationName,
        operations: workspace.operations.map { op in
            let first = op.workUnitSupplies.first
            let status: String
            if let first, first.waived {
                status = "waived"
            }
            else if let first, first.fulfilledDate != nil {
                status = "fulfilled"
            }
            else {
                status = "pending"
            }
            return .init(
                workUnitSupplyId: first?.id ?? 0,
                name: op.operation.name,
                instructions: op.operation.instructions,
                status: status,
                active: true,
                fields: first?.supplyFieldValues.map(makeWorkspaceFieldFragment) ?? []
            )
        }
    )
}

private func makeWorkspaceFieldFragment(_ value: bosslib.SupplyFieldValue) -> LeanFragment.WorkspaceField {
    switch value.value {
    case .plain(let text), .textarea(let text), .phoneNumber(let text):
        return .init(id: value.id, name: "Field \(value.supplyFieldId)", type: "text", textType: "plain", value: text, options: nil, selectedOptionIds: nil, fileResource: nil, workUnit: nil, intakeQueueId: nil)
    case .numeric(let number), .price(let number):
        return .init(id: value.id, name: "Field \(value.supplyFieldId)", type: "text", textType: "numeric", value: String(number), options: nil, selectedOptionIds: nil, fileResource: nil, workUnit: nil, intakeQueueId: nil)
    case .url(let url):
        return .init(id: value.id, name: "Field \(value.supplyFieldId)", type: "text", textType: "url", value: url.absoluteString, options: nil, selectedOptionIds: nil, fileResource: nil, workUnit: nil, intakeQueueId: nil)
    case .wholeNumber(let number):
        return .init(id: value.id, name: "Field \(value.supplyFieldId)", type: "text", textType: "wholeNumber", value: String(number), options: nil, selectedOptionIds: nil, fileResource: nil, workUnit: nil, intakeQueueId: nil)
    case .button:
        return .init(id: value.id, name: "Field \(value.supplyFieldId)", type: "button", textType: nil, value: nil, options: nil, selectedOptionIds: nil, fileResource: nil, workUnit: nil, intakeQueueId: nil)
    case .file(let file):
        return .init(id: value.id, name: "Field \(value.supplyFieldId)", type: "file", textType: nil, value: nil, options: nil, selectedOptionIds: nil, fileResource: makeFileResource(file), workUnit: nil, intakeQueueId: nil)
    case .radio(let option):
        return .init(id: value.id, name: "Field \(value.supplyFieldId)", type: "radio", textType: nil, value: nil, options: nil, selectedOptionIds: [option.supplyFieldOptionId], fileResource: nil, workUnit: nil, intakeQueueId: nil)
    case .multiSelect(let options):
        return .init(id: value.id, name: "Field \(value.supplyFieldId)", type: "multiSelect", textType: nil, value: nil, options: nil, selectedOptionIds: options.map { $0.supplyFieldOptionId }, fileResource: nil, workUnit: nil, intakeQueueId: nil)
    case .workUnit(let workUnitId):
        return .init(id: value.id, name: "Field \(value.supplyFieldId)", type: "intakeQueue", textType: nil, value: nil, options: nil, selectedOptionIds: nil, fileResource: nil, workUnit: .init(id: workUnitId, name: "Work Unit \(workUnitId)"), intakeQueueId: nil)
    }
}

private func makeFactoryFloorFragment(factory: bosslib.Factory, floor: bosslib.FactoryFloor) -> LeanFragment.FactoryFloor {
    .init(
        id: factory.id,
        companyId: factory.companyId,
        name: factory.name,
        throughputInterval: "daily",
        lines: floor.lines.map { line in
            LeanFragment.FactoryFloor.Line(
                id: line.id,
                gridX: line.viewState.x,
                gridY: line.viewState.y,
                name: line.name,
                locked: line.viewState.locked,
                hasOutput: line.output != nil,
                subAssemblyLine: {
                    if case .subAssembly = line.type { return true }
                    return false
                }(),
                leadTime: line.flowMetrics?.leadTime,
                taktTime: line.flowMetrics?.taktTime,
                throughput: line.flowMetrics?.completedWorkUnits,
                hopperWorkUnit: line.hopper.workUnit.map {
                    .init(id: $0.id, key: $0.key, name: $0.name, intakeQueueId: $0.intakeQueueID, eta: $0.flowMetrics.map { ISO8601DateFormatter().string(from: $0.eta) })
                },
                intakeQueues: line.intakeQueues.map {
                    .init(id: $0.id, name: $0.name, mixRatio: $0.mixRatio, cycleTime: 0, numWorkUnits: 0, color: .init(fill: $0.theme?.fillColor?.description ?? "", border: $0.theme?.strokeColor?.description ?? ""))
                },
                stations: line.stations.map { station in
                    let connectsToIntakeQueue: Int?
                    switch station.type {
                    case .intakeQueue(let intakeQueue):
                        connectsToIntakeQueue = intakeQueue.id
                    case .station:
                        connectsToIntakeQueue = nil
                    }
                    return .init(
                        id: station.id,
                        name: station.name,
                        cycleTime: station.flowMetrics?.cycleTime,
                        connectsToInventory: nil,
                        connectsToIntakeQueue: connectsToIntakeQueue,
                        color: station.theme.map { .init(fill: $0.fillColor?.description ?? "", border: $0.strokeColor?.description ?? "") },
                        workUnits: station.workUnits.map { wu in
                            .init(
                                id: wu.id,
                                key: wu.key,
                                name: wu.name,
                                intakeQueueId: wu.intakeQueueID,
                                assignees: wu.assignees.map { .init(id: String($0.id), name: "Operator \($0.id)", avatar: nil) },
                                onHold: wu.onHold != nil,
                                startTime: nil,
                                eta: wu.flowMetrics.map { ISO8601DateFormatter().string(from: $0.eta) },
                                totalOperations: station.operations.count,
                                completedOperations: 0
                            )
                        },
                        overlay: "none",
                        posX: 0,
                        posY: 0
                    )
                }
            )
        },
        inventories: floor.inventories.map {
            .init(
                id: $0.id,
                gridX: $0.viewState.x,
                gridY: $0.viewState.y,
                name: $0.supply.name,
                cycleStock: nil,
                bufferStockLevel: nil,
                safetyStockLevel: nil,
                reorderAlgorithm: nil,
                orderRequest: nil,
                health: nil
            )
        }
    )
}

private func makeStationAssigneeActionString(_ action: bosslib.StationAssigneeAction) -> String {
    switch action {
    case .remove:
        return "remove"
    case .retain:
        return "retain"
    case .replace:
        return "replace"
    }
}

private func makeStationTypeString(_ type: bosslib.Station.StationType) -> String {
    switch type {
    case .station:
        return "station"
    case .intakeQueue:
        return "intakeQueue"
    }
}

private func makeStationAssigneeOptions(_ action: bosslib.StationAssigneeAction) -> [Fragment.Option] {
    switch action {
    case .replace(let operators):
        return operators.map { .init(id: $0.id, name: "Operator \($0.id)") }
    default:
        return []
    }
}

private func makeStationIntakeQueueOption(_ type: bosslib.Station.StationType) -> Fragment.Option? {
    switch type {
    case .intakeQueue(let intakeQueue):
        return .init(id: intakeQueue.id, name: intakeQueue.name)
    case .station:
        return nil
    }
}

private func makeStationFlowMetrics(_ metrics: bosslib.StationFlowMetrics?) -> LeanFragment.StationFlowMetrics? {
    guard let metrics else {
        return nil
    }
    return .init(
        id: metrics.id,
        createDate: ISO8601DateFormatter().string(from: metrics.createDate),
        cycleTime: metrics.cycleTime
    )
}

private func makeStationFragment(user: User, station: bosslib.Station) async throws -> LeanFragment.Station {
    let line = try await api.lean.line(user: user, lineId: station.lineId)
    let factory = try await api.lean.factory(user: user, id: line.factoryId)
    return .init(
        id: station.id,
        lineId: station.lineId,
        companyId: factory.companyId,
        name: station.name,
        type: makeStationTypeString(station.type),
        assigneeAction: makeStationAssigneeActionString(station.assigneeAction),
        assignees: makeStationAssigneeOptions(station.assigneeAction),
        intakeQueue: makeStationIntakeQueueOption(station.type),
        theme: makeThemeFragment(station.theme),
        metrics: makeStationFlowMetrics(station.flowMetrics)
    )
}
