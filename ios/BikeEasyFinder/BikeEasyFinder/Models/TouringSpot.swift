import CoreLocation
import Foundation

struct TouringSpot: Identifiable, Equatable {
    let id: UUID
    let name: String
    let summary: String
    let latitude: Double
    let longitude: Double
    let tags: Set<SpotInterest>
    let outboundMinutes: Int
    let returnMinutes: Int
    let stayMinutes: Int
    let distanceKilometers: Double
    let recommendationReason: String

    var totalMinutes: Int {
        outboundMinutes + stayMinutes + returnMinutes
    }

    var coordinate: CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
    }

    var formattedDuration: String {
        let hours = totalMinutes / 60
        let minutes = totalMinutes % 60
        if hours == 0 { return "\(minutes)分" }
        if minutes == 0 { return "\(hours)時間" }
        return "\(hours)時間\(minutes)分"
    }
}

