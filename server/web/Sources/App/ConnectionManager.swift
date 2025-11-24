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
    private let encoder = JSONEncoder()
    
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
        
        // Close old
        if let conn = connections[userId] {
            conn.timeoutTask?.cancel()
            try? await conn.webSocket.close(code: .normalClosure)
        }
        
        // Register new
        let conn = Connection(authUser: authUser, webSocket: ws)
        connections[userId] = conn
        
        restartTimeout(conn: conn)
        
        ws.onText { [weak self] ws, message in
            guard let self else { return }
            
            boss.log.d("Client (\(userId)) sent message (\(message))")
            if message == "ping" {
                let msg = Fragment.NotificationResponse(type: 0, command: "pong", notifications: nil, sessionExpiresInSeconds: nil)
                if let str = try? String(data: self.encoder.encode(msg), encoding: .utf8) {
                    ws.send(str)
                }
                else {
                    boss.log.w("Failed to send pong")
                }
            }
            
            Task { await self.recordActivity(for: userId) }
        }
        
        ws.onClose.whenComplete { [weak self] result in
            Task {
                await self?.closeConnection(for: userId)
            }
        }
    }

    func send(to userId: UserID, message: String) async {
        if let conn = connections[userId], !conn.webSocket.isClosed {
            try? await conn.webSocket.send(message)
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
        let response = Fragment.NotificationResponse(
            type: Fragment.NotificationResponse.NotificationType.sessionIsExpiring.rawValue,
            command: nil,
            notifications: nil,
            sessionExpiresInSeconds: Global.amountOfTimeToWarnBeforeExpiryInSeconds
        )
        
        if let data = try? encoder.encode(response), let string = String(data: data, encoding: .utf8), !ws.isClosed {
            try? await ws.send(string)
        }
    }
}
