/// Copyright ⓒ 2022 Bithead LLC. All rights reserved.

/**
 Provides contextual information for a transaction.
 */

import Foundation

enum AnalyticsTransaction {
    enum Status {
        case started
        case cancelled
        case stopped
    }

    case start(AnalyticsStartedTransaction)
    case finish(AnalyticsFinishedTransaction)
}

struct AnalyticsStartedTransaction {
    let status: AnalyticsTransaction.Status = .started
    let startTime: Double // UNIX time in seconds

    init(startTime: Double) {
        self.startTime = startTime
    }
}

struct AnalyticsFinishedTransaction {
    let status: AnalyticsTransaction.Status
    let startTime: Double // UNIX time in seconds
    let stopTime: Double // UNIX time in seconds
    let totalTime: Double // Seconds elapsed from start to end
}
