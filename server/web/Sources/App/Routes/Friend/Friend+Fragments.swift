/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import bosslib
import Vapor

extension Fragment {
    struct FriendRequest: Content {
        let id: String
        let name: String
        let avatarUrl: String?
    }

    struct Friend: Content {
        let id: String
        let userId: UserID
        let name: String
        let avatarUrl: String?
    }

    struct Friends: Content {
        let friendRequests: [Fragment.FriendRequest]
        let yourRequests: [Fragment.FriendRequest]
        let friends: [Fragment.Friend]
    }
}

extension bosslib.Friend {
    func makeFriendOption() -> Fragment.Friend {
        .init(id: String(id), userId: friendUserId, name: name, avatarUrl: avatarUrl)
    }
}

extension bosslib.FriendRequest {
    func makeFriendRequestOption() -> Fragment.FriendRequest {
        .init(id: String(id), name: name, avatarUrl: avatarUrl)
    }
    
    func makeMyFriendRequestOption() -> Fragment.FriendRequest {
        .init(id: String(id), name: email, avatarUrl: avatarUrl)
    }
}
