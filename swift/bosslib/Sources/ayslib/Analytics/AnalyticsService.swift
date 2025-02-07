/// Copyright ⓒ 2022 Bithead LLC. All rights reserved.

/**
 Provides a way to track analytics.
 */

import Foundation

class AnalyticsService {

    private let listeners: [AnalyticsListener]

    private var transactions = [String /* Event location */: DispatchTime /* Time started */]()

    init(listeners: [AnalyticsListener]) {
        self.listeners = listeners
    }

    func send(_ event: AnalyticsEvent) {
        listeners.forEach { (listener) in
            listener.receive(event)
        }
    }

    func start( _ event: AnalyticsEvent) {
        let id = eventId(for: event)
        guard transactions[id] == nil else {
            print("WARN: Attempting to start a transaction event for \(event) which has already been started")
            return
        }
        let startTime = DispatchTime.now()
        transactions[id] = startTime

        listeners.forEach { (listener) in
            let context: AnalyticsTransaction = .start(AnalyticsStartedTransaction(
                startTime: Double(startTime.uptimeNanoseconds) / 1_000_000_000
            ))
            listener.transaction(event, context)
        }
    }

    func cancel( _ event: AnalyticsEvent) {
        finishTransaction(event, status: .stopped)
    }

    func stop( _ event: AnalyticsEvent) {
        finishTransaction(event, status: .stopped)
    }

    func publisher<T: AnalyticsEvent>() -> AnalyticsPublisher<T> {
        return AnalyticsPublisher<T>(service: self)
    }

    // MARK: - Private methods

    private func eventId(for event: AnalyticsEvent) -> String {
        return String(describing: event)
    }

    private func finishTransaction(_ event: AnalyticsEvent, status: AnalyticsTransaction.Status) {
        let id = eventId(for: event)
        guard let startTime = transactions[id] else {
            return
        }
        transactions.removeValue(forKey: id)

        let stopTime = DispatchTime.now()

        let nanoTime = stopTime.uptimeNanoseconds - startTime.uptimeNanoseconds
        let totalTime = Double(nanoTime) / 1_000_000_000

        listeners.forEach { (listener) in
            let context: AnalyticsTransaction = .finish(AnalyticsFinishedTransaction(
                status: status,
                startTime: Double(startTime.uptimeNanoseconds) / 1_000_000_000,
                stopTime: Double(stopTime.uptimeNanoseconds) / 1_000_000_000,
                totalTime: totalTime
            ))
            listener.transaction(event, context)
        }
    }
}
