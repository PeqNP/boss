/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import Foundation

public typealias FriendRequestID = Int
public typealias FriendID = Int

public struct FriendRequest: Equatable {
    public let id: FriendRequestID
    /// User who initiated the friend request
    public let userId: UserID
    /// The time the request was made to become friends by userId
    public let createDate: Date
    /// The e-mail of the friend making the request, or the recipient (depending on who is making the request)
    public let email: String
}

public struct Friend: Equatable {
    public let id: FriendID
    public let userId: UserID
    public let friendUserId: UserID
    public let createDate: Date
    /// This is the friend's full name
    public let name: String
}
