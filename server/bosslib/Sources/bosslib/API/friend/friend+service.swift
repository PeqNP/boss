/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import Foundation
internal import SQLiteKit

struct FriendService: FriendProvider {
    func friendRequests(session: Database.Session, user: User) async throws -> [FriendRequest] {
        let conn = try await session.conn()
        let rows = try await conn.query("""
            SELECT
                fr.*,
                u.full_name
            FROM
                friend_requests AS fr
                JOIN users AS u ON fr.user_id = u.id
            WHERE
                fr.user_id = $1
                OR fr.email = $2  
            """, [.integer(user.id), .text(user.email)])
        return try rows.map { (row) -> FriendRequest in
            try makeFriend(from: row.sql())
        }
    }
    
    func addFriend(session: Database.Session, user: User, email: String?) async throws {
        guard !user.isGuestUser else {
            throw api.error.GuestCanNotBeFriend()
        }
        
        let email = try validateEmail(email)
        
        guard email != user.email else {
            throw api.error.FriendIsSelf()
        }
        
        // Friend request already exists
        guard try await friendRequest(session: session, user: user, email: email) == nil else {
            return
        }
        
        // If friend already sent us request, auto-accept the request
        if let request = try await friendRequest(session: session, myEmail: user.email, friendEmail: email) {
            return try await acceptFriendRequest(session: session, user: user, id: request.id)
        }
                
        let conn = try await session.conn()
        _ = try await conn.sql().insert(into: "friend_requests")
            .columns("id", "create_date", "user_id", "email")
            .values(
                SQLLiteral.null,
                SQLBind(Date.now),
                SQLBind(user.id),
                SQLBind(email)
            )
            .returning("id")
            .all()
    }
    
    func acceptFriendRequest(session: Database.Session, user: User, id: FriendRequestID) async throws {
        guard let request = try await friendRequest(session: session, id: id, email: user.email) else {
            throw api.error.FriendRequestNotFound()
        }
        
        let conn = try await session.conn()
        try await conn.begin()
        
        // Delete request
        try await conn.sql().delete(from: "friend_requests")
            .where("id", .equal, SQLBind(request.id))
            .run()
                
        // Create friend
        _ = try await conn.sql().insert(into: "friends")
            .columns("id", "create_date", "user_id", "friend_user_id")
            .values(
                SQLLiteral.null,
                SQLBind(Date.now),
                SQLBind(user.id),
                SQLBind(request.userId)
            )
            .returning("id")
            .all()
        
        _ = try await conn.sql().insert(into: "friends")
            .columns("id", "create_date", "user_id", "friend_user_id")
            .values(
                SQLLiteral.null,
                SQLBind(Date.now),
                SQLBind(request.userId),
                SQLBind(user.id)
            )
            .returning("id")
            .all()
        
        try await conn.commit()
    }
    
    func removeFriendRequest(session: Database.Session, user: User, id: FriendRequestID) async throws {
        
    }
    
    func friends(session: Database.Session, user: User) async throws -> [Friend] {
        []
    }
    
    func removeFriend(session: Database.Session, user: User, id: FriendID) async throws {
        
    }
    
    func friendRequest(session: Database.Session, user: User, email: String) async throws -> FriendRequest? {
        let conn = try await session.conn()
        let rows = try await conn.query("""
            SELECT
                fr.*,
                u.full_name
            FROM
                friend_requests AS fr
                JOIN users AS u ON fr.user_id = u.id
            WHERE
                fr.user_id = $1
                AND fr.email = $2  
            """, [.integer(user.id), .text(email)])
        
        guard rows.count == 1 else {
            return nil
        }
        
        return try makeFriend(from: rows[0].sql())
    }
    
    func friendRequest(session: Database.Session, id: FriendRequestID, email: String) async throws -> FriendRequest? {
        let conn = try await session.conn()
        let rows = try await conn.query("""
            SELECT
                fr.*,
                u.full_name
            FROM
                friend_requests AS fr
                JOIN users AS u ON fr.user_id = u.id
            WHERE
                fr.id = $1
                AND fr.email = $2  
            """, [.integer(id), .text(email)])
        guard rows.count == 1 else {
            return nil
        }
        
        return try makeFriend(from: rows[0].sql())
    }
    
    /// Get friend request that was initiated to my e-mail from the same user I am trying to invite to be friends with.
    ///
    /// - Parameter myEmail: The initiator e-mail
    /// - Parameter friendEmail: The e-mail of friend I want to connect with
    /// - Returns: Request that friend may have already initiated
    func friendRequest(session: Database.Session, myEmail: String, friendEmail: String) async throws -> FriendRequest? {
        let conn = try await session.conn()
        let rows = try await conn.query("""
            SELECT
                fr.*,
                u.full_name
            FROM
                friend_requests AS fr
                JOIN users AS u ON fr.user_id = u.id
            WHERE
                fr.email = $1
                AND u.email = $2  
            """, [.text(myEmail), .text(friendEmail)])
        guard rows.count == 1 else {
            return nil
        }
        
        return try makeFriend(from: rows[0].sql())
    }
    
    func makeFriend(from row: SQLRow) throws -> FriendRequest {
        .init(
            id: try row.decode(column: "id", as: FriendRequestID.self),
            userId: try row.decode(column: "user_id", as: UserID.self),
            createDate: try row.decode(column: "create_date", as: Date.self),
            name: try row.decode(column: "full_name", as: String.self),
            email: try row.decode(column: "email", as: String.self)
        )
    }
}
