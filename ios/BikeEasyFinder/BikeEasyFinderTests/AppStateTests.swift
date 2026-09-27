import XCTest
import SwiftData
@testable import BikeEasyFinder

final class AppStateTests: XCTestCase {
    @MainActor
    func testCriteriaAndOnboardingPersistAcrossInstances() {
        let (defaults, suiteName) = makeDefaults()
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let container = makeContainer()
        let criteria = SearchCriteria(
            availableMinutes: 240,
            interests: [.sea, .cafe],
            allowsHighway: true
        )
        let first = AppState(defaults: defaults, modelContainer: container)

        first.completeOnboarding()
        first.saveCriteria(criteria)

        let restored = AppState(defaults: defaults, modelContainer: container)
        XCTAssertTrue(restored.hasCompletedOnboarding)
        XCTAssertEqual(restored.lastCriteria, criteria)
    }

    @MainActor
    func testInterestedReactionSavesSpotAndPersists() {
        let (defaults, suiteName) = makeDefaults()
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let container = makeContainer()
        let spot = Array<TouringSpot>.demoSpots[0]
        let state = AppState(defaults: defaults, modelContainer: container)

        state.react(to: spot, as: .interested)

        let restored = AppState(defaults: defaults, modelContainer: container)
        XCTAssertEqual(restored.reactions[spot.id], .interested)
        XCTAssertEqual(restored.savedSpots, [spot])
    }

    @MainActor
    func testUndoRestoresPreviousReactionAndSavedSpot() {
        let (defaults, suiteName) = makeDefaults()
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let container = makeContainer()
        let spot = Array<TouringSpot>.demoSpots[0]
        let state = AppState(defaults: defaults, modelContainer: container)
        state.react(to: spot, as: .interested)

        let previous = state.react(to: spot, as: .visited)
        state.restoreReaction(for: spot, to: previous)

        XCTAssertEqual(state.reactions[spot.id], .interested)
        XCTAssertEqual(state.savedSpots, [spot])
    }

    @MainActor
    func testClearingReactionsAlsoClearsSavedSpots() {
        let (defaults, suiteName) = makeDefaults()
        defer { defaults.removePersistentDomain(forName: suiteName) }
        let container = makeContainer()
        let spot = Array<TouringSpot>.demoSpots[0]
        let state = AppState(defaults: defaults, modelContainer: container)
        state.react(to: spot, as: .interested)

        state.clearReactions()

        XCTAssertTrue(state.reactions.isEmpty)
        XCTAssertTrue(state.savedSpots.isEmpty)
    }

    private func makeDefaults() -> (UserDefaults, String) {
        let suiteName = "AppStateTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defaults.removePersistentDomain(forName: suiteName)
        return (defaults, suiteName)
    }

    private func makeContainer() -> ModelContainer {
        let configuration = ModelConfiguration(isStoredInMemoryOnly: true)
        return try! ModelContainer(
            for: SpotReactionRecord.self,
            configurations: configuration
        )
    }
}
