import CoreLocation
import Foundation
import WeatherKit

@MainActor
final class SpotWeatherViewModel: ObservableObject {
    enum State: Equatable {
        case loading
        case ok(String)
        case warning(String)
        case unavailable
    }

    @Published private(set) var state: State = .loading
    private let service: WeatherService

    init(service: WeatherService = .shared) {
        self.service = service
    }

    func load(for spot: TouringSpot) async {
        state = .loading
        do {
            let forecast = try await service.weather(
                for: CLLocation(latitude: spot.latitude, longitude: spot.longitude),
                including: .hourly
            )
            let targetDate = Date.now.addingTimeInterval(TimeInterval(spot.outboundMinutes * 60))
            guard let weather = forecast.forecast.min(by: {
                abs($0.date.timeIntervalSince(targetDate)) < abs($1.date.timeIntervalSince(targetDate))
            }) else {
                state = .unavailable
                return
            }
            let temperature = weather.temperature.converted(to: .celsius).value
            let wind = weather.wind.speed.converted(to: .metersPerSecond).value
            let precipitation = weather.precipitationChance
            let summary = String(
                format: "気温 %.0f℃・降水確率 %.0f%%・風速 %.1fm/s",
                temperature,
                precipitation * 100,
                wind
            )
            if precipitation >= 0.5 || wind >= 10 || temperature < 5 || temperature > 35 {
                state = .warning(summary)
            } else {
                state = .ok(summary)
            }
        } catch {
            state = .unavailable
        }
    }
}
