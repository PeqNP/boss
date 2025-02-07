/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import bosslib
import Foundation
import Vapor

/// Register the `/slack/` routes.
public func registerSlack(_ app: Application) {
    struct VerifySlackContent: Content {
        var code: String?
    }

    app.group("slack") { group in
        group.get { req async throws -> View in
            return try await req.view.render("slack/index")
        }.openAPI(
            summary: "Begin the process of registering @ys with Slack."
        )

        group.get("register") { req async throws -> View in
            let code: String
            do {
                let form = try req.query.decode(VerifySlackContent.self)
                code = try await api.account.registerSlackCode(form.code)
            }
            catch {
                return try await req.view.render("slack/error")
            }

            // TODO: https://trello.com/c/B2lDQdE4/3-integrate-with-slack
            app.logger.info("Slack registration code (\(code))")

            return try await req.view.render("slack/registered", VerifySlackContent(code: code))
        }.openAPI(
            summary: "Register a Slack account.",
            query: .type(VerifySlackContent.self)
        )
    }
}
