import CoreLocation
import MapKit

enum MapCameraFitting {
    static func region(
        destination: CLLocationCoordinate2D,
        origin: CLLocationCoordinate2D? = nil
    ) -> MKCoordinateRegion {
        guard let origin else {
            return MKCoordinateRegion(
                center: destination,
                span: MKCoordinateSpan(latitudeDelta: 0.08, longitudeDelta: 0.08)
            )
        }

        let latitudeDelta = max(abs(destination.latitude - origin.latitude) * 1.5, 0.05)
        let longitudeDelta = max(abs(destination.longitude - origin.longitude) * 1.5, 0.05)
        return MKCoordinateRegion(
            center: CLLocationCoordinate2D(
                latitude: (destination.latitude + origin.latitude) / 2,
                longitude: (destination.longitude + origin.longitude) / 2
            ),
            span: MKCoordinateSpan(
                latitudeDelta: min(latitudeDelta, 180),
                longitudeDelta: min(longitudeDelta, 360)
            )
        )
    }
}
