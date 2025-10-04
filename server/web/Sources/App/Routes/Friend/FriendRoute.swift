/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import bosslib
import Foundation
import Vapor

/// Register the `/friend/` routes.
public func registerFriend(_ app: Application) {
    app.group("friend") { group in
        group.get { req in
            let authUser = try await verifyAccess(cookie: req)
            return try await makeFriends(for: authUser)
        }.openAPI(
            summary: "Get all friends, friend requests, and pending requests",
            response: .type(Fragment.Friends.self),
            responseContentType: .application(.json)
        )
        
        group.post("add") { req in
            let authUser = try await verifyAccess(cookie: req)
            let form = try req.content.decode(FriendForm.AddFriend.self)
            try await api.friend.addFriend(user: authUser.user, email: form.email)
            return try await makeFriends(for: authUser)
        }.openAPI(
            summary: "Add a new friend",
            body: .type(FriendForm.AddFriend.self),
            contentType: .application(.json),
            response: .type(Fragment.Friends.self),
            responseContentType: .application(.json)
        )
        
        group.post("remove") { req in
            let authUser = try await verifyAccess(cookie: req)
            let form = try req.content.decode(FriendForm.RemoveFriend.self)
            try await api.friend.removeFriend(user: authUser.user, id: form.id)
            return try await makeFriends(for: authUser)
        }.openAPI(
            summary: "Remove a friend",
            body: .type(FriendForm.RemoveFriend.self),
            contentType: .application(.json),
            response: .type(Fragment.Friends.self),
            responseContentType: .application(.json)
        )
        
        group.post("accept") { req in
            let authUser = try await verifyAccess(cookie: req)
            let form = try req.content.decode(FriendForm.AcceptFriendRequest.self)
            try await api.friend.acceptFriendRequest(user: authUser.user, id: form.id)
            return try await makeFriends(for: authUser)
        }.openAPI(
            summary: "Accept a friend request",
            body: .type(FriendForm.AcceptFriendRequest.self),
            contentType: .application(.json),
            response: .type(Fragment.Friends.self),
            responseContentType: .application(.json)
        )
        
        group.post("reject") { req in
            let authUser = try await verifyAccess(cookie: req)
            let form = try req.content.decode(FriendForm.RejectFriendRequest.self)
            try await api.friend.removeFriendRequest(user: authUser.user, id: form.id)
            return try await makeFriends(for: authUser)
        }.openAPI(
            summary: "Reject friend request",
            body: .type(FriendForm.RejectFriendRequest.self),
            contentType: .application(.json),
            response: .type(Fragment.Friends.self),
            responseContentType: .application(.json)
        )
    }
}

private func makeFriends(for authUser: AuthenticatedUser) async throws -> Fragment.Friends {
    let friends = try await api.friend.friends(user: authUser.user)
    let requests = try await api.friend.friendRequests(user: authUser.user)
    return .init(
        friendRequests: requests
            .filter { $0.userId != authUser.user.id }
            .map { $0.makeFriendRequestOption() },
        yourRequests: requests
            .filter { $0.userId == authUser.user.id }
            .map { $0.makeMyFriendRequestOption() },
        friends: friends
            .map { $0.makeFriendOption() }
    )
}
