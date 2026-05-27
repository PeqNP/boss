/// Copyright ⓒ 2026 Bithead LLC. All rights reserved.

import bosslib
import Vapor

enum LeanForm {
    struct CreateCompany: Content {
        var companyId: bosslib.Company.ID?
        var name: String?
    }

    struct CreateFactory: Content {
        var companyId: bosslib.Company.ID
        var factoryId: bosslib.Factory.ID?
        var name: String?
    }

    struct CreateLine: Content {
        var factoryId: bosslib.Factory.ID
        var name: String?
    }

    struct CreateInventory: Content {
        var factoryId: bosslib.Factory.ID
        var name: String?
    }

    struct CreateStation: Content {
        var lineId: Int
        var name: String?
    }

    struct CreateIntakeQueue: Content {
        var lineId: Int
        var name: String?
    }

    struct UpdateLinePosition: Content {
        var id: Int
        var gridX: Int
        var gridY: Int
    }

    struct UpdateLineLocked: Content {
        var id: Int
        var locked: Bool
    }

    struct UpdateLineFocus: Content {
        var id: Int
        var focused: Bool
    }

    struct StartWorkUnit: Content {
        var id: Int
    }

    struct UpdateLineName: Content {
        var id: Int
        var name: String
    }

    struct UpdateLine: Content {
        var name: String
        var hasOutput: Bool
        var subAssemblyLine: Bool
    }

    struct UpdateInventory: Content {
        var name: String?
    }

    struct UpdateInventoryPosition: Content {
        var id: Int
        var gridX: Int
        var gridY: Int
    }

    struct UpdateInventoryLocked: Content {
        var id: Int
        var locked: Bool
    }

    struct UpdateInventoryFocus: Content {
        var id: Int
        var focused: Bool
    }

    struct UpdateStationName: Content {
        var id: Int
        var name: String
    }

    struct Theme: Content {
        var id: Int?
        var fill: String
        var stroke: String
    }

    struct UpdateStation: Content {
        var name: String?
        /// "remove" | "retain" | "replace"
        var assigneeAction: String?
        var theme: LeanForm.Theme?
    }

    struct UpdateIntakeQueue: Content {
        var name: String?
        var key: String?
        var mixRatioType: String?
        var mixRatio: Int?
        var workUnitNameType: String?
        var workUnitMaterialName: String?
        var theme: LeanForm.Theme?
    }

    struct UpdateStationTypeIntakeQueue: Content {
        var intakeQueueId: Int
    }

    struct UpdateIntakeQueueName: Content {
        var id: Int
        var name: String
    }

    struct UpdateIntakeQueueMixRatio: Content {
        var id: Int
        var mixRatio: Int
    }

    struct UpdateInventoryName: Content {
        var id: Int
        var name: String
    }

    struct UpdateCompany: Content {
        var name: String?
    }

    struct UpdateFactory: Content {
        var name: String?
    }

    struct UpdateWorkUnits: Content {
        var name: String?
        var key: String?
        var mixRatioType: String?
        var mixRatio: Int?
        var workUnitNameType: String?
        var workUnitMaterialName: String?
    }

    struct UpdateWorkUnit: Content {
        var name: String?
        var eta: String?
    }

    struct CreateWorkUnit: Content {
        var intakeQueueId: Int
        var name: String
        var reporterId: Int?
        var assigneeIds: [Int]
        var parentWorkUnitId: Int?
    }

    struct UpdateWorkUnitReporter: Content {
        var operatorId: Operator.ID?
    }

    struct UpdateWorkUnitAssignees: Content {
        var operatorIds: [Operator.ID]
    }

    struct UpdateWorkUnitParent: Content {
        var parentWorkUnitId: Int?
    }

    struct AddWorkUnitChild: Content {
        var childWorkUnitId: Int
    }

    struct ClearWorkUnitHold: Content {
        var comments: String?
    }

    struct UpdateWorkUnitPosition: Content {
        var position: Int
        var workUnitIds: [Int]
    }

    struct CreateOperator: Content {
        var userId: Int?
        var agentId: Int?
    }

    struct UpdateOperator: Content {
        var userId: Int?
        var agentId: Int?
    }

    struct CreateWorkUnitComment: Content {
        var workUnitId: Int
        var text: String
    }

    struct UpdateWorkUnitComment: Content {
        var text: String
    }

    struct CreateOperation: Content {
        var stationId: Int
        var name: String
        var agentId: Int?
    }

    struct UpdateOperation: Content {
        var name: String
        var agentId: Int?
    }

    struct UpdateOperationPositions: Content {
        var position: Int
        var operationIds: [Int]
    }

    struct CreateSupplyRequest: Content {
        var operationId: Int
        var type: String
        var inventoryId: Int?
        var amount: Int?
        var supplyId: Int?
        var intakeQueueId: Int?
    }

    struct UpdateSupplyRequest: Content {
        var inventoryId: Int?
        var amount: Int?
        var supplyId: Int?
        var intakeQueueId: Int?
    }

    struct UpdateSupplyRequestPositions: Content {
        var position: Int
        var supplyRequestTypes: [String]
    }

    struct CreateSupplyField: Content {
        var supplyId: Int
        var name: String
        var type: String
        // Text type
        var textType: String?
        var placeholder: String?
        // IntakeQueue type
        var intakeQueueId: Int?
        // Options type
        var append: Bool?
        var optionNames: [String]?
    }

    struct UpdateSupplyField: Content {
        var name: String?
        var type: String?
        var textType: String?
        var placeholder: String?
        // IntakeQueue type
        var intakeQueueId: Int?
        var append: Bool?
        var optionNames: [String]?
    }

    struct UpdateSupplyFieldPositions: Content {
        var position: Int
        var fieldIds: [Int]
    }

    struct CreateSupplyFieldOption: Content {
        var supplyFieldId: Int
        var name: String
        var hidden: Bool?
    }

    struct UpdateSupplyFieldOption: Content {
        var name: String?
        var hidden: Bool?
    }

    struct CreateStationNotificationTrigger: Content {
        var stationId: Int
        var events: [String]
        var operatorIds: [Int]
        var message: String?
    }

    struct UpdateStationNotificationTrigger: Content {
        var events: [String]?
        var operatorIds: [Int]?
        var message: String?
    }
}
