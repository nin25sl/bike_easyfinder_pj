import Foundation

struct SearchCriteria: Equatable {
    var availableMinutes: Int = 120
    var interests: Set<SpotInterest> = [.any]
    var allowsHighway = false
}

enum SpotInterest: String, CaseIterable, Identifiable, Hashable {
    case any
    case sea
    case scenic
    case mountain
    case winding
    case cafe
    case food
    case onsen
    case roadsideStation = "roadside_station"
    case nightView = "night_view"
    case historic

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .any: "おまかせ"
        case .sea: "海"
        case .scenic: "景色"
        case .mountain: "山"
        case .winding: "ワインディング"
        case .cafe: "カフェ"
        case .food: "食事"
        case .onsen: "温泉"
        case .roadsideStation: "道の駅"
        case .nightView: "夜景"
        case .historic: "歴史・観光"
        }
    }
}

struct DurationOption: Identifiable, Hashable {
    let minutes: Int
    let label: String

    var id: Int { minutes }

    static let mvpOptions = [
        DurationOption(minutes: 60, label: "1時間"),
        DurationOption(minutes: 120, label: "2時間"),
        DurationOption(minutes: 180, label: "3時間"),
        DurationOption(minutes: 240, label: "4時間"),
        DurationOption(minutes: 360, label: "半日"),
        DurationOption(minutes: 600, label: "1日")
    ]
}

