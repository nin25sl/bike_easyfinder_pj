import CoreLocation
import Foundation

struct TouringSpot: Codable, Identifiable, Equatable {
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
    var recommendationID: UUID? = nil
    var verifiedAt: Date = Date(timeIntervalSince1970: 1_788_566_400)
    var sourceLabel: String = "公開情報・現地確認"
    var motorcycleParkingNote: String = "二輪駐車場所は現地の案内を確認してください"

    static let safetyBufferMinutes = 15

    var totalMinutes: Int {
        outboundMinutes + stayMinutes + returnMinutes
    }

    var coordinate: CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
    }

    var isWeatherSensitive: Bool {
        !tags.isDisjoint(with: [.sea, .mountain, .scenic, .winding, .nightView])
    }

    var estimatedTotalMinutes: Int {
        totalMinutes + Self.safetyBufferMinutes
    }

    var formattedDuration: String {
        Self.format(minutes: totalMinutes)
    }

    var formattedEstimatedDuration: String {
        Self.format(minutes: estimatedTotalMinutes)
    }

    private static func format(minutes totalMinutes: Int) -> String {
        let hours = totalMinutes / 60
        let minutes = totalMinutes % 60
        if hours == 0 { return "\(minutes)分" }
        if minutes == 0 { return "\(hours)時間" }
        return "\(hours)時間\(minutes)分"
    }
}
