import SwiftUI

struct OnboardingView: View {
    let onStart: () -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                hero

                VStack(alignment: .leading, spacing: 18) {
                    feature(
                        icon: "clock.badge.checkmark",
                        title: "時間から提案",
                        message: "今から使える時間に収まる目的地だけを提案します。"
                    )
                    feature(
                        icon: "rectangle.stack",
                        title: "1件ずつ判断",
                        message: "一覧で迷わず、気になる場所を一つずつ確認できます。"
                    )
                    feature(
                        icon: "map",
                        title: "ナビはApple Maps",
                        message: "行き先を決めたら、Apple Mapsへ安全に引き渡します。"
                    )
                }

                StatusNotice(
                    kind: .warning,
                    title: "安全のために",
                    message: "所要時間は予測です。走行中は操作せず、現地の標識と最新の道路情報を優先してください。"
                )

                NavigationLink("プライバシーポリシー", destination: PrivacyPolicyView())
                    .font(.footnote)
                    .frame(maxWidth: .infinity)
            }
            .padding()
        }
        .safeAreaInset(edge: .bottom) {
            PrimaryBottomAction(title: "はじめる", systemImage: "arrow.right", action: onStart)
        }
        .toolbar(.hidden, for: .navigationBar)
    }

    private var hero: some View {
        VStack(alignment: .leading, spacing: 16) {
            Image(systemName: "motorcycle.fill")
                .font(.system(size: 46))
                .foregroundStyle(AppTheme.brand)
                .accessibilityHidden(true)
            Text("今の時間に\nちょうどいい行き先を")
                .font(.largeTitle.bold())
                .fixedSize(horizontal: false, vertical: true)
            Text("Bike EasyFinder")
                .font(.headline)
                .foregroundStyle(.secondary)
        }
        .padding(.top, 36)
    }

    private func feature(icon: String, title: String, message: String) -> some View {
        HStack(alignment: .top, spacing: 16) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundStyle(AppTheme.brand)
                .frame(width: 34)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(.headline)
                Text(message).foregroundStyle(.secondary)
            }
        }
        .accessibilityElement(children: .combine)
    }
}
