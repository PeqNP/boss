/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import bosslib
import Vapor

extension Fragment {
    struct NotificationResponse: Content, Codable {
        enum NotificationType: Int {
            case command = 0
            case notification = 1
            case sessionIsExpiring = 2
        }
        
        static let encoder = JSONEncoder()
        
        static func command(_ command: String) -> Self {
            .init(type: 0, command: command, notifications: nil, sessionExpiresInSeconds: nil)
        }
        
        static func notifications(_ notifications: [bosslib.Notification]) -> Self {
            .init(type: 1, command: nil, notifications: notifications, sessionExpiresInSeconds: nil)
        }
        
        static func sessionIsExpiring(_ sessionExpiresInSeconds: TimeInterval) -> Self {
            .init(type: 2, command: nil, notifications: nil, sessionExpiresInSeconds: sessionExpiresInSeconds)
        }
        
        var jsonString: String? {
            guard let data = try? Self.encoder.encode(self), let string = String(data: data, encoding: .utf8) else {
                boss.log.e("Failed to encode NotificationResponse (\(self))")
                return nil
            }
            return string
        }
        
        let type: Fragment.NotificationResponse.NotificationType.RawValue
        // Response from command
        let command: String?
        // Display notifications
        let notifications: [bosslib.Notification]?
        // Amount of time until session expires, in seconds
        let sessionExpiresInSeconds: TimeInterval?
    }
}

actor ConnectionManager {
    static let shared = ConnectionManager()
    
    private var connections: [UserID: Connection] = [:]
    
    final private class Connection {
        let authUser: AuthenticatedUser
        let webSocket: WebSocket
        var timeoutTask: Task<Void, Never>?
        
        init(authUser: AuthenticatedUser, webSocket: WebSocket) {
            self.authUser = authUser
            self.webSocket = webSocket
        }
    }

    func register(_ ws: WebSocket, to authUser: AuthenticatedUser) async {
        let userId = authUser.user.id
        
        // Close old connection, if any
        if let conn = connections[userId] {
            conn.timeoutTask?.cancel()
            try? await conn.webSocket.close(code: .normalClosure)
        }
        
        // Register new connection
        let conn = Connection(authUser: authUser, webSocket: ws)
        connections[userId] = conn
        
        restartTimeout(conn: conn)
        
        ws.onText { [weak self] ws, message async in
            guard let self else { return }
            
            switch message {
            case "ping":
                boss.log.d("Client (\(userId)) pinged")
                let msg = Fragment.NotificationResponse.command("pong")
                if let str = msg.jsonString {
                    try? await ws.send(str)
                }
            case "refresh":
                boss.log.d("Client (\(userId)) requested refresh")
            default:
                boss.log.w("Client (\(userId)) sent unrecognized message (\(message))")
                return // Do not record activity
            }
            
            // Record activity, which resets session TTL
            Task { await self.recordActivity(for: userId) }
        }
        
        ws.onClose.whenComplete { [weak self] result in
            Task {
                await self?.closeConnection(for: userId)
            }
        }
    }

    /// Send message to `User`.
    func send(to userId: UserID, message: String) async {
        if let conn = connections[userId], !conn.webSocket.isClosed {
            try? await conn.webSocket.send(message)
        }
    }
    
    /// Send notification to `User`.
    func sendNotification(_ notification: bosslib.Notification) async {
        await sendNotifications([notification])
    }
    
    /// Send notifications to specific `User`.
    ///
    /// This assumes all notifications are being sent to the same `User`.
    func sendNotifications(_ notifications: [bosslib.Notification]) async {
        // Not given a notification
        guard let userId = notifications.first?.userId else {
            return
        }
        guard let conn = connections[userId], !conn.webSocket.isClosed else {
            return
        }
        
        let msg = Fragment.NotificationResponse.notifications(notifications)
        if let string = msg.jsonString {
            try? await conn.webSocket.send(string)
        }
    }
    
    func recordActivity(for userId: UserID) async {
        guard let conn = connections[userId] else { return }
        restartTimeout(conn: conn)
    }
    
    private func restartTimeout(conn: Connection) {
        // Cancel existing timeout
        conn.timeoutTask?.cancel()
        
        let authUser = conn.authUser
        let ws = conn.webSocket
        
        // Create new sliding timeout
        conn.timeoutTask = Task.detached { [weak self] in
            guard let self else { return }
            
            // Wait N seconds before sending expiry warning
            let totalTimeout = Global.maxAllowableInactivityInSeconds
            let warningAt = totalTimeout - Global.amountOfTimeToWarnBeforeExpiryInSeconds
            // NOTE: Referencing `Task` here references the task we are in
            try? await Task.sleep(for: .seconds(warningAt))
            if Task.isCancelled { return }
            
            await self.sendSessionIsExpiringWarning(to: ws)
            
            // If not responded to within a minute, close, and invalidate session
            try? await Task.sleep(for: .seconds(Global.amountOfTimeToWarnBeforeExpiryInSeconds))
            if Task.isCancelled { return }

            // NOTE: This could also be wrapped in a `Task { ... }`, but I kind of want to block the close logic until this is complete to avoid the `Task` from getting prematurely cancelled... btw, I don't know if this actually happens. It may execute just fine.
            do {
                try await api.account.signOut(user: authUser)
            }
            catch { }
            
            try? await ws.close(code: .policyViolation)
            await self.closeConnection(for: authUser.user.id)
        }
    }
    
    private func closeConnection(for userId: UserID) async {
        boss.log.d("Disconnecting user (\(userId))")
        if let state = connections.removeValue(forKey: userId) {
            state.timeoutTask?.cancel()
            if !state.webSocket.isClosed {
                try? await state.webSocket.close(code: .normalClosure)
            }
        }
    }
    
    private func sendSessionIsExpiringWarning(to ws: WebSocket) async {
        let response = Fragment.NotificationResponse.sessionIsExpiring(Global.amountOfTimeToWarnBeforeExpiryInSeconds)
        guard let string = response.jsonString else {
            return
        }
        guard !ws.isClosed else {
            return boss.log.w("WebSocket for user already closed")
        }
        try? await ws.send(string)
    }
}
