/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

class NotificationService: NotificationProvider {
    func saveNotification(session: Database.Session, bundleId: String, controllerName: String, deepLink: String?, title: String?, body: String?, metadata: [String : String]?, userId: UserID, persist: Bool) async throws -> Notification {
        .init(id: 0, bundleId: bundleId, controllerName: controllerName, deepLink: deepLink, title: title, body: body, metadata: metadata, userId: userId, persist: persist, seen: false)
    }
}
