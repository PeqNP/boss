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
            ORDER BY fr.create_date ASC
            """, [.integer(user.id), .text(user.email)])
        return try rows.map { (row) -> FriendRequest in
            try makeFriendRequest(from: row.sql())
        }
    }
    
    func addFriend(session: Database.Session, user: User, email: String?) async throws -> FriendRequestID {
        guard !user.isGuestUser else {
            throw api.error.GuestCanNotBeFriend()
        }
        
        let email = try validateEmail(email)
        
        guard email != user.email else {
            throw api.error.FriendIsSelf()
        }
        
        // Friend request already exists
        if let request = try await friendRequest(session: session, user: user, email: email) {
            return request.id
        }
        
        // If friend already sent us request, auto-accept the request
        if let request = try await friendRequest(session: session, myEmail: user.email, friendEmail: email) {
            try await acceptFriendRequest(session: session, user: user, id: request.id)
            return request.id
        }
                
        let conn = try await session.conn()
        let rows = try await conn.sql().insert(into: "friend_requests")
            .columns("id", "create_date", "user_id", "email")
            .values(
                SQLLiteral.null,
                SQLBind(Date.now),
                SQLBind(user.id),
                SQLBind(email)
            )
            .returning("id")
            .all()
        return try rows[0].decode(column: "id", as: FriendRequestID.self)
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
        let conn = try await session.conn()
        guard let request = try await friendRequest(session: session, id: id) else {
            throw api.error.FriendRequestNotFound()
        }
        // Only initiator or recipient may remove the request
        guard request.userId == user.id || request.email == user.email else {
            throw api.error.FriendRequestNotFound()
        }
        
        try await conn.sql().delete(from: "friend_requests")
            .where("id", .equal, SQLBind(id))
            .run()
    }
    
    func friends(session: Database.Session, user: User) async throws -> [Friend] {
        let conn = try await session.conn()
        let rows = try await conn.query("""
            SELECT
                f.*,
                u.full_name
            FROM
                friends AS f
                JOIN users AS u ON f.friend_user_id = u.id
            WHERE
                f.user_id = $1
            ORDER BY f.create_date
            """, [.integer(user.id)])
        
        return try rows.map { (row: SQLRow) -> Friend in
            try makeFriend(from: row)
        }
    }
    
    func removeFriend(session: Database.Session, user: User, id: FriendID) async throws {
        let conn = try await session.conn()
        guard let friend = try await friend(session: session, id: id) else {
            throw api.error.FriendNotFound()
        }
        // Only initiator or recipient may remove the request
        guard friend.userId == user.id else {
            throw api.error.FriendNotFound()
        }
        
        try await conn.begin()
        // Remove primary record
        try await conn.sql().delete(from: "friends")
            .where("id", .equal, SQLBind(id))
            .run()
        // Remove friend record
        try await conn.sql().delete(from: "friends")
            .where("user_id", .equal, SQLBind(friend.friendUserId))
            .where("friend_user_id", .equal, SQLBind(user.id))
            .run()
        try await conn.commit()
    }
    
    func cleanFriends(conn: Database.Connection, for userId: UserID) async throws {
        try await conn.sql().delete(from: "friend_requests")
            .where("user_id", .equal, SQLBind(userId))
            .run()
        try await conn.sql().delete(from: "friends")
            .where("user_id", .equal, SQLBind(userId))
            .orWhere("friend_user_id", .equal, SQLBind(userId))
            .run()
    }
}

private extension FriendService {
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
        
        return try makeFriendRequest(from: rows[0].sql())
    }
    
    func friendRequest(session: Database.Session, id: FriendRequestID) async throws -> FriendRequest? {
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
            """, [.integer(id)])
        guard rows.count == 1 else {
            return nil
        }
        
        return try makeFriendRequest(from: rows[0].sql())
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
        
        return try makeFriendRequest(from: rows[0].sql())
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
        
        return try makeFriendRequest(from: rows[0].sql())
    }
    
    func friend(session: Database.Session, id: FriendRequestID) async throws -> Friend? {
        let conn = try await session.conn()
        let rows = try await conn.query("""
            SELECT
                fr.*,
                u.full_name
            FROM
                friends AS fr
                JOIN users AS u ON fr.friend_user_id = u.id
            WHERE
                fr.id = $1
            """, [.integer(id)])
        guard rows.count == 1 else {
            return nil
        }
        
        return try makeFriend(from: rows[0].sql())
    }
    
    func makeFriendRequest(from row: SQLRow) throws -> FriendRequest {
        .init(
            id: try row.decode(column: "id", as: FriendRequestID.self),
            userId: try row.decode(column: "user_id", as: UserID.self),
            createDate: try row.decode(column: "create_date", as: Date.self),
            name: try row.decode(column: "full_name", as: String.self),
            email: try row.decode(column: "email", as: String.self),
            // TODO: Compute avatar URL for requesting user_id
            avatarUrl: nil
        )
    }
    
    func makeFriend(from row: SQLRow) throws -> Friend {
        .init(
            id: try row.decode(column: "id", as: FriendID.self),
            userId: try row.decode(column: "user_id", as: UserID.self),
            friendUserId: try row.decode(column: "friend_user_id", as: UserID.self),
            createDate: try row.decode(column: "create_date", as: Date.self),
            name: try row.decode(column: "full_name", as: String.self),
            // TODO: Compute avatar URL for friend_user_id
            avatarUrl: nil
        )
    }
}
