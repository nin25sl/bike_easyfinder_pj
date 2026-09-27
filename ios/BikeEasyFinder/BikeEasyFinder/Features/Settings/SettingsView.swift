import SwiftUI

struct SettingsView: View {
    @ObservedObject var appState: AppState

    @State private var confirmation: Confirmation?
    @State private var showPrivacyPolicy = false

    private enum Confirmation: String, Identifiable {
        case criteria, reactions, anonymousData
        var id: String { rawValue }

        var title: String {
            switch self {
            case .criteria: "前回の条件を消去しますか？"
            case .reactions: "リアクション履歴を消去しますか？"
            case .anonymousData: "匿名データを削除しますか？"
            }
        }

        var message: String {
            switch self {
            case .criteria: "保存した時間・興味・高速道路の条件をこの端末から消去します。"
            case .reactions: "興味あり、今回は違う、訪問済みの履歴と保存一覧をこの端末から消去します。"
            case .anonymousData: "固定データ版では分析同意を解除します。サーバ削除APIは接続後に利用できます。"
            }
        }
    }

    var body: some View {
        Form {
            Section("分析") {
                Toggle("匿名の利用状況を共有", isOn: $appState.analyticsEnabled)
                Text("任意です。オフでも提案、保存、ナビを利用できます。固定データ版はイベントを送信しません。")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }

            Section("この端末のデータ") {
                Button("前回の条件を消去") { confirmation = .criteria }
                    .disabled(appState.lastCriteria == nil)
                Button("リアクション履歴を消去", role: .destructive) { confirmation = .reactions }
                    .disabled(appState.reactions.isEmpty)
                Button("匿名データを削除", role: .destructive) { confirmation = .anonymousData }
            }

            Section("プライバシーとアプリ情報") {
                Button("プライバシーポリシー") { showPrivacyPolicy = true }
                LabeledContent("バージョン", value: "MVP fixed-data v1")
            }
        }
        .navigationTitle("設定・プライバシー")
        .confirmationDialog(
            Text(confirmation?.title ?? ""),
            isPresented: Binding(
                get: { confirmation != nil },
                set: { if !$0 { confirmation = nil } }
            ),
            titleVisibility: .visible,
            presenting: confirmation
        ) { value in
            Button("実行する", role: .destructive) { execute(value) }
            Button("キャンセル", role: .cancel) {}
        } message: { value in
            Text(value.message)
        }
        .sheet(isPresented: $showPrivacyPolicy) {
            NavigationStack { PrivacyPolicyView() }
        }
    }

    private func execute(_ confirmation: Confirmation) {
        switch confirmation {
        case .criteria: appState.clearLastCriteria()
        case .reactions: appState.clearReactions()
        case .anonymousData: appState.clearAnonymousData()
        }
        self.confirmation = nil
    }
}

struct PrivacyPolicyView: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text("プライバシーポリシー（要約）")
                    .font(.largeTitle.bold())
                Text("現在地は提案時にのみ取得し、履歴として保存しません。前回条件とリアクションはこの端末に保存され、設定から消去できます。")
                Text("分析データの共有は任意です。固定データ版では分析イベントを外部へ送信しません。正式版では公開済みのポリシー全文、送信先、保持期間、削除方法をアプリ内から確認できるようにします。")
                StatusNotice(
                    kind: .info,
                    title: "固定データ版",
                    message: "推薦API、WeatherKit、分析APIには接続していません。"
                )
            }
            .padding()
        }
        .navigationTitle("プライバシー")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                Button("閉じる") { dismiss() }
            }
        }
    }
}
