import CoreLocation
import Foundation

@MainActor
final class LocationService: NSObject, ObservableObject {
    enum State: Equatable {
        case idle
        case requestingPermission
        case locating
        case available
        case denied
        case failed(String)
    }

    @Published private(set) var state: State = .idle
    @Published private(set) var currentLocation: CLLocation?

    private let manager = CLLocationManager()

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
    }

    func requestCurrentLocation() {
        switch manager.authorizationStatus {
        case .notDetermined:
            state = .requestingPermission
            manager.requestWhenInUseAuthorization()
        case .authorizedWhenInUse, .authorizedAlways:
            state = .locating
            manager.requestLocation()
        case .denied, .restricted:
            state = .denied
        @unknown default:
            state = .failed("位置情報の権限状態を確認できませんでした。")
        }
    }
}

extension LocationService: CLLocationManagerDelegate {
    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        Task { @MainActor in
            switch manager.authorizationStatus {
            case .authorizedWhenInUse, .authorizedAlways:
                state = .locating
                manager.requestLocation()
            case .denied, .restricted:
                state = .denied
            case .notDetermined:
                state = .requestingPermission
            @unknown default:
                state = .failed("位置情報の権限状態を確認できませんでした。")
            }
        }
    }

    nonisolated func locationManager(
        _ manager: CLLocationManager,
        didUpdateLocations locations: [CLLocation]
    ) {
        Task { @MainActor in
            guard let location = locations.last else {
                state = .failed("現在地を取得できませんでした。")
                return
            }
            currentLocation = location
            state = .available
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        Task { @MainActor in
            state = .failed("現在地を取得できませんでした。もう一度お試しください。")
        }
    }
}

