/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import bosslib
import Vapor

enum FriendForm {
    struct AddFriend: Content {
        var email: String
    }
    struct RemoveFriend: Content {
        var id: FriendID
    }
    
    struct AcceptFriendRequest: Content {
        var id: FriendRequestID
    }
    struct RejectFriendRequest: Content {
        var id: FriendRequestID
    }
}
