import MapKit
import SwiftUI

struct SpotMapView: View {
    let spot: TouringSpot
    @State private var cameraPosition: MapCameraPosition

    init(spot: TouringSpot) {
        self.spot = spot
        _cameraPosition = State(
            initialValue: .region(
                MKCoordinateRegion(
                    center: spot.coordinate,
                    span: MKCoordinateSpan(latitudeDelta: 0.08, longitudeDelta: 0.08)
                )
            )
        )
    }

    var body: some View {
        Map(position: $cameraPosition) {
            Marker(spot.name, coordinate: spot.coordinate)
        }
        .mapStyle(.standard)
        .accessibilityLabel("\(spot.name)の地図")
    }
}

