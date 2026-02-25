/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import Foundation

public typealias FriendRequestID = Int

public struct FriendRequest: Equatable {
    public let id: FriendRequestID
    /// User who initiated the friend request
    public let userId: User.ID
    /// The time the request was made to become friends by userId
    public let createDate: Date
    /// The name of the user initiating the request
    public let name: String
    /// The e-mail of the friend making the request, or the recipient (depending on who is making the request)
    public let email: String
    /// Avatar of the user initiating the request
    public let avatarUrl: String?
}

public struct Friend: Equatable {
    public typealias ID = Int
    public let id: ID
    public let userId: User.ID
    public let friendUserId: User.ID
    public let createDate: Date
    /// This is the friend's full name
    public let name: String
    public let email: String
    public let avatarUrl: String?
}
