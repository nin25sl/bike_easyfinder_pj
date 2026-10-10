import CoreLocation
import Foundation

enum APIRecommendationError: LocalizedError {
    case invalidResponse
    case serviceUnavailable

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            "推薦データを読み取れませんでした。"
        case .serviceUnavailable:
            "推薦サービスに接続できませんでした。もう一度お試しください。"
        }
    }
}

struct APIRecommendationService: RecommendationProviding {
    private let baseURL: URL
    private let session: URLSession
    private let decoder: JSONDecoder

    static var live: APIRecommendationService {
        let configured = Bundle.main.object(forInfoDictionaryKey: "BikeAPIBaseURL") as? String
        let url = URL(string: configured ?? "http://127.0.0.1:8000")!
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 5
        configuration.timeoutIntervalForResource = 5
        return APIRecommendationService(baseURL: url, session: URLSession(configuration: configuration))
    }

    init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
        decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let value = try container.decode(String.self)
            let fractional = ISO8601DateFormatter()
            fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = fractional.date(from: value) { return date }
            let standard = ISO8601DateFormatter()
            guard let date = standard.date(from: value) else {
                throw DecodingError.dataCorruptedError(in: container, debugDescription: "Invalid ISO-8601 date")
            }
            return date
        }
    }

    func recommendations(
        origin: CLLocationCoordinate2D,
        criteria: SearchCriteria,
        reactions: [UUID: SpotReaction]
    ) async throws -> RecommendationResult {
        guard CLLocationCoordinate2DIsValid(origin) else { throw RecommendationError.invalidOrigin }
        let body = RecommendationRequestDTO(
            origin: CoordinateDTO(latitude: origin.latitude, longitude: origin.longitude),
            availableMinutes: criteria.availableMinutes,
            interests: criteria.interests.map(\.rawValue).sorted(),
            allowHighway: criteria.allowsHighway,
            locale: Locale.current.identifier.replacingOccurrences(of: "_", with: "-"),
            preferenceProfile: PreferenceProfileDTO(
                spotReactions: reactions.map {
                    SpotReactionDTO(spotID: $0.key, reaction: $0.value.apiValue)
                }
                .sorted { $0.spotID.uuidString < $1.spotID.uuidString },
                categoryWeights: [:],
                tagWeights: [:]
            )
        )
        var request = URLRequest(url: baseURL.appending(path: "v1/recommendations"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(UUID().uuidString, forHTTPHeaderField: "X-Request-ID")
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        request.httpBody = try encoder.encode(body)

        let (data, response) = try await perform(request, retryCount: 1)
        guard let http = response as? HTTPURLResponse else { throw APIRecommendationError.invalidResponse }
        guard http.statusCode == 200 else {
            throw [503, 504].contains(http.statusCode)
                ? APIRecommendationError.serviceUnavailable
                : APIRecommendationError.invalidResponse
        }
        do {
            let response = try decoder.decode(RecommendationResponseDTO.self, from: data)
            return RecommendationResult(
                spots: response.candidates.map { $0.spot(recommendationID: response.recommendationID) },
                warnings: response.warnings.map(\.message)
            )
        } catch {
            throw APIRecommendationError.invalidResponse
        }
    }

    private func perform(_ request: URLRequest, retryCount: Int) async throws -> (Data, URLResponse) {
        do {
            let result = try await session.data(for: request)
            if retryCount > 0,
               let response = result.1 as? HTTPURLResponse,
               [429, 503, 504].contains(response.statusCode) {
                let seconds = min(Double(response.value(forHTTPHeaderField: "Retry-After") ?? "1") ?? 1, 3)
                try await Task.sleep(for: .seconds(seconds))
                return try await perform(request, retryCount: retryCount - 1)
            }
            return result
        } catch {
            guard retryCount > 0 else { throw APIRecommendationError.serviceUnavailable }
            try await Task.sleep(for: .seconds(1))
            return try await perform(request, retryCount: retryCount - 1)
        }
    }
}

private struct RecommendationRequestDTO: Encodable {
    let origin: CoordinateDTO
    let availableMinutes: Int
    let interests: [String]
    let allowHighway: Bool
    let locale: String
    let preferenceProfile: PreferenceProfileDTO
}

private struct PreferenceProfileDTO: Encodable {
    let spotReactions: [SpotReactionDTO]
    let categoryWeights: [String: Int]
    let tagWeights: [String: Int]
}

private struct SpotReactionDTO: Encodable {
    let spotID: UUID
    let reaction: String
}

private extension SpotReaction {
    var apiValue: String {
        switch self {
        case .interested: "interested"
        case .notInterested: "not_interested"
        case .visited: "visited"
        }
    }
}

private struct CoordinateDTO: Codable {
    let latitude: Double
    let longitude: Double
}

private struct RecommendationResponseDTO: Decodable {
    let recommendationID: UUID
    let candidates: [RecommendationCandidateDTO]
    let warnings: [WarningDTO]
}

private struct WarningDTO: Decodable {
    let code: String
    let message: String
}

private struct RecommendationCandidateDTO: Decodable {
    let spotID: UUID
    let name: String
    let summary: String?
    let coordinate: CoordinateDTO
    let tags: [String]
    let outboundMinutes: Int
    let stayMinutes: Int
    let returnMinutes: Int
    let distanceKm: Double
    let reasons: [String]
    let freshness: FreshnessDTO

    func spot(recommendationID: UUID) -> TouringSpot {
        TouringSpot(
            id: spotID,
            name: name,
            summary: summary ?? "詳細情報は現地で確認してください。",
            latitude: coordinate.latitude,
            longitude: coordinate.longitude,
            tags: Set(tags.compactMap(SpotInterest.init(rawValue:))),
            outboundMinutes: outboundMinutes,
            returnMinutes: returnMinutes,
            stayMinutes: stayMinutes,
            distanceKilometers: distanceKm,
            recommendationReason: reasons.joined(separator: " / "),
            recommendationID: recommendationID,
            verifiedAt: freshness.spotVerifiedAt,
            sourceLabel: "Bike EasyFinder Canonical",
            motorcycleParkingNote: "二輪駐車場と道路状況は出発前に現地情報を確認してください。"
        )
    }
}

private struct FreshnessDTO: Decodable {
    let spotVerifiedAt: Date
}
