/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

internal import SQLKit

class Version1_3_0: DatabaseVersion {
    var version: String { "1.3.0" }

    func update(_ conn: Database.Connection) async throws {
        let sql = conn.sql()

        // MARK: - Themes

        /// Used by Line, IntakeQueue, Station, Supply, etc. The owning table stores `theme_id`.
        try await sql.create(table: "themes")
            .column("id", type: .int, .primaryKey)
            // 0 = system icon, 1 = url
            .column("icon_type", type: .int)
            // When icon_type = 0 (system), the SystemIcon raw value
            .column("icon_system_value", type: .int)
            // When icon_type = 1 (url), the URL string
            .column("icon_url", type: .text)
            .column("stroke_color", type: .text)
            .column("fill_color", type: .text)
            .run()

        // MARK: - Change Log

        try await sql.create(table: "change_logs")
            .column("id", type: .int, .primaryKey)
            // BusinessModel raw value
            .column("business_model_id", type: .int)
            .column("date", type: .timestamp)
            .column("operator_id", type: .int)
            // JSON array of Change objects: [{column, before, after}]
            .column("metadata", type: .text)
            .run()
        try await sql.create(index: "change_logs_operator_id_idx")
            .on("change_logs")
            .column("operator_id")
            .run()
        try await sql.create(index: "change_logs_business_model_id_idx")
            .on("change_logs")
            .column("business_model_id")
            .run()

        // MARK: - Agents

        try await sql.create(table: "agents")
            .column("id", type: .int, .primaryKey)
            .column("name", type: .text)
            .run()

        // MARK: - Operators

        /// An Operator maps to either a User (type=0) or an Agent (type=1).
        try await sql.create(table: "operators")
            .column("id", type: .int, .primaryKey)
            // 0 = user, 1 = agent
            .column("type", type: .int)
            .column("user_id", type: .bigint)
            .column("agent_id", type: .int)
            .foreignKey(["user_id"], references: "users", ["id"], onDelete: .setNull)
            .foreignKey(["agent_id"], references: "agents", ["id"], onDelete: .setNull)
            .run()
        try await sql.create(index: "operators_user_id_idx")
            .on("operators")
            .column("user_id")
            .run()
        try await sql.create(index: "operators_agent_id_idx")
            .on("operators")
            .column("agent_id")
            .run()

        // MARK: - Factories

        try await sql.create(table: "factories")
            .column("id", type: .int, .primaryKey)
            .column("name", type: .text)
            // FlowMetricInterval: 0 = seconds, 1 = daily, 2 = weekly
            .column("flow_metric_interval_type", type: .int)
            // When type = 0 (seconds), the TimeInterval value
            .column("flow_metric_interval_seconds", type: .real)
            // When type = 1 or 2, the Date value
            .column("flow_metric_interval_date", type: .timestamp)
            .run()

        // MARK: - Lines

        try await sql.create(table: "lines")
            .column("id", type: .int, .primaryKey)
            .column("factory_id", type: .int)
            .column("theme_id", type: .int)
            .column("name", type: .text)
            // LineType: 0 = model, 1 = replica, 2 = subAssembly
            .column("line_type", type: .int)
            // When line_type = 1 (replica): the model line this replicates
            .column("model_line_id", type: .int)
            .column("inherit_shifts", type: .smallint)
            // ViewState
            .column("view_x", type: .int)
            .column("view_y", type: .int)
            .column("view_locked", type: .smallint)
            .column("is_parallel", type: .smallint)
            .foreignKey(["factory_id"], references: "factories", ["id"], onDelete: .cascade)
            .foreignKey(["theme_id"], references: "themes", ["id"], onDelete: .setNull)
            .foreignKey(["model_line_id"], references: "lines", ["id"], onDelete: .setNull)
            .run()
        try await sql.create(index: "lines_factory_id_idx")
            .on("lines")
            .column("factory_id")
            .run()
        try await sql.create(index: "lines_model_line_id_idx")
            .on("lines")
            .column("model_line_id")
            .run()

        // Line managers (many-to-many)
        try await sql.create(table: "line_managers")
            .column("id", type: .int, .primaryKey)
            .column("line_id", type: .int)
            .column("operator_id", type: .int)
            .foreignKey(["line_id"], references: "lines", ["id"], onDelete: .cascade)
            .foreignKey(["operator_id"], references: "operators", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "line_managers_line_id_idx")
            .on("line_managers")
            .column("line_id")
            .run()
        try await sql.create(index: "line_managers_operator_id_idx")
            .on("line_managers")
            .column("operator_id")
            .run()

        // MARK: - Shifts

        /// Shift.Time is stored inline on the shifts table (start_ and end_ prefixes).
        try await sql.create(table: "shifts")
            .column("id", type: .int, .primaryKey)
            .column("line_id", type: .int)
            // Shift.Time (start)
            .column("start_day_of_week", type: .int)
            .column("start_time", type: .real)
            .column("end_time_start", type: .real)
            // Shift.Time (end)
            .column("end_day_of_week", type: .int)
            .column("end_time", type: .real)
            .column("end_time_end", type: .real)
            .column("breaks_in_minutes", type: .real)
            .foreignKey(["line_id"], references: "lines", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "shifts_line_id_idx")
            .on("shifts")
            .column("line_id")
            .run()

        // MARK: - Operator Shifts

        try await sql.create(table: "operator_shifts")
            .column("id", type: .int, .primaryKey)
            .column("operator_id", type: .int)
            .column("shift_id", type: .int)
            .foreignKey(["operator_id"], references: "operators", ["id"], onDelete: .cascade)
            .foreignKey(["shift_id"], references: "shifts", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "operator_shifts_operator_id_idx")
            .on("operator_shifts")
            .column("operator_id")
            .run()
        try await sql.create(index: "operator_shifts_shift_id_idx")
            .on("operator_shifts")
            .column("shift_id")
            .run()

        // MARK: - Completed Operator Shifts

        try await sql.create(table: "completed_operator_shifts")
            .column("id", type: .int, .primaryKey)
            .column("operator_shift_id", type: .int)
            .column("week_number", type: .int)
            .foreignKey(["operator_shift_id"], references: "operator_shifts", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "completed_operator_shifts_operator_shift_id_idx")
            .on("completed_operator_shifts")
            .column("operator_shift_id")
            .run()

        // MARK: - Operator Absences

        try await sql.create(table: "operator_absences")
            .column("id", type: .int, .primaryKey)
            .column("operator_id", type: .int)
            .column("shift_id", type: .int)
            .column("entire_shift", type: .smallint)
            .column("time_off_in_minutes", type: .real)
            .column("week_number", type: .int)
            // AbsenceReason: 0 = sickLeave, 1 = paidTimeOff, 2 = other
            .column("reason", type: .int)
            // When reason = 2 (other), the reason message
            .column("reason_message", type: .text)
            .foreignKey(["operator_id"], references: "operators", ["id"], onDelete: .cascade)
            .foreignKey(["shift_id"], references: "shifts", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "operator_absences_operator_id_idx")
            .on("operator_absences")
            .column("operator_id")
            .run()
        try await sql.create(index: "operator_absences_shift_id_idx")
            .on("operator_absences")
            .column("shift_id")
            .run()

        // MARK: - Supplies

        try await sql.create(table: "supplies")
            .column("id", type: .int, .primaryKey)
            .column("name", type: .text)
            .column("theme_id", type: .int)
            .column("amount", type: .int)
            .foreignKey(["theme_id"], references: "themes", ["id"], onDelete: .setNull)
            .run()
        try await sql.create(index: "supplies_theme_id_idx")
            .on("supplies")
            .column("theme_id")
            .run()

        // MARK: - Supply Fields

        try await sql.create(table: "supply_fields")
            .column("id", type: .int, .primaryKey)
            .column("supply_id", type: .int)
            // Icon type: 0 = system, 1 = url
            .column("icon_type", type: .int)
            .column("icon_system_value", type: .int)
            .column("icon_url", type: .text)
            .column("name", type: .text)
            // SupplyFieldType discriminator: 0=text, 1=textArea, 2=file, 3=radio, 4=multiSelect
            .column("supply_field_type", type: .int)
            // For text: TextType discriminator
            .column("text_type", type: .int)
            // For text/textArea: default value
            .column("default_value", type: .text)
            // For file: mime type
            .column("mime_type", type: .text)
            .foreignKey(["supply_id"], references: "supplies", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "supply_fields_supply_id_idx")
            .on("supply_fields")
            .column("supply_id")
            .run()

        // MARK: - Supply Field Options

        try await sql.create(table: "supply_field_options")
            .column("id", type: .int, .primaryKey)
            .column("supply_field_id", type: .int)
            .column("name", type: .text)
            .column("hidden", type: .smallint)
            .foreignKey(["supply_field_id"], references: "supply_fields", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "supply_field_options_supply_field_id_idx")
            .on("supply_field_options")
            .column("supply_field_id")
            .run()

        // MARK: - Outputs

        try await sql.create(table: "outputs")
            .column("id", type: .int, .primaryKey)
            .column("line_id", type: .int)
            .column("name", type: .text)
            .foreignKey(["line_id"], references: "lines", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "outputs_line_id_idx")
            .on("outputs")
            .column("line_id")
            .run()

        // MARK: - Output Reasons

        try await sql.create(table: "output_reasons")
            .column("id", type: .int, .primaryKey)
            .column("output_id", type: .int)
            .column("name", type: .text)
            .column("hidden", type: .smallint)
            .foreignKey(["output_id"], references: "outputs", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "output_reasons_output_id_idx")
            .on("output_reasons")
            .column("output_id")
            .run()

        // MARK: - Intake Queues

        try await sql.create(table: "intake_queues")
            .column("id", type: .int, .primaryKey)
            .column("line_id", type: .int)
            .column("sort_order", type: .int)
            .column("name", type: .text)
            .column("theme_id", type: .int)
            .column("mix_ratio", type: .real)
            // WorkUnitName: NULL = operatorProvided, NOT NULL = material (fixed name)
            .column("work_unit_name", type: .text)
            // The Supply.ID if this intake queue produces a finished product
            .column("finished_product_supply_id", type: .int)
            .foreignKey(["line_id"], references: "lines", ["id"], onDelete: .cascade)
            .foreignKey(["theme_id"], references: "themes", ["id"], onDelete: .setNull)
            .foreignKey(["finished_product_supply_id"], references: "supplies", ["id"], onDelete: .setNull)
            .run()
        try await sql.create(index: "intake_queues_line_id_idx")
            .on("intake_queues")
            .column("line_id")
            .run()

        // MARK: - Intake Queue Supplies

        try await sql.create(table: "intake_queue_supplies")
            .column("id", type: .int, .primaryKey)
            .column("intake_queue_id", type: .int)
            .column("supply_id", type: .int)
            .foreignKey(["intake_queue_id"], references: "intake_queues", ["id"], onDelete: .cascade)
            .foreignKey(["supply_id"], references: "supplies", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "intake_queue_supplies_intake_queue_id_idx")
            .on("intake_queue_supplies")
            .column("intake_queue_id")
            .run()

        // MARK: - Stations

        try await sql.create(table: "stations")
            .column("id", type: .int, .primaryKey)
            .column("line_id", type: .int)
            .column("sort_order", type: .int)
            // StationType: 0 = station, 1 = intakeQueue
            .column("type", type: .int)
            // When type = 1 (intakeQueue): the referenced IntakeQueue
            .column("intake_queue_id", type: .int)
            .column("name", type: .text)
            .column("theme_id", type: .int)
            // StationAssigneeAction: 0 = remove, 1 = retain, 2 = replace
            .column("assignee_action", type: .int)
            .foreignKey(["line_id"], references: "lines", ["id"], onDelete: .cascade)
            .foreignKey(["theme_id"], references: "themes", ["id"], onDelete: .setNull)
            .foreignKey(["intake_queue_id"], references: "intake_queues", ["id"], onDelete: .setNull)
            .run()
        try await sql.create(index: "stations_line_id_idx")
            .on("stations")
            .column("line_id")
            .run()
        try await sql.create(index: "stations_intake_queue_id_idx")
            .on("stations")
            .column("intake_queue_id")
            .run()

        // Station assignee replacements (when assignee_action = 2 / replace)
        try await sql.create(table: "station_assignee_replacements")
            .column("id", type: .int, .primaryKey)
            .column("station_id", type: .int)
            .column("operator_id", type: .int)
            .foreignKey(["station_id"], references: "stations", ["id"], onDelete: .cascade)
            .foreignKey(["operator_id"], references: "operators", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "station_assignee_replacements_station_id_idx")
            .on("station_assignee_replacements")
            .column("station_id")
            .run()

        // MARK: - Station Notification Triggers

        try await sql.create(table: "station_notification_triggers")
            .column("id", type: .int, .primaryKey)
            .column("station_id", type: .int)
            // StationTriggerEvent: 0 = onEnter, 1 = onExit
            .column("event", type: .int)
            .column("message", type: .text)
            .foreignKey(["station_id"], references: "stations", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "station_notification_triggers_station_id_idx")
            .on("station_notification_triggers")
            .column("station_id")
            .run()

        // Station notification trigger operators (many-to-many)
        try await sql.create(table: "station_notification_trigger_operators")
            .column("id", type: .int, .primaryKey)
            .column("station_notification_trigger_id", type: .int)
            .column("operator_id", type: .int)
            .foreignKey(["station_notification_trigger_id"], references: "station_notification_triggers", ["id"], onDelete: .cascade)
            .foreignKey(["operator_id"], references: "operators", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "station_notification_trigger_operators_trigger_id_idx")
            .on("station_notification_trigger_operators")
            .column("station_notification_trigger_id")
            .run()

        // MARK: - Station Script Triggers

        try await sql.create(table: "station_script_triggers")
            .column("id", type: .int, .primaryKey)
            .column("station_id", type: .int)
            // StationTriggerEvent: 0 = onEnter, 1 = onExit
            .column("event", type: .int)
            .column("script", type: .text)
            .foreignKey(["station_id"], references: "stations", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "station_script_triggers_station_id_idx")
            .on("station_script_triggers")
            .column("station_id")
            .run()

        // MARK: - Operations

        try await sql.create(table: "operations")
            .column("id", type: .int, .primaryKey)
            .column("station_id", type: .int)
            .column("sort_order", type: .int)
            .column("name", type: .text)
            // agent_id references operators.id (must be OperatorType.agent)
            .column("agent_id", type: .int)
            // SupplyRequest discriminator: NULL = none, 0 = inventory, 1 = supply, 2 = workUnits
            .column("supply_request_type", type: .int)
            // When supply_request_type = 0 (inventory)
            .column("supply_request_inventory_id", type: .int)
            .column("supply_request_amount", type: .int)
            // When supply_request_type = 1 (supply)
            .column("supply_request_supply_id", type: .int)
            // When supply_request_type = 2 (workUnits)
            .column("supply_request_intake_queue_id", type: .int)
            .foreignKey(["station_id"], references: "stations", ["id"], onDelete: .cascade)
            .foreignKey(["agent_id"], references: "operators", ["id"], onDelete: .setNull)
            .run()
        try await sql.create(index: "operations_station_id_idx")
            .on("operations")
            .column("station_id")
            .run()

        // MARK: - Work Units

        try await sql.create(table: "work_units")
            .column("id", type: .int, .primaryKey)
            .column("intake_queue_id", type: .int)
            .column("creator_operator_id", type: .int)
            .column("reporter_operator_id", type: .int)
            .column("name", type: .text)
            .column("on_hold", type: .smallint)
            .column("output_reason_id", type: .int)
            // ParentWorkUnit discriminator: NULL = no parent, 0 = operationWorkUnit, 1 = parentWorkUnit
            .column("parent_type", type: .int)
            // When parent_type = 0 (operationWorkUnit)
            .column("parent_operation_id", type: .int)
            .column("parent_operation_work_unit_id", type: .int)
            // When parent_type = 1 (parentWorkUnit)
            .column("parent_work_unit_id", type: .int)
            // Expedite
            .column("expedite_create_date", type: .timestamp)
            .column("expedite_by_operator_id", type: .int)
            // LineState columns (cf. LineState enum)
            .column("line_state_intake_queue_id", type: .int)
            .column("line_state_station_id", type: .int)
            .column("line_state_operation_id", type: .int)
            // OperationStatus: 0=waiting, 1=inProgress, 2=error, 3=finished
            .column("line_state_operation_status", type: .int)
            .column("line_state_operation_status_message", type: .text)
            .column("line_state_output_id", type: .int)
            .foreignKey(["intake_queue_id"], references: "intake_queues", ["id"], onDelete: .cascade)
            .foreignKey(["creator_operator_id"], references: "operators", ["id"], onDelete: .restrict)
            .foreignKey(["reporter_operator_id"], references: "operators", ["id"], onDelete: .restrict)
            .foreignKey(["output_reason_id"], references: "output_reasons", ["id"], onDelete: .setNull)
            .foreignKey(["parent_work_unit_id"], references: "work_units", ["id"], onDelete: .setNull)
            .foreignKey(["parent_operation_work_unit_id"], references: "work_units", ["id"], onDelete: .setNull)
            .run()
        try await sql.create(index: "work_units_intake_queue_id_idx")
            .on("work_units")
            .column("intake_queue_id")
            .run()
        try await sql.create(index: "work_units_creator_operator_id_idx")
            .on("work_units")
            .column("creator_operator_id")
            .run()
        try await sql.create(index: "work_units_parent_work_unit_id_idx")
            .on("work_units")
            .column("parent_work_unit_id")
            .run()

        // Work unit assignees (many-to-many)
        try await sql.create(table: "work_unit_assignees")
            .column("id", type: .int, .primaryKey)
            .column("work_unit_id", type: .int)
            .column("operator_id", type: .int)
            .foreignKey(["work_unit_id"], references: "work_units", ["id"], onDelete: .cascade)
            .foreignKey(["operator_id"], references: "operators", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "work_unit_assignees_work_unit_id_idx")
            .on("work_unit_assignees")
            .column("work_unit_id")
            .run()

        // returnToStation: ordered list of Station.IDs for a WorkUnit (FILO)
        try await sql.create(table: "work_unit_return_stations")
            .column("id", type: .int, .primaryKey)
            .column("work_unit_id", type: .int)
            .column("station_id", type: .int)
            // Position in the FILO stack; higher sort_order = pushed later
            .column("sort_order", type: .int)
            .foreignKey(["work_unit_id"], references: "work_units", ["id"], onDelete: .cascade)
            .foreignKey(["station_id"], references: "stations", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "work_unit_return_stations_work_unit_id_idx")
            .on("work_unit_return_stations")
            .column("work_unit_id")
            .run()

        // MARK: - Work Unit Logs

        try await sql.create(table: "work_unit_logs")
            .column("id", type: .bigint, .primaryKey)
            .column("work_unit_id", type: .int)
            .column("line_id", type: .int)
            // Columns mirror LineState enum
            .column("intake_queue_id", type: .int)
            .column("station_id", type: .int)
            .column("operation_id", type: .int)
            // OperationStatus raw value
            .column("operation_status", type: .int)
            .column("operation_status_message", type: .text)
            .column("output_id", type: .int)
            .column("enter_date", type: .timestamp)
            .column("exit_date", type: .timestamp)
            .foreignKey(["work_unit_id"], references: "work_units", ["id"], onDelete: .cascade)
            .foreignKey(["line_id"], references: "lines", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "work_unit_logs_work_unit_id_idx")
            .on("work_unit_logs")
            .column("work_unit_id")
            .run()
        try await sql.create(index: "work_unit_logs_line_id_idx")
            .on("work_unit_logs")
            .column("line_id")
            .run()

        // MARK: - Work Unit Comments

        try await sql.create(table: "work_unit_comments")
            .column("id", type: .int, .primaryKey)
            .column("work_unit_id", type: .int)
            .column("parent_work_unit_comment_id", type: .int)
            .column("create_date", type: .timestamp)
            .column("operator_id", type: .int)
            .column("text", type: .text)
            .foreignKey(["work_unit_id"], references: "work_units", ["id"], onDelete: .cascade)
            .foreignKey(["parent_work_unit_comment_id"], references: "work_unit_comments", ["id"], onDelete: .setNull)
            .foreignKey(["operator_id"], references: "operators", ["id"], onDelete: .restrict)
            .run()
        try await sql.create(index: "work_unit_comments_work_unit_id_idx")
            .on("work_unit_comments")
            .column("work_unit_id")
            .run()

        try await sql.create(table: "work_unit_comment_emojis")
            .column("id", type: .int, .primaryKey)
            .column("work_unit_comment_id", type: .int)
            .column("create_date", type: .timestamp)
            .column("operator_id", type: .int)
            .column("emoji", type: .text)
            .foreignKey(["work_unit_comment_id"], references: "work_unit_comments", ["id"], onDelete: .cascade)
            .foreignKey(["operator_id"], references: "operators", ["id"], onDelete: .restrict)
            .run()
        try await sql.create(index: "work_unit_comment_emojis_comment_id_idx")
            .on("work_unit_comment_emojis")
            .column("work_unit_comment_id")
            .run()

        // MARK: - Operation Comments

        try await sql.create(table: "operation_comments")
            .column("id", type: .int, .primaryKey)
            .column("operation_id", type: .int)
            .column("parent_work_unit_comment_id", type: .int)
            .column("create_date", type: .timestamp)
            .column("operator_id", type: .int)
            .column("text", type: .text)
            .foreignKey(["operation_id"], references: "operations", ["id"], onDelete: .cascade)
            .foreignKey(["parent_work_unit_comment_id"], references: "work_unit_comments", ["id"], onDelete: .setNull)
            .foreignKey(["operator_id"], references: "operators", ["id"], onDelete: .restrict)
            .run()
        try await sql.create(index: "operation_comments_operation_id_idx")
            .on("operation_comments")
            .column("operation_id")
            .run()

        try await sql.create(table: "operation_comment_emojis")
            .column("id", type: .int, .primaryKey)
            .column("operation_comment_id", type: .int)
            .column("create_date", type: .timestamp)
            .column("operator_id", type: .int)
            .column("emoji", type: .text)
            .foreignKey(["operation_comment_id"], references: "operation_comments", ["id"], onDelete: .cascade)
            .foreignKey(["operator_id"], references: "operators", ["id"], onDelete: .restrict)
            .run()
        try await sql.create(index: "operation_comment_emojis_comment_id_idx")
            .on("operation_comment_emojis")
            .column("operation_comment_id")
            .run()

        // MARK: - Work Unit Notification Triggers

        try await sql.create(table: "work_unit_notification_triggers")
            .column("id", type: .int, .primaryKey)
            .column("work_unit_id", type: .int)
            // OnEnterEvent flags (stored as individual columns for clarity)
            .column("event_intake_queue", type: .smallint)
            .column("event_station", type: .smallint)
            .column("event_operation", type: .smallint)
            .column("event_output", type: .smallint)
            .foreignKey(["work_unit_id"], references: "work_units", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "work_unit_notification_triggers_work_unit_id_idx")
            .on("work_unit_notification_triggers")
            .column("work_unit_id")
            .run()

        // Operators for work unit notification triggers (many-to-many)
        try await sql.create(table: "work_unit_notification_trigger_operators")
            .column("id", type: .int, .primaryKey)
            .column("work_unit_notification_trigger_id", type: .int)
            .column("operator_id", type: .int)
            .foreignKey(["work_unit_notification_trigger_id"], references: "work_unit_notification_triggers", ["id"], onDelete: .cascade)
            .foreignKey(["operator_id"], references: "operators", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "work_unit_notification_trigger_operators_trigger_id_idx")
            .on("work_unit_notification_trigger_operators")
            .column("work_unit_notification_trigger_id")
            .run()

        // MARK: - Work Unit Supplies

        try await sql.create(table: "work_unit_supplies")
            .column("id", type: .int, .primaryKey)
            .column("work_unit_id", type: .int)
            .column("supply_id", type: .int)
            .column("create_date", type: .timestamp)
            .column("fulfilled_date", type: .timestamp)
            .column("fulfilled_by_operator_id", type: .int)
            .column("waivable", type: .smallint)
            .column("waived", type: .smallint)
            .foreignKey(["work_unit_id"], references: "work_units", ["id"], onDelete: .cascade)
            .foreignKey(["supply_id"], references: "supplies", ["id"], onDelete: .restrict)
            .foreignKey(["fulfilled_by_operator_id"], references: "operators", ["id"], onDelete: .setNull)
            .run()
        try await sql.create(index: "work_unit_supplies_work_unit_id_idx")
            .on("work_unit_supplies")
            .column("work_unit_id")
            .run()

        // MARK: - Work Unit Supply Field Values

        try await sql.create(table: "work_unit_supply_field_values")
            .column("id", type: .int, .primaryKey)
            .column("work_unit_supply_id", type: .int)
            .column("supply_field_id", type: .int)
            // SupplyFieldValue discriminator: 0=text, 1=textArea, 2=number, 3=url, 4=photo, 5=file, 6=radio, 7=multiSelect, 8=intakeQueue, 9=workUnit
            .column("value_type", type: .int)
            // Scalar value (text, textArea, number as text, url, photo url)
            .column("value_text", type: .text)
            // For file: the file name
            .column("value_file_name", type: .text)
            // For radio: SelectedFieldOptionValue.id
            .column("value_selected_option_id", type: .int)
            // For multiSelect: JSON array of SelectedFieldOptionValue IDs
            .column("value_selected_option_ids", type: .text)
            // For intakeQueue: IntakeQueue.ID
            .column("value_intake_queue_id", type: .int)
            // For workUnit: WorkUnit.ID
            .column("value_work_unit_id", type: .int)
            .foreignKey(["work_unit_supply_id"], references: "work_unit_supplies", ["id"], onDelete: .cascade)
            .foreignKey(["supply_field_id"], references: "supply_fields", ["id"], onDelete: .restrict)
            .run()
        try await sql.create(index: "work_unit_supply_field_values_supply_id_idx")
            .on("work_unit_supply_field_values")
            .column("work_unit_supply_id")
            .run()

        // MARK: - Hoppers

        try await sql.create(table: "hoppers")
            .column("id", type: .int, .primaryKey)
            .column("line_id", type: .int)
            // NULL when no work unit is suggested
            .column("work_unit_id", type: .int)
            .foreignKey(["line_id"], references: "lines", ["id"], onDelete: .cascade)
            .foreignKey(["work_unit_id"], references: "work_units", ["id"], onDelete: .setNull)
            .run()
        try await sql.create(index: "hoppers_line_id_idx")
            .on("hoppers")
            .column("line_id")
            .run()

        // MARK: - Finished Products

        try await sql.create(table: "finished_products")
            .column("id", type: .int, .primaryKey)
            .column("supply_id", type: .int)
            .column("inventory_id", type: .int)
            .column("amount", type: .int)
            .column("facility_code", type: .text)
            .column("line_id", type: .int)
            .column("manufacture_date", type: .timestamp)
            .column("expiration_date", type: .timestamp)
            .column("lot_number", type: .int)
            .column("batch_number", type: .int)
            .column("serial_number", type: .text)
            .foreignKey(["line_id"], references: "lines", ["id"], onDelete: .restrict)
            .run()
        try await sql.create(index: "finished_products_line_id_idx")
            .on("finished_products")
            .column("line_id")
            .run()
        try await sql.create(index: "finished_products_supply_id_idx")
            .on("finished_products")
            .column("supply_id")
            .run()

        // MARK: - Station Inventory Buffers

        try await sql.create(table: "station_inventory_buffers")
            .column("id", type: .int, .primaryKey)
            .column("station_id", type: .int)
            .column("minimum", type: .int)
            .column("maximum", type: .int)
            .column("current", type: .int)
            .foreignKey(["station_id"], references: "stations", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "station_inventory_buffers_station_id_idx")
            .on("station_inventory_buffers")
            .column("station_id")
            .run()

        try await sql.create(table: "station_inventory_buffer_trays")
            .column("id", type: .int, .primaryKey)
            .column("station_inventory_buffer_id", type: .int)
            .column("inventory_id", type: .int)
            .column("amount", type: .int)
            .foreignKey(["station_inventory_buffer_id"], references: "station_inventory_buffers", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "station_inventory_buffer_trays_buffer_id_idx")
            .on("station_inventory_buffer_trays")
            .column("station_inventory_buffer_id")
            .run()

        try await sql.create(table: "station_inventory_buffer_open_requests")
            .column("id", type: .int, .primaryKey)
            .column("station_inventory_buffer_id", type: .int)
            .column("create_date", type: .timestamp)
            .column("fulfilled_date", type: .timestamp)
            .foreignKey(["station_inventory_buffer_id"], references: "station_inventory_buffers", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "station_inventory_buffer_open_requests_buffer_id_idx")
            .on("station_inventory_buffer_open_requests")
            .column("station_inventory_buffer_id")
            .run()

        // Database: 1-to-many — WorkUnits associated to an OpenRequest
        try await sql.create(table: "open_request_work_units")
            .column("id", type: .int, .primaryKey)
            .column("open_request_id", type: .int)
            .column("work_unit_id", type: .int)
            .foreignKey(["open_request_id"], references: "station_inventory_buffer_open_requests", ["id"], onDelete: .cascade)
            .foreignKey(["work_unit_id"], references: "work_units", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "open_request_work_units_open_request_id_idx")
            .on("open_request_work_units")
            .column("open_request_id")
            .run()

        // MARK: - Supplier Contacts

        try await sql.create(table: "supplier_contacts")
            .column("id", type: .int, .primaryKey)
            .column("supplier_id", type: .int)
            .column("name", type: .text)
            .column("phone_number", type: .text)
            .column("fax_number", type: .text)
            .column("email", type: .text)
            .run()
        try await sql.create(index: "supplier_contacts_supplier_id_idx")
            .on("supplier_contacts")
            .column("supplier_id")
            .run()

        // MARK: - Suppliers

        try await sql.create(table: "suppliers")
            .column("id", type: .int, .primaryKey)
            .column("name", type: .text)
            .run()

        // Back-fill FK on supplier_contacts now that suppliers table exists
        // (SQLite doesn't enforce FK order at DDL time, so this is safe)

        // MARK: - Supplier Supplies

        try await sql.create(table: "supplier_supplies")
            .column("id", type: .int, .primaryKey)
            .column("supplier_id", type: .int)
            .column("supply_id", type: .int)
            .column("lead_time", type: .int)
            .column("max_order_quantity", type: .int)
            .foreignKey(["supplier_id"], references: "suppliers", ["id"], onDelete: .cascade)
            .foreignKey(["supply_id"], references: "supplies", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "supplier_supplies_supplier_id_idx")
            .on("supplier_supplies")
            .column("supplier_id")
            .run()
        try await sql.create(index: "supplier_supplies_supply_id_idx")
            .on("supplier_supplies")
            .column("supply_id")
            .run()

        // MARK: - Inventories

        try await sql.create(table: "inventories")
            .column("id", type: .int, .primaryKey)
            .column("supply_id", type: .int)
            .column("in_stock", type: .int)
            .column("reorder_point", type: .int)
            .column("estimated_reorder_point", type: .timestamp)
            .foreignKey(["supply_id"], references: "supplies", ["id"], onDelete: .restrict)
            .run()
        try await sql.create(index: "inventories_supply_id_idx")
            .on("inventories")
            .column("supply_id")
            .run()

        /// Inventory providers: either an external Supplier (via SupplierSupply) or an internal IntakeQueue.
        try await sql.create(table: "inventory_providers")
            .column("id", type: .int, .primaryKey)
            .column("inventory_id", type: .int)
            .column("preference", type: .int)
            // Provider type: 0 = supplier, 1 = intakeQueue
            .column("provider_type", type: .int)
            .column("supplier_supply_id", type: .int)
            .column("intake_queue_id", type: .int)
            .foreignKey(["inventory_id"], references: "inventories", ["id"], onDelete: .cascade)
            .foreignKey(["supplier_supply_id"], references: "supplier_supplies", ["id"], onDelete: .setNull)
            .foreignKey(["intake_queue_id"], references: "intake_queues", ["id"], onDelete: .setNull)
            .run()
        try await sql.create(index: "inventory_providers_inventory_id_idx")
            .on("inventory_providers")
            .column("inventory_id")
            .run()

        // MARK: - Flow Metrics

        try await sql.create(table: "line_flow_metrics")
            .column("id", type: .int, .primaryKey)
            .column("line_id", type: .int)
            .column("create_date", type: .timestamp)
            .column("operating_time", type: .int)
            .column("lead_time", type: .int)
            .column("value", type: .real)
            .column("performance_efficiency", type: .real)
            .column("total_work_units_completed", type: .int)
            .column("num_operators", type: .real)
            .column("takt_time", type: .int)
            .column("completed_work_units", type: .int)
            .foreignKey(["line_id"], references: "lines", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "line_flow_metrics_line_id_idx")
            .on("line_flow_metrics")
            .column("line_id")
            .run()
        try await sql.create(index: "line_flow_metrics_create_date_idx")
            .on("line_flow_metrics")
            .column("create_date")
            .run()

        try await sql.create(table: "station_flow_metrics")
            .column("id", type: .int, .primaryKey)
            .column("station_id", type: .int)
            .column("create_date", type: .timestamp)
            .column("cycle_time", type: .int)
            .foreignKey(["station_id"], references: "stations", ["id"], onDelete: .cascade)
            .run()
        try await sql.create(index: "station_flow_metrics_station_id_idx")
            .on("station_flow_metrics")
            .column("station_id")
            .run()
    }
}
