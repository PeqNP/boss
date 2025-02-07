/// Copyright ⓒ 2022 Bithead LLC. All rights reserved.

import Foundation

class AnalyticsPublisher<T: AnalyticsEvent> {

    private let service: AnalyticsService

    init(service: AnalyticsService) {
        self.service = service
    }

    func send(_ type: T) {
        service.send(type)
    }

    func start(_ type: T) {
        service.start(type)
    }

    func cancel(_ type: T) {
        service.cancel(type)
    }

    func stop(_ type: T) {
        service.stop(type)
    }
}
