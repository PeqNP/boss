/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import bosslib
import Smtp
import Vapor
import VaporToOpenAPI

private enum Constant {
    static let scope = "scope"
    static let aclCatalogName = "web"
}

func routes(_ app: Application) throws {
    app.logger.info("Environment (\(app.environment.name))")
    app.logger.info("Log Level (\(app.logger.logLevel))")
    
    boss.log.setLevel(Global.logLevel)
    
    if boss.config.smtp.enabled {
        app.smtp.configuration.hostname = boss.config.smtp.host
        app.smtp.configuration.port = boss.config.smtp.port
        app.smtp.configuration.secure = .startTls
        app.smtp.configuration.signInMethod = .credentials(
            username: boss.config.smtp.username,
            password: boss.config.smtp.password
        )
    }
    
    /// UI testing not available in production
    if !app.environment.isRelease {
        app.group("debug") { debug in
            /// Reset database to an empty state.
            /// Used for UI testing.
            debug.get("uitests", ":storage") { req in
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
            debug.put("uitests", "snapshot", ":snapshot") { req in
                guard let snapshot = req.parameters.get("snapshot")?.trimmingCharacters(in: .whitespacesAndNewlines), !snapshot.isEmpty else {
                    throw api.error.InvalidParameter(name: "snapshot")
                }
                try boss.saveSnapshot(name: snapshot)
                return HTTPStatus.ok
            }
            
            /// Recovers a database snapshot
            debug.get("uitests", "snapshot", ":snapshot") { req in
                guard let snapshot = req.parameters.get("snapshot")?.trimmingCharacters(in: .whitespacesAndNewlines), !snapshot.isEmpty else {
                    throw api.error.InvalidParameter(name: "snapshot")
                }
                try await boss.loadSnapshot(name: snapshot)
                return HTTPStatus.ok
            }
            
            // Mapped from /private/send
            // TODO: Is there a way to re-route this to the `/private/send/notifications` API? Rather than duplicating the logic?
            debug.group("send") { notification in
                notification.post("notifications") { req in
                    let form = try req.content.decode(PrivateForm.SendNotifications.self)
                    var notifications = [bosslib.Notification]()
                    for notif in form.notifications {
                        let n = try await api.notification.saveNotification(
                            bundleId: notif.bundleId,
                            controllerName: notif.controllerName,
                            deepLink: notif.deepLink,
                            title: notif.title,
                            body: notif.body,
                            metadata: notif.metadata,
                            userId: notif.userId,
                            persist: notif.persist
                        )
                        notifications.append(n)
                    }
                    await ConnectionManager.shared.sendNotifications(notifications)
                    return Fragment.OK()
                }.openAPI(
                    summary: "Send notification(s) to user(s)",
                    body: .type(PrivateForm.SendNotifications.self),
                    contentType: .application(.json),
                    response: .type(Fragment.OK.self),
                    responseContentType: .application(.json)
                )
                .addScope(.user)
                
                notification.post("events") { req in
                    let form = try req.content.decode(PrivateForm.SendEvents.self)
                    await ConnectionManager.shared.sendEvents(form.events)
                    return Fragment.OK()
                }.openAPI(
                    summary: "Send event(s) to user(s)",
                    body: .type(PrivateForm.SendEvents.self),
                    contentType: .application(.json),
                    response: .type(Fragment.OK.self),
                    responseContentType: .application(.json)
                )
                .addScope(.user)
            }
        }
    }
    
    registerAccount(app)
    registerPrivate(app)
    registerSlack(app)
    registerTestManagement(app)
    registerFriend(app)
    registerNotification(app)

    /// This is called by the client, to the internal Python app @ `/api/heartbeat`, then to this Swift server, to determine if all services are running.
    app.get("heartbeat") { req in
        let isSignedIn: Bool
        do {
            _ = try await verifyAccess(req, refreshToken: false)
            isSignedIn = true
        } catch {
            isSignedIn = false
        }
        return Fragment.Heartbeat(
            isSignedIn: isSignedIn,
            isSecurityEnabled: Global.isSecurityEnabled
        )
    }.openAPI(
        summary: "Check if server is online",
        description: "This is used to determine if the server is online and the user's session is valid. This has no affect on extending the user's session. The user's session is refreshed only when the user performs a mouse/keyboard event or accesses a secure endpoint.",
        response: .type(Fragment.Heartbeat.self),
        responseContentType: .application(.json)
    )

    app.get("version") { req -> String in
        try api.version()
    }.openAPI(
        summary: "BOSS server version"
    )

    // Provides Swagger documentation.
    app.get("swagger.json") { req in
        req.application.routes.openAPI(
            info: InfoObject(
                title: "BOSS API - OpenAPI 3.0",
                description: "BOSS services based on the OpenAPI 3.0.1 specification.",
                termsOfService: URL(string: "https://smartbear.com/terms-of-use/"),
                contact: ContactObject(
                    email: "bitheadrl@protonmail.com"
                ),
                license: LicenseObject(
                    name: "MIT",
                    url: URL(string: "/LICENSE.txt")
                ),
                version: Version(1, 0, 0)
            ),
            externalDocs: ExternalDocumentationObject(
                description: "Find out more about Swagger",
                url: URL(string: "https://swagger.io/")!
            )
        )
    }.excludeFromOpenAPI()

    // Necessary to provide custom error handling
    app.middleware = .init()
    app.middleware.use(RouteLoggingMiddleware(logLevel: .info))

    // Error handling
    app.middleware.use(ErrorHandlingMiddleware())
    // ACL
    app.middleware.use(ACLMiddleware())
    registerACLScopes(for: app)

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

// MARK: - Error Handling

private func makeErrorResponse(status: HTTPResponseStatus, error: Error) -> Response {
    var headers: HTTPHeaders = [:]
    headers.contentType = .plainText
    return Response(status: .unauthorized, headers: headers, body: .init(stringLiteral: error.localizedDescription))
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
            case _ as api.error.InvalidJWT,
                 _ as api.error.UserNotFoundInSessionStore:
                return makeErrorResponse(status: .unauthorized, error: error.localizedDescription)
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

// MARK: - ACL

/// This is an intermediary structure used when registering an ACL catalog.
public enum ACLScope: Equatable, Sendable {
    /// The signed in user must be an admin
    case admin
    /// A signed in user is required to access the service
    case user
    /// Used when an app only cares that the user has access to use the app
    case app(BundleID)
    /// Used when needing to provide more granular control over features within an app. Expects value to be in "FeatureName.Permission" format.
    case feature(BundleID, ACLFeature)
    
    var isAdmin: Bool {
        switch self {
        case .admin:
            true
        case .user, .app, .feature:
            false
        }
    }
    
    /// Creates an ACLKey used to verify the user against for all web resources
    public func key() -> ACLKey? {
        switch self {
        case .admin:
            nil
        case .user:
            nil
        case let .app(bundleId):
            .init(catalog: Constant.aclCatalogName, bundleId: bundleId, feature: nil)
        case let .feature(bundleId, feature):
            .init(catalog: Constant.aclCatalogName, bundleId: bundleId, feature: feature)
        }
    }
        
    /// Add a `.feature` to an `.app` scope.
    /// This is a convenience method used when building route permissions.
    public func feature(_ feature: String) -> ACLScope {
        switch self {
        case .admin:
            boss.log.w("Can not add feature to .admin scope")
            return self
        case .user:
            boss.log.w("Can not add feature to .user scope")
            return self
        case let .app(bundleId):
            return .feature(bundleId, feature)
        case .feature:
            boss.log.w("Can not add feature to .feature scope")
            return self
        }
    }
}

/// Register all of the Swift+Vapor's app ACL scopes.
private func registerACLScopes(for app: Application) {
    var catalog = [String: Set<String>]()
    for route in app.routes.all {
        guard let route = route.userInfo[Constant.scope] as? RouteScope else {
            continue
        }
        switch route.scope {
        case .admin:
            break
        case .user:
            break
        case let .app(bundleId):
            if catalog.index(forKey: bundleId) == nil {
                catalog[bundleId] = []
            }
        case let .feature(bundleId, featureName):
            if catalog.index(forKey: bundleId) == nil {
                catalog[bundleId] = []
            }
            catalog[bundleId]?.insert(featureName)
        }
    }
    
    var apps = [ACLApp]()
    for (bundleId, features) in catalog {
        apps.append(.init(bundleId: bundleId, features: features))
    }
    Task { @MainActor in
        try await bosslib.api.acl.createAclCatalog(for: Constant.aclCatalogName, apps: apps)
    }
}

struct AuthenticatedUserKey: StorageKey {
    typealias Value = AuthenticatedUser
}

struct RouteScope: Sendable {
    let scope: ACLScope
    let verifyMFAChallenge: Bool
}

extension RoutesBuilder {
    func makeAclApp(_ bundleId: String) -> ACLApp {
        return ACLApp(bundleId: bundleId, features: [])
    }
}

extension Route {
    /// Add ACL scope to a route
    @discardableResult
    func addScope(_ scope: ACLScope, verifyMFAChallenge: Bool = true) -> Self {
        userInfo[Constant.scope] = RouteScope(scope: scope, verifyMFAChallenge: verifyMFAChallenge)
        return self
    }
}

extension Request {
    var authUser: AuthenticatedUser {
        get throws {
            guard let u = storage[AuthenticatedUserKey.self] else {
                let path = route?.path.map { part -> String in "\(part)" }.joined(separator: "/")
                boss.log.c("Route (\(path ?? "unknown")) is not configured for ACL")
                throw Abort(.forbidden, reason: "Route is not configured for ACL")
            }
            return u
        }
    }
}

struct ACLMiddleware: AsyncMiddleware {
    func respond(to request: Vapor.Request, chainingTo next: any Vapor.AsyncResponder) async throws -> Vapor.Response {
        guard let route = request.route else {
            return try await next.respond(to: request)
        }
        
        guard let scope = route.userInfo[Constant.scope] as? RouteScope else {
            // No ACL set on route → allow
            return try await next.respond(to: request)
        }

        do {
            let auth = try await verifyAccess(
                request,
                requireSuperAdmin: scope.scope.isAdmin,
                acl: scope.scope.key()
            )
            
            // NOTE: This records new activity only when the user accesses a secure endpoint (or heartbeat). Luckily, many endpoints ask for the current user, and the client heartbeat is configured to be sent every ~2 minutes. This behavior ensures the user is not prematurely signed out because they hit no secure endpoints after N minutes. Ideally, the activity is updated regardless of the endpoint being called. Secure or not. However, we don't know who the user is until they hit an endpoint that requires verification.
            await ConnectionManager.shared.recordActivity(for: auth.user.id)
            
            request.storage[AuthenticatedUserKey.self] = auth
            return try await next.respond(to: request)
        }
        catch {
            switch error {
            case _ as Abort:
                throw error
            case _ as api.error.UserSessionExpiredDueToInactivity:
                throw Abort(.unauthorized, reason: error.localizedDescription)
            case _ as api.error.AccessDenied:
                throw Abort(.forbidden, reason: error.localizedDescription)
            default:
                throw error // Not a verification/permissions issue
            }
        }
    }
}
