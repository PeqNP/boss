/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import bosslib
import Foundation
import Vapor

// FIXME: `AgentPayload` may need to be part of `web` to silence these warnings
extension AgentPayload: @retroactive AsyncResponseEncodable {}
extension AgentPayload: @retroactive AsyncRequestDecodable {}
extension AgentPayload: @retroactive ResponseEncodable {}
extension AgentPayload: @retroactive RequestDecodable {}
extension AgentPayload: @retroactive Content { }

/// Register the `/account/` routes.
public func registerAgent(_ app: Application) {
    app.group("agent") { group in
        group.post { req async throws -> HTTPResponseStatus in
            let payload = try req.content.decode(AgentPayload.self)
            try bosslib.api.agent.ingestAgentPayload(payload)
            return HTTPStatus.noContent
        }.openAPI(
            summary: "Ingest agent messages.",
            description: "This provides a way for services, or hardware devices, to send signals directly to @ys.",
            body: .type(AgentPayload.self),
            contentType: .application(.json)
        )
    }
}
