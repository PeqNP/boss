/// Copyright ⓒ 2024 Bithead LLC. All rights reserved.

import bosslib
import Vapor

actor ConnectionManager {
    private var connections: [UserID: WebSocket] = [:]

    func register(_ ws: WebSocket, for userId: UserID) async {
        // Close old
        if let old = connections[userId] {
            try? await old.close(code: .normalClosure)
        }
        
        // Register new
        connections[userId] = ws

        ws.onText { ws, message in
            if message == "ping" {
                ws.send("pong")
            }
        }
        
        // Cleanup on close
        ws.onClose.whenComplete { result in
            Task {
                await self.removeIfCurrent(ws, for: userId)
            }
        }
    }

    func removeIfCurrent(_ ws: WebSocket, for userId: UserID) async {
        if connections[userId] === ws {
            connections.removeValue(forKey: userId)
        }
    }

    func send(to userId: UserID, message: String) async {
        if let ws = connections[userId] {
            try? await ws.send(message)
        }
    }
}
