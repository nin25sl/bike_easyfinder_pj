import CoreLocation
import Foundation

protocol RecommendationProviding {
    func recommendations(
        origin: CLLocationCoordinate2D,
        criteria: SearchCriteria
    ) async throws -> [TouringSpot]
}

enum RecommendationError: LocalizedError {
    case invalidOrigin

    var errorDescription: String? {
        switch self {
        case .invalidOrigin:
            "現在地が正しくないため候補を取得できませんでした。"
        }
    }
}

/// RD-06のAPI契約が確定するまで使用する開発用スタブ。
struct MockRecommendationService: RecommendationProviding {
    var spots: [TouringSpot] = .demoSpots

    func recommendations(
        origin: CLLocationCoordinate2D,
        criteria: SearchCriteria
    ) async throws -> [TouringSpot] {
        guard CLLocationCoordinate2DIsValid(origin) else {
            throw RecommendationError.invalidOrigin
        }

        let usesAnyInterest = criteria.interests.contains(.any)
        return Array(
            spots
                .filter { $0.totalMinutes <= criteria.availableMinutes }
                .filter { spot in
                    usesAnyInterest || !spot.tags.isDisjoint(with: criteria.interests)
                }
                .sorted {
                    if $0.totalMinutes == $1.totalMinutes {
                        return $0.name.localizedStandardCompare($1.name) == .orderedAscending
                    }
                    return $0.totalMinutes < $1.totalMinutes
                }
                .prefix(5)
        )
    }
}

extension Array where Element == TouringSpot {
    static let demoSpots: [TouringSpot] = [
        TouringSpot(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000001")!,
            name: "糸島・桜井二見ヶ浦",
            summary: "海沿いの景色を楽しめる福岡近郊の定番スポット。",
            latitude: 33.6407,
            longitude: 130.1962,
            tags: [.sea, .scenic, .cafe],
            outboundMinutes: 45,
            returnMinutes: 45,
            stayMinutes: 25,
            distanceKilometers: 62,
            recommendationReason: "海と景色の希望に合い、時間内に往復できます"
        ),
        TouringSpot(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000002")!,
            name: "志賀島",
            summary: "市街地からアクセスしやすい海沿いの周回候補。",
            latitude: 33.6774,
            longitude: 130.3100,
            tags: [.sea, .scenic, .historic],
            outboundMinutes: 40,
            returnMinutes: 40,
            stayMinutes: 30,
            distanceKilometers: 54,
            recommendationReason: "短時間でも海沿いを楽しめます"
        ),
        TouringSpot(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000003")!,
            name: "油山展望台周辺",
            summary: "福岡市街を見渡せる近距離の景観候補。",
            latitude: 33.5268,
            longitude: 130.3660,
            tags: [.scenic, .mountain, .nightView],
            outboundMinutes: 30,
            returnMinutes: 30,
            stayMinutes: 20,
            distanceKilometers: 28,
            recommendationReason: "限られた時間で景色を楽しめます"
        ),
        TouringSpot(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000004")!,
            name: "秋月城下町",
            summary: "歴史ある町並みと食事を組み合わせやすい目的地。",
            latitude: 33.4703,
            longitude: 130.6925,
            tags: [.historic, .food, .cafe],
            outboundMinutes: 70,
            returnMinutes: 70,
            stayMinutes: 45,
            distanceKilometers: 92,
            recommendationReason: "歴史・観光と食事の希望に合います"
        ),
        TouringSpot(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000005")!,
            name: "道の駅むなかた周辺",
            summary: "休憩と食事を目的にしやすい海側のツーリング候補。",
            latitude: 33.8424,
            longitude: 130.5410,
            tags: [.roadsideStation, .food, .sea],
            outboundMinutes: 65,
            returnMinutes: 65,
            stayMinutes: 40,
            distanceKilometers: 96,
            recommendationReason: "食事と休憩を含めて時間内に往復できます"
        ),
        TouringSpot(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000006")!,
            name: "英彦山周辺",
            summary: "山間部の景観を楽しむ長めのツーリング候補。",
            latitude: 33.4761,
            longitude: 130.9262,
            tags: [.mountain, .scenic, .winding],
            outboundMinutes: 110,
            returnMinutes: 110,
            stayMinutes: 40,
            distanceKilometers: 152,
            recommendationReason: "山とワインディングの希望に合います"
        )
    ]
}

