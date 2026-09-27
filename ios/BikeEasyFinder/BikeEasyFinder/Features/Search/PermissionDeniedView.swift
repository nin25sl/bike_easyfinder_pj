import SwiftUI
import UIKit

struct PermissionDeniedView: View {
    var onRetry: (() -> Void)?

    init(onRetry: (() -> Void)? = nil) {
        self.onRetry = onRetry
    }

    var body: some View {
        ContentUnavailableView {
            Label("位置情報が必要です", systemImage: "location.slash")
        } description: {
            Text("現在地から時間内に往復できる候補を探すため、設定で位置情報の利用を許可してください。")
        } actions: {
            Button("設定を開く") {
                guard let url = URL(string: UIApplication.openSettingsURLString) else { return }
                UIApplication.shared.open(url)
            }
            if let onRetry {
                Button("再試行", action: onRetry)
            }
        }
    }
}
