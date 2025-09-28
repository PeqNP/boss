/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

struct FriendService: FriendProvider {
    func friendRequests(session: Database.Session, user: User) async throws -> [FriendRequest] {
        []
    }
    
    func addFriend(session: Database.Session, user: User, email: String?) async throws {
        
    }
    
    func acceptFriendRequest(session: Database.Session, user: User, id: FriendRequestID) async throws {
        
    }
    
    func removeFriendRequest(session: Database.Session, user: User, id: FriendRequestID) async throws {
        
    }
    
    func friends(session: Database.Session, user: User) async throws -> [Friend] {
        []
    }
    
    func removeFriend(session: Database.Session, user: User, id: FriendID) async throws {
        
    }
}
