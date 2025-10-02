/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import Foundation
import SwiftOTP
import XCTest

@testable import bosslib

final class friendTests: XCTestCase {
    /// Test adding, accepting, removing and querying for friends.
    func testFriends() async throws {
        try await boss.start(storage: .memory)
        
        let user = try await api.account.saveUser(user: superUser(), id: nil, email: "eric@example.com", password: "Password1!", fullName: "Eric", verified: true, enabled: true)
        let mario = try await api.account.saveUser(user: superUser(), id: nil, email: "mario@example.com", password: "Password1!", fullName: "Mario", verified: true, enabled: true)
        let luigi = try await api.account.saveUser(user: superUser(), id: nil, email: "luigi@example.com", password: "Password1!", fullName: "Luigi", verified: true, enabled: true)
        let lonelyUser = try await api.account.saveUser(user: superUser(), id: nil, email: "lonely@example.com", password: "Password1!", fullName: "Lonely", verified: true, enabled: true)
        
        // when: user is not enabled (This is caught when attempting to sign in. Not necessary)
        // when: user is not verified (This is caught when attempting to sign in. Not necessary)
        
        // describe: add a friend
        
        // when: user is guest
        await XCTAssertError(
            try await api.friend.addFriend(user: guestUser().user, email: nil),
            api.error.GuestCanNotBeFriend()
        )
        
        // when: email is empty
        await XCTAssertError(
            try await api.friend.addFriend(user: user, email: nil),
            api.error.InvalidAccountInfo(field: .email)
        )
        
        // when: email is the same as user's e-mail
        await XCTAssertError(
            try await api.friend.addFriend(user: user, email: "eric@example.com"),
            api.error.FriendIsSelf()
        )
        
        // when: email does not exist in system
        try await api.friend.addFriend(user: user, email: "fake@example.com")
        // it: should still create the request
                
        // when: email does exist in the system
        try await api.friend.addFriend(user: user, email: "mario@example.com")
        // it: should create the request
        
        // when: friend request has already been made
        try await api.friend.addFriend(user: user, email: "mario@example.com")
        // it: should NOT create another friend request (tested when `friendRequests` is called below)
        
        // when: stranger sends friend request to us (eric)
        try await api.friend.addFriend(user: luigi, email: "eric@example.com")
        
        // describe: query friend requests (made to other users)
        var requests = try await api.friend.friendRequests(user: user)
        XCTAssertEqual(requests.count, 3, "it: should return all friend requests")
        XCTAssertEqual(requests[safe: 0]?.email, "fake@example.com")
        XCTAssertEqual(requests[safe: 1]?.name, "Eric")
        XCTAssertEqual(requests[safe: 1]?.email, "mario@example.com")
        XCTAssertEqual(requests[safe: 2]?.name, "Luigi")
        XCTAssertEqual(requests[safe: 2]?.email, "eric@example.com")
        
        var friends = try await api.friend.friends(user: user)
        XCTAssertEqual(friends.count, 0, "it: should return no friends") // Sanity
        
        // when: query friend requests (user did not initiate friend request)
        requests = try await api.friend.friendRequests(user: mario)
        XCTAssertEqual(requests.count, 1)
        XCTAssertEqual(requests.first?.name, "Eric")
        XCTAssertEqual(requests.first?.email, "mario@example.com")
        
        requests = try await api.friend.friendRequests(user: luigi)
        XCTAssertEqual(requests.count, 1)
        XCTAssertEqual(requests.first?.email, "eric@example.com")
        
        // when: user has no friend requests
        requests = try await api.friend.friendRequests(user: lonelyUser)
        XCTAssertEqual(requests.count, 0)
        
        // describe: add friend
        
        // when: user attempts to accept friend request that was never made
        await XCTAssertError(
            try await api.friend.acceptFriendRequest(user: lonelyUser, id: 20),
            api.error.FriendRequestNotFound()
        )
        
        // when: user accepts a friend request that does not belong to them
        // NOTE: `id` belongs to fake@example.com
        await XCTAssertError(
            try await api.friend.acceptFriendRequest(user: luigi, id: 1),
            api.error.FriendRequestNotFound()
        )
        
        // when: user who initiated the request accepts a friend request they made to someone else
        await XCTAssertError(
            try await api.friend.acceptFriendRequest(user: user, id: 1),
            api.error.FriendRequestNotFound()
        )
        
        // when: user accepts friend request
        try await api.friend.acceptFriendRequest(user: mario, id: 2)
        
        // when: user sends friend request to a user who has already initiated a friend request with them
        // it: should automatically accept the invite
        try await api.friend.addFriend(user: user, email: "luigi@example.com")
        
        // when: friend requests are accepted
        requests = try await api.friend.friendRequests(user: user)
        XCTAssertEqual(requests.count, 1) // it: should remove accepted requests
        XCTAssertEqual(requests[0].email, "fake@example.com")
        
        // describe: query friends
        
        // when: user has friends
        friends = try await api.friend.friends(user: user)
        XCTAssertEqual(friends.count, 2)
        XCTAssertEqual(friends.first?.name, "Mario", "it: should return full name")
        XCTAssertEqual(friends.last?.name, "luigi@example.com", "it: should return e-mail if no full name")
        
        // when: user has no friends
        friends = try await api.friend.friends(user: lonelyUser)
        XCTAssertEqual(friends.count, 0)
        
        // when: user has friend (request was initiated by another user)
        friends = try await api.friend.friends(user: mario)
        XCTAssertEqual(friends.count, 1)
        XCTAssertEqual(friends.first?.name, "Eric")
        
        // when: user has friend (added friend instead of accepting request)
        friends = try await api.friend.friends(user: luigi)
        XCTAssertEqual(friends.count, 1)
        XCTAssertEqual(friends.first?.name, "Eric")
    
        // when: friend request sent to existing friend
        try await api.friend.addFriend(user: user, email: "mario@example.com")
        friends = try await api.friend.friends(user: user)
        XCTAssertEqual(friends.count, 2, "it: should not create friend request")
        
        // describe: remove friend
        
        // when: friend does not exist
        await XCTAssertError(
            try await api.friend.removeFriend(user: mario, id: 10),
            api.error.FriendNotFound()
        )
        
        // when: initiator removes friend request (fake user)
        try await api.friend.removeFriend(user: user, id: 1)
        
        // TODO: when: friend request is rejected
        
        // it: should remove Mario
        friends = try await api.friend.friends(user: user)
        XCTAssertEqual(friends.count, 1)
        XCTAssertEqual(friends.first?.name, "luigi@example.com")
        
        // it: should remove Eric
        friends = try await api.friend.friends(user: mario)
        XCTAssertEqual(friends.count, 0)
    }
}
