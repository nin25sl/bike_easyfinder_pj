import CryptoKit
import Foundation
import Security

private struct AnalyticsCredentials {
    let installationID: UUID
    let deletionToken: String

    var tokenHash: String {
        SHA256.hash(data: Data(deletionToken.utf8)).map { String(format: "%02x", $0) }.joined()
    }
}

private struct QueuedInteraction: Codable, Identifiable {
    let eventID: UUID
    let sessionID: UUID
    let recommendationID: UUID
    let spotID: UUID
    let eventType: String
    let occurredAt: Date
    let availableMinutes: Int?
    let interests: [String]

    var id: UUID { eventID }
}

@MainActor
final class AnonymousAnalyticsClient {
    static let live = AnonymousAnalyticsClient()

    private enum Keys {
        static let queue = "anonymousAnalyticsQueue"
        static let installationID = "analyticsInstallationID"
        static let deletionToken = "analyticsDeletionToken"
    }

    private let baseURL: URL
    private let session: URLSession
    private let defaults: UserDefaults
    private let keychain: KeychainStore
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()
    private var queue: [QueuedInteraction]

    init(
        baseURL: URL? = nil,
        session: URLSession = .shared,
        defaults: UserDefaults = .standard,
        keychain: KeychainStore = KeychainStore(service: "com.bikeeasyfinder.analytics")
    ) {
        let configured = Bundle.main.object(forInfoDictionaryKey: "BikeAPIBaseURL") as? String
        self.baseURL = baseURL ?? URL(string: configured ?? "http://127.0.0.1:8000")!
        self.session = session
        self.defaults = defaults
        self.keychain = keychain
        queue = []
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.dateEncodingStrategy = .iso8601
        decoder.dateDecodingStrategy = .iso8601
        queue = defaults.data(forKey: Keys.queue)
            .flatMap { try? decoder.decode([QueuedInteraction].self, from: $0) } ?? []
        pruneExpired()
    }

    func enable() {
        _ = credentials(createIfMissing: true)
        Task { await flush() }
    }

    func enqueue(
        eventType: String,
        spot: TouringSpot,
        sessionID: UUID,
        criteria: SearchCriteria?,
        enabled: Bool
    ) {
        guard enabled, let recommendationID = spot.recommendationID else { return }
        queue.append(
            QueuedInteraction(
                eventID: UUID(),
                sessionID: sessionID,
                recommendationID: recommendationID,
                spotID: spot.id,
                eventType: eventType,
                occurredAt: .now,
                availableMinutes: criteria?.availableMinutes,
                interests: criteria?.interests.map(\.rawValue).sorted() ?? []
            )
        )
        pruneExpired()
        persistQueue()
        Task { await flush() }
    }

    func flush() async {
        guard !queue.isEmpty, let credentials = credentials(createIfMissing: false) else { return }
        let batch = Array(queue.prefix(50))
        var request = URLRequest(url: baseURL.appending(path: "v1/interactions"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(credentials.installationID.uuidString, forHTTPHeaderField: "X-Installation-ID")
        request.setValue(credentials.tokenHash, forHTTPHeaderField: "X-Deletion-Token-Hash")
        request.httpBody = try? encoder.encode(["events": batch])
        guard let (_, response) = try? await session.data(for: request),
              let http = response as? HTTPURLResponse,
              http.statusCode == 202 else { return }
        let sent = Set(batch.map(\.eventID))
        queue.removeAll { sent.contains($0.eventID) }
        persistQueue()
        if !queue.isEmpty { await flush() }
    }

    func requestDeletion() async {
        guard let credentials = credentials(createIfMissing: false) else {
            queue = []
            persistQueue()
            return
        }
        var request = URLRequest(
            url: baseURL.appending(path: "v1/installations/\(credentials.installationID)/data")
        )
        request.httpMethod = "DELETE"
        request.setValue(credentials.deletionToken, forHTTPHeaderField: "X-Deletion-Token")
        guard let (_, response) = try? await session.data(for: request),
              let http = response as? HTTPURLResponse,
              http.statusCode == 202 else { return }
        queue = []
        persistQueue()
        keychain.remove(Keys.installationID)
        keychain.remove(Keys.deletionToken)
    }

    private func credentials(createIfMissing: Bool) -> AnalyticsCredentials? {
        if let idValue = keychain.read(Keys.installationID),
           let id = UUID(uuidString: idValue),
           let token = keychain.read(Keys.deletionToken) {
            return AnalyticsCredentials(installationID: id, deletionToken: token)
        }
        guard createIfMissing else { return nil }
        let id = UUID()
        var bytes = [UInt8](repeating: 0, count: 32)
        guard SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes) == errSecSuccess else { return nil }
        let token = Data(bytes).base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
        guard keychain.write(id.uuidString, key: Keys.installationID),
              keychain.write(token, key: Keys.deletionToken) else { return nil }
        return AnalyticsCredentials(installationID: id, deletionToken: token)
    }

    private func pruneExpired() {
        let cutoff = Date.now.addingTimeInterval(-7 * 24 * 60 * 60)
        queue.removeAll { $0.occurredAt < cutoff }
    }

    private func persistQueue() {
        defaults.set(try? encoder.encode(queue), forKey: Keys.queue)
    }
}

final class KeychainStore {
    private let service: String

    init(service: String) {
        self.service = service
    }

    func read(_ key: String) -> String? {
        var query = baseQuery(key)
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    @discardableResult
    func write(_ value: String, key: String) -> Bool {
        let data = Data(value.utf8)
        let query = baseQuery(key)
        let attributes = [kSecValueData as String: data]
        let status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if status == errSecSuccess { return true }
        var insertion = query
        insertion[kSecValueData as String] = data
        insertion[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        return SecItemAdd(insertion as CFDictionary, nil) == errSecSuccess
    }

    func remove(_ key: String) {
        SecItemDelete(baseQuery(key) as CFDictionary)
    }

    private func baseQuery(_ key: String) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
        ]
    }
}

