/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import Foundation

extension api {
    public nonisolated(unsafe) internal(set) static var friend = FriendAPI(provider: FriendService())
}

protocol FriendProvider {
    func friendRequests(session: Database.Session, user: User) async throws -> [FriendRequest]
    func addFriend(session: Database.Session, user: User, email: String?) async throws -> FriendRequestID
    func acceptFriendRequest(session: Database.Session, user: User, id: FriendRequestID) async throws
    func removeFriendRequest(session: Database.Session, user: User, id: FriendRequestID) async throws
    
    func friends(session: Database.Session, user: User) async throws -> [Friend]
    func removeFriend(session: Database.Session, user: User, id: FriendID) async throws
}

final public class FriendAPI {
    let p: FriendProvider

    init(provider: FriendProvider) {
        self.p = provider
    }
    
    /// Returns all friend requests.
    ///
    /// - Returns: All open friend requests
    public func friendRequests(
        session: Database.Session = Database.session(),
        user: User
    ) async throws -> [FriendRequest] {
        try await p.friendRequests(session: session, user: user)
    }
    
    /// Add a friend.
    ///
    /// - Note: This puts the friend in a "pending" state. The other user must accept the invite before these users can become friends.
    /// - Note: This friend request will stay open, even a user w/ the respective e-mail doesn't exist. This is designed to prevent abuse where a user may try to determine if a user exists in the system.
    @discardableResult
    public func addFriend(
        session: Database.Session = Database.session(),
        user: User,
        email: String?
    ) async throws -> FriendRequestID {
        try await p.addFriend(session: session, user: user, email: email)
    }

    /// Accept a friend request.
    public func acceptFriendRequest(
        session: Database.Session = Database.session(),
        user: User,
        id: FriendRequestID
    ) async throws {
        try await p.acceptFriendRequest(session: session, user: user, id: id)
    }
    
    /// Remove (reject) a friend request.
    ///
    /// - Note: If the user already exists, an account recovery e-mail will be sent.
    public func removeFriendRequest(
        session: Database.Session = Database.session(),
        user: User,
        id: FriendRequestID
    ) async throws {
        try await p.removeFriendRequest(session: session, user: user, id: id)
    }
    
    /// Returns all friends.
    ///
    /// - Returns: All friends who have accepted friend request
    public func friends(
        session: Database.Session = Database.session(),
        user: User
    ) async throws -> [Friend] {
        try await p.friends(session: session, user: user)
    }
    
    /// Remove friend from list of friends.
    ///
    /// - Note: If the user already exists, an account recovery e-mail will be sent.
    public func removeFriend(
        session: Database.Session = Database.session(),
        user: User,
        id: FriendID
    ) async throws {
        try await p.removeFriend(session: session, user: user, id: id)
    }
}
