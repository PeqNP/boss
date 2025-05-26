/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import bosslib
import Vapor
import VaporToOpenAPI

func routes(_ app: Application) throws {
    app.logger.info("Environment (\(app.environment.name))")
    app.logger.info("Log Level (\(app.logger.logLevel))")
    
    /// UI testing not available in production
    if !app.environment.isRelease {
        /// Reset database to an empty state.
        /// Used for UI testing.
        app.get("uitests", ":storage") { req in
            let storage = req.parameters.get("storage")
            switch storage {
            case "memory":
                try await boss.start(storage: .memory)
            case "automatic":
                try await boss.deleteDatabase(storage: .file(boss.config.testDatabasePath))
                try await boss.start(storage: .file(boss.config.testDatabasePath))
            default:
                try await boss.deleteDatabase(storage: .file(boss.config.testDatabasePath))
                try await boss.start(storage: .file(boss.config.testDatabasePath))
            }
            return HTTPStatus.ok
        }.excludeFromOpenAPI()
        
        /// Creates a snapshot of the database
        app.put("uitests", "snapshot", ":snapshot") { req in
            guard let snapshot = req.parameters.get("snapshot")?.trimmingCharacters(in: .whitespacesAndNewlines), !snapshot.isEmpty else {
                throw api.error.InvalidParameter(name: "snapshot")
            }
            try boss.saveSnapshot(name: snapshot)
            return HTTPStatus.ok
        }
        
        /// Recovers a database snapshot
        app.get("uitests", "snapshot", ":snapshot") { req in
            guard let snapshot = req.parameters.get("snapshot")?.trimmingCharacters(in: .whitespacesAndNewlines), !snapshot.isEmpty else {
                throw api.error.InvalidParameter(name: "snapshot")
            }
            try await boss.loadSnapshot(name: snapshot)
            return HTTPStatus.ok
        }
    }
    
    registerAccount(app)
    registerAgent(app)
    registerNode(app)
    registerSlack(app)
    registerTestManagement(app)

    /// This is called by the internal Python app @ `/api/heartbeat` to determine if this Swift service is running and the user is signed in.
    app.get("heartbeat") { req in
        let isSignedIn: Bool
        do {
            _ = try await verifyAccess(cookie: req, refreshToken: false)
            isSignedIn = true
        } catch {
            isSignedIn = false
        }
        return Fragment.Heartbeat(isSignedIn: isSignedIn)
    }.openAPI(
        summary: "Test @ys user session.",
        description: "Used to test if the @ays server is running and whether the user is signed in.",
        response: .type(Fragment.Heartbeat.self),
        responseContentType: .application(.json)
    )

    app.get("version") { req -> String in
        try api.version()
    }.openAPI(
        summary: "@ys server version."
    )

    // Provides Swagger documentation.
    app.get("swagger.json") { req in
        req.application.routes.openAPI(
            info: InfoObject(
                title: "Swagger @ys - OpenAPI 3.0",
                description: "@ys services based on the OpenAPI 3.0.1 specification.",
                termsOfService: URL(string: "http://swagger.io/terms/"),
                contact: ContactObject(
                    email: "apiteam@swagger.io"
                ),
                license: LicenseObject(
                    name: "MIT",
                    url: URL(string: "/license")
                ),
                version: Version(1, 0, 17)
            ),
            externalDocs: ExternalDocumentationObject(
                description: "Find out more about Swagger",
                url: URL(string: "http://swagger.io")!
            )
        )
    }.excludeFromOpenAPI()

    // Necessary to provide custom error handling
    app.middleware = .init()
    app.middleware.use(RouteLoggingMiddleware(logLevel: .info))

    // Error handling
    app.middleware.use(ErrorHandlingMiddleware())

    // Serves documentation and all other assets required by webserver such as JS/CSS/etc.
    /**
     * Now handled by nginx --
     *
    let docsFiles = FileMiddleware(
        publicDirectory: boss.config.mediaPath,
        defaultFile: "index.html"
    )
    app.middleware.use(docsFiles)
     */

    let encoder = JSONEncoder()
    encoder.outputFormatting = .sortedKeys
    ContentConfiguration.global.use(encoder: encoder, for: .json)
}

struct ErrorHandlingMiddleware: Middleware {
    /// The reason there is an `error` var is to mitigate the possibility of any other structure having a name conflict.
    struct ErrorResponse: Encodable {
        struct Error: Encodable {
            let status: HTTPResponseStatus
            let message: String
        }
        
        static func make(status: HTTPResponseStatus, message: String) -> ErrorResponse {
            .init(error: .init(status: status, message: message))
        }
        
        let error: ErrorResponse.Error
    }

    func respond(to request: Request, chainingTo next: Responder) -> EventLoopFuture<Response> {
        next.respond(to: request).flatMapErrorThrowing { error in
            let source: ErrorSource = .capture()
            request.logger.report(error: error, file: source.file, function: source.function, line: source.line)
            let message: String
            
            switch error {
            case _ as api.error.InvalidJWT:
                // Session expired
                return request.redirect(to: "/")
                
            case let bossError as any BOSSError:
                message = bossError.description
                
            default:
                message = "Unexpected error \(String(describing: error))"
            }
            
            var headers: HTTPHeaders = [:]
            let body: Response.Body
            do {
                body = .init(
                    buffer: try JSONEncoder().encodeAsByteBuffer(ErrorResponse.make(status: .internalServerError, message: message), allocator: request.byteBufferAllocator),
                    byteBufferAllocator: request.byteBufferAllocator
                )
                headers.contentType = .json
            } catch {
                body = .init(string: "Error encountered (\(String(describing: error))) while encoding error (\(message))", byteBufferAllocator: request.byteBufferAllocator)
                headers.contentType = .plainText
            }
            return Response(status: .ok, headers: headers, body: body)
        }
    }
}
