/// Copyright ⓒ 2025 Bithead LLC. All rights reserved.

import bosslib
import Foundation
import Vapor

/// Register the `/friend/` routes.
public func registerFriend(_ app: Application) {
    app.group("friend") { group in
        group.get { req in
            let authUser = try await verifyAccess(cookie: req)
            let fragment = Fragment.Friends(friendRequests: [], yourRequests: [], friends: [])
            return fragment
        }.openAPI(
            summary: "Get all friends, friend requests, and pending requests",
            response: .type(Fragment.Friends.self),
            responseContentType: .application(.json)
        )
        
        group.post("add") { req in
            let authUser = try await verifyAccess(cookie: req)
            let fragment = Fragment.Friends(friendRequests: [], yourRequests: [], friends: [])
            return fragment
        }.openAPI(
            summary: "Add a new friend",
            body: .type(FriendForm.AddFriend.self),
            contentType: .application(.json),
            response: .type(Fragment.Friends.self),
            responseContentType: .application(.json)
        )
        
        group.post("remove") { req in
            let authUser = try await verifyAccess(cookie: req)
            let fragment = Fragment.Friends(friendRequests: [], yourRequests: [], friends: [])
            return fragment
        }.openAPI(
            summary: "Remove a friend",
            body: .type(FriendForm.RemoveFriend.self),
            contentType: .application(.json),
            response: .type(Fragment.Friends.self),
            responseContentType: .application(.json)
        )
        
        group.post("accept") { req in
            let authUser = try await verifyAccess(cookie: req)
            let fragment = Fragment.Friends(friendRequests: [], yourRequests: [], friends: [])
            return fragment
        }.openAPI(
            summary: "Accept a friend request",
            body: .type(FriendForm.AcceptFriendRequest.self),
            contentType: .application(.json),
            response: .type(Fragment.Friends.self),
            responseContentType: .application(.json)
        )
        
        group.post("reject") { req in
            let authUser = try await verifyAccess(cookie: req)
            let fragment = Fragment.Friends(friendRequests: [], yourRequests: [], friends: [])
            return fragment
        }.openAPI(
            summary: "Reject friend request",
            body: .type(FriendForm.RejectFriendRequest.self),
            contentType: .application(.json),
            response: .type(Fragment.Friends.self),
            responseContentType: .application(.json)
        )
    }
}
