import MapKit

@MainActor
struct ExternalNavigationService {
    func openInAppleMaps(_ spot: TouringSpot) -> Bool {
        let placemark = MKPlacemark(coordinate: spot.coordinate)
        let mapItem = MKMapItem(placemark: placemark)
        mapItem.name = spot.name

        return mapItem.openInMaps(
            launchOptions: [MKLaunchOptionsDirectionsModeKey: MKLaunchOptionsDirectionsModeDriving]
        )
    }
}
