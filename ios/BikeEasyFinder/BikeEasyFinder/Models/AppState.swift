import Combine
import Foundation
import SwiftData

@Model
final class SpotReactionRecord {
    @Attribute(.unique) var spotID: String
    var reactionRawValue: String
    var spotSnapshot: Data?
    var updatedAt: Date

    init(
        spotID: String,
        reactionRawValue: String,
        spotSnapshot: Data?,
        updatedAt: Date = .now
    ) {
        self.spotID = spotID
        self.reactionRawValue = reactionRawValue
        self.spotSnapshot = spotSnapshot
        self.updatedAt = updatedAt
    }
}

enum SpotReaction: String, Codable, CaseIterable, Identifiable {
    case interested
    case notInterested
    case visited

    var id: String { rawValue }

    var label: String {
        switch self {
        case .interested: "興味あり"
        case .notInterested: "今回は違う"
        case .visited: "行ったことがある"
        }
    }

    var systemImage: String {
        switch self {
        case .interested: "heart"
        case .notInterested: "hand.thumbsdown"
        case .visited: "checkmark.circle"
        }
    }
}

@MainActor
final class AppState: ObservableObject {
    @Published private(set) var hasCompletedOnboarding = false
    @Published private(set) var lastCriteria: SearchCriteria?
    @Published private(set) var reactions: [UUID: SpotReaction] = [:]
    @Published private(set) var savedSpots: [TouringSpot] = []
    @Published var analyticsEnabled = false {
        didSet {
            defaults.set(analyticsEnabled, forKey: Keys.analyticsEnabled)
            if analyticsEnabled { analyticsClient.enable() }
        }
    }

    private enum Keys {
        static let hasCompletedOnboarding = "hasCompletedOnboarding"
        static let lastCriteria = "lastCriteria"
        static let analyticsEnabled = "analyticsEnabled"
    }

    private let defaults: UserDefaults
    private let analyticsClient: AnonymousAnalyticsClient
    private let analyticsSessionID = UUID()
    private let modelContainer: ModelContainer
    private let modelContext: ModelContext
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()
    private var reactionRecords: [UUID: SpotReactionRecord] = [:]

    init(
        defaults: UserDefaults = .standard,
        modelContainer: ModelContainer? = nil,
        analyticsClient: AnonymousAnalyticsClient = .live
    ) {
        self.defaults = defaults
        self.analyticsClient = analyticsClient
        let resolvedContainer: ModelContainer
        if let modelContainer {
            resolvedContainer = modelContainer
        } else {
            do {
                resolvedContainer = try ModelContainer(for: SpotReactionRecord.self)
            } catch {
                fatalError("SwiftDataストアを初期化できませんでした: \(error.localizedDescription)")
            }
        }
        self.modelContainer = resolvedContainer
        modelContext = ModelContext(resolvedContainer)

        hasCompletedOnboarding = defaults.bool(forKey: Keys.hasCompletedOnboarding)
        analyticsEnabled = defaults.bool(forKey: Keys.analyticsEnabled)

        if let data = defaults.data(forKey: Keys.lastCriteria) {
            lastCriteria = try? decoder.decode(SearchCriteria.self, from: data)
        } else {
            lastCriteria = nil
        }

        loadReactionRecords()
    }

    func completeOnboarding() {
        hasCompletedOnboarding = true
        defaults.set(true, forKey: Keys.hasCompletedOnboarding)
    }

    func saveCriteria(_ criteria: SearchCriteria) {
        lastCriteria = criteria
        if let data = try? encoder.encode(criteria) {
            defaults.set(data, forKey: Keys.lastCriteria)
        }
    }

    @discardableResult
    func react(to spot: TouringSpot, as reaction: SpotReaction) -> SpotReaction? {
        let previous = reactions[spot.id]
        reactions[spot.id] = reaction

        if reaction == .interested {
            savedSpots.removeAll { $0.id == spot.id }
            savedSpots.append(spot)
        } else {
            savedSpots.removeAll { $0.id == spot.id }
        }

        upsertRecord(for: spot, reaction: reaction)
        analyticsClient.enqueue(
            eventType: reaction.apiEventType,
            spot: spot,
            sessionID: analyticsSessionID,
            criteria: lastCriteria,
            enabled: analyticsEnabled
        )
        return previous
    }

    func restoreReaction(for spot: TouringSpot, to previous: SpotReaction?) {
        if let previous {
            reactions[spot.id] = previous
            if previous == .interested {
                savedSpots.removeAll { $0.id == spot.id }
                savedSpots.append(spot)
            } else {
                savedSpots.removeAll { $0.id == spot.id }
            }
        } else {
            reactions.removeValue(forKey: spot.id)
            savedSpots.removeAll { $0.id == spot.id }
        }
        if let previous {
            upsertRecord(for: spot, reaction: previous)
        } else {
            deleteRecord(for: spot.id)
        }
    }

    func removeSavedSpot(_ spot: TouringSpot) {
        savedSpots.removeAll { $0.id == spot.id }
        if reactions[spot.id] == .interested {
            reactions.removeValue(forKey: spot.id)
        }
        deleteRecord(for: spot.id)
    }

    func clearLastCriteria() {
        lastCriteria = nil
        defaults.removeObject(forKey: Keys.lastCriteria)
    }

    func clearReactions() {
        reactions = [:]
        savedSpots = []
        for record in reactionRecords.values {
            modelContext.delete(record)
        }
        reactionRecords = [:]
        try? modelContext.save()
    }

    func clearAnonymousData() {
        analyticsEnabled = false
        Task { await analyticsClient.requestDeletion() }
    }

    func recordShown(_ spots: [TouringSpot]) {
        for spot in spots.prefix(5) {
            recordAnalyticsEvent("shown", spot: spot)
        }
    }

    func recordSelected(_ spot: TouringSpot) {
        recordAnalyticsEvent("selected", spot: spot)
    }

    func recordRouteStarted(_ spot: TouringSpot) {
        recordAnalyticsEvent("route_started", spot: spot)
    }

    private func recordAnalyticsEvent(_ eventType: String, spot: TouringSpot) {
        analyticsClient.enqueue(
            eventType: eventType,
            spot: spot,
            sessionID: analyticsSessionID,
            criteria: lastCriteria,
            enabled: analyticsEnabled
        )
    }

    private func loadReactionRecords() {
        let descriptor = FetchDescriptor<SpotReactionRecord>(
            sortBy: [SortDescriptor(\.updatedAt)]
        )
        guard let records = try? modelContext.fetch(descriptor) else { return }

        for record in records {
            guard let id = UUID(uuidString: record.spotID),
                  let reaction = SpotReaction(rawValue: record.reactionRawValue) else {
                modelContext.delete(record)
                continue
            }

            reactionRecords[id] = record
            reactions[id] = reaction
            if reaction == .interested,
               let data = record.spotSnapshot,
               let spot = try? decoder.decode(TouringSpot.self, from: data) {
                savedSpots.removeAll { $0.id == spot.id }
                savedSpots.append(spot)
            }
        }
        try? modelContext.save()
    }

    private func upsertRecord(for spot: TouringSpot, reaction: SpotReaction) {
        let snapshot: Data?
        if reaction == .interested {
            snapshot = try? encoder.encode(spot)
        } else {
            snapshot = nil
        }
        if let record = reactionRecords[spot.id] {
            record.reactionRawValue = reaction.rawValue
            record.spotSnapshot = snapshot
            record.updatedAt = .now
        } else {
            let record = SpotReactionRecord(
                spotID: spot.id.uuidString,
                reactionRawValue: reaction.rawValue,
                spotSnapshot: snapshot
            )
            modelContext.insert(record)
            reactionRecords[spot.id] = record
        }
        try? modelContext.save()
    }

    private func deleteRecord(for spotID: UUID) {
        guard let record = reactionRecords.removeValue(forKey: spotID) else { return }
        modelContext.delete(record)
        try? modelContext.save()
    }
}

private extension SpotReaction {
    var apiEventType: String {
        switch self {
        case .interested: "interested"
        case .notInterested: "not_interested"
        case .visited: "visited"
        }
    }
}
