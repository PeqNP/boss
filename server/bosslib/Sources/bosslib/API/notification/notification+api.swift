/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

extension api {
    public nonisolated(unsafe) internal(set) static var notification = NotificationAPI(provider: NotificationService())
}

protocol NotificationProvider {
    func saveNotification(session: Database.Session, bundleId: String, controllerName: String, deepLink: String, title: String, body: String?, metadata: [String: String]?, userId: UserID, persist: Bool) async throws -> Notification
}

public class NotificationAPI {
    let provider: NotificationProvider
    
    init(provider: NotificationProvider) {
        self.provider = provider
    }
    
    public func saveNotification(
        session: Database.Session = Database.session(),
        bundleId: String,
        controllerName: String,
        deepLink: String,
        title: String,
        body: String?,
        metadata: [String: String]?,
        userId: UserID,
        persist: Bool
    ) async throws -> Notification {
        return try await provider.saveNotification(session: session, bundleId: bundleId, controllerName: controllerName, deepLink: deepLink, title: title, body: body, metadata: metadata, userId: userId, persist: persist)
    }
}
