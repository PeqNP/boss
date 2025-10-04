/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import bosslib
import Vapor

extension Fragment {
    struct Friends: Content {
        let friendRequests: [Fragment.Option]
        let yourRequests: [Fragment.Option]
        let friends: [Fragment.Option]
    }
}

extension bosslib.Friend {
    func makeFriendOption() -> Fragment.Option {
        .init(id: id, name: name)
    }
}

extension bosslib.FriendRequest {
    func makeFriendRequestOption() -> Fragment.Option {
        .init(id: id, name: name)
    }
    
    func makeMyFriendRequestOption() -> Fragment.Option {
        .init(id: id, name: email)
    }
}
