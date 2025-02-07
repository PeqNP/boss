/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import bosslib
import NIOSSL
import Leaf
import Vapor

// configures your application
public func configure(_ app: Application) async throws {
    app.http.server.configuration.reuseAddress = true
    app.http.server.configuration.address = .hostname("0.0.0.0", port: 8081)

    // Max file upload size
    app.routes.defaultMaxBodySize = "10mb"
    
    // try await ays.start(storage: .automatic)
    // try await ays.deleteDatabase(storage: .automatic)
    try await ays.start(storage: .automatic)

    app.views.use(.leaf)
    
    let leaf = app.leaf
    leaf.tags["Null"] = NullTag()
    leaf.tags["isNil"] = IsNilTag()
    leaf.tags["jsonObject"] = JSONObjectTag()

    // register routes
    try routes(app)
}
